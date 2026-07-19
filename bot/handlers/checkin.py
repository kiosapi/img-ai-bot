"""Daily check-in + streak."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from datetime import date

import db
import ui
from i18n import t
from tgutil import safe_edit

router = Router()


def _checkin_text(info: dict, lang: str) -> str:
    last = info.get("last_checkin")
    streak = info.get("streak", 0)
    total = info.get("total_checkin", 0)
    today = date.today()
    can = last != today
    return t("checkin_status", lang, streak=streak, total=total, can=t("checkin_can" if can else "checkin_done_today", lang))


@router.message(Command("checkin"))
async def cmd_checkin(message: Message):
    lang = await db.get_lang(message.from_user.id)
    info = await db.get_checkin_info(message.from_user.id)
    today = date.today()
    if info.get("last_checkin") == today:
        await message.answer(t("checkin_already", lang, streak=info.get("streak", 0)), reply_markup=ui.back_menu(lang))
        return
    ok, new_streak, total, bonus = await db.try_checkin(message.from_user.id)
    if not ok:
        await message.answer(t("checkin_already", lang, streak=new_streak), reply_markup=ui.back_menu(lang))
        return
    await message.answer(t("checkin_ok", lang, streak=new_streak, bonus=bonus, total=total), reply_markup=ui.checkin_menu(lang))


@router.callback_query(F.data == "menu:checkin")
async def nav_checkin(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    info = await db.get_checkin_info(callback.from_user.id)
    text = t("checkin_title", lang, streak=info.get("streak", 0), total=info.get("total_checkin", 0))
    can = info.get("last_checkin") != date.today()
    await safe_edit(callback.message, text, reply_markup=ui.checkin_menu(lang, can=can))
    await callback.answer()


@router.callback_query(F.data == "checkin:do")
async def do_checkin(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    ok, new_streak, total, bonus = await db.try_checkin(callback.from_user.id)
    if not ok:
        await callback.answer(t("checkin_already", lang, streak=new_streak), show_alert=True)
        # refresh
        await safe_edit(callback.message, t("checkin_title", lang, streak=new_streak, total=total), reply_markup=ui.checkin_menu(lang, can=False))
        return
    await safe_edit(callback.message, t("checkin_ok", lang, streak=new_streak, bonus=bonus, total=total), reply_markup=ui.checkin_menu(lang, can=False))
    await callback.answer(t("checkin_toast", lang, bonus=bonus))
