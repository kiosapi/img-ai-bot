"""Model picker — user selects image model. Privacy: never show provider name."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
import db
from i18n import t
import ui

router = Router()


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

    # current pref
    try:
        cur = await db.get_active_model_for_user(message.from_user.id)
        cur_id = cur["id"] if cur else None
    except Exception:
        cur_id = None

    text = t("model_pick", lang) if t("model_pick", lang) != "model_pick" else "Pilih model gambar:"
    if cur_id:
        text += f"\nSaat ini: <b>{cur_id}</b>"

    await message.answer(text, reply_markup=ui.model_menu(models, cur_id, lang))


@router.callback_query(F.data.startswith("model:"))
async def cb_set_model(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    try:
        model_id = callback.data.split(":", 1)[1]
    except Exception:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return

    # validate active
    try:
        m = await db.get_model(model_id)
        if not m or not m.get("is_active"):
            await callback.answer(t("invalid_data", lang), show_alert=True)
            return
        # also check provider active
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

    await callback.answer(t("model_set", lang, model=model_id) if "model_set" in t.__code__.co_varnames or True else f"Model {model_id} selected")
    try:
        model_obj = await db.get_model(model_id)
        label = model_obj.get("display_name") if model_obj else model_id
        await callback.message.edit_text(
            f"Model dipilih: <b>{label}</b>\n\nSekarang kirim prompt untuk generate.",
            reply_markup=ui.back_menu(lang)
        )
    except Exception:
        await callback.message.answer(f"Model dipilih: {model_id}", reply_markup=ui.back_menu(lang))


@router.callback_query(F.data == "menu:model")
async def cb_menu_model(callback: CallbackQuery):
    # reuse cmd_model logic but via callback
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
    except Exception:
        cur_id = None
    text = "Pilih model gambar:" if lang == "id" else "Pick image model:"
    if cur_id:
        text += f"\nCurrent: <b>{cur_id}</b>"
    from tgutil import safe_edit
    await safe_edit(callback.message, text, reply_markup=ui.model_menu(models, cur_id, lang))
    await callback.answer()
