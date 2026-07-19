"""Bot entrypoint (aiogram v3, long polling)."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

import db
import config
from middlewares.subscription import SubscriptionMiddleware
from handlers import start, generate, edit, premium, balance, style, myworks

logging.basicConfig(level=logging.INFO)


async def _set_commands(bot: Bot):
    await bot.set_my_commands([
        BotCommand(command="start", description="🏠 Menu utama / Main menu"),
        BotCommand(command="generate", description="🎨 Buat gambar / Generate image"),
        BotCommand(command="myworks", description="🖼️ Karya Saya / My Works"),
        BotCommand(command="size", description="📐 Ukuran / Size"),
        BotCommand(command="quota", description="📊 Kuota / Quota"),
        BotCommand(command="balance", description="💰 Saldo / Balance"),
        BotCommand(command="upgrade", description="💎 Premium"),
        BotCommand(command="referral", description="🎁 Ajak Teman / Invite Friends"),
        BotCommand(command="lang", description="🌐 Bahasa / Language"),
        BotCommand(command="help", description="❓ Bantuan / Help"),
    ])


async def main():
    await db.init_pool(config.DATABASE_URL)
    await db.seed_default_plan()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Subscription gate applies to messages and callbacks
    sub_mw = SubscriptionMiddleware()
    dp.message.middleware(sub_mw)
    dp.callback_query.middleware(sub_mw)

    # Routers order matters: edit before balance for photo collision fix
    dp.include_router(start.router)
    dp.include_router(generate.router)
    dp.include_router(edit.router)
    dp.include_router(style.router)
    dp.include_router(myworks.router)
    dp.include_router(premium.router)
    dp.include_router(balance.router)

    logging.info("Bot starting (polling)...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await _set_commands(bot)
        await dp.start_polling(bot)
    finally:
        await db.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
