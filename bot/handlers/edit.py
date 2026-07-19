"""Image-to-image / edit: user sends a photo with a caption prompt (in the same
message), OR sends the photo first and the instruction as a separate
follow-up message (very common on mobile Telegram clients) — both flows are
supported. Editing itself is shared between them via _do_edit().
"""
import io
from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile, ForceReply

import db
import ui
import cubence
from i18n import t
from handlers.generate import check_and_consume, _size_of, is_maintenance
from tgutil import ProgressAnimator

router = Router()

# Marker embedded in the ForceReply prompt we send when a photo arrives
# without a caption, so the follow-up plain-text reply can be matched back to
# the photo's file_id without needing any separate in-memory/DB state (same
# trick used for the balance custom-amount flow).
EDIT_MARKER = "EDIT_PHOTO_PENDING"


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
async def handle_photo(message: Message):
    lang = await db.get_lang(message.from_user.id)
    prompt = (message.caption or "").strip()
    file_id = message.photo[-1].file_id  # highest resolution

    if not prompt:
        # No caption yet -> remember this photo via a ForceReply marker and
        # ask the user to type the instruction as a reply. Covers the common
        # "send photo, then type instructions separately" mobile flow that
        # previously made the bot ask for photo+caption again in a loop.
        # The marker is wrapped in a spoiler tag so it's blurred/hidden from
        # the user instead of showing as ugly raw text, while message.text
        # (read back on the reply) still contains the plain marker for us.
        await message.answer(
            f"<tg-spoiler>{EDIT_MARKER}:{file_id}</tg-spoiler>\n{ui.edit_ask(lang)}",
            reply_markup=ForceReply(input_field_placeholder="..."))
        return

    await _do_edit(message, file_id, prompt)


def _extract_pending_edit(message: Message) -> str | None:
    """If this message replies to our EDIT_MARKER prompt, return the file_id.
    Note: Telegram strips HTML formatting tags (like <tg-spoiler>) from the
    stored message text/caption — they become separate "entities", not part
    of the text itself — so the marker line here is always plain text.
    """
    rt = message.reply_to_message
    raw = (rt.text or rt.caption or "") if rt else ""
    if not (rt and rt.from_user and rt.from_user.is_bot and raw.startswith(EDIT_MARKER + ":")):
        return None
    marker_line = raw.split("\n", 1)[0]
    return marker_line.split(":", 1)[1]


async def _is_pending_edit_reply(message: Message) -> bool:
    return _extract_pending_edit(message) is not None


@router.message(F.reply_to_message, F.text, ~F.text.startswith("/"), _is_pending_edit_reply)
async def reply_edit_instruction(message: Message):
    file_id = _extract_pending_edit(message)
    await _do_edit(message, file_id, message.text.strip())
