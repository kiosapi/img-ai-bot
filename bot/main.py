"""Bot entrypoint (aiogram v3, long polling) + heartbeat for Bot Health Center."""
import asyncio
import logging
import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

import db
import config
from middlewares.subscription import SubscriptionMiddleware, MaintenanceMiddleware
from handlers import start, generate, edit, premium, balance, style, myworks, checkin, inline, batch, sticker, model

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

_heartbeat_task: asyncio.Task | None = None


async def _heartbeat_loop():
    """Update settings bot_last_heartbeat every 60s."""
    while True:
        try:
            iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            await db.set_setting("bot_last_heartbeat", iso)
            log.info("heartbeat updated: %s", iso)
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.warning("heartbeat failed: %s", e)
        await asyncio.sleep(60)


async def _set_commands(bot: Bot):
    await bot.set_my_commands([
        BotCommand(command="start", description="🏠 Menu utama / Main menu"),
        BotCommand(command="generate", description="🎨 Buat gambar / Generate image"),
        BotCommand(command="model", description="🤖 Pilih Model / Select Model"),
        BotCommand(command="enhance", description="✨ Enhance prompt + generate"),
        BotCommand(command="batch", description="🎲 Batch x4 generate (cth: /batch 4 kucing)"),
        BotCommand(command="sticker", description="🎖️ Sticker pack dari karya"),
        BotCommand(command="myworks", description="🖼️ Karya Saya / My Works"),
        BotCommand(command="checkin", description="📅 Check-in harian / Daily check-in"),
        BotCommand(command="size", description="📐 Ukuran / Size"),
        BotCommand(command="quota", description="📊 Kuota / Quota"),
        BotCommand(command="balance", description="💰 Saldo / Balance"),
        BotCommand(command="upgrade", description="💎 Premium"),
        BotCommand(command="referral", description="🎁 Ajak Teman / Invite Friends"),
        BotCommand(command="lang", description="🌐 Bahasa / Language"),
        BotCommand(command="help", description="❓ Bantuan / Help"),
    ])

def _get_storage():
    try:
        from fsm_pg import PGStorage
        return PGStorage(lambda: db._pool)
    except Exception:
        return MemoryStorage()

async def main():
    await db.init_pool(config.DATABASE_URL)
    await db.seed_default_plan()

    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = _get_storage()
    dp = Dispatcher(storage=storage)

    maint_mw = MaintenanceMiddleware()
    sub_mw = SubscriptionMiddleware()
    for obs in (dp.message, dp.callback_query, dp.inline_query):
        obs.middleware(maint_mw)
        obs.middleware(sub_mw)

    dp.include_router(start.router)
    dp.include_router(checkin.router)
    dp.include_router(generate.router)
    dp.include_router(edit.router)
    dp.include_router(style.router)
    dp.include_router(myworks.router)
    dp.include_router(premium.router)
    dp.include_router(balance.router)
    dp.include_router(model.router)
    dp.include_router(batch.router)
    dp.include_router(sticker.router)
    dp.include_router(inline.router)

    # start heartbeat task
    global _heartbeat_task
    _heartbeat_task = asyncio.create_task(_heartbeat_loop())
    logging.info("Bot heartbeat task started (60s)")

    logging.info("Bot starting (polling)...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await _set_commands(bot)
        await dp.start_polling(bot)
    finally:
        if _heartbeat_task:
            _heartbeat_task.cancel()
            try:
                await _heartbeat_task
            except asyncio.CancelledError:
                pass
        await db.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
