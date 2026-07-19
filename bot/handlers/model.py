"""Model picker — user selects image model. Privacy: never show provider name, use short code RC/ CB."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
import db
from i18n import t
import ui

router = Router()


def _short_label(m: dict) -> str:
    try:
        from model_display import format_model_label
        return format_model_label(m.get("provider_id",""), m.get("external_id") or m.get("id",""), m.get("display_name"))
    except Exception:
        return m.get("display_name") or m.get("external_id") or m.get("id","")


@router.message(Command("model"))
@router.message(F.text == "/models")
async def cmd_model(message: Message):
    lang = await db.get_lang(message.from_user.id)
    if (await db.get_setting("feat_model_enabled", "1")) == "0":
        await message.answer(t("feature_disabled", lang), reply_markup=ui.back_menu(lang))
        return

    try:
        models = await db.list_models(active_only=True)
    except Exception:
        models = []

    if not models:
        await message.answer(t("model_no_models", lang), reply_markup=ui.back_menu(lang))
        return

    try:
        cur = await db.get_active_model_for_user(message.from_user.id)
        cur_id = cur["id"] if cur else None
        cur_label = _short_label(cur) if cur else None
    except Exception:
        cur_id = None
        cur_label = None

    text = t("model_pick", lang) if t("model_pick", lang) != "model_pick" else "Pilih model gambar:"
    if cur_label:
        text += f"\nSaat ini: {cur_label}"

    await message.answer(text, reply_markup=ui.model_menu(models, cur_id, lang))


@router.callback_query(F.data.startswith("model:"))
async def cb_set_model(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    try:
        # model:provider:external -> need keep everything after first colon
        model_id = callback.data.split(":", 1)[1]
    except Exception:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return

    try:
        m = await db.get_model(model_id)
        if not m or not m.get("is_active"):
            await callback.answer(t("invalid_data", lang), show_alert=True)
            return
        prov = await db.get_provider(m["provider_id"])
        if not prov or not prov.get("is_active"):
            await callback.answer(t("model_inactive", lang) if t("model_inactive", lang) != "model_inactive" else "Model tidak aktif", show_alert=True)
            return
    except Exception:
        pass

    try:
        await db.set_user_model(callback.from_user.id, model_id)
    except Exception as e:
        await callback.answer(f"Gagal: {e}", show_alert=True)
        return

    # display short code
    try:
        mobj = await db.get_model(model_id)
        label = _short_label(mobj) if mobj else model_id
    except Exception:
        label = model_id

    await callback.answer(t("model_set", lang, model=label) if "model" in t("model_set", lang, model=label) or True else f"Model {label} selected")
    try:
        await callback.message.edit_text(
            f"Model dipilih: {label}\n\nSekarang kirim prompt untuk generate.",
            reply_markup=ui.back_menu(lang)
        )
    except Exception:
        await callback.message.answer(f"Model dipilih: {label}", reply_markup=ui.back_menu(lang))


@router.callback_query(F.data == "menu:model")
async def cb_menu_model(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    if (await db.get_setting("feat_model_enabled", "1")) == "0":
        await callback.answer(t("feature_disabled", lang), show_alert=True)
        return
    try:
        models = await db.list_models(active_only=True)
    except Exception:
        models = []
    if not models:
        await callback.answer("Tidak ada model aktif", show_alert=True)
        return
    try:
        cur = await db.get_active_model_for_user(callback.from_user.id)
        cur_id = cur["id"] if cur else None
        cur_label = _short_label(cur) if cur else None
    except Exception:
        cur_id = None
        cur_label = None
    text = "Pilih model gambar:" if lang == "id" else "Pick image model:"
    if cur_label:
        text += f"\nCurrent: {cur_label}"
    from tgutil import safe_edit
    await safe_edit(callback.message, text, reply_markup=ui.model_menu(models, cur_id, lang))
    await callback.answer()
