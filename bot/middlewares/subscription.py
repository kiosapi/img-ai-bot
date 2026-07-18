"""Middleware: enforce channel subscription before allowing bot usage."""
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import REQUIRED_CHANNEL, ADMIN_IDS

_ALLOWED_STATUSES = {"member", "administrator", "creator"}


def _join_keyboard():
    kb = InlineKeyboardBuilder()
    ch = REQUIRED_CHANNEL.lstrip("@")
    kb.button(text="📢 Join Channel", url=f"https://t.me/{ch}")
    kb.button(text="✅ Sudah Join", callback_data="check_sub")
    kb.adjust(1)
    return kb.as_markup()


async def is_subscribed(bot, user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in _ALLOWED_STATUSES
    except Exception:
        # If bot can't check (not admin / channel issue), fail open=False
        return False


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = data.get("event_from_user")
        bot = data["bot"]
        if user is None:
            return await handler(event, data)

        if await is_subscribed(bot, user.id):
            return await handler(event, data)

        text = (
            "🔒 Untuk memakai bot ini, kamu harus join channel kami dulu.\n\n"
            f"Join {REQUIRED_CHANNEL} lalu tekan <b>Sudah Join</b>."
        )
        if isinstance(event, CallbackQuery):
            await event.answer("Kamu belum join channel.", show_alert=True)
            await event.message.answer(text, reply_markup=_join_keyboard())
        elif isinstance(event, Message):
            await event.answer(text, reply_markup=_join_keyboard())
        return  # stop processing
