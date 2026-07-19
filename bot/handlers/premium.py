"""Premium upgrade flow: browse plans, pick payment method, submit proof."""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery

import db
import ui
from config import ADMIN_IDS

router = Router()


# ---------------- Browse plans ----------------
@router.callback_query(F.data == "menu:upgrade")
async def show_plans(callback: CallbackQuery):
    plans = await db.get_active_plans()
    await callback.message.edit_text(
        ui.upgrade_intro(bool(plans)),
        reply_markup=ui.plans_menu(plans) if plans else ui.back_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("plan:"))
async def show_plan(callback: CallbackQuery):
    plan_id = int(callback.data.split(":", 1)[1])
    plan = await db.get_plan(plan_id)
    if not plan or not plan["is_active"]:
        await callback.answer("Paket tidak tersedia", show_alert=True)
        return
    methods = await db.get_active_methods()
    if not methods:
        await callback.answer("Belum ada metode pembayaran tersedia. Hubungi admin.", show_alert=True)
        return
    await callback.message.edit_text(ui.plan_detail(plan), reply_markup=ui.methods_menu(methods, plan_id))
    await callback.answer()


# ---------------- Pick method -> create order ----------------
@router.callback_query(F.data.startswith("pay:"))
async def pick_method(callback: CallbackQuery):
    _, plan_id, method_id = callback.data.split(":")
    plan = await db.get_plan(int(plan_id))
    method = await db.get_method(int(method_id))
    if not plan or not method:
        await callback.answer("Data tidak valid", show_alert=True)
        return

    order_id = await db.create_order(callback.from_user.id, plan, method)
    text = ui.payment_info(plan, method, order_id)

    # If method is QRIS and has an image, send it as a photo.
    if method.get("qr_image"):
        await callback.message.answer_photo(
            method["qr_image"], caption=text, reply_markup=ui.cancel_order_menu())
    else:
        await callback.message.answer(text, reply_markup=ui.cancel_order_menu())
    await callback.answer("Order dibuat ✓")


@router.callback_query(F.data == "order:cancel")
async def cancel_order(callback: CallbackQuery):
    order = await db.get_pending_order(callback.from_user.id)
    if order:
        await db.cancel_order(order["id"])
    await callback.message.edit_text("❌ Order dibatalkan.", reply_markup=ui.back_menu())
    await callback.answer()


# ---------------- Receive payment proof ----------------
async def _awaiting_proof(message: Message) -> bool:
    """True only when the user has a pending order that has no proof yet."""
    order = await db.get_pending_order(message.from_user.id)
    return bool(order and not order["proof_file_id"])


@router.message(F.photo, _awaiting_proof)
async def receive_proof(message: Message, bot: Bot):
    order = await db.get_pending_order(message.from_user.id)
    if not order:
        return
    file_id = message.photo[-1].file_id
    await db.attach_proof(order["id"], file_id)
    await message.answer(ui.proof_received(), reply_markup=ui.back_menu())

    # Heads-up to admins (approval itself happens in the dashboard).
    uname = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    note = (
        f"🔔 <b>Order baru #{order['id']}</b>\n\n"
        f"👤 {uname} (<code>{message.from_user.id}</code>)\n"
        f"💎 Paket: <b>{order['plan_name']}</b>\n"
        f"💰 {ui.rupiah(order['amount'])}\n"
        f"💳 {order['method_name']}\n\n"
        f"📸 Bukti terlampir. Buka dashboard untuk verifikasi ✅"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(admin_id, file_id, caption=note)
        except Exception:
            pass
