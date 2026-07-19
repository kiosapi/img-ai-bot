"""Small Telegram-specific helpers shared across handlers."""
import asyncio
import contextlib

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest


async def safe_edit(message, text: str, reply_markup=None):
    """Edit a message's text, falling back to deleting it and sending a new
    message when the original isn't editable as text (e.g. it's a photo
    result or a QR-code image — Telegram rejects edit_text on those with
    "there is no text in the message to edit"). This keeps "Menu"/"Back"
    buttons working after image results and photo-based messages.
    """
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        msg = str(e)
        if "message is not modified" in msg:
            return
        # Not a text message (photo/etc) -> replace it with a fresh message.
        try:
            await message.delete()
        except Exception:
            pass
        await message.answer(text, reply_markup=reply_markup)


class ProgressAnimator:
    """Periodically sends a Telegram 'uploading photo' chat action and updates
    a status message with elapsed time + a moving progress bar, so users can
    see the bot is actively working instead of it looking stuck during long
    (can be 30s-3min) AI generation/edit calls.
    """

    FRAMES = [
        "▰▱▱▱▱▱▱▱▱▱", "▰▰▱▱▱▱▱▱▱▱", "▰▰▰▱▱▱▱▱▱▱", "▰▰▰▰▱▱▱▱▱▱", "▰▰▰▰▰▱▱▱▱▱",
        "▰▰▰▰▰▰▱▱▱▱", "▰▰▰▰▰▰▰▱▱▱", "▰▰▰▰▰▰▰▰▱▱", "▰▰▰▰▰▰▰▰▰▱", "▰▰▰▰▰▰▰▰▰▰",
    ]

    def __init__(self, bot: Bot, chat_id: int, status_message, base_text: str, interval: float = 4.0):
        self.bot = bot
        self.chat_id = chat_id
        self.status_message = status_message
        self.base_text = base_text
        self.interval = interval
        self._task: asyncio.Task | None = None

    async def _run(self):
        elapsed = 0
        i = 0
        while True:
            await asyncio.sleep(self.interval)
            elapsed += int(self.interval)
            i = (i + 1) % len(self.FRAMES)
            with contextlib.suppress(Exception):
                await self.bot.send_chat_action(self.chat_id, "upload_photo")
            with contextlib.suppress(Exception):
                await self.status_message.edit_text(
                    f"{self.base_text}\n{self.FRAMES[i]}  ⏱️ {elapsed}s"
                )

    def start(self):
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await self._task
