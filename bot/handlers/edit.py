"""Image-to-image / edit: user sends a photo with a caption prompt (in the same
message), OR sends the photo first and the instruction as a separate
follow-up message (very common on mobile Telegram clients) — both flows are
supported. Editing itself is shared between them via _do_edit().
Also hosts result actions: regen / variation / hd / editthis.
"""
import io
import random
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile

import db
import ui
import cubence
import styles as style_presets
from i18n import t
from handlers.generate import check_and_consume, _size_of, is_maintenance, _style_of
from tgutil import ProgressAnimator, safe_edit
from states import EditStates
from gen_queue import QUEUE

router = Router()


async def _has_pending_deposit_awaiting_proof(user_id: int) -> bool:
    dep = await db.get_pending_deposit(user_id)
    return bool(dep and not dep["proof_file_id"])


async def _do_edit(message: Message, file_id: str, prompt: str, force_size: str | None = None):
    lang = await db.get_lang(message.from_user.id)
    if not await QUEUE.acquire(message.from_user.id):
        await message.answer(t("busy_generating", lang), reply_markup=ui.back_menu(lang))
        return
    if await is_maintenance():
        await QUEUE.release(message.from_user.id)
        await message.answer(t("maintenance", lang))
        return

    allowed, used, limit = await check_and_consume(message.from_user.id)
    if not allowed:
        await QUEUE.release(message.from_user.id)
        await message.answer(
            t("quota_exhausted", lang, used=used, limit=limit, bar=ui.quota_bar(used, limit)),
            reply_markup=ui.back_menu(lang))
        return

    size = force_size or await _size_of(message.from_user.id)
    style_id = await _style_of(message.from_user.id)
    styled_prompt = style_presets.apply_style(prompt, style_id)

    status = await message.answer(t("editing", lang, used=used, limit=limit) + "\n▱▱▱▱▱▱▱▱▱▱  ⏱️ 0s")
    animator = ProgressAnimator(message.bot, message.chat.id, status, t("editing", lang, used=used, limit=limit))
    animator.start()
    try:
        buf = io.BytesIO()
        await message.bot.download(file_id, destination=buf)
        image_bytes = buf.getvalue()

        img = await cubence.edit_image(image_bytes, styled_prompt, size=size)
        sent = await message.answer_photo(
            BufferedInputFile(img, filename="edited.png"),
            caption=t("edit_done", lang, prompt=prompt[:200], size=size, left=ui.sisa_text(used, limit, lang)),
            reply_markup=ui.result_menu(lang, gen_id=0),
        )
        try:
            result_file_id = sent.photo[-1].file_id
        except Exception:
            result_file_id = None
        gen_id = await db.log_generation(
            message.from_user.id, "edit", prompt, size, True,
            result_file_id=result_file_id, style_id=style_id if style_id != "none" else None
        )
        if result_file_id and gen_id:
            try:
                await sent.edit_caption(
                    caption=t("edit_done", lang, prompt=prompt[:200], size=size, left=ui.sisa_text(used, limit, lang)),
                    reply_markup=ui.result_menu(lang, gen_id=gen_id, file_id=result_file_id)
                )
            except Exception:
                pass
    except cubence.CubenceError as e:
        await db.log_generation(message.from_user.id, "edit", prompt, size, False, style_id=style_id if style_id != "none" else None)
        await message.answer(t("edit_failed", lang, err=e), reply_markup=ui.back_menu(lang))
    except Exception as e:
        await db.log_generation(message.from_user.id, "edit", prompt, size, False, style_id=style_id if style_id != "none" else None)
        await message.answer(t("edit_failed", lang, err=f"Unexpected error: {e}"), reply_markup=ui.back_menu(lang))
    finally:
        await QUEUE.release(message.from_user.id)
        await animator.stop()
        try:
            await status.delete()
        except Exception:
            pass


@router.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    lang = await db.get_lang(message.from_user.id)
    prompt = (message.caption or "").strip()
    file_id = message.photo[-1].file_id  # highest resolution

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


# ---- editthis flow: user clicked Edit on a result, then we ask instruction ----
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


# ---- result action callbacks ----
@router.callback_query(F.data.startswith("regen:"))
async def cb_regen(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    try:
        gen_id = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    gen = await db.get_generation_by_id(gen_id)
    if not gen or not gen.get("prompt"):
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    await callback.answer(t("generating", lang, used=0, limit=0)[:30])
    # reuse _do_generate flow but via message object
    await _do_generate(callback.message, gen["prompt"])


@router.callback_query(F.data.startswith("var:"))
async def cb_variation(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    try:
        gen_id = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    gen = await db.get_generation_by_id(gen_id)
    if not gen or not gen.get("prompt"):
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    await callback.answer("✨ Variation")
    await _do_generate(callback.message, gen["prompt"], variation=True)


@router.callback_query(F.data.startswith("hd:"))
async def cb_hd(callback: CallbackQuery):
    """HD = re-generate with larger size (1536x1024 if current was square, else max)."""
    lang = await db.get_lang(callback.from_user.id)
    try:
        gen_id = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    gen = await db.get_generation_by_id(gen_id)
    if not gen or not gen.get("prompt"):
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    await callback.answer("🔍 HD")
    # Force larger size: pick landscape max for HD
    await _do_generate(callback.message, gen["prompt"], force_size="1536x1024")


@router.callback_query(F.data.startswith("editthis:"))
async def cb_editthis(callback: CallbackQuery, state: FSMContext):
    lang = await db.get_lang(callback.from_user.id)
    try:
        gen_id = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    gen = await db.get_generation_by_id(gen_id)
    if not gen or not gen.get("result_file_id"):
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    await state.set_state(EditStates.waiting_editthis_instruction)
    await state.update_data(editthis_file_id=gen["result_file_id"])
    await callback.message.answer(
        t("edit_ask", lang) + "\n\n" + t("myworks_regen_hint", lang)
    )
    await callback.answer()
