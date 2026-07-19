"""Minimal i18n layer: id (default) + en. Auto-detected from Telegram language_code,
stored per-user in DB, and switchable anytime from the menu.

Usage:
    from i18n import t
    t("welcome", lang, name="Budi")
"""

TEXTS: dict[str, dict[str, str]] = {
    "id": {
        # ---- generic ----
        "back_home": "◀️ Menu Utama",
        "back": "◀️ Kembali",
        "cancel": "❌ Batal",
        "saved": "Tersimpan ✓",
        "maintenance": "🛠️ <b>Bot sedang maintenance</b>\nCoba lagi beberapa saat ya.",
        "invalid_data": "Data tidak valid",

        # ---- welcome / menu ----
        "welcome": (
            "✨ <b>Halo, {name}!</b>\n\n"
            "Selamat datang di <b>{brand}</b> — bikin & edit gambar pakai AI langsung dari Telegram.\n\n"
            "🎨 <b>Buat Gambar</b> — ketik ide, jadi gambar\n"
            "🖌️ <b>Edit Foto</b> — kirim foto + instruksi\n"
            "📐 <b>Ukuran</b> — atur rasio gambar\n"
            "📊 <b>Kuota</b> — cek sisa pemakaian harian\n"
            "💰 <b>Saldo</b> — top up buat beli premium\n\n"
            "Pilih menu di bawah untuk mulai 👇"
        ),
        "menu_gen": "🎨 Buat Gambar",
        "menu_edit": "🖌️ Edit Foto",
        "menu_size": "📐 Ukuran",
        "menu_quota": "📊 Kuota",
        "menu_upgrade": "💎 Upgrade Premium",
        "menu_balance": "💰 Saldo Saya",
        "menu_help": "❓ Bantuan",
        "menu_lang": "🌐 Bahasa",

        "help": (
            "❓ <b>Panduan Pemakaian</b>\n\n"
            "🎨 <b>Buat gambar dari teks</b>\n"
            "Tekan <b>Buat Gambar</b> lalu ketik prompt, atau langsung:\n"
            "<code>/generate kucing astronot di bulan</code>\n\n"
            "🖌️ <b>Edit / ubah foto</b>\n"
            "Kirim sebuah <b>foto</b> disertai <b>caption</b> instruksi.\n"
            "Contoh caption: <i>ganti background jadi pantai senja</i>\n\n"
            "📐 <b>Ukuran</b> — pilih rasio: persegi, potret, atau lanskap\n"
            "📊 <b>Kuota</b> — lihat sisa jatah harianmu\n"
            "💰 <b>Saldo</b> — top up saldo buat beli paket premium instan\n\n"
            "💡 <b>Tips:</b> makin detail prompt, makin bagus hasilnya!"
        ),

        "prompt_ask": (
            "🎨 <b>Buat Gambar</b>\n\n"
            "Ketik deskripsi gambar yang kamu mau (balas pesan ini):\n"
            "<i>contoh: robot lucu main skateboard, gaya 3D render</i>"
        ),
        "edit_ask": (
            "🖌️ <b>Edit Foto</b>\n\n"
            "Kirim <b>foto</b> yang mau diedit, sertakan <b>caption</b> berisi instruksi.\n"
            "<i>contoh caption: jadikan gaya lukisan cat air</i>"
        ),
        "size_pick": "📐 <b>Pilih Ukuran Gambar</b>",
        "size_set": "✅ Ukuran diset ke <b>{size}</b>",
        "size_saved": "Ukuran tersimpan ✓",
        "size_square": "⬜ Persegi (1:1)",
        "size_portrait": "📱 Potret (2:3)",
        "size_landscape": "🖥️ Lanskap (3:2)",

        # ---- quota ----
        "quota_title": "📊 <b>Kuota Harian</b>\n",
        "quota_status_premium": "👑 <b>Status:</b> Premium — {plan}\n⏳ Aktif s/d <b>{until}</b>\n",
        "quota_status_free": "🆓 <b>Status:</b> Free\n",
        "quota_used": "Terpakai <b>{used}</b> dari <b>{total}</b>",
        "quota_left": "Sisa: <b>{left}</b>\n",
        "quota_reset": "🔄 Kuota reset otomatis tiap hari.",
        "quota_upsell": "\n💎 Mau kuota lebih banyak? Tekan <b>Upgrade Premium</b>!",
        "quota_unlimited": "♾️ tanpa batas",
        "quota_images": "{n} gambar",
        "quota_exhausted": "🚫 <b>Kuota harian habis</b> ({used}/{limit})\n{bar}\n\nReset otomatis besok 🔄",

        # ---- generate/edit results ----
        "generating": "🎨 <b>Membuat gambar...</b>\n⏳ Mohon tunggu sebentar ({used}/{limit})",
        "editing": "🖌️ <b>Mengedit gambar...</b>\n⏳ Mohon tunggu sebentar ({used}/{limit})",
        "gen_done": "✅ <b>Gambar selesai!</b>\n\n📝 <i>{prompt}</i>\n📐 {size}  ·  📊 Sisa {left}",
        "edit_done": "✅ <b>Edit selesai!</b>\n\n📝 <i>{prompt}</i>\n📐 {size}  ·  📊 Sisa {left}",
        "gen_failed": "❌ <b>Gagal membuat gambar</b>\n<code>{err}</code>",
        "edit_failed": "❌ <b>Gagal mengedit gambar</b>\n<code>{err}</code>",
        "result_again": "🔄 Buat Lagi",
        "result_menu": "◀️ Menu",

        # ---- subscription gate ----
        "join_channel": "📢 Join Channel",
        "already_joined": "✅ Sudah Join",
        "join_success": "✅ <b>Berhasil!</b> Kamu sudah join. Selamat berkreasi 🎨",
        "join_not_detected": "Belum terdeteksi join {channel}. Coba lagi.",

        # ---- premium ----
        "upgrade_no_plans": "💎 <b>Upgrade Premium</b>\n\nMaaf, saat ini belum ada paket yang tersedia. Coba lagi nanti ya 🙏",
        "upgrade_intro": "💎 <b>Upgrade ke Premium</b>\n\nDapatkan <b>kuota lebih banyak</b> setiap hari!\nBayar instan pakai <b>Saldo</b> 👇",
        "plan_unavailable": "Paket tidak tersedia",
        "plan_unlimited": "Unlimited",
        "plan_per_day": "{n}/hari",
        "plan_detail": (
            "💎 <b>Paket {name}</b>\n\n"
            "💰 Harga: <b>{price}</b>\n"
            "📊 Kuota: <b>{limit}</b>\n"
            "⏳ Masa aktif: <b>{days} hari</b>"
        ),
        "plan_detail_desc": "\n📝 {desc}",
        "plan_balance_line": "\n💰 Saldo kamu: <b>{balance}</b>",
        "plan_buy_button": "💳 Beli dengan Saldo ({price})",
        "plan_insufficient": "Saldo tidak cukup",
        "plan_topup_needed": (
            "⚠️ <b>Saldo tidak cukup</b>\n\n"
            "Saldo kamu: <b>{balance}</b>\nHarga paket: <b>{price}</b>\nKurang: <b>{diff}</b>\n\n"
            "Silakan top up saldo dulu ya."
        ),
        "plan_topup_button": "💰 Top Up Saldo",
        "plan_bought": "🎉 Paket berhasil dibeli!",
        "premium_activated": (
            "🎉 <b>Selamat! Premium kamu aktif!</b>\n\n"
            "💎 Paket: <b>{plan}</b>\n"
            "📊 Kuota: <b>{limit}</b>\n"
            "⏳ Berlaku s/d: <b>{until}</b>\n"
            "💰 Sisa saldo: <b>{balance}</b>\n\n"
            "Terima kasih sudah upgrade! Selamat berkreasi 🎨"
        ),

        # ---- balance / deposit ----
        "balance_title": "💰 <b>Saldo Saya</b>\n\nSaldo kamu saat ini:\n<b>{balance}</b>",
        "balance_topup_button": "➕ Top Up Saldo",
        "balance_history_button": "🧾 Riwayat Deposit",
        "deposit_disabled": "💰 <b>Top Up Saldo</b>\n\nFitur top up saldo sedang tidak tersedia. Coba lagi nanti ya 🙏",
        "deposit_pick_amount": (
            "💰 <b>Top Up Saldo</b>\n\n"
            "Pilih nominal top up (min {min}, maks {max}):"
        ),
        "deposit_custom_button": "✏️ Nominal Lain",
        "deposit_custom_ask": "✏️ Ketik nominal top up yang kamu mau (angka saja, min {min}, maks {max}):",
        "deposit_custom_invalid": "❌ Nominal tidak valid. Ketik angka saja, contoh: 50000",
        "deposit_custom_range": "❌ Nominal harus antara {min} dan {max}.",
        "deposit_pick_method": "💰 <b>Top Up {amount}</b>\n\nPilih metode pembayaran 👇",
        "deposit_info": (
            "🧾 <b>Deposit #{id}</b>\n\n"
            "💰 Nominal: <b>{amount}</b>\n\n"
            "{method_label} — <b>{method_name}</b>"
        ),
        "deposit_account_number": "📌 Nomor/ID: <code>{v}</code>",
        "deposit_account_name": "👤 Atas nama: <b>{v}</b>",
        "deposit_instructions": "\nℹ️ {v}",
        "deposit_after": (
            "\n📸 <b>Setelah transfer</b>, kirim <b>foto bukti pembayaran</b> ke chat ini.\n"
            "Admin akan verifikasi & saldo masuk otomatis setelah disetujui ✅"
        ),
        "deposit_cancel_button": "❌ Batalkan Deposit",
        "deposit_cancelled": "❌ Deposit dibatalkan.",
        "deposit_proof_received": (
            "✅ <b>Bukti top up diterima!</b>\n\n"
            "Depositmu sedang <b>diverifikasi admin</b>. Kamu akan dapat notifikasi begitu disetujui 🔔\n\n"
            "Biasanya diproses dalam beberapa menit s/d jam kerja."
        ),
        "deposit_approved": (
            "🎉 <b>Top up berhasil!</b>\n\n"
            "💰 Nominal: <b>{amount}</b>\n"
            "💳 Saldo sekarang: <b>{balance}</b>\n\n"
            "Terima kasih! 🙏"
        ),
        "deposit_rejected": "❌ <b>Deposit ditolak</b>\n\nMaaf, top up tidak dapat diverifikasi.",
        "deposit_history_empty": "🧾 <b>Riwayat Deposit</b>\n\nBelum ada riwayat deposit.",
        "deposit_history_item": "{icon} #{id} — {amount} — {status}",
        "status_pending": "menunggu",
        "status_approved": "disetujui",
        "status_rejected": "ditolak",

        # ---- language ----
        "lang_pick": "🌐 <b>Pilih Bahasa / Choose Language</b>",
        "lang_id": "🇮🇩 Indonesia",
        "lang_en": "🇬🇧 English",
        "lang_set": "✅ Bahasa diubah ke <b>Indonesia</b>",

        # ---- admin heads-up ----
        "order_note": (
            "🔔 <b>Order baru #{id}</b>\n\n"
            "👤 {uname} (<code>{uid}</code>)\n"
            "💎 Paket: <b>{plan}</b>\n"
            "💰 {amount}\n"
            "💳 {method}\n\n"
            "📸 Bukti terlampir. Buka dashboard untuk verifikasi ✅"
        ),
        "deposit_note": (
            "🔔 <b>Deposit baru #{id}</b>\n\n"
            "👤 {uname} (<code>{uid}</code>)\n"
            "💰 Nominal: <b>{amount}</b>\n"
            "💳 {method}\n\n"
            "📸 Bukti terlampir. Buka dashboard untuk verifikasi ✅"
        ),
    },
    "en": {
        "back_home": "◀️ Main Menu",
        "back": "◀️ Back",
        "cancel": "❌ Cancel",
        "saved": "Saved ✓",
        "maintenance": "🛠️ <b>Bot is under maintenance</b>\nPlease try again shortly.",
        "invalid_data": "Invalid data",

        "welcome": (
            "✨ <b>Hi, {name}!</b>\n\n"
            "Welcome to <b>{brand}</b> — create & edit images with AI right from Telegram.\n\n"
            "🎨 <b>Generate Image</b> — type an idea, get an image\n"
            "🖌️ <b>Edit Photo</b> — send a photo + instructions\n"
            "📐 <b>Size</b> — set the image aspect ratio\n"
            "📊 <b>Quota</b> — check your daily usage\n"
            "💰 <b>Balance</b> — top up to buy premium\n\n"
            "Pick a menu below to get started 👇"
        ),
        "menu_gen": "🎨 Generate Image",
        "menu_edit": "🖌️ Edit Photo",
        "menu_size": "📐 Size",
        "menu_quota": "📊 Quota",
        "menu_upgrade": "💎 Upgrade Premium",
        "menu_balance": "💰 My Balance",
        "menu_help": "❓ Help",
        "menu_lang": "🌐 Language",

        "help": (
            "❓ <b>How to Use</b>\n\n"
            "🎨 <b>Generate image from text</b>\n"
            "Tap <b>Generate Image</b> then type a prompt, or directly:\n"
            "<code>/generate an astronaut cat on the moon</code>\n\n"
            "🖌️ <b>Edit / modify a photo</b>\n"
            "Send a <b>photo</b> with a <b>caption</b> as instruction.\n"
            "Example caption: <i>change background to a sunset beach</i>\n\n"
            "📐 <b>Size</b> — choose ratio: square, portrait, or landscape\n"
            "📊 <b>Quota</b> — check your remaining daily allowance\n"
            "💰 <b>Balance</b> — top up to buy premium plans instantly\n\n"
            "💡 <b>Tip:</b> the more detailed your prompt, the better the result!"
        ),

        "prompt_ask": (
            "🎨 <b>Generate Image</b>\n\n"
            "Type a description of the image you want (reply to this message):\n"
            "<i>example: a cute robot skateboarding, 3D render style</i>"
        ),
        "edit_ask": (
            "🖌️ <b>Edit Photo</b>\n\n"
            "Send the <b>photo</b> you want to edit, with a <b>caption</b> containing your instructions.\n"
            "<i>example caption: turn it into a watercolor painting</i>"
        ),
        "size_pick": "📐 <b>Choose Image Size</b>",
        "size_set": "✅ Size set to <b>{size}</b>",
        "size_saved": "Size saved ✓",
        "size_square": "⬜ Square (1:1)",
        "size_portrait": "📱 Portrait (2:3)",
        "size_landscape": "🖥️ Landscape (3:2)",

        "quota_title": "📊 <b>Daily Quota</b>\n",
        "quota_status_premium": "👑 <b>Status:</b> Premium — {plan}\n⏳ Active until <b>{until}</b>\n",
        "quota_status_free": "🆓 <b>Status:</b> Free\n",
        "quota_used": "Used <b>{used}</b> of <b>{total}</b>",
        "quota_left": "Left: <b>{left}</b>\n",
        "quota_reset": "🔄 Quota resets automatically every day.",
        "quota_upsell": "\n💎 Want more quota? Tap <b>Upgrade Premium</b>!",
        "quota_unlimited": "♾️ unlimited",
        "quota_images": "{n} images",
        "quota_exhausted": "🚫 <b>Daily quota reached</b> ({used}/{limit})\n{bar}\n\nResets automatically tomorrow 🔄",

        "generating": "🎨 <b>Generating image...</b>\n⏳ Please wait a moment ({used}/{limit})",
        "editing": "🖌️ <b>Editing image...</b>\n⏳ Please wait a moment ({used}/{limit})",
        "gen_done": "✅ <b>Image done!</b>\n\n📝 <i>{prompt}</i>\n📐 {size}  ·  📊 Left {left}",
        "edit_done": "✅ <b>Edit done!</b>\n\n📝 <i>{prompt}</i>\n📐 {size}  ·  📊 Left {left}",
        "gen_failed": "❌ <b>Failed to generate image</b>\n<code>{err}</code>",
        "edit_failed": "❌ <b>Failed to edit image</b>\n<code>{err}</code>",
        "result_again": "🔄 Generate Again",
        "result_menu": "◀️ Menu",

        "join_channel": "📢 Join Channel",
        "already_joined": "✅ Already Joined",
        "join_success": "✅ <b>Success!</b> You've joined. Happy creating 🎨",
        "join_not_detected": "Couldn't detect you joining {channel}. Try again.",

        "upgrade_no_plans": "💎 <b>Upgrade Premium</b>\n\nSorry, no plans are available right now. Please check back later 🙏",
        "upgrade_intro": "💎 <b>Upgrade to Premium</b>\n\nGet <b>more daily quota</b>!\nPay instantly with <b>Balance</b> 👇",
        "plan_unavailable": "Plan unavailable",
        "plan_unlimited": "Unlimited",
        "plan_per_day": "{n}/day",
        "plan_detail": (
            "💎 <b>{name} Plan</b>\n\n"
            "💰 Price: <b>{price}</b>\n"
            "📊 Quota: <b>{limit}</b>\n"
            "⏳ Duration: <b>{days} days</b>"
        ),
        "plan_detail_desc": "\n📝 {desc}",
        "plan_balance_line": "\n💰 Your balance: <b>{balance}</b>",
        "plan_buy_button": "💳 Buy with Balance ({price})",
        "plan_insufficient": "Insufficient balance",
        "plan_topup_needed": (
            "⚠️ <b>Insufficient balance</b>\n\n"
            "Your balance: <b>{balance}</b>\nPlan price: <b>{price}</b>\nShortfall: <b>{diff}</b>\n\n"
            "Please top up your balance first."
        ),
        "plan_topup_button": "💰 Top Up Balance",
        "plan_bought": "🎉 Plan purchased!",
        "premium_activated": (
            "🎉 <b>Congrats! Your Premium is active!</b>\n\n"
            "💎 Plan: <b>{plan}</b>\n"
            "📊 Quota: <b>{limit}</b>\n"
            "⏳ Valid until: <b>{until}</b>\n"
            "💰 Remaining balance: <b>{balance}</b>\n\n"
            "Thanks for upgrading! Happy creating 🎨"
        ),

        "balance_title": "💰 <b>My Balance</b>\n\nYour current balance:\n<b>{balance}</b>",
        "balance_topup_button": "➕ Top Up Balance",
        "balance_history_button": "🧾 Deposit History",
        "deposit_disabled": "💰 <b>Top Up Balance</b>\n\nTop-up is currently unavailable. Please check back later 🙏",
        "deposit_pick_amount": (
            "💰 <b>Top Up Balance</b>\n\n"
            "Choose an amount (min {min}, max {max}):"
        ),
        "deposit_custom_button": "✏️ Custom Amount",
        "deposit_custom_ask": "✏️ Type the top-up amount you want (numbers only, min {min}, max {max}):",
        "deposit_custom_invalid": "❌ Invalid amount. Type numbers only, e.g. 50000",
        "deposit_custom_range": "❌ Amount must be between {min} and {max}.",
        "deposit_pick_method": "💰 <b>Top Up {amount}</b>\n\nChoose a payment method 👇",
        "deposit_info": (
            "🧾 <b>Deposit #{id}</b>\n\n"
            "💰 Amount: <b>{amount}</b>\n\n"
            "{method_label} — <b>{method_name}</b>"
        ),
        "deposit_account_number": "📌 Number/ID: <code>{v}</code>",
        "deposit_account_name": "👤 Account name: <b>{v}</b>",
        "deposit_instructions": "\nℹ️ {v}",
        "deposit_after": (
            "\n📸 <b>After transferring</b>, send a <b>photo of your payment proof</b> to this chat.\n"
            "Admin will verify & your balance will be topped up automatically once approved ✅"
        ),
        "deposit_cancel_button": "❌ Cancel Deposit",
        "deposit_cancelled": "❌ Deposit cancelled.",
        "deposit_proof_received": (
            "✅ <b>Top-up proof received!</b>\n\n"
            "Your deposit is being <b>reviewed by admin</b>. You'll be notified once approved 🔔\n\n"
            "Usually processed within a few minutes to a few working hours."
        ),
        "deposit_approved": (
            "🎉 <b>Top-up successful!</b>\n\n"
            "💰 Amount: <b>{amount}</b>\n"
            "💳 Current balance: <b>{balance}</b>\n\n"
            "Thank you! 🙏"
        ),
        "deposit_rejected": "❌ <b>Deposit rejected</b>\n\nSorry, we couldn't verify your top-up.",
        "deposit_history_empty": "🧾 <b>Deposit History</b>\n\nNo deposit history yet.",
        "deposit_history_item": "{icon} #{id} — {amount} — {status}",
        "status_pending": "pending",
        "status_approved": "approved",
        "status_rejected": "rejected",

        "lang_pick": "🌐 <b>Choose Language / Pilih Bahasa</b>",
        "lang_id": "🇮🇩 Indonesia",
        "lang_en": "🇬🇧 English",
        "lang_set": "✅ Language switched to <b>English</b>",

        "order_note": (
            "🔔 <b>New order #{id}</b>\n\n"
            "👤 {uname} (<code>{uid}</code>)\n"
            "💎 Plan: <b>{plan}</b>\n"
            "💰 {amount}\n"
            "💳 {method}\n\n"
            "📸 Proof attached. Open the dashboard to verify ✅"
        ),
        "deposit_note": (
            "🔔 <b>New deposit #{id}</b>\n\n"
            "👤 {uname} (<code>{uid}</code>)\n"
            "💰 Amount: <b>{amount}</b>\n"
            "💳 {method}\n\n"
            "📸 Proof attached. Open the dashboard to verify ✅"
        ),
    },
}


def t(key: str, lang: str = "id", **kwargs) -> str:
    lang = lang if lang in TEXTS else "id"
    template = TEXTS[lang].get(key) or TEXTS["id"].get(key) or key
    return template.format(**kwargs) if kwargs else template
