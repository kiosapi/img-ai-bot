"""Premium upgrade flow: browse plans, buy instantly with account balance."""
from aiogram import Router, F
from aiogram.types import CallbackQuery

import db
import ui
from i18n import t
from tgutil import safe_edit

router = Router()


# ---------------- Browse plans ----------------
@router.callback_query(F.data == "menu:upgrade")
async def show_plans(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    plans = await db.get_active_plans()
    await safe_edit(callback.message, 
        ui.upgrade_intro(bool(plans), lang),
        reply_markup=ui.plans_menu(plans, lang) if plans else ui.back_menu(lang))
    await callback.answer()


@router.callback_query(F.data.startswith("plan:"))
async def show_plan(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    plan_id = int(callback.data.split(":", 1)[1])
    plan = await db.get_plan(plan_id)
    if not plan or not plan["is_active"]:
        await callback.answer(t("plan_unavailable", lang), show_alert=True)
        return
    balance = await db.get_balance(callback.from_user.id)
    await safe_edit(callback.message, 
        ui.plan_detail(plan, balance, lang), reply_markup=ui.plan_buy_menu(plan, lang))
    await callback.answer()


# ---------------- Buy with balance ----------------
@router.callback_query(F.data.startswith("buyplan:"))
async def buy_plan(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    plan_id = int(callback.data.split(":", 1)[1])
    plan = await db.get_plan(plan_id)
    if not plan or not plan["is_active"]:
        await callback.answer(t("plan_unavailable", lang), show_alert=True)
        return

    ok, new_until, balance = await db.buy_plan_with_balance(callback.from_user.id, plan)
    if not ok:
        await safe_edit(callback.message, 
            ui.plan_topup_needed(balance, plan["price"], lang),
            reply_markup=ui.plan_topup_menu(lang))
        await callback.answer(t("plan_insufficient", lang), show_alert=True)
        return

    await safe_edit(callback.message, 
        ui.premium_activated(plan["name"], new_until, plan["daily_limit"], balance, lang),
        reply_markup=ui.back_menu(lang))
    await callback.answer(t("plan_bought", lang))
