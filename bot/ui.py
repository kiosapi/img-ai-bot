"""Centralized UI: message templates + inline keyboards for a modern bot look.
All user-facing text goes through i18n.t(key, lang, **kwargs) for id/en support.
"""
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ALLOWED_SIZES, REQUIRED_CHANNEL
from i18n import t

BRAND = "Image Generator"


def quota_bar(used: int, limit: int, slots: int = 10) -> str:
    """Render a visual progress bar like ▰▰▰▱▱▱▱▱▱▱. limit 0 = unlimited."""
    if limit == 0:
        return "♾️ Unlimited"
    if limit < 0:
        return "▱" * slots
    filled = min(slots, round(used / limit * slots))
    return "▰" * filled + "▱" * (slots - filled)


def rupiah(n: int) -> str:
    return "Rp" + f"{int(n):,}".replace(",", ".")


def sisa_text(used: int, limit: int, lang: str = "id") -> str:
    """Human 'remaining' phrase, unlimited-aware."""
    if limit == 0:
        return t("quota_unlimited", lang)
    return t("quota_images", lang, n=max(0, limit - used))


# ---------------- Text templates ----------------
def welcome(name: str, lang: str = "id") -> str:
    return t("welcome", lang, name=name, brand=BRAND)


def help_text(lang: str = "id") -> str:
    return t("help", lang)


def quota_text(used: int, limit: int, premium: dict | None = None, lang: str = "id", bonus_quota: int = 0) -> str:
    bar = quota_bar(used, limit)
    left = sisa_text(used, limit, lang)
    lines = [t("quota_title", lang)]
    if premium:
        exp = premium["premium_until"].strftime("%d %b %Y")
        lines.append(t("quota_status_premium", lang, plan=premium["plan_name"], until=exp))
    else:
        lines.append(t("quota_status_free", lang))
    lines.append(bar)
    total = "♾️" if limit == 0 else str(limit)
    lines.append(t("quota_used", lang, used=used, total=total))
    lines.append(t("quota_left", lang, left=left))
    if bonus_quota > 0:
        lines.append(t("quota_bonus", lang, n=bonus_quota))
    lines.append(t("quota_reset", lang))
    if not premium:
        lines.append(t("quota_upsell", lang))
    return "\n".join(lines)


def prompt_ask(lang: str = "id") -> str:
    return t("prompt_ask", lang)


def edit_ask(lang: str = "id") -> str:
    return t("edit_ask", lang)


# ---------------- Keyboards ----------------
def main_menu(lang: str = "id"):
    kb = InlineKeyboardBuilder()
    kb.button(text=t("menu_gen", lang), callback_data="menu:gen")
    kb.button(text=t("menu_edit", lang), callback_data="menu:edit")
    kb.button(text=t("menu_size", lang), callback_data="menu:size")
    kb.button(text=t("menu_quota", lang), callback_data="menu:quota")
    kb.button(text=t("menu_balance", lang), callback_data="menu:balance")
    kb.button(text=t("menu_upgrade", lang), callback_data="menu:upgrade")
    kb.button(text=t("menu_referral", lang), callback_data="menu:referral")
    kb.button(text=t("menu_lang", lang), callback_data="menu:lang")
    kb.button(text=t("menu_help", lang), callback_data="menu:help")
    kb.adjust(2, 2, 2, 1, 1, 1)
    return kb.as_markup()


def back_menu(lang: str = "id"):
    kb = InlineKeyboardBuilder()
    kb.button(text=t("back_home", lang), callback_data="menu:home")
    return kb.as_markup()


