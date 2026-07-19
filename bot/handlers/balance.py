"""Balance / deposit flow: user picks amount, picks method, uploads proof.
Admin approves/rejects the deposit from the dashboard; approval credits the balance.
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ForceReply

import db
import ui
from i18n import t
from config import ADMIN_IDS
from tgutil import safe_edit

router = Router()

ASK_CUSTOM_MARKER = "TOPUP_CUSTOM_AMOUNT"


# ---------------- Balance home ----------------
@router.callback_query(F.data == "menu:balance")
async def show_balance(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    balance = await db.get_balance(callback.from_user.id)
    await safe_edit(callback.message, ui.balance_text(balance, lang), reply_markup=ui.balance_menu(lang))
    await callback.answer()


# ---------------- Start a new deposit ----------------
@router.callback_query(F.data == "deposit:new")
async def new_deposit(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
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
async def ask_custom_amount(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    settings = await db.get_balance_settings()
    text = t("deposit_custom_ask", lang, min=ui.rupiah(settings["min_amount"]), max=ui.rupiah(settings["max_amount"]))
    await callback.message.answer(
        f"{ASK_CUSTOM_MARKER}\n{text}", reply_markup=ForceReply(input_field_placeholder="50000"))
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
    amount = int(callback.data.split(":", 1)[1])
    settings = await db.get_balance_settings()
    if amount < settings["min_amount"] or amount > settings["max_amount"]:
        await callback.answer(t("deposit_custom_range", lang, min=ui.rupiah(settings["min_amount"]), max=ui.rupiah(settings["max_amount"])), show_alert=True)
        return
    await _proceed_amount(callback, callback.from_user.id, amount, lang, edit=True)
    await callback.answer()


# Reply to the ForceReply "custom amount" prompt.
async def _is_custom_amount_reply(message: Message) -> bool:
    rt = message.reply_to_message
    return bool(rt and rt.from_user and rt.from_user.is_bot and (rt.text or "").startswith(ASK_CUSTOM_MARKER))


@router.message(F.reply_to_message, F.text, ~F.text.startswith("/"), _is_custom_amount_reply)
async def reply_custom_amount(message: Message):
    rt = message.reply_to_message
    if not (rt and rt.from_user and rt.from_user.is_bot and (rt.text or "").startswith(ASK_CUSTOM_MARKER)):
        return
    lang = await db.get_lang(message.from_user.id)
    settings = await db.get_balance_settings()
    raw = message.text.strip().replace(".", "").replace(",", "").replace(" ", "")
    if not raw.isdigit():
        await message.answer(t("deposit_custom_invalid", lang))
        return
    amount = int(raw)
    if amount < settings["min_amount"] or amount > settings["max_amount"]:
        await message.answer(t("deposit_custom_range", lang, min=ui.rupiah(settings["min_amount"]), max=ui.rupiah(settings["max_amount"])))
        return
    await _proceed_amount(message, message.from_user.id, amount, lang, edit=False)


# ---------------- Pick method -> create deposit ----------------
@router.callback_query(F.data.startswith("depmethod:"))
async def pick_method(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    _, amount, method_id = callback.data.split(":")
    amount = int(amount)
    method = await db.get_method(int(method_id))
    if not method:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return

    deposit_id = await db.create_deposit(callback.from_user.id, amount, method)
    text = ui.deposit_info(deposit_id, amount, method, lang)

    if method.get("qr_image"):
        await callback.message.answer_photo(
            method["qr_image"], caption=text, reply_markup=ui.deposit_cancel_menu(lang))
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


# ---------------- History ----------------
@router.callback_query(F.data == "deposit:history")
async def deposit_history(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    deposits = await db.get_user_deposits(callback.from_user.id)
    await safe_edit(callback.message, ui.deposit_history_text(deposits, lang), reply_markup=ui.back_menu(lang))
    await callback.answer()


# ---------------- Receive deposit proof ----------------
async def _awaiting_deposit_proof(message: Message) -> bool:
    dep = await db.get_pending_deposit(message.from_user.id)
    return bool(dep and not dep["proof_file_id"])


@router.message(F.photo, _awaiting_deposit_proof)
async def receive_deposit_proof(message: Message, bot: Bot):
    lang = await db.get_lang(message.from_user.id)
    dep = await db.get_pending_deposit(message.from_user.id)
    if not dep:
        return
    file_id = message.photo[-1].file_id
    await db.attach_deposit_proof(dep["id"], file_id)
    await message.answer(t("deposit_proof_received", lang), reply_markup=ui.back_menu(lang))

    uname = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    note = t(
        "deposit_note", "id", id=dep["id"], uname=uname, uid=message.from_user.id,
        amount=ui.rupiah(dep["amount"]), method=dep["method_name"])
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(admin_id, file_id, caption=note)
        except Exception:
            pass
