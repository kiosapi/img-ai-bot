"""Centralized UI: message templates + inline keyboards for a modern bot look."""
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ALLOWED_SIZES, REQUIRED_CHANNEL

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


def sisa_text(used: int, limit: int) -> str:
    """Human 'remaining' phrase, unlimited-aware."""
    if limit == 0:
        return "♾️ tanpa batas"
    return f"{max(0, limit - used)} gambar"


# ---------------- Text templates ----------------
def welcome(name: str) -> str:
    return (
        f"✨ <b>Halo, {name}!</b>\n\n"
        f"Selamat datang di <b>{BRAND}</b> — bikin & edit gambar pakai AI langsung dari Telegram.\n\n"
        "🎨 <b>Buat Gambar</b> — ketik ide, jadi gambar\n"
        "🖌️ <b>Edit Foto</b> — kirim foto + instruksi\n"
        "📐 <b>Ukuran</b> — atur rasio gambar\n"
        "📊 <b>Kuota</b> — cek sisa pemakaian harian\n\n"
        "Pilih menu di bawah untuk mulai 👇"
    )


HELP = (
    "❓ <b>Panduan Pemakaian</b>\n\n"
    "🎨 <b>Buat gambar dari teks</b>\n"
    "Tekan <b>Buat Gambar</b> lalu ketik prompt, atau langsung:\n"
    "<code>/generate kucing astronot di bulan</code>\n\n"
    "🖌️ <b>Edit / ubah foto</b>\n"
    "Kirim sebuah <b>foto</b> disertai <b>caption</b> instruksi.\n"
    "Contoh caption: <i>ganti background jadi pantai senja</i>\n\n"
    "📐 <b>Ukuran</b> — pilih rasio: persegi, potret, atau lanskap\n"
    "📊 <b>Kuota</b> — lihat sisa jatah harianmu\n\n"
    "💡 <b>Tips:</b> makin detail prompt, makin bagus hasilnya!"
)


def quota_text(used: int, limit: int, premium: dict | None = None) -> str:
    bar = quota_bar(used, limit)
    left = sisa_text(used, limit)
    lines = ["📊 <b>Kuota Harian</b>\n"]
    if premium:
        exp = premium["premium_until"].strftime("%d %b %Y")
        lines.append(f"👑 <b>Status:</b> Premium — {premium['plan_name']}\n⏳ Aktif s/d <b>{exp}</b>\n")
    else:
        lines.append("🆓 <b>Status:</b> Free\n")
    lines.append(f"{bar}")
    total = "♾️" if limit == 0 else str(limit)
    lines.append(f"Terpakai <b>{used}</b> dari <b>{total}</b>")
    lines.append(f"Sisa: <b>{left}</b>\n")
    lines.append("🔄 Kuota reset otomatis tiap hari.")
    if not premium:
        lines.append("\n💎 Mau kuota lebih banyak? Tekan <b>Upgrade Premium</b>!")
    return "\n".join(lines)


def prompt_ask() -> str:
    return (
        "🎨 <b>Buat Gambar</b>\n\n"
        "Ketik deskripsi gambar yang kamu mau (balas pesan ini):\n"
        "<i>contoh: robot lucu main skateboard, gaya 3D render</i>"
    )


def edit_ask() -> str:
    return (
        "🖌️ <b>Edit Foto</b>\n\n"
        "Kirim <b>foto</b> yang mau diedit, sertakan <b>caption</b> berisi instruksi.\n"
        "<i>contoh caption: jadikan gaya lukisan cat air</i>"
    )


# ---------------- Keyboards ----------------
def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="🎨 Buat Gambar", callback_data="menu:gen")
    kb.button(text="🖌️ Edit Foto", callback_data="menu:edit")
    kb.button(text="📐 Ukuran", callback_data="menu:size")
    kb.button(text="📊 Kuota", callback_data="menu:quota")
    kb.button(text="💎 Upgrade Premium", callback_data="menu:upgrade")
    kb.button(text="❓ Bantuan", callback_data="menu:help")
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()


def back_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Menu Utama", callback_data="menu:home")
    return kb.as_markup()


