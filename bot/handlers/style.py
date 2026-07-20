"""Style presets: pick visual style."""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

import db
import ui
import styles as style_presets
from i18n import t
from tgutil import safe_edit

router = Router()

async def _load_styles_active() -> list[dict]:
    """Try DB custom_styles active only, fallback to hardcoded STYLES.
    Returns list of dicts with at least code,name,prompt_prefix,category,is_active,sort_order.
    TODO: once fully migrated, remove fallback and rely solely on DB.
    """
    try:
        rows = await db.get_custom_styles(active_only=True)
        # rows already from DB, but apply fallback if only contains 'none' placeholder?
        if rows and len(rows) > 0:
            # normalize to shape expected by UI: need code mapping
            # if rows came from fallback (hardcoded converted) already fine
            # ensure legacy compatibility: if row dict has code -> keep, else skip
            filtered = [r for r in rows if r.get("is_active", True)]
            if filtered:
                return filtered
    except Exception:
        pass
    # fallback to hardcoded dict → convert to list shape
    out = []
    for idx, (code, info) in enumerate(style_presets.STYLES.items()):
        out.append({
            "code": code,
            "name": info.get("label_en") or info.get("label_id") or code,
            "prompt_prefix": info.get("prompt_suffix") or "",
            "thumbnail_url": None,
            "category": "general",
            "is_active": True,
            "sort_order": idx,
            "id": idx + 1,
        })
    return out

def _build_dynamic_style_menu(styles_list: list[dict], current_code: str | None, lang: str = "id"):
    kb = InlineKeyboardBuilder()
    for s in styles_list:
        code = s.get("code", "")
        name = s.get("name", code)
        mark = "✓ " if code == current_code else ""
        # keep simple label, no emoji dependency — DB has no emoji
        kb.button(text=f"{mark}{name}", callback_data=f"style:{code}")
    kb.button(text=t("back_home", lang), callback_data="menu:home")
    kb.adjust(2)
    return kb.as_markup()


@router.callback_query(F.data == "menu:style")
async def show_style(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    current_id = await db.get_pref_style(callback.from_user.id, "none") or "none"
    styles_list = await _load_styles_active()
    # resolve current label
    cur_label = None
    for s in styles_list:
        if s.get("code") == current_id:
            cur_label = s.get("name")
            break
    if not cur_label:
        # fallback to hardcoded get_style
        cur_info = style_presets.get_style(current_id)
        cur_label = cur_info["label_id"] if lang == "id" else cur_info["label_en"]
        if current_id == "none":
            cur_label = t("style_none", lang)
    await safe_edit(callback.message, t("style_title", lang, current=cur_label or current_id), reply_markup=_build_dynamic_style_menu(styles_list, current_id, lang))
    await callback.answer()


@router.callback_query(F.data.startswith("style:"))
async def set_style(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    sid = callback.data.split(":", 1)[1]
    # validate against dynamic list + hardcoded fallback
    styles_list = await _load_styles_active()
    valid_codes = {s.get("code") for s in styles_list}
    # also allow hardcoded codes for resilience
    valid_codes.update(style_presets.STYLES.keys())
    if sid not in valid_codes:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    await db.set_pref_style(callback.from_user.id, sid if sid != "none" else None)
    # label for feedback
    label = sid
    for s in styles_list:
        if s.get("code") == sid:
            label = s.get("name", sid)
            break
    else:
        info = style_presets.get_style(sid)
        label = info["label_id"] if lang == "id" else info["label_en"]
        if sid == "none":
            label = t("style_none", lang)
    # refresh menu
    styles_list2 = await _load_styles_active()
    await safe_edit(
        callback.message,
        t("style_title", lang, current=label),
        reply_markup=_build_dynamic_style_menu(styles_list2, sid, lang),
    )
    await callback.answer(t("style_set", lang, style=label))
