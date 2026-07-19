"""Image-to-image / edit: photo + prompt, plus result actions callbacks. Uses providers."""
import io
import db
import ui
import styles as style_presets
from i18n import t
from tgutil import ProgressAnimator, safe_edit
from states import EditStates
from gen_queue import QUEUE
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile

router = Router()


async def is_maintenance() -> bool:
    return (await db.get_setting("maintenance", "0")) == "1"


async def _size_of(uid: int):
    from config import DEFAULT_SIZE
    return await db.get_pref_size(uid, DEFAULT_SIZE)


async def _style_of(uid: int):
    return await db.get_pref_style(uid, "none") or "none"


async def _has_pending_deposit_awaiting_proof(user_id: int) -> bool:
    dep = await db.get_pending_deposit(user_id)
    return bool(dep and not dep["proof_file_id"])


async def _check_and_consume(uid: int):
    from config import DEFAULT_DAILY_LIMIT
    return await db.check_and_consume_atomic(uid, DEFAULT_DAILY_LIMIT)


async def _do_edit(message: Message, file_id: str, prompt: str, force_size: str | None = None):
    lang = await db.get_lang(message.from_user.id)
    if (await db.get_setting("feat_queue_enabled", "1")) == "1":
        if not await QUEUE.acquire(message.from_user.id):
            await message.answer(t("busy_generating", lang), reply_markup=ui.back_menu(lang))
            return
    if await is_maintenance():
        if (await db.get_setting("feat_queue_enabled", "1")) == "1":
            await QUEUE.release(message.from_user.id)
        await message.answer(t("maintenance", lang))
        return
    allowed, used, limit, _bonus = await _check_and_consume(message.from_user.id)
    if not allowed:
        if (await db.get_setting("feat_queue_enabled", "1")) == "1":
            await QUEUE.release(message.from_user.id)
        await message.answer(t("quota_exhausted", lang, used=used, limit=limit, bar=ui.quota_bar(used, limit)), reply_markup=ui.back_menu(lang))
        return
    size = force_size or await _size_of(message.from_user.id)
    style_id = await _style_of(message.from_user.id)
    styled_prompt = style_presets.apply_style(prompt, style_id)

    try:
        from watermark import should_watermark, apply_watermark_image
        wm_on, wm_text = await should_watermark(message.from_user.id)
    except Exception:
        wm_on, wm_text = False, ""

    try:
        active_model = await db.get_active_model_for_user(message.from_user.id)
    except Exception:
        active_model = None

    status = await message.answer(t("editing", lang, used=used, limit=limit) + "\n▱▱▱▱▱▱▱▱▱▱  ⏱️ 0s")
    animator = ProgressAnimator(message.bot, message.chat.id, status, t("editing", lang, used=used, limit=limit))
    animator.start()
    try:
        buf = io.BytesIO()
        await message.bot.download(file_id, destination=buf)
        image_bytes = buf.getvalue()

        from providers import edit_image as provider_edit
        img = await provider_edit(active_model, image_bytes, styled_prompt, size=size, user_id=message.from_user.id)

        if wm_on and wm_text:
            try:
                img = apply_watermark_image(img, wm_text)
            except Exception:
                pass
        cap = t("edit_done", lang, prompt=prompt[:200], size=size, left=ui.sisa_text(used, limit, lang))
        if active_model:
            try:
                from model_display import format_model_label
                _ml = format_model_label(active_model.get("provider_id",""), active_model.get("external_id") or active_model.get("id",""), active_model.get("display_name"))
            except Exception:
                _ml = active_model.get("display_name") or active_model.get("external_id") or ""
            cap += f"\nModel: {_ml}"
        if wm_on and wm_text:
            cap += f"\n\n{wm_text}"
        sent = await message.answer_photo(BufferedInputFile(img, filename="edited.png"), caption=cap, reply_markup=ui.result_menu(lang, gen_id=0))
        try:
            result_file_id = sent.photo[-1].file_id
        except Exception:
            result_file_id = None
        gen_id = await db.log_generation(message.from_user.id, "edit", prompt, size, True, result_file_id=result_file_id, style_id=style_id if style_id != "none" else None)
        if gen_id and active_model:
            try:
                async with db._pool.acquire() as con:
                    await con.execute("UPDATE generations SET model_id=$2 WHERE id=$1", gen_id, active_model["id"])
            except Exception:
                pass
        if result_file_id and gen_id:
            try:
                await sent.edit_caption(caption=cap, reply_markup=ui.result_menu(lang, gen_id=gen_id, file_id=result_file_id))
            except Exception:
                pass
    except Exception as e:
        try:
            await db.log_generation(message.from_user.id, "edit", prompt, size, False, style_id=style_id if style_id != "none" else None)
        except Exception:
            pass
        await message.answer(t("edit_failed", lang, err=str(e)[:500]), reply_markup=ui.back_menu(lang))
    finally:
        if (await db.get_setting("feat_queue_enabled", "1")) == "1":
            await QUEUE.release(message.from_user.id)
        await animator.stop()
        try:
            await status.delete()
        except Exception:
            pass


