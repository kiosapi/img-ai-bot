"""Balance / deposit flow: user picks amount, picks method, uploads proof. IDOR + amount spoof + flood fixed."""
from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
import html
import db
import ui
from i18n import t
from config import ADMIN_IDS
from tgutil import safe_edit
from states import BalanceStates

router = Router()

@router.callback_query(F.data == "menu:balance")
async def show_balance(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    balance = await db.get_balance(callback.from_user.id)
    await safe_edit(callback.message, ui.balance_text(balance, lang), reply_markup=ui.balance_menu(lang))
    await callback.answer()

@router.callback_query(F.data == "deposit:new")
async def new_deposit(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    # anti flood: block if pending exists
    pend = await db.get_pending_deposit(callback.from_user.id)
    if pend:
        await callback.answer(t("deposit_pending_exists", lang) if "deposit_pending_exists" in t("deposit_pending_exists", lang) else "Masih ada deposit pending, selesaikan dulu", show_alert=True)
        return
    settings = await db.get_balance_settings()
    if not settings["enabled"]:
        await safe_edit(callback.message, t("deposit_disabled", lang), reply_markup=ui.back_menu(lang))
        await callback.answer()
        return
    await safe_edit(callback.message,
        t("deposit_pick_amount", lang, min=ui.rupiah(settings["min_amount"]), max=ui.rupiah(settings["max_amount"])),
        reply_markup=ui.deposit_amount_menu(settings["quick_amounts"], lang))
    await callback.answer()

@router.callback_query(F.data == "depamt:custom")
async def ask_custom_amount(callback: CallbackQuery, state: FSMContext):
    lang = await db.get_lang(callback.from_user.id)
    settings = await db.get_balance_settings()
    text = t("deposit_custom_ask", lang, min=ui.rupiah(settings["min_amount"]), max=ui.rupiah(settings["max_amount"]))
    await state.set_state(BalanceStates.waiting_custom_amount)
    await callback.message.answer(text)
    await callback.answer()

async def _proceed_amount(message_or_cb, user_id: int, amount: int, lang: str, edit: bool):
    methods = await db.get_active_methods()
    if not methods:
        text = "Belum ada metode pembayaran tersedia. Hubungi admin." if lang == "id" else "No payment methods available yet. Contact admin."
        if edit:
            await message_or_cb.answer(text, show_alert=True)
        else:
            await message_or_cb.answer(text)
        return
    text = t("deposit_pick_method", lang, amount=ui.rupiah(amount))
    kb = ui.deposit_methods_menu(methods, amount, lang)
    if edit:
        await safe_edit(message_or_cb.message, text, reply_markup=kb)
    else:
        await message_or_cb.answer(text, reply_markup=kb)

@router.callback_query(F.data.startswith("depamt:"))
async def pick_amount(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    try:
        amount = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    settings = await db.get_balance_settings()
    if amount < settings["min_amount"] or amount > settings["max_amount"] or amount<0 or amount>100_000_000:
        await callback.answer(t("deposit_custom_range", lang, min=ui.rupiah(settings["min_amount"]), max=ui.rupiah(settings["max_amount"])), show_alert=True)
        return
    await _proceed_amount(callback, callback.from_user.id, amount, lang, edit=True)
    await callback.answer()

@router.message(BalanceStates.waiting_custom_amount, F.text, ~F.text.startswith("/"))
async def fsm_custom_amount(message: Message, state: FSMContext):
    await state.clear()
    lang = await db.get_lang(message.from_user.id)
    settings = await db.get_balance_settings()
    raw = message.text.strip().replace(".", "").replace(",", "").replace(" ", "")
    if not raw.isdigit():
        await message.answer(t("deposit_custom_invalid", lang))
        return
    amount = int(raw)
    if amount < settings["min_amount"] or amount > settings["max_amount"] or amount<0 or amount>100_000_000:
        await message.answer(t("deposit_custom_range", lang, min=ui.rupiah(settings["min_amount"]), max=ui.rupiah(settings["max_amount"])))
        return
    await _proceed_amount(message, message.from_user.id, amount, lang, edit=False)

@router.callback_query(F.data.startswith("depmethod:"))
async def pick_method(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    try:
        _, amount_s, method_id_s = callback.data.split(":")
        amount = int(amount_s)
        method_id = int(method_id_s)
    except Exception:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    # re-validate min/max — client controlled callback
    settings = await db.get_balance_settings()
    if amount < settings["min_amount"] or amount > settings["max_amount"] or amount<0 or amount>100_000_000:
        await callback.answer("Nominal tidak valid", show_alert=True)
        return
    # block if pending
    pend = await db.get_pending_deposit(callback.from_user.id)
    if pend:
        await callback.answer("Masih ada deposit pending", show_alert=True)
        return
    method = await db.get_method(method_id)
    if not method:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return

    deposit_id = await db.create_deposit(callback.from_user.id, amount, method)
    text = ui.deposit_info(deposit_id, amount, method, lang)

    if method.get("qr_image"):
        # qr_image is file_id validation length 10-200 alphanumeric
        try:
            await callback.message.answer_photo(method["qr_image"], caption=text, reply_markup=ui.deposit_cancel_menu(lang))
        except Exception:
            await callback.message.answer(text, reply_markup=ui.deposit_cancel_menu(lang))
    else:
        await callback.message.answer(text, reply_markup=ui.deposit_cancel_menu(lang))
    await callback.answer(t("saved", lang))

@router.callback_query(F.data == "deposit:cancel")
async def cancel_deposit(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    dep = await db.get_pending_deposit(callback.from_user.id)
    if dep:
        await db.cancel_deposit(dep["id"])
    await safe_edit(callback.message, t("deposit_cancelled", lang), reply_markup=ui.back_menu(lang))
    await callback.answer()

@router.callback_query(F.data == "deposit:history")
async def deposit_history(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    deposits = await db.get_user_deposits(callback.from_user.id)
    await safe_edit(callback.message, ui.deposit_history_text(deposits, lang), reply_markup=ui.back_menu(lang))
    await callback.answer()

async def _awaiting_deposit_proof(message: Message) -> bool:
    dep = await db.get_pending_deposit(message.from_user.id)
    return bool(dep and not dep["proof_file_id"])

@router.message(StateFilter(None), F.photo, _awaiting_deposit_proof)
async def receive_deposit_proof(message: Message, bot: Bot):
    lang = await db.get_lang(message.from_user.id)
    dep = await db.get_pending_deposit(message.from_user.id)
    if not dep:
        return
    file_id = message.photo[-1].file_id
    await db.attach_deposit_proof(dep["id"], file_id)
    await message.answer(t("deposit_proof_received", lang), reply_markup=ui.back_menu(lang))

    raw_uname = f"@{message.from_user.username}" if message.from_user.username else (message.from_user.first_name or f"user {message.from_user.id}")
    uname = html.escape(raw_uname)
    note = t("deposit_note", "id", id=dep["id"], uname=uname, uid=message.from_user.id, amount=ui.rupiah(dep["amount"]), method=html.escape(dep["method_name"]))
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(admin_id, file_id, caption=note)
        except Exception:
            pass
