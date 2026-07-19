"""/start, /help, /quota, main-menu navigation, language switch, and 'check subscription' callback."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ForceReply

import db
import ui
from i18n import t
from config import REQUIRED_CHANNEL, DEFAULT_DAILY_LIMIT, DEFAULT_SIZE
from middlewares.subscription import is_subscribed
from tgutil import safe_edit

router = Router()


async def _lang(user_id: int) -> str:
    return await db.get_lang(user_id)


@router.message(Command("start"))
async def cmd_start(message: Message):
    u = message.from_user
    await db.upsert_user(u.id, u.username, u.first_name, u.language_code)
    lang = await _lang(u.id)
    await message.answer(ui.welcome(u.first_name or "kawan", lang), reply_markup=ui.main_menu(lang))


@router.message(Command("help"))
async def cmd_help(message: Message):
    lang = await _lang(message.from_user.id)
    await message.answer(ui.help_text(lang), reply_markup=ui.back_menu(lang))


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    lang = await _lang(message.from_user.id)
    await message.answer(ui.welcome(message.from_user.first_name or "kawan", lang), reply_markup=ui.main_menu(lang))


@router.message(Command("quota"))
async def cmd_quota(message: Message):
    lang = await _lang(message.from_user.id)
    limit = await db.effective_daily_limit(message.from_user.id, DEFAULT_DAILY_LIMIT)
    used = await db.get_today_count(message.from_user.id)
    premium = await db.get_premium_info(message.from_user.id)
    await message.answer(ui.quota_text(used, limit, premium, lang), reply_markup=ui.back_menu(lang))


@router.message(Command("upgrade"))
async def cmd_upgrade(message: Message):
    lang = await _lang(message.from_user.id)
    plans = await db.get_active_plans()
    await message.answer(
        ui.upgrade_intro(bool(plans), lang),
        reply_markup=ui.plans_menu(plans, lang) if plans else ui.back_menu(lang))


@router.message(Command("balance"))
async def cmd_balance(message: Message):
    lang = await _lang(message.from_user.id)
    balance = await db.get_balance(message.from_user.id)
    await message.answer(ui.balance_text(balance, lang), reply_markup=ui.balance_menu(lang))


@router.message(Command("lang"))
async def cmd_lang(message: Message):
    lang = await _lang(message.from_user.id)
    await message.answer(t("lang_pick", lang), reply_markup=ui.lang_menu())


# ---------------- Menu navigation ----------------
@router.callback_query(F.data == "menu:home")
async def nav_home(callback: CallbackQuery):
    lang = await _lang(callback.from_user.id)
    await safe_edit(callback.message, 
        ui.welcome(callback.from_user.first_name or "kawan", lang), reply_markup=ui.main_menu(lang))
    await callback.answer()


@router.callback_query(F.data == "menu:help")
async def nav_help(callback: CallbackQuery):
    lang = await _lang(callback.from_user.id)
    await safe_edit(callback.message, ui.help_text(lang), reply_markup=ui.back_menu(lang))
    await callback.answer()


@router.callback_query(F.data == "menu:quota")
async def nav_quota(callback: CallbackQuery):
    lang = await _lang(callback.from_user.id)
    limit = await db.effective_daily_limit(callback.from_user.id, DEFAULT_DAILY_LIMIT)
    used = await db.get_today_count(callback.from_user.id)
    premium = await db.get_premium_info(callback.from_user.id)
    await safe_edit(callback.message, ui.quota_text(used, limit, premium, lang), reply_markup=ui.back_menu(lang))
    await callback.answer()


@router.callback_query(F.data == "menu:size")
async def nav_size(callback: CallbackQuery):
    lang = await _lang(callback.from_user.id)
    current = await db.get_pref_size(callback.from_user.id, DEFAULT_SIZE)
    await safe_edit(callback.message, t("size_pick", lang), reply_markup=ui.size_menu(current, lang))
    await callback.answer()


@router.callback_query(F.data == "menu:gen")
async def nav_gen(callback: CallbackQuery):
    lang = await _lang(callback.from_user.id)
    await callback.message.answer(ui.prompt_ask(lang), reply_markup=ForceReply(input_field_placeholder="..."))
    await callback.answer()


@router.callback_query(F.data == "menu:edit")
async def nav_edit(callback: CallbackQuery):
    lang = await _lang(callback.from_user.id)
    await callback.message.answer(ui.edit_ask(lang))
    await callback.answer()


# ---------------- Language switch ----------------
@router.callback_query(F.data == "menu:lang")
async def nav_lang(callback: CallbackQuery):
    lang = await _lang(callback.from_user.id)
    await safe_edit(callback.message, t("lang_pick", lang), reply_markup=ui.lang_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("lang:"))
async def set_lang(callback: CallbackQuery):
    new_lang = callback.data.split(":", 1)[1]
    await db.set_lang(callback.from_user.id, new_lang)
    await safe_edit(callback.message, 
        ui.welcome(callback.from_user.first_name or "kawan", new_lang), reply_markup=ui.main_menu(new_lang))
    await callback.answer(t("lang_set", new_lang))


# ---------------- Subscription gate ----------------
@router.callback_query(F.data == "check_sub")
async def check_sub(callback: CallbackQuery):
    lang = await _lang(callback.from_user.id)
    if await is_subscribed(callback.bot, callback.from_user.id):
        await safe_edit(callback.message, t("join_success", lang), reply_markup=ui.main_menu(lang))
    else:
        await callback.answer(t("join_not_detected", lang, channel=REQUIRED_CHANNEL), show_alert=True)
