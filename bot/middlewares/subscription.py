"""Middleware: enforce channel subscription before allowing bot usage."""
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.utils.keyboard import InlineKeyboardBuilder

import db
from config import REQUIRED_CHANNEL, ADMIN_IDS
from i18n import t

_ALLOWED_STATUSES = {"member", "administrator", "creator"}


def _join_keyboard(lang: str = "id"):
    kb = InlineKeyboardBuilder()
    ch = REQUIRED_CHANNEL.lstrip("@")
    kb.button(text=t("join_channel", lang), url=f"https://t.me/{ch}")
    kb.button(text=t("already_joined", lang), callback_data="check_sub")
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


async def _notify_referrer(bot, reward: dict, referred_user):
    """Best-effort DM to the referrer telling them their bonus just landed."""
    try:
        lang = await db.get_lang(reward["referrer_id"])
        name = f"@{referred_user.username}" if referred_user.username else (referred_user.first_name or "Seseorang")
        if reward["reward_type"] == "quota":
            desc = (f"{reward['reward_amount']} kuota gambar tambahan" if lang == "id"
                    else f"{reward['reward_amount']} extra image quota")
        else:
            from ui import rupiah
            desc = (f"Saldo {rupiah(reward['reward_amount'])}" if lang == "id"
                    else f"Balance {rupiah(reward['reward_amount'])}")
        text = (
            f"🎉 <b>Bonus referral cair!</b>\n\n{name} baru saja join lewat link kamu.\nKamu dapat: <b>{desc}</b>"
            if lang == "id" else
            f"🎉 <b>Referral bonus unlocked!</b>\n\n{name} just joined via your link.\nYou received: <b>{desc}</b>"
        )
        await bot.send_message(reward["referrer_id"], text)
    except Exception:
        pass  # never let a notification failure break the subscription flow


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = data.get("event_from_user")
        bot = data["bot"]
        if user is None:
            return await handler(event, data)

        # Register/refresh the user and capture any referral deep-link
        # (/start ref_<referrer_id>) BEFORE the subscription gate — this
        # middleware runs ahead of every router, so a brand-new user who
        # hasn't joined the channel yet would otherwise never reach
        # cmd_start and their referral would be lost.
        is_new = not await db.user_exists(user.id)
        await db.upsert_user(user.id, user.username, user.first_name, user.language_code)

        if is_new and isinstance(event, Message) and event.text:
            payload = event.text.partition(" ")[2].strip()
            if payload.startswith("ref_"):
                try:
                    referrer_id = int(payload[4:])
                    await db.record_referral_signup(referrer_id, user.id)
                except ValueError:
                    pass

        if await is_subscribed(bot, user.id):
            # Reward the referrer as soon as the referred user clears the
            # subscription gate for the first time (per user's decision:
            # bonus is granted on join-channel, not on raw /start).
            reward = await db.try_reward_referral(user.id)
            if reward:
                await _notify_referrer(bot, reward, user)
            return await handler(event, data)

        lang = await db.get_lang(user.id)
        text = t("join_required", lang, channel=REQUIRED_CHANNEL)
        if isinstance(event, CallbackQuery):
            await event.answer(t("join_not_joined", lang), show_alert=True)
            await event.message.answer(text, reply_markup=_join_keyboard(lang))
        elif isinstance(event, Message):
            await event.answer(text, reply_markup=_join_keyboard(lang))
        return  # stop processing