def size_menu(current: str):
    labels = {
        "1024x1024": "⬜ Persegi (1:1)",
        "1024x1536": "📱 Potret (2:3)",
        "1536x1024": "🖥️ Lanskap (3:2)",
    }
    kb = InlineKeyboardBuilder()
    for s in ALLOWED_SIZES:
        mark = "✓ " if s == current else ""
        kb.button(text=f"{mark}{labels.get(s, s)}", callback_data=f"size:{s}")
    kb.button(text="◀️ Menu Utama", callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()


def result_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Buat Lagi", callback_data="menu:gen")
    kb.button(text="◀️ Menu", callback_data="menu:home")
    kb.adjust(2)
    return kb.as_markup()


def join_keyboard():
    kb = InlineKeyboardBuilder()
    ch = REQUIRED_CHANNEL.lstrip("@")
    kb.button(text="📢 Join Channel", url=f"https://t.me/{ch}")
    kb.button(text="✅ Sudah Join", callback_data="check_sub")
    kb.adjust(1)
    return kb.as_markup()

# ---------------- Premium / Upgrade UI ----------------
def upgrade_intro(has_plans: bool) -> str:
    if not has_plans:
        return (
            "💎 <b>Upgrade Premium</b>\n\n"
            "Maaf, saat ini belum ada paket yang tersedia. "
            "Coba lagi nanti ya 🙏"
        )
    return (
        "💎 <b>Upgrade ke Premium</b>\n\n"
        "Dapatkan <b>kuota lebih banyak</b> setiap hari!\n"
        "Pilih paket yang kamu mau di bawah 👇"
    )


def plans_menu(plans: list[dict]):
    kb = InlineKeyboardBuilder()
    for p in plans:
        limit = "Unlimited" if p["daily_limit"] == 0 else f"{p['daily_limit']}/hari"
        kb.button(
            text=f"💎 {p['name']} — {rupiah(p['price'])} ({limit})",
            callback_data=f"plan:{p['id']}")
    kb.button(text="◀️ Menu Utama", callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()


def plan_detail(p: dict) -> str:
    limit = "♾️ Unlimited" if p["daily_limit"] == 0 else f"{p['daily_limit']} gambar/hari"
    lines = [
        f"💎 <b>Paket {p['name']}</b>\n",
        f"💰 Harga: <b>{rupiah(p['price'])}</b>",
        f"📊 Kuota: <b>{limit}</b>",
        f"⏳ Masa aktif: <b>{p['duration_days']} hari</b>",
    ]
    if p.get("description"):
        lines.append(f"\n📝 {p['description']}")
    lines.append("\nPilih metode pembayaran 👇")
    return "\n".join(lines)


def methods_menu(methods: list[dict], plan_id: int):
    type_icon = {"bank": "🏦", "ewallet": "📱", "qris": "🔳", "other": "💳"}
    kb = InlineKeyboardBuilder()
    for m in methods:
        icon = type_icon.get(m["type"], "💳")
        kb.button(text=f"{icon} {m['name']}", callback_data=f"pay:{plan_id}:{m['id']}")
    kb.button(text="◀️ Kembali", callback_data="menu:upgrade")
    kb.adjust(1)
    return kb.as_markup()


def payment_info(plan: dict, method: dict, order_id: int) -> str:
    type_label = {"bank": "Transfer Bank", "ewallet": "E-Wallet", "qris": "QRIS", "other": "Pembayaran"}
    lines = [
        f"🧾 <b>Order #{order_id}</b>\n",
        f"💎 Paket: <b>{plan['name']}</b>",
        f"💰 Total bayar: <b>{rupiah(plan['price'])}</b>\n",
        f"{type_label.get(method['type'], 'Pembayaran')} — <b>{method['name']}</b>",
    ]
    if method.get("account_number"):
        lines.append(f"📌 Nomor/ID: <code>{method['account_number']}</code>")
    if method.get("account_name"):
        lines.append(f"👤 Atas nama: <b>{method['account_name']}</b>")
    if method.get("instructions"):
        lines.append(f"\nℹ️ {method['instructions']}")
    lines.append(
        "\n📸 <b>Setelah transfer</b>, kirim <b>foto bukti pembayaran</b> ke chat ini.\n"
        "Admin akan verifikasi & premium aktif otomatis setelah disetujui ✅"
    )
    return "\n".join(lines)


def cancel_order_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Batalkan Order", callback_data="order:cancel")
    kb.button(text="◀️ Menu Utama", callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()


def proof_received() -> str:
    return (
        "✅ <b>Bukti pembayaran diterima!</b>\n\n"
        "Pesananmu sedang <b>diverifikasi admin</b>. "
        "Kamu akan dapat notifikasi begitu disetujui 🔔\n\n"
        "Biasanya diproses dalam beberapa menit s/d jam kerja."
    )


def premium_activated(plan_name: str, until, limit: int) -> str:
    lim = "♾️ Unlimited" if limit == 0 else f"{limit} gambar/hari"
    return (
        "🎉 <b>Selamat! Premium kamu aktif!</b>\n\n"
        f"💎 Paket: <b>{plan_name}</b>\n"
        f"📊 Kuota: <b>{lim}</b>\n"
        f"⏳ Berlaku s/d: <b>{until.strftime('%d %b %Y')}</b>\n\n"
        "Terima kasih sudah upgrade! Selamat berkreasi 🎨"
    )


def order_rejected(note: str | None) -> str:
    base = (
        "❌ <b>Pembayaran ditolak</b>\n\n"
        "Maaf, pembayaranmu tidak dapat diverifikasi."
    )
    if note:
        base += f"\n\n📝 Catatan admin: <i>{note}</i>"
    base += "\n\nSilakan coba lagi atau hubungi admin ya 🙏"
    return base
