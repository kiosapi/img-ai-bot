"""/start, /help, /quota, main-menu navigation, and 'check subscription' callback."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ForceReply

import db
import ui
from config import REQUIRED_CHANNEL, DEFAULT_DAILY_LIMIT, DEFAULT_SIZE
from middlewares.subscription import is_subscribed

router = Router()

# Markers placed in ForceReply prompts so we know what the user's reply is for.
ASK_GEN = "🎨 Ketik prompt gambarmu:"


@router.message(Command("start"))
async def cmd_start(message: Message):
    u = message.from_user
    await db.upsert_user(u.id, u.username, u.first_name)
    await message.answer(ui.welcome(u.first_name or "kawan"), reply_markup=ui.main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(ui.HELP, reply_markup=ui.back_menu())


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer(ui.welcome(message.from_user.first_name or "kawan"), reply_markup=ui.main_menu())


@router.message(Command("quota"))
async def cmd_quota(message: Message):
    limit = await db.effective_daily_limit(message.from_user.id, DEFAULT_DAILY_LIMIT)
    used = await db.get_today_count(message.from_user.id)
    premium = await db.get_premium_info(message.from_user.id)
    await message.answer(ui.quota_text(used, limit, premium), reply_markup=ui.back_menu())


@router.message(Command("upgrade"))
async def cmd_upgrade(message: Message):
    plans = await db.get_active_plans()
    await message.answer(
        ui.upgrade_intro(bool(plans)),
        reply_markup=ui.plans_menu(plans) if plans else ui.back_menu())


# ---------------- Menu navigation ----------------
@router.callback_query(F.data == "menu:home")
async def nav_home(callback: CallbackQuery):
    await callback.message.edit_text(
        ui.welcome(callback.from_user.first_name or "kawan"), reply_markup=ui.main_menu())
    await callback.answer()


@router.callback_query(F.data == "menu:help")
async def nav_help(callback: CallbackQuery):
    await callback.message.edit_text(ui.HELP, reply_markup=ui.back_menu())
    await callback.answer()


@router.callback_query(F.data == "menu:quota")
async def nav_quota(callback: CallbackQuery):
    limit = await db.effective_daily_limit(callback.from_user.id, DEFAULT_DAILY_LIMIT)
    used = await db.get_today_count(callback.from_user.id)
    premium = await db.get_premium_info(callback.from_user.id)
    await callback.message.edit_text(ui.quota_text(used, limit, premium), reply_markup=ui.back_menu())
    await callback.answer()


@router.callback_query(F.data == "menu:size")
async def nav_size(callback: CallbackQuery):
    current = await db.get_pref_size(callback.from_user.id, DEFAULT_SIZE)
    await callback.message.edit_text("📐 <b>Pilih Ukuran Gambar</b>", reply_markup=ui.size_menu(current))
    await callback.answer()


@router.callback_query(F.data == "menu:gen")
async def nav_gen(callback: CallbackQuery):
    await callback.message.answer(ui.prompt_ask(), reply_markup=ForceReply(input_field_placeholder="Ketik prompt..."))
    await callback.answer()


@router.callback_query(F.data == "menu:edit")
async def nav_edit(callback: CallbackQuery):
    await callback.message.answer(ui.edit_ask())
    await callback.answer()


# ---------------- Subscription gate ----------------
@router.callback_query(F.data == "check_sub")
async def check_sub(callback: CallbackQuery):
    if await is_subscribed(callback.bot, callback.from_user.id):
        await callback.message.edit_text(
            "✅ <b>Berhasil!</b> Kamu sudah join. Selamat berkreasi 🎨",
            reply_markup=ui.main_menu())
    else:
        await callback.answer(f"Belum terdeteksi join {REQUIRED_CHANNEL}. Coba lagi.", show_alert=True)
