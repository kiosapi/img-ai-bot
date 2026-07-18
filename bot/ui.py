"""Centralized UI: message templates + inline keyboards for a modern bot look."""
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ALLOWED_SIZES, REQUIRED_CHANNEL

BRAND = "Image Generator"


def quota_bar(used: int, limit: int, slots: int = 10) -> str:
    """Render a visual progress bar like ▰▰▰▱▱▱▱▱▱▱."""
    if limit <= 0:
        return "▱" * slots
    filled = min(slots, round(used / limit * slots))
    return "▰" * filled + "▱" * (slots - filled)


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


def quota_text(used: int, limit: int) -> str:
    left = max(0, limit - used)
    bar = quota_bar(used, limit)
    return (
        "📊 <b>Kuota Harian</b>\n\n"
        f"{bar}\n"
        f"Terpakai <b>{used}</b> dari <b>{limit}</b>\n"
        f"Sisa: <b>{left}</b> gambar\n\n"
        "🔄 Kuota reset otomatis tiap hari."
    )


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
    kb.button(text="❓ Bantuan", callback_data="menu:help")
    kb.adjust(2, 2, 1)
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