async def _do_generate_from_edit(msg: Message, prompt: str, variation=False, force_size: str | None = None):
    from handlers.generate import _do_generate
    await _do_generate(msg, prompt, variation=variation, force_size=force_size)


@router.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    lang = await db.get_lang(message.from_user.id)
    prompt = (message.caption or "").strip()
    file_id = message.photo[-1].file_id
    fsm_state = await state.get_state()
    if fsm_state is None and await _has_pending_deposit_awaiting_proof(message.from_user.id):
        return
    if not prompt:
        await state.set_state(EditStates.waiting_instruction)
        await state.update_data(file_id=file_id)
        await message.answer(ui.edit_ask(lang))
        return
    await state.clear()
    await _do_edit(message, file_id, prompt)


@router.message(EditStates.waiting_instruction, F.text, ~F.text.startswith("/"))
async def fsm_edit_instruction(message: Message, state: FSMContext):
    data = await state.get_data()
    file_id = data.get("file_id")
    if not file_id:
        lang = await db.get_lang(message.from_user.id)
        await message.answer(ui.edit_ask(lang))
        return
    await state.clear()
    await _do_edit(message, file_id, message.text.strip())


@router.message(EditStates.waiting_editthis_instruction, F.text, ~F.text.startswith("/"))
async def fsm_editthis_instruction(message: Message, state: FSMContext):
    data = await state.get_data()
    file_id = data.get("editthis_file_id")
    if not file_id:
        await state.clear()
        lang = await db.get_lang(message.from_user.id)
        await message.answer(t("invalid_data", lang), reply_markup=ui.back_menu(lang))
        return
    await state.clear()
    await _do_edit(message, file_id, message.text.strip())


@router.callback_query(F.data.startswith("regen:"))
async def cb_regen(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    try: gen_id = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer(t("invalid_data", lang), show_alert=True); return
    gen = await db.get_generation_by_id(gen_id)
    if not gen or not gen.get("prompt"):
        await callback.answer(t("invalid_data", lang), show_alert=True); return
    await callback.answer(t("generating", lang, used=0, limit=0)[:30])
    await _do_generate_from_edit(callback.message, gen["prompt"])


@router.callback_query(F.data.startswith("var:"))
async def cb_variation(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    try: gen_id = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer(t("invalid_data", lang), show_alert=True); return
    gen = await db.get_generation_by_id(gen_id)
    if not gen or not gen.get("prompt"):
        await callback.answer(t("invalid_data", lang), show_alert=True); return
    await callback.answer("Variation")
    await _do_generate_from_edit(callback.message, gen["prompt"], variation=True)


@router.callback_query(F.data.startswith("hd:"))
async def cb_hd(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    try: gen_id = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer(t("invalid_data", lang), show_alert=True); return
    gen = await db.get_generation_by_id(gen_id)
    if not gen or not gen.get("prompt"):
        await callback.answer(t("invalid_data", lang), show_alert=True); return
    await callback.answer("HD")
    await _do_generate_from_edit(callback.message, gen["prompt"], force_size="1536x1024")


@router.callback_query(F.data.startswith("editthis:"))
async def cb_editthis(callback: CallbackQuery, state: FSMContext):
    lang = await db.get_lang(callback.from_user.id)
    try: gen_id = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer(t("invalid_data", lang), show_alert=True); return
    gen = await db.get_generation_by_id(gen_id)
    if not gen or not gen.get("result_file_id"):
        await callback.answer(t("invalid_data", lang), show_alert=True); return
    await state.set_state(EditStates.waiting_editthis_instruction)
    await state.update_data(editthis_file_id=gen["result_file_id"])
    await callback.message.answer(t("edit_ask", lang) + "\n\n" + t("myworks_regen_hint", lang))
    await callback.answer()
