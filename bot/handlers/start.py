"""/start, /help, /quota, main-menu navigation, language switch, and 'check subscription' callback."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, ForceReply

import db
import ui
import texts as dyn_texts
from i18n import t
from config import REQUIRED_CHANNEL, DEFAULT_DAILY_LIMIT, DEFAULT_SIZE
from middlewares.subscription import is_subscribed
from tgutil import safe_edit
from states import GenerateStates, EditStates

router = Router()


async def _lang(user_id: int) -> str:
    return await db.get_lang(user_id)

async def _welcome_dynamic(name: str, lang: str) -> str:
    # Try dynamic first, fallback to ui.welcome
    base = ui.welcome(name, lang)
    dyn = await dyn_texts.get_dynamic_text_or_none("welcome_text")
    if dyn:
        try:
            # support {name} {brand} placeholders if admin used them
            return dyn.format(name=name, brand=ui.BRAND) if "{" in dyn else dyn
        except Exception:
            return dyn
    return base

async def _help_dynamic(lang: str) -> str:
    dyn = await dyn_texts.get_dynamic_text_or_none("help_text")
    if dyn:
        return dyn
    return ui.help_text(lang)


async def _handle_web_login(message: Message, code: str) -> None:
    """Claim one-time web login code (public web-app Model B)."""
    import re
    import secrets as _secrets
    import time as _time

    u = message.from_user
    lang = await _lang(u.id)
    await db.upsert_user(u.id, u.username, u.first_name, getattr(u, "language_code", None))
    if await db.is_banned(u.id):
        await message.answer(
            "Akun diblokir. Login web gagal." if lang == "id" else "Account banned. Web login failed."
        )
        return
    if not code or not re.match(r"^[A-Za-z0-9_-]{8,48}$", code):
        await message.answer(
            "Kode login tidak valid. Buka ulang halaman web."
            if lang == "id"
            else "Invalid login code. Reopen the website."
        )
        return
    if not db._pool:
        await message.answer("DB offline. Coba lagi." if lang == "id" else "DB offline. Try again.")
        return
    async with db._pool.acquire() as con:
        await con.execute(
            """
            CREATE TABLE IF NOT EXISTS web_login_codes (
                code TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'pending',
                user_id BIGINT,
                session_token TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + interval '5 minutes',
                claimed_at TIMESTAMPTZ,
                ip TEXT,
                user_agent TEXT
            )
            """
        )
        await con.execute(
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
                token TEXT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + interval '30 days',
                user_agent TEXT,
                ip TEXT
            )
            """
        )
        row = await con.fetchrow(
            "SELECT code, status, expires_at FROM web_login_codes WHERE code=$1",
            code,
        )
        if not row:
            msg = (
                "Kode login tidak ditemukan / sudah kadaluarsa.\nBuka ulang website, klik Login, lalu buka link baru."
                if lang == "id"
                else "Login code not found or expired.\nReopen the site, click Login, then open the new link."
            )
            await message.answer(msg)
            return
        if row["status"] != "pending":
            await message.answer(
                "Kode ini sudah dipakai. Buka ulang website untuk login baru."
                if lang == "id"
                else "This code was already used. Reopen the site for a new login."
            )
            return
        if row["expires_at"].timestamp() < _time.time():
            await con.execute(
                "UPDATE web_login_codes SET status='expired' WHERE code=$1 AND status='pending'",
                code,
            )
            await message.answer(
                "Kode login kadaluarsa (5 menit). Buka ulang website."
                if lang == "id"
                else "Login code expired (5 min). Reopen the website."
            )
            return
        token = _secrets.token_urlsafe(32)
        await con.execute(
            """
            INSERT INTO user_sessions (token, user_id, expires_at, user_agent, ip)
            VALUES ($1, $2, now() + interval '30 days', $3, $4)
            """,
            token,
            u.id,
            "telegram-bot-login",
            "bot",
        )
        updated = await con.fetchval(
            """
            UPDATE web_login_codes
            SET status='claimed', user_id=$2, session_token=$3, claimed_at=now()
            WHERE code=$1 AND status='pending'
            RETURNING code
            """,
            code,
            u.id,
            token,
        )
        if not updated:
            await message.answer(
                "Kode sudah diklaim. Coba login lagi dari web."
                if lang == "id"
                else "Code already claimed. Try login again from the web."
            )
            return
    ok = (
        "<b>Login web berhasil</b>\n\nKembali ke browser — halaman imgaai akan otomatis masuk.\nKalau belum, refresh tab website."
        if lang == "id"
        else "<b>Web login successful</b>\n\nReturn to your browser — imgaai will sign in automatically.\nIf not, refresh the website tab."
    )
    await message.answer(ok, reply_markup=ui.main_menu(lang))


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    u = message.from_user
    lang = await _lang(u.id)
    payload = (message.text or "").partition(" ")[2].strip()
    # Model B web login: /start login_<code>
    if payload.startswith("login_"):
        code = payload[6:].strip()
        await _handle_web_login(message, code)
        return
    if payload.startswith("gen_"):
        raw = payload[4:].replace("_", " ").strip()
        if raw and raw not in ("inline_empty", "inline_new"):
            await message.answer(await _welcome_dynamic(u.first_name or "kawan", lang), reply_markup=ui.main_menu(lang))
            from handlers.generate import _do_generate
            lang2 = await _lang(u.id)
            await message.answer(f"🎨 <b>Generate:</b> <i>{raw}</i>\n\nMulai membuat...", reply_markup=ui.back_menu(lang2))
            await _do_generate(message, raw)
            return
    await message.answer(await _welcome_dynamic(u.first_name or "kawan", lang), reply_markup=ui.main_menu(lang))


