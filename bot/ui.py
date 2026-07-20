"""Centralized UI: message templates + inline keyboards for production image generator bot."""
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ALLOWED_SIZES, REQUIRED_CHANNEL, ALLOWED_BATCHES, ASPECT_MAP
from i18n import t
import styles as style_presets

BRAND = "Image Generator"

# Size label map production — 7 sizes
SIZE_LABELS = {
    "1024x1024": "1:1 Square",
    "1024x1792": "9:16 Story",
    "1792x1024": "16:9 Wide",
    "1024x1536": "2:3 Portrait",
    "1536x1024": "3:2 Landscape",
    "1152x1536": "3:4 Potret",
    "1536x1152": "4:3 Lanskap",
}
# Emoji icons for aspect
SIZE_ICONS = {
    "1024x1024": "⬜",
    "1024x1792": "📱",
    "1792x1024": "🖥️",
    "1024x1536": "🧍",
    "1536x1024": "🏞️",
    "1152x1536": "📷",
    "1536x1152": "🖼️",
}

def quota_bar(used: int, limit: int, slots: int = 10) -> str:
    if limit == 0:
        return "♾️ Unlimited"
    if limit < 0:
        return "▱" * slots
    filled = min(slots, round(used / limit * slots))
    return "▰" * filled + "▱" * (slots - filled)

def rupiah(n: int) -> str:
    return "Rp" + f"{int(n):,}".replace(",", ".")

def sisa_text(used: int, limit: int, lang: str = "id") -> str:
    if limit == 0:
        return t("quota_unlimited", lang)
    return t("quota_images", lang, n=max(0, limit - used))

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

def main_menu(lang: str = "id"):
    kb = InlineKeyboardBuilder()
    kb.button(text=t("menu_gen", lang), callback_data="menu:gen")
    kb.button(text=t("menu_model", lang) if t("menu_model", lang) != "menu_model" else "🤖 Model", callback_data="menu:model")
    kb.button(text=t("menu_edit", lang), callback_data="menu:edit")
    kb.button(text=t("menu_style", lang), callback_data="menu:style")
    kb.button(text=t("menu_myworks", lang), callback_data="myworks:0")
    kb.button(text=t("menu_checkin", lang), callback_data="menu:checkin")
    kb.button(text=t("menu_sticker", lang), callback_data="menu:sticker")
    kb.button(text=t("menu_size", lang), callback_data="menu:size")
    kb.button(text=t("menu_batch", lang) if t("menu_batch", lang) != "menu_batch" else "🔢 Jumlah", callback_data="menu:batch")
    kb.button(text=t("menu_adv", lang) if t("menu_adv", lang) != "menu_adv" else "⚙️ Advanced", callback_data="menu:adv")
    kb.button(text=t("menu_quota", lang), callback_data="menu:quota")
    kb.button(text=t("menu_balance", lang), callback_data="menu:balance")
    kb.button(text=t("menu_upgrade", lang), callback_data="menu:upgrade")
    kb.button(text=t("menu_referral", lang), callback_data="menu:referral")
    kb.button(text=t("menu_lang", lang), callback_data="menu:lang")
    kb.button(text=t("menu_help", lang), callback_data="menu:help")
    kb.adjust(2, 2, 2, 2, 2, 2, 3)
    return kb.as_markup()

def back_menu(lang: str = "id"):
    kb = InlineKeyboardBuilder()
    kb.button(text=t("back_home", lang), callback_data="menu:home")
    return kb.as_markup()

def gen_prompt_menu(lang: str = "id", enhance_on: bool = False):
    from aiogram.types import ForceReply
    return ForceReply(input_field_placeholder=t("gen_placeholder", lang) if t("gen_placeholder", lang) != "gen_placeholder" else "...")

