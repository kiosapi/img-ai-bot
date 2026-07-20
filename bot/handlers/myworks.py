"""My Works / History: list text dulu, gambar muncul hanya pas view."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command

import db
import ui
from i18n import t
from tgutil import safe_edit
import feature_flags as ff

router = Router()
PAGE_SIZE = 10

@router.message(Command("myworks"))
async def cmd_myworks(message: Message):
    lang = await db.get_lang(message.from_user.id)
    if not await ff.is_command_enabled("myworks"):
        await message.answer(t("feature_disabled", lang), reply_markup=ui.back_menu(lang))
        return
    total = await db.count_user_generations(message.from_user.id)
    if total == 0:
        await message.answer(t("myworks_empty", lang), reply_markup=ui.back_menu(lang))
        return
    gens = await db.get_user_generations(message.from_user.id, limit=PAGE_SIZE, offset=0)
    text = t("myworks_title", lang, total=total, shown=len(gens))
    await message.answer(text, reply_markup=ui.myworks_menu(gens, total, 0, PAGE_SIZE, lang))

@router.callback_query(F.data.startswith("myworks:"))
async def cb_myworks(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    if not await ff.is_command_enabled("myworks"):
        await callback.answer(t("feature_disabled", lang), show_alert=True)
        return
    try:
        offset = int(callback.data.split(":", 1)[1])
    except Exception:
        offset = 0
    total = await db.count_user_generations(callback.from_user.id)
    if total == 0:
        await safe_edit(callback.message, t("myworks_empty", lang), reply_markup=ui.back_menu(lang))
        await callback.answer()
        return
    gens = await db.get_user_generations(callback.from_user.id, limit=PAGE_SIZE, offset=offset)
    if not gens and offset > 0:
        offset = 0
        gens = await db.get_user_generations(callback.from_user.id, limit=PAGE_SIZE, offset=0)
    text = t("myworks_title", lang, total=total, shown=len(gens))
    await safe_edit(callback.message, text, reply_markup=ui.myworks_menu(gens, total, offset, PAGE_SIZE, lang))
    await callback.answer()

@router.callback_query(F.data.startswith("view:"))
async def cb_view(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    try:
        gen_id = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    gen = await db.get_generation_by_id(gen_id)
    if not gen or gen["user_id"] != callback.from_user.id:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    if not gen.get("result_file_id"):
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    date_str = gen["created_at"].strftime("%d %b %Y") if gen.get("created_at") else ""
    extra = ""
    if gen.get("negative_prompt"):
        extra += f"\n🚫 Neg: {gen['negative_prompt'][:60]}"
    if gen.get("seed"):
        extra += f"\n🎲 Seed: {gen['seed']}"
    if gen.get("batch_id"):
        extra += f"\n🎲 Batch: {gen['batch_id'][:8]}"
    if gen.get("ref_file_id"):
        extra += "\n🖼️ Ref: ON"
    caption = t("myworks_view", lang, id=gen["id"], prompt=(gen.get("prompt") or "")[:300], size=gen.get("size") or "-", kind=gen.get("kind") or "-", date=date_str) + extra
    try:
        await callback.message.answer_photo(
            gen["result_file_id"],
            caption=caption[:1000],
            reply_markup=ui.myworks_view_menu(gen["id"], lang)
        )
    except Exception:
        try:
            await callback.message.answer(caption[:1000], reply_markup=ui.myworks_view_menu(gen["id"], lang))
        except Exception:
            pass
    await callback.answer()
