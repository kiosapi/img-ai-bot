"""Sticker pack generator — create sticker set from generated images. IDOR fixed + queue leak fixed."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InputSticker
from aiogram.filters import Command
import io, re, logging

import db
import feature_flags as ff
from i18n import t
import ui
from tgutil import safe_edit

router = Router()
log = logging.getLogger(__name__)
PIL_AVAILABLE = True
try:
    from PIL import Image  # type: ignore
except ImportError:
    PIL_AVAILABLE = False

def _sanitize_pack_name(user_id: int, suffix: str = "") -> str:
    base = f"imgbot_{user_id}{suffix}"
    base = re.sub(r"[^a-z0-9_]", "_", base.lower())
    return base[:40]

def _resize_to_sticker(img_bytes: bytes) -> bytes:
    if not PIL_AVAILABLE:
        return img_bytes
    try:
        im = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        w, h = im.size
        if w > h:
            nw = 512; nh = max(1, round(h * 512 / w))
        else:
            nh = 512; nw = max(1, round(w * 512 / h))
        im = im.resize((nw, nh), Image.LANCZOS)
        out = io.BytesIO()
        im.save(out, format="PNG")
        return out.getvalue()
    except Exception as e:
        log.warning("sticker resize fail: %s", e)
        return img_bytes

@router.message(Command("sticker"))
async def cmd_sticker(message: Message):
    lang = await db.get_lang(message.from_user.id)
    if not await ff.sticker_enabled():
        await message.answer(t("feature_disabled", lang), reply_markup=ui.back_menu(lang))
        return
    bot_me = await message.bot.get_me()
    pack_name = f"{_sanitize_pack_name(message.from_user.id)}_by_{bot_me.username}"
    packs = await db.get_user_sticker_packs(message.from_user.id)
    max_pack = await ff.sticker_max()
    text = t("sticker_intro", lang, max=max_pack, pack=pack_name)
    await message.answer(text, reply_markup=ui.sticker_menu(packs, lang, can_create=True))

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
    if not gen or not gen.get("result_file_id") or gen.get("user_id")!=callback.from_user.id:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return

    bot_me = await callback.bot.get_me()
    pack_name = f"{_sanitize_pack_name(callback.from_user.id)}_by_{bot_me.username}"
    max_per = await ff.sticker_max()

    try:
        file = await callback.bot.get_file(gen["result_file_id"])
        buf = io.BytesIO()
        await callback.bot.download_file(file.file_path, buf)
        buf.seek(0)
        img_bytes = _resize_to_sticker(buf.getvalue())
    except Exception as e:
        await callback.answer(t("sticker_dl_fail", lang, err=str(e)[:100]), show_alert=True)
        return

    existing = await db.get_sticker_pack(pack_name)
    try:
        if not existing:
            sticker = InputSticker(sticker=BufferedInputFile(img_bytes, filename="sticker.png"), emoji_list=["🎨"], format="static")
            await callback.bot.create_new_sticker_set(user_id=callback.from_user.id, name=pack_name, title=f"ImageBot Pack {callback.from_user.id}", stickers=[sticker])
            await db.create_sticker_pack(callback.from_user.id, pack_name, title=f"Pack {callback.from_user.id}")
            await db.set_user_last_sticker_pack(callback.from_user.id, pack_name)
            await callback.answer(t("sticker_created", lang))
            await callback.message.answer(t("sticker_added", lang, pack=pack_name, link=f"https://t.me/addstickers/{pack_name}"), reply_markup=ui.back_menu(lang))
        else:
            cnt_row = await db.get_sticker_pack(pack_name)
            if cnt_row and cnt_row.get("sticker_count", 0) >= max_per:
                await callback.answer(t("sticker_full", lang, max=max_per), show_alert=True)
                return
            sticker = InputSticker(sticker=BufferedInputFile(img_bytes, filename="sticker.png"), emoji_list=["🎨"], format="static")
            await callback.bot.add_sticker_to_set(user_id=callback.from_user.id, name=pack_name, sticker=sticker)
            await db.increment_sticker_count(pack_name)
            await callback.message.answer(t("sticker_added", lang, pack=pack_name, link=f"https://t.me/addstickers/{pack_name}"), reply_markup=ui.back_menu(lang))
            await callback.answer(t("sticker_added", lang, pack=pack_name, link=f"https://t.me/addstickers/{pack_name}")[:200])
    except Exception as e:
        err = str(e)[:300]
        if "STICKERSET_INVALID" not in err and "already" in err.lower() and not existing:
            try:
                sticker = InputSticker(sticker=BufferedInputFile(img_bytes, filename="sticker.png"), emoji_list=["🎨"], format="static")
                await callback.bot.add_sticker_to_set(user_id=callback.from_user.id, name=pack_name, sticker=sticker)
                await db.create_sticker_pack(callback.from_user.id, pack_name, title=f"Pack {callback.from_user.id}")
                await db.increment_sticker_count(pack_name)
                await callback.message.answer(t("sticker_added", lang, pack=pack_name, link=f"https://t.me/addstickers/{pack_name}"), reply_markup=ui.back_menu(lang))
                await callback.answer("✅ Added")
                return
            except Exception as e2:
                err = str(e2)[:300]
        await callback.answer(t("sticker_create_fail", lang, err=err), show_alert=True)