@router.message(Command("help"))
async def cmd_help(message: Message):
    lang = await _lang(message.from_user.id)
    await message.answer(await _help_dynamic(lang), reply_markup=ui.back_menu(lang))


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    lang = await _lang(message.from_user.id)
    await message.answer(await _welcome_dynamic(message.from_user.first_name or "kawan", lang), reply_markup=ui.main_menu(lang))


@router.message(Command("quota"))
async def cmd_quota(message: Message):
    lang = await _lang(message.from_user.id)
    limit = await db.effective_daily_limit(message.from_user.id, DEFAULT_DAILY_LIMIT)
    used = await db.get_today_count(message.from_user.id)
    premium = await db.get_premium_info(message.from_user.id)
    bonus_quota = await db.get_bonus_quota(message.from_user.id)
    await message.answer(ui.quota_text(used, limit, premium, lang, bonus_quota), reply_markup=ui.back_menu(lang))


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
    bonus_quota = await db.get_bonus_quota(callback.from_user.id)
    await safe_edit(callback.message, ui.quota_text(used, limit, premium, lang, bonus_quota), reply_markup=ui.back_menu(lang))
    await callback.answer()


@router.callback_query(F.data == "menu:size")
async def nav_size(callback: CallbackQuery):
    lang = await _lang(callback.from_user.id)
    current = await db.get_pref_size(callback.from_user.id, DEFAULT_SIZE)
    await safe_edit(callback.message, t("size_pick", lang), reply_markup=ui.size_menu(current, lang))
    await callback.answer()


@router.callback_query(F.data == "menu:gen")
async def nav_gen(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await state.set_state(GenerateStates.waiting_prompt)
    # check if enhance enabled to show enhance option
    import feature_flags as ff
    enhance_on = await ff.enhance_enabled()
    kb = ui.gen_prompt_menu(lang, enhance_on=enhance_on)
    await callback.message.answer(ui.prompt_ask(lang), reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "menu:edit")
async def nav_edit(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await state.set_state(EditStates.waiting_instruction)
    await callback.message.answer(ui.edit_ask(lang), reply_markup=ForceReply(input_field_placeholder="..."))
    await callback.answer()


@router.callback_query(F.data == "menu:referral")
async def nav_referral(callback: CallbackQuery):
    lang = await _lang(callback.from_user.id)
    bot_user = await callback.bot.get_me()
    stats = await db.get_referral_stats(callback.from_user.id)
    settings = await db.get_referral_settings()
    text = ui.referral_text(
        bot_user.username, callback.from_user.id, stats,
        settings["reward_type"], settings["reward_amount"], lang)
    await safe_edit(callback.message, text, reply_markup=ui.referral_menu(lang))
    await callback.answer()


@router.message(Command("referral"))
async def cmd_referral(message: Message):
    lang = await _lang(message.from_user.id)
    bot_user = await message.bot.get_me()
    stats = await db.get_referral_stats(message.from_user.id)
    settings = await db.get_referral_settings()
    text = ui.referral_text(
        bot_user.username, message.from_user.id, stats,
        settings["reward_type"], settings["reward_amount"], lang)
    await message.answer(text, reply_markup=ui.referral_menu(lang))


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