def size_menu(current: str, lang: str = "id"):
    labels = {
        "1024x1024": t("size_square", lang),
        "1024x1536": t("size_portrait", lang),
        "1536x1024": t("size_landscape", lang),
    }
    kb = InlineKeyboardBuilder()
    for s in ALLOWED_SIZES:
        mark = "✓ " if s == current else ""
        kb.button(text=f"{mark}{labels.get(s, s)}", callback_data=f"size:{s}")
    kb.button(text=t("back_home", lang), callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()


def result_menu(lang: str = "id"):
    kb = InlineKeyboardBuilder()
    kb.button(text=t("result_again", lang), callback_data="menu:gen")
    kb.button(text=t("result_menu", lang), callback_data="menu:home")
    kb.adjust(2)
    return kb.as_markup()


def join_keyboard(lang: str = "id"):
    kb = InlineKeyboardBuilder()
    ch = REQUIRED_CHANNEL.lstrip("@")
    kb.button(text=t("join_channel", lang), url=f"https://t.me/{ch}")
    kb.button(text=t("already_joined", lang), callback_data="check_sub")
    kb.adjust(1)
    return kb.as_markup()


# ---------------- Language ----------------
def lang_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="🇮🇩 Indonesia", callback_data="lang:id")
    kb.button(text="🇬🇧 English", callback_data="lang:en")
    kb.adjust(2)
    return kb.as_markup()


# ---------------- Premium / Upgrade UI ----------------
def upgrade_intro(has_plans: bool, lang: str = "id") -> str:
    if not has_plans:
        return t("upgrade_no_plans", lang)
    return t("upgrade_intro", lang)


