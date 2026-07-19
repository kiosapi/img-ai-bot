"""Sticker pack generator — create sticker set from generated images."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InputSticker
from aiogram.filters import Command
import io
import re

import db
import feature_flags as ff
from i18n import t
import ui
from tgutil import safe_edit

router = Router()


def _sanitize_pack_name(user_id: int, suffix: str = "") -> str:
    # Telegram sticker set name must be: [a-z]_ by {bot_username}, format {name}_by_{bot}
    # We'll build in handler where bot username known
    base = f"imgbot_{user_id}{suffix}"
    base = re.sub(r"[^a-z0-9_]", "_", base.lower())
    return base[:40]


@router.message(Command("sticker"))
async def cmd_sticker(message: Message):
    lang = await db.get_lang(message.from_user.id)
    if not await ff.sticker_enabled():
        await message.answer(t("feature_disabled", lang), reply_markup=ui.back_menu(lang))
        return
    bot_me = await message.bot.get_me()
    pack_name = f"{_sanitize_pack_name(message.from_user.id)}_by_{bot_me.username}"
    # check existing packs
    packs = await db.get_user_sticker_packs(message.from_user.id)
    max_pack = await ff.sticker_max()
    text = t("sticker_intro", lang, max=max_pack, pack=pack_name)
    kb = ui.sticker_menu(packs, lang, can_create=True)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "menu:sticker")
async def nav_sticker(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    if not await ff.sticker_enabled():
        await callback.answer(t("feature_disabled", lang), show_alert=True)
        return
    bot_me = await callback.bot.get_me()
    pack_name = f"{_sanitize_pack_name(callback.from_user.id)}_by_{bot_me.username}"
    packs = await db.get_user_sticker_packs(callback.from_user.id)
    max_pack = await ff.sticker_max()
    text = t("sticker_intro", lang, max=max_pack, pack=pack_name)
    await safe_edit(callback.message, text, reply_markup=ui.sticker_menu(packs, lang, can_create=True))
    await callback.answer()


@router.callback_query(F.data.startswith("sticker:add:"))
async def cb_sticker_add(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    try:
        gen_id = int(callback.data.split(":")[2])
    except Exception:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    gen = await db.get_generation_by_id(gen_id)
    if not gen or not gen.get("result_file_id"):
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return

    bot_me = await callback.bot.get_me()
    bot_username = bot_me.username
    pack_name = f"{_sanitize_pack_name(callback.from_user.id)}_by_{bot_username}"

    # check pack exists via API, if not create later
    max_per = await ff.sticker_max()

    # get file bytes from Telegram file_id: need download via bot
    try:
        # download image bytes using file_id
        file = await callback.bot.get_file(gen["result_file_id"])
        buf = io.BytesIO()
        await callback.bot.download_file(file.file_path, buf)
        buf.seek(0)
        img_bytes = buf.getvalue()
    except Exception as e:
        await callback.answer(t("sticker_dl_fail", lang, err=str(e)[:100]), show_alert=True)
        return

    # Check if pack exists already
    existing = await db.get_sticker_pack(pack_name)

    try:
        if not existing:
            # create new sticker set
            sticker = InputSticker(sticker=BufferedInputFile(img_bytes, filename="sticker.png"), emoji_list=["🎨"], format="static")
            # Actually aiogram expects InputSticker with sticker file
            from aiogram.types import FSInputFile
            # Use workaround: upload via BufferedInputFile inside InputSticker
            await callback.bot.create_new_sticker_set(
                user_id=callback.from_user.id,
                name=pack_name,
                title=f"ImageBot Pack {callback.from_user.id}",
                stickers=[sticker],
            )
            await db.create_sticker_pack(callback.from_user.id, pack_name, title=f"Pack {callback.from_user.id}")
            await db.set_user_last_sticker_pack(callback.from_user.id, pack_name)
            await callback.answer(t("sticker_created", lang), show_alert=False)
            await callback.message.answer(
                t("sticker_added", lang, pack=pack_name, link=f"https://t.me/addstickers/{pack_name}"),
                reply_markup=ui.back_menu(lang)
            )
        else:
            # add to existing
            cnt_row = await db.get_sticker_pack(pack_name)
            if cnt_row and cnt_row.get("sticker_count", 0) >= max_per:
                await callback.answer(t("sticker_full", lang, max=max_per), show_alert=True)
                return
            sticker = InputSticker(sticker=BufferedInputFile(img_bytes, filename="sticker.png"), emoji_list=["🎨"], format="static")
            await callback.bot.add_sticker_to_set(
                user_id=callback.from_user.id,
                name=pack_name,
                sticker=sticker,
            )
            await db.increment_sticker_count(pack_name)
            await callback.answer(t("sticker_added", lang, pack=pack_name, link=f"https://t.me/addstickers/{pack_name}"))
            await callback.message.answer(
                t("sticker_added", lang, pack=pack_name, link=f"https://t.me/addstickers/{pack_name}"),
                reply_markup=ui.back_menu(lang)
            )
    except Exception as e:
        err = str(e)
        # If pack already exists error, try add instead
        if "STICKERSET_INVALID" in err or "not found" in err.lower():
            await callback.answer(t("sticker_create_fail", lang, err=err[:150]), show_alert=True)
        else:
            await callback.answer(t("sticker_create_fail", lang, err=err[:150]), show_alert=True)
