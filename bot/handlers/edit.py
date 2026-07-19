"""Image-to-image / edit: user sends a photo with a caption prompt (in the same
message), OR sends the photo first and the instruction as a separate
follow-up message (very common on mobile Telegram clients) — both flows are
supported. Editing itself is shared between them via _do_edit().
"""
import io
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, BufferedInputFile

import db
import ui
import cubence
from i18n import t
from handlers.generate import check_and_consume, _size_of, is_maintenance
from tgutil import ProgressAnimator
from states import EditStates

router = Router()


async def _has_pending_deposit_awaiting_proof(user_id: int) -> bool:
    dep = await db.get_pending_deposit(user_id)
    return bool(dep and not dep["proof_file_id"])


async def _do_edit(message: Message, file_id: str, prompt: str):
    lang = await db.get_lang(message.from_user.id)
    if await is_maintenance():
        await message.answer(t("maintenance", lang))
        return

    allowed, used, limit = await check_and_consume(message.from_user.id)
    if not allowed:
        await message.answer(
            t("quota_exhausted", lang, used=used, limit=limit, bar=ui.quota_bar(used, limit)),
            reply_markup=ui.back_menu(lang))
        return

    size = await _size_of(message.from_user.id)
    status = await message.answer(t("editing", lang, used=used, limit=limit) + "\n▱▱▱▱▱▱▱▱▱▱  ⏱️ 0s")
    animator = ProgressAnimator(message.bot, message.chat.id, status, t("editing", lang, used=used, limit=limit))
    animator.start()
    try:
        buf = io.BytesIO()
        await message.bot.download(file_id, destination=buf)
        image_bytes = buf.getvalue()

        img = await cubence.edit_image(image_bytes, prompt, size=size)
        await message.answer_photo(
            BufferedInputFile(img, filename="edited.png"),
            caption=t("edit_done", lang, prompt=prompt[:200], size=size, left=ui.sisa_text(used, limit, lang)),
            reply_markup=ui.result_menu(lang),
        )
        await db.log_generation(message.from_user.id, "edit", prompt, size, True)
    except cubence.CubenceError as e:
        await db.log_generation(message.from_user.id, "edit", prompt, size, False)
        await message.answer(t("edit_failed", lang, err=e), reply_markup=ui.back_menu(lang))
    except Exception as e:
        await db.log_generation(message.from_user.id, "edit", prompt, size, False)
        await message.answer(t("edit_failed", lang, err=f"Unexpected error: {e}"), reply_markup=ui.back_menu(lang))
    finally:
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

    # Guard: if user has a pending deposit awaiting proof AND is not in edit FSM,
    # let the deposit handler (StateFilter(None)) handle it instead.
    # If they ARE in edit FSM (clicked Edit Photo), edit takes priority.
    fsm_state = await state.get_state()
    if fsm_state is None and await _has_pending_deposit_awaiting_proof(message.from_user.id):
        # Don't consume — return without handling so balance router can pick it up
        return

    if not prompt:
        # No caption yet -> store file_id in FSM data and ask for instruction.
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
        # User clicked "Edit Foto" and typed before sending a photo. Keep the
        # state active and tell them a photo is required first.
        lang = await db.get_lang(message.from_user.id)
        await message.answer(ui.edit_ask(lang))
        return
    await state.clear()
    await _do_edit(message, file_id, message.text.strip())