def plans_menu(plans: list[dict], lang: str = "id"):
    kb = InlineKeyboardBuilder()
    for p in plans:
        limit = t("plan_unlimited", lang) if p["daily_limit"] == 0 else t("plan_per_day", lang, n=p["daily_limit"])
        kb.button(
            text=f"💎 {p['name']} — {rupiah(p['price'])} ({limit})",
            callback_data=f"plan:{p['id']}")
    kb.button(text=t("back_home", lang), callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()


def plan_detail(p: dict, balance: int, lang: str = "id") -> str:
    limit = t("plan_unlimited", lang) if p["daily_limit"] == 0 else t("plan_per_day", lang, n=p["daily_limit"])
    text = t("plan_detail", lang, name=p["name"], price=rupiah(p["price"]), limit=limit, days=p["duration_days"])
    if p.get("description"):
        text += t("plan_detail_desc", lang, desc=p["description"])
    text += t("plan_balance_line", lang, balance=rupiah(balance))
    return text


def plan_buy_menu(plan: dict, lang: str = "id"):
    kb = InlineKeyboardBuilder()
    kb.button(text=t("plan_buy_button", lang, price=rupiah(plan["price"])), callback_data=f"buyplan:{plan['id']}")
    kb.button(text=t("back", lang), callback_data="menu:upgrade")
    kb.adjust(1)
    return kb.as_markup()


def plan_topup_needed(balance: int, price: int, lang: str = "id") -> str:
    return t("plan_topup_needed", lang, balance=rupiah(balance), price=rupiah(price), diff=rupiah(price - balance))


def plan_topup_menu(lang: str = "id"):
    kb = InlineKeyboardBuilder()
    kb.button(text=t("plan_topup_button", lang), callback_data="menu:balance")
    kb.button(text=t("back", lang), callback_data="menu:upgrade")
    kb.adjust(1)
    return kb.as_markup()


def premium_activated(plan_name: str, until, limit: int, balance: int, lang: str = "id") -> str:
    lim = t("plan_unlimited", lang) if limit == 0 else t("plan_per_day", lang, n=limit).replace("/hari", " gambar/hari").replace("/day", " images/day")
    return t("premium_activated", lang, plan=plan_name, limit=lim, until=until.strftime("%d %b %Y"), balance=rupiah(balance))


def order_rejected(note: str | None, lang: str = "id") -> str:
    base = t("deposit_rejected", lang) if False else (
        "❌ <b>Pembayaran ditolak</b>\n\nMaaf, pembayaranmu tidak dapat diverifikasi." if lang == "id"
        else "❌ <b>Payment rejected</b>\n\nSorry, your payment could not be verified.")
    if note:
        label = "📝 Catatan admin" if lang == "id" else "📝 Admin note"
        base += f"\n\n{label}: <i>{note}</i>"
    tail = "\n\nSilakan coba lagi atau hubungi admin ya 🙏" if lang == "id" else "\n\nPlease try again or contact admin 🙏"
    return base + tail


# ---------------- Balance / Deposit UI ----------------
def balance_menu(lang: str = "id"):
    kb = InlineKeyboardBuilder()
    kb.button(text=t("balance_topup_button", lang), callback_data="deposit:new")
    kb.button(text=t("balance_history_button", lang), callback_data="deposit:history")
    kb.button(text=t("back_home", lang), callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()


def balance_text(balance: int, lang: str = "id") -> str:
    return t("balance_title", lang, balance=rupiah(balance))


def deposit_amount_menu(quick_amounts: list[int], lang: str = "id"):
    kb = InlineKeyboardBuilder()
    for a in quick_amounts:
        kb.button(text=rupiah(a), callback_data=f"depamt:{a}")
    kb.button(text=t("deposit_custom_button", lang), callback_data="depamt:custom")
    kb.button(text=t("back_home", lang), callback_data="menu:home")
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()


def deposit_methods_menu(methods: list[dict], amount: int, lang: str = "id"):
    type_icon = {"bank": "🏦", "ewallet": "📱", "qris": "🔳", "other": "💳"}
    kb = InlineKeyboardBuilder()
    for m in methods:
        icon = type_icon.get(m["type"], "💳")
        kb.button(text=f"{icon} {m['name']}", callback_data=f"depmethod:{amount}:{m['id']}")
    kb.button(text=t("back", lang), callback_data="menu:balance")
    kb.adjust(1)
    return kb.as_markup()


def deposit_info(deposit_id: int, amount: int, method: dict, lang: str = "id") -> str:
    type_label_id = {"bank": "Transfer Bank", "ewallet": "E-Wallet", "qris": "QRIS", "other": "Pembayaran"}
    type_label_en = {"bank": "Bank Transfer", "ewallet": "E-Wallet", "qris": "QRIS", "other": "Payment"}
    label = (type_label_id if lang == "id" else type_label_en).get(method["type"], "Payment")
    text = t("deposit_info", lang, id=deposit_id, amount=rupiah(amount), method_label=label, method_name=method["name"])
    if method.get("account_number"):
        text += "\n" + t("deposit_account_number", lang, v=method["account_number"])
    if method.get("account_name"):
        text += "\n" + t("deposit_account_name", lang, v=method["account_name"])
    if method.get("instructions"):
        text += t("deposit_instructions", lang, v=method["instructions"])
    text += t("deposit_after", lang)
    return text


def deposit_cancel_menu(lang: str = "id"):
    kb = InlineKeyboardBuilder()
    kb.button(text=t("deposit_cancel_button", lang), callback_data="deposit:cancel")
    kb.button(text=t("back_home", lang), callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()


def deposit_history_text(deposits: list[dict], lang: str = "id") -> str:
    if not deposits:
        return t("deposit_history_empty", lang)
    icon = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
    status_key = {"pending": "status_pending", "approved": "status_approved", "rejected": "status_rejected"}
    lines = [t("deposit_history_empty", lang).split("\n\n")[0] + "\n"]
    for d in deposits:
        lines.append(t(
            "deposit_history_item", lang,
            icon=icon.get(d["status"], "•"), id=d["id"], amount=rupiah(d["amount"]),
            status=t(status_key.get(d["status"], "status_pending"), lang)))
    return "\n".join(lines)


# ---------------- Referral UI ----------------
def referral_text(bot_username: str, user_id: int, stats: dict, reward_type: str, reward_amount: int, lang: str = "id") -> str:
    link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    reward_desc = (
        (t("referral_reward_balance", lang, amount=rupiah(reward_amount)) if reward_type == "balance"
         else t("referral_reward_quota", lang, n=reward_amount))
    )
    return t(
        "referral_text", lang,
        link=link, reward_desc=reward_desc,
        total=stats["total"], rewarded=stats["rewarded"], pending=stats["pending"],
        bonus_quota=stats["bonus_quota"],
    )


def referral_menu(lang: str = "id"):
    kb = InlineKeyboardBuilder()
    kb.button(text=t("back_home", lang), callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()
