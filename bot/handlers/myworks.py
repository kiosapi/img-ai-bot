"""My Works / History: list user's generated images using stored Telegram file_id."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command

import db
import ui
from i18n import t
from tgutil import safe_edit

router = Router()
PAGE_SIZE = 5


@router.message(Command("myworks"))
async def cmd_myworks(message: Message):
    lang = await db.get_lang(message.from_user.id)
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
    caption = t("myworks_view", lang, id=gen["id"], prompt=(gen.get("prompt") or "")[:200], size=gen.get("size") or "-", kind=gen.get("kind") or "-", date=date_str)
    # We cannot edit current text message to photo (if current is text), safe_edit handles photo case by delete+send
    # But for view we want to send photo directly
    try:
        await callback.message.answer_photo(
            gen["result_file_id"],
            caption=caption,
            reply_markup=ui.myworks_view_menu(gen["id"], lang)
        )
    except Exception as e:
        await callback.message.answer(caption, reply_markup=ui.myworks_view_menu(gen["id"], lang))
    await callback.answer()
