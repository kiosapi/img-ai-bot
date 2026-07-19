"""Style presets: pick visual style."""
from aiogram import Router, F
from aiogram.types import CallbackQuery

import db
import ui
import styles as style_presets
from i18n import t
from tgutil import safe_edit

router = Router()


@router.callback_query(F.data == "menu:style")
async def show_style(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    current_id = await db.get_pref_style(callback.from_user.id, "none") or "none"
    cur_info = style_presets.get_style(current_id)
    cur_label = cur_info["label_id"] if lang == "id" else cur_info["label_en"]
    if current_id == "none":
        cur_label = t("style_none", lang)
    await safe_edit(callback.message, t("style_title", lang, current=cur_label), reply_markup=ui.style_menu(current_id, lang))
    await callback.answer()


@router.callback_query(F.data.startswith("style:"))
async def set_style(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    sid = callback.data.split(":", 1)[1]
    if sid not in style_presets.STYLES:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    await db.set_pref_style(callback.from_user.id, sid if sid != "none" else None)
    info = style_presets.get_style(sid)
    label = info["label_id"] if lang == "id" else info["label_en"]
    if sid == "none":
        label = t("style_none", lang)
    # refresh menu with new checkmark
    await safe_edit(callback.message,
        t("style_title", lang, current=label),
        reply_markup=ui.style_menu(sid, lang))
    await callback.answer(t("style_set", lang, style=label))