def size_menu(current: str, lang: str = "id"):
    kb = InlineKeyboardBuilder()
    for s in ALLOWED_SIZES:
        icon = SIZE_ICONS.get(s, "🖼️")
        label = SIZE_LABELS.get(s, s)
        # human readable aspect
        aspect = ""
        for k, v in ASPECT_MAP.items():
            if v == s:
                aspect = k
                break
        mark = "✅ " if s == current else ""
        kb.button(text=f"{mark}{icon} {aspect} {s}", callback_data=f"size:{s}")
    kb.button(text=t("back_home", lang), callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()

def batch_menu(current: int, lang: str = "id"):
    kb = InlineKeyboardBuilder()
    for b in ALLOWED_BATCHES:
        mark = "✅ " if b == current else ""
        kb.button(text=f"{mark}🔢 {b} gambar" if lang=="id" else f"{mark}🔢 {b} images", callback_data=f"batch:{b}")
    kb.button(text=t("back_home", lang), callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()

def adv_menu(lang: str = "id", has_negative: bool = False, has_seed: bool = False, has_ref: bool = False):
    kb = InlineKeyboardBuilder()
    neg_label = (t("adv_neg_set", lang, val="ON") if has_negative else t("adv_neg", lang)) if t("adv_neg", lang)!="adv_neg" else ("🚫 Neg: ON" if has_negative else "🚫 Negative Prompt")
    seed_label = (t("adv_seed_set", lang) if has_seed else t("adv_seed", lang)) if t("adv_seed", lang)!="adv_seed" else ("🎲 Seed: ON" if has_seed else "🎲 Seed")
    ref_label = (t("adv_ref_set", lang) if has_ref else t("adv_ref", lang)) if t("adv_ref", lang)!="adv_ref" else ("🖼️ Ref: ON" if has_ref else "🖼️ Reference Photo")
    kb.button(text=neg_label, callback_data="adv:neg")
    kb.button(text=seed_label, callback_data="adv:seed")
    kb.button(text=ref_label, callback_data="adv:ref")
    kb.button(text=t("adv_clear", lang) if t("adv_clear", lang)!="adv_clear" else "🗑️ Clear Advanced", callback_data="adv:clear")
    kb.button(text=t("back_home", lang), callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()

def result_menu(lang: str = "id", gen_id: int | None = None, file_id: str | None = None):
    kb = InlineKeyboardBuilder()
    if gen_id:
        kb.button(text=t("result_regen", lang), callback_data=f"regen:{gen_id}")
        kb.button(text=t("result_var", lang), callback_data=f"var:{gen_id}")
        kb.button(text=t("result_enhance", lang), callback_data=f"enhance:{gen_id}")
        kb.button(text=t("result_edit_this", lang), callback_data=f"editthis:{gen_id}")
        kb.button(text=t("result_hd", lang), callback_data=f"hd:{gen_id}")
        kb.button(text=t("result_sticker", lang), callback_data=f"sticker:add:{gen_id}")
        kb.button(text=t("result_batch", lang), callback_data=f"batchgen:{gen_id}:4")
        kb.button(text=t("result_style", lang), callback_data="menu:style")
        kb.button(text=t("result_menu", lang), callback_data="menu:home")
        kb.adjust(3, 3, 3)
    else:
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

def lang_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="🇮🇩 Indonesia", callback_data="lang:id")
    kb.button(text="🇬🇧 English", callback_data="lang:en")
    kb.adjust(2)
    return kb.as_markup()

def style_menu(current: str | None, lang: str = "id", dynamic_styles: list[dict] | None = None):
    """TODO: migrate fully to DB custom_styles. If dynamic_styles provided, use it (from db.get_custom_styles).
    Fallback to hardcoded STYLES dict for offline/resilience.
    """
    kb = InlineKeyboardBuilder()
    if dynamic_styles:
        for s in dynamic_styles:
            code = s.get("code", "")
            name = s.get("name", code)
            mark = "✓ " if code == current else ""
            kb.button(text=f"{mark}{name}", callback_data=f"style:{code}")
    else:
        for sid, info in style_presets.STYLES.items():
            mark = "✓ " if sid == current else ""
            label = info["label_id"] if lang == "id" else info["label_en"]
            kb.button(text=f"{mark}{info['emoji']} {label}", callback_data=f"style:{sid}")
    kb.button(text=t("back_home", lang), callback_data="menu:home")
    kb.adjust(2)
    return kb.as_markup()

def myworks_menu(generations: list[dict], total: int, offset: int, limit: int, lang: str = "id"):
    kb = InlineKeyboardBuilder()
    for g in generations:
        preview = (g.get("prompt") or "")[:28].replace("\n", " ")
        if len((g.get("prompt") or "")) > 28:
            preview += "..."
        # show batch indicator if part of batch
        bmark = "🎲 " if g.get("batch_id") else ""
        kb.button(text=f"{bmark}🖼️ #{g['id']} {preview}", callback_data=f"view:{g['id']}")
    has_prev = offset > 0
    has_next = offset + limit < total
    if has_prev:
        kb.button(text=t("myworks_prev", lang), callback_data=f"myworks:{max(0, offset-limit)}")
    if has_next:
        kb.button(text=t("myworks_next", lang), callback_data=f"myworks:{offset+limit}")
    kb.button(text=t("back_home", lang), callback_data="menu:home")
    if generations:
        if has_prev or has_next:
            kb.adjust(*([1]*len(generations) + [2 if (has_prev and has_next) else 1, 1]))
        else:
            kb.adjust(*([1]*len(generations) + [1]))
    else:
        kb.adjust(1)
    return kb.as_markup()

def myworks_view_menu(gen_id: int, lang: str = "id"):
    kb = InlineKeyboardBuilder()
    kb.button(text=t("result_regen", lang), callback_data=f"regen:{gen_id}")
    kb.button(text=t("result_var", lang), callback_data=f"var:{gen_id}")
    kb.button(text=t("result_enhance", lang), callback_data=f"enhance:{gen_id}")
    kb.button(text=t("result_edit_this", lang), callback_data=f"editthis:{gen_id}")
    kb.button(text=t("result_sticker", lang), callback_data=f"sticker:add:{gen_id}")
    kb.button(text=t("back", lang), callback_data="myworks:0")
    kb.button(text=t("back_home", lang), callback_data="menu:home")
    kb.adjust(3, 2, 2)
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
        kb.button(text=f"💎 {p['name']} — {rupiah(p['price'])} ({limit})", callback_data=f"plan:{p['id']}")
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
    base = t("order_rejected", lang) if t("order_rejected", lang) != "order_rejected" else (
        "❌ <b>Pembayaran ditolak</b>\n\nMaaf, pembayaranmu tidak dapat diverifikasi." if lang == "id"
        else "❌ <b>Payment rejected</b>\n\nSorry, your payment could not be verified.")
    if note:
        label = "📝 Catatan admin" if lang == "id" else "📝 Admin note"
        base += f"\n\n{label}: <i>{note}</i>"
    tail = "\n\nSilakan coba lagi atau hubungi admin ya 🙏" if lang == "id" else "\n\nPlease try again or contact admin 🙏"
    return base + tail

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
        lines.append(t("deposit_history_item", lang, icon=icon.get(d["status"], "•"), id=d["id"], amount=rupiah(d["amount"]), status=t(status_key.get(d["status"], "status_pending"), lang)))
    return "\n".join(lines)

def referral_text(bot_username: str, user_id: int, stats: dict, reward_type: str, reward_amount: int, lang: str = "id") -> str:
    link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    reward_desc = (t("referral_reward_balance", lang, amount=rupiah(reward_amount)) if reward_type == "balance" else t("referral_reward_quota", lang, n=reward_amount))
    return t("referral_text", lang, link=link, reward_desc=reward_desc, total=stats["total"], rewarded=stats["rewarded"], pending=stats["pending"], bonus_quota=stats["bonus_quota"])

def referral_menu(lang: str = "id"):
    kb = InlineKeyboardBuilder()
    kb.button(text=t("back_home", lang), callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()

def checkin_menu(lang: str = "id", can: bool = True):
    kb = InlineKeyboardBuilder()
    if can:
        kb.button(text=t("checkin_button", lang), callback_data="checkin:do")
    kb.button(text=t("back_home", lang), callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()

def model_menu(models: list[dict], current_id: str | None, lang: str = "id"):
    kb = InlineKeyboardBuilder()
    for m in models:
        mid = m.get("id") or m.get("model_id") or ""
        try:
            from model_display import format_model_label
            display = format_model_label(m.get("provider_id",""), m.get("external_id") or mid, m.get("display_name"))
        except Exception:
            display = m.get("display_name") or m.get("external_id") or mid
        prefix = "[x] " if mid == current_id else ""
        label = f"{prefix}{display}"
        if len(label) > 44:
            label = label[:41] + "..."
        kb.button(text=label, callback_data=f"model:{mid}")
    kb.button(text=t("back_home", lang), callback_data="menu:home")
    kb.adjust(2)
    return kb.as_markup()

# ---------------- Sticker ----------------
def sticker_menu(packs: list[dict], lang: str = "id", can_create: bool = True):
    kb = InlineKeyboardBuilder()
    for p in packs:
        kb.button(text=f"{p['pack_name']} ({p.get('sticker_count',0)})", callback_data=f"sticker:view:{p['pack_name']}")
    kb.button(text=t("back_home", lang), callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()
