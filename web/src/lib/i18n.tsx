"use client";
import React, { createContext, useContext, useEffect, useState } from "react";

type Lang = "id" | "en";
type Dict = Record<string, { id: string; en: string }>;

const TRANSLATIONS: Dict = {
  // Shell nav
  "nav.general": { id: "Umum", en: "General" },
  "nav.dashboard": { id: "Dashboard", en: "Dashboard" },
  "nav.analytics": { id: "Analytics", en: "Analytics" },
  "nav.users": { id: "User", en: "Users" },
  "nav.broadcast": { id: "Broadcast", en: "Broadcast" },
  "nav.referral": { id: "Referral", en: "Referral" },
  "nav.models": { id: "Models & Provider", en: "Models & Provider" },
  "nav.errors": { id: "Error", en: "Errors" },
  "nav.logs": { id: "Live Logs", en: "Live Logs" },
  "nav.system": { id: "System", en: "System" },
  "nav.health": { id: "Bot Health", en: "Bot Health" },
  "nav.settings": { id: "Setting", en: "Settings" },
  "nav.audit": { id: "Audit Log", en: "Audit Log" },
  "nav.premium": { id: "Premium", en: "Premium" },
  "nav.orders": { id: "Pesanan", en: "Orders" },
  "nav.plans": { id: "Paket", en: "Plans" },
  "nav.payments": { id: "Pembayaran", en: "Payments" },
  "nav.balance": { id: "Saldo", en: "Balance" },
  "nav.deposits": { id: "Deposit", en: "Deposits" },
  "nav.balance_settings": { id: "Pengaturan Saldo", en: "Balance Settings" },
  "nav.logout": { id: "Keluar", en: "Logout" },
  "nav.light": { id: "Light Mode", en: "Light Mode" },
  "nav.dark": { id: "Dark Mode", en: "Dark Mode" },

  // Dashboard home
  "dash.title": { id: "Dashboard", en: "Dashboard" },
  "dash.sub": { id: "Ringkasan aktivitas bot", en: "Bot activity summary" },
  "dash.total_users": { id: "Total User", en: "Total Users" },
  "dash.today_gens": { id: "Gambar Hari Ini", en: "Images Today" },
  "dash.active_today": { id: "User Aktif", en: "Active Users" },
  "dash.total_gens": { id: "Total Gambar", en: "Total Images" },
  "dash.chart_7d": { id: "Aktivitas 7 Hari", en: "Last 7 Days Activity" },
  "dash.recent_activity": { id: "Aktivitas Terbaru", en: "Recent Activity" },
  "dash.no_activity": { id: "Belum ada aktivitas", en: "No activity yet" },

  // Analytics
  "analytics.title": { id: "Analytics", en: "Analytics" },
  "analytics.sub": { id: "Wawasan mendalam aktivitas bot", en: "In-depth bot activity insights" },
  "analytics.busy_hours": { id: "Jam Sibuk (30 hari)", en: "Busy Hours (30 days)" },
  "analytics.success_rate": { id: "Success Rate (14 hari)", en: "Success Rate (14 days)" },
  "analytics.activity_type": { id: "Jenis Aktivitas", en: "Activity Type" },
  "analytics.top_prompts": { id: "Prompt Terpopuler", en: "Top Prompts" },
  "analytics.top_users": { id: "User Teraktif", en: "Most Active Users" },
  "analytics.no_data": { id: "Belum ada data", en: "No data yet" },
  "analytics.hour_label": { id: "Jam {h}:00", en: "{h}:00" },
  "analytics.images": { id: "Gambar", en: "Images" },

  // Users
  "users.title": { id: "Kelola User", en: "Manage Users" },
  "users.count": { id: "{n} user ditampilkan - data real-time dari bot", en: "{n} users shown - real-time from bot" },
  "users.search_ph": { id: "Cari username / ID / nama...", en: "Search username / ID / name..." },
  "users.empty": { id: "Tidak ada user - bot belum menerima start dari user lain", en: "No users - bot hasn't received /start from others yet" },
  "users.banned": { id: "banned", en: "banned" },
  "users.ban": { id: "Ban", en: "Ban" },
  "users.unban": { id: "Unban", en: "Unban" },
  "users.detail": { id: "Detail", en: "Detail" },
  "users.images": { id: "{n} gambar", en: "{n} images" },
  "users.hint": { id: "Jika daftar hanya 1 padahal link di-share: cek channel gate REQUIRED_CHANNEL. Bot middleware sekarang fail-open jadi user tetap tercatat walaupun get_chat_member error di channel private.", en: "If only 1 user appears: check REQUIRED_CHANNEL gate. Middleware fail-open so users are recorded even if get_chat_member fails." },
  "users.total_images": { id: "Total Gambar", en: "Total Images" },
  "users.balance": { id: "Saldo Akun", en: "Account Balance" },
  "users.balance_history": { id: "Riwayat", en: "History" },
  "users.add_balance": { id: "Tambah Saldo", en: "Add Balance" },
  "users.deduct_balance": { id: "Kurangi Saldo", en: "Deduct Balance" },
  "users.gen_history": { id: "Riwayat Generate", en: "Generation History" },
  "users.user_not_found": { id: "User tidak ditemukan", en: "User not found" },
  "users.amount": { id: "Nominal", en: "Amount" },
  "users.note": { id: "Catatan", en: "Note" },
  "users.note_ph": { id: "mis. Kompensasi gangguan bot", en: "e.g. Compensation for downtime" },
  "users.saving": { id: "Menyimpan...", en: "Saving..." },
  "users.balance_changed": { id: "Saldo berhasil {mode}", en: "Balance {mode} successfully" },
  "users.balance_history_title": { id: "Riwayat Perubahan Saldo", en: "Balance Change History" },

  // Broadcast
  "bc.title": { id: "Broadcast", en: "Broadcast" },
  "bc.sub": { id: "Kirim pesan ke user bot — bisa dengan gambar & tombol (opsional)", en: "Send message to bot users — can include image & button (optional)" },
  "bc.audience": { id: "Target Audience", en: "Target Audience" },
  "bc.all": { id: "Semua User", en: "All Users" },
  "bc.premium": { id: "Premium Aktif", en: "Active Premium" },
  "bc.free": { id: "Free (non-premium)", en: "Free" },
  "bc.new_msg": { id: "Pesan Baru", en: "New Message" },
  "bc.placeholder": { id: "Tulis pesan... (mendukung HTML: <b>, <i>, <a>). Jika pakai gambar, teks ini jadi caption.", en: "Write message... (supports HTML: <b>, <i>, <a>). If image set, text becomes caption." },
  "bc.image": { id: "Gambar (opsional)", en: "Image (optional)" },
  "bc.pick_image": { id: "Pilih Gambar", en: "Pick Image" },
  "bc.uploading": { id: "Mengupload...", en: "Uploading..." },
  "bc.remove_image": { id: "Hapus gambar", en: "Remove image" },
  "bc.button": { id: "Tombol Menu + URL (opsional)", en: "Menu Button + URL (optional)" },
  "bc.preview": { id: "Preview", en: "Preview" },
  "bc.send": { id: "Kirim ke {audience}", en: "Send to {audience}" },
  "bc.sending": { id: "Mengirim...", en: "Sending..." },
  "bc.history": { id: "Riwayat Broadcast", en: "Broadcast History" },
  "bc.info": { id: "Info", en: "Info" },
  "bc.info_text": { id: "Pesan dikirim ke user pada audience terpilih yang tidak dibanned. Upload gambar sekarang silent (disable_notification + auto-delete).", en: "Message sent to selected audience. Image upload is now silent (disable_notification + auto-delete)." },
  "bc.confirm_title": { id: "Kirim Broadcast", en: "Send Broadcast" },
  "bc.confirm_yes": { id: "Ya, Kirim", en: "Yes, Send" },
  "bc.confirm_desc": { id: "Pesan {img}akan dikirim ke {count} user pada target {audience}. Aksi ini tidak bisa dibatalkan setelah dikirim.", en: "Message {img}will be sent to {count} users in {audience}. Cannot be undone." },
  "bc.only_image": { id: "(hanya gambar)", en: "(image only)" },

  // Errors
  "errors.title": { id: "Log Error", en: "Error Log" },
  "errors.sub": { id: "Generate yang gagal", en: "Failed generations" },
  "errors.total_failed": { id: "Total Gagal", en: "Total Failed" },
  "errors.failed_today": { id: "Gagal Hari Ini", en: "Failed Today" },
  "errors.failure_list": { id: "Daftar Kegagalan", en: "Failure List" },
  "errors.no_errors": { id: "Tidak ada error — semua generate berhasil!", en: "No errors — all generations succeeded!" },
  "errors.export_csv": { id: "Export Data (CSV)", en: "Export Data (CSV)" },
  "errors.export_users": { id: "Export User", en: "Export Users" },
  "errors.export_gens": { id: "Export Generasi", en: "Export Generations" },
  "errors.no_prompt": { id: "tanpa prompt", en: "no prompt" },
  "errors.count_suffix": { id: "({n})", en: "({n})" },

  // Settings
  "settings.title": { id: "Pengaturan & Fitur", en: "Settings & Features" },
  "settings.sub": { id: "Kelola bot tanpa ubah code - toggle instant, berlaku langsung", en: "Manage bot without code — instant toggle" },
  "settings.limit_maintenance": { id: "Limit & Maintenance", en: "Limit & Maintenance" },
  "settings.daily_limit": { id: "Limit Harian per User", en: "Daily Limit per User" },
  "settings.maint_mode": { id: "Mode Maintenance", en: "Maintenance Mode" },
  "settings.maint_desc": { id: "Blokir semua user (kecuali admin) - butuh global middleware", en: "Block all users except admin" },
  "settings.save_limit": { id: "Simpan Limit & Maintenance", en: "Save Limit & Maintenance" },
  "settings.saving": { id: "Menyimpan...", en: "Saving..." },
  "settings.saved": { id: "Pengaturan disimpan", en: "Settings saved" },
  "settings.feature_control": { id: "Kontrol Fitur Lengkap (Tanpa Code)", en: "Full Feature Control (No Code)" },
  "settings.save_features": { id: "Simpan Semua Fitur (Instant)", en: "Save All Features (Instant)" },
  "settings.features_saved": { id: "Fitur disimpan - berlaku instant tanpa restart", en: "Features saved — instant, no restart" },
  "settings.failed": { id: "Gagal menyimpan", en: "Failed to save" },
  "settings.info": { id: "Info", en: "Info" },
  "settings.channel_required": { id: "Channel Wajib", en: "Required Channel" },
  "settings.model": { id: "Model", en: "Model" },
  "settings.core_features": { id: "Fitur Inti", en: "Core Features" },
  "settings.other_features": { id: "Fitur Lain", en: "Other Features" },
  "settings.feat_note": { id: "Semua toggle berlaku instant tanpa restart bot. Bot baca settings dari DB tiap request via feature_flags.", en: "All toggles apply instantly. Bot reads settings from DB each request." },

  // Feature defs
  "feat.enhance": { id: "Prompt Enhance", en: "Prompt Enhance" },
  "feat.enhance_desc": { id: "Tombol enhance prompt via LLM (fitur 10)", en: "Enhance prompt button via LLM (feature 10)" },
  "feat.enhance_model": { id: "Model Enhance", en: "Enhance Model" },
  "feat.enhance_model_desc": { id: "Model OpenAI-compatible untuk enhance (default gpt-4o-mini)", en: "OpenAI-compatible model for enhance (default gpt-4o-mini)" },
  "feat.batch": { id: "Batch Generate", en: "Batch Generate" },
  "feat.batch_desc": { id: "Generate multiple variasi sekaligus (fitur 14)", en: "Generate multiple variations at once (feature 14)" },
  "feat.batch_limit_free": { id: "Batch Limit Free", en: "Batch Limit Free" },
  "feat.batch_limit_free_desc": { id: "Max batch untuk user free", en: "Max batch for free users" },
  "feat.batch_limit_premium": { id: "Batch Limit Premium", en: "Batch Limit Premium" },
  "feat.batch_limit_premium_desc": { id: "Max batch untuk premium", en: "Max batch for premium" },
  "feat.watermark": { id: "Watermark", en: "Watermark" },
  "feat.watermark_desc": { id: "Tambah watermark text ke caption + overlay gambar (fitur 15) modern @imgaai_bot pill", en: "Add watermark text overlay (feature 15) modern @imgaai_bot pill" },
  "feat.watermark_text": { id: "Watermark Text", en: "Watermark Text" },
  "feat.watermark_text_desc": { id: "Text watermark (sekarang hanya @imgaai_bot, icon dihapus, font premium)", en: "Watermark text (now only @imgaai_bot, no icon, premium font)" },
  "feat.watermark_free_only": { id: "Watermark Free Only", en: "Watermark Free Only" },
  "feat.watermark_free_only_desc": { id: "ON = premium bebas watermark, OFF = semua kena watermark", en: "ON = premium free of watermark, OFF = all get watermark" },
  "feat.sticker": { id: "Sticker Pack", en: "Sticker Pack" },
  "feat.sticker_desc": { id: "Buat sticker Telegram dari karya (fitur 17)", en: "Create Telegram stickers from works (feature 17)" },
  "feat.sticker_max": { id: "Sticker Max per Pack", en: "Sticker Max per Pack" },
  "feat.sticker_max_desc": { id: "Maks sticker per pack", en: "Max stickers per pack" },
  "feat.checkin": { id: "Daily Check-in", en: "Daily Check-in" },
  "feat.checkin_desc": { id: "Check-in harian streak (fitur 6)", en: "Daily streak check-in (feature 6)" },
  "feat.inline": { id: "Inline Mode", en: "Inline Mode" },
  "feat.inline_desc": { id: "Gallery inline @bot (fitur 7)", en: "Inline gallery @bot (feature 7)" },
  "feat.myworks": { id: "My Works / History", en: "My Works / History" },
  "feat.myworks_desc": { id: "History karya user (fitur 2)", en: "User works history (feature 2)" },
  "feat.style": { id: "Style Presets", en: "Style Presets" },
  "feat.style_desc": { id: "Preset gaya visual (fitur 3)", en: "Visual style presets (feature 3)" },
  "feat.queue": { id: "Anti-Spam Queue", en: "Anti-Spam Queue" },
  "feat.queue_desc": { id: "Batas 1 job per user (fitur 9)", en: "Limit 1 job per user (feature 9)" },

  // Models
  "models.title": { id: "Models and Providers", en: "Models and Providers" },
  "models.sub": { id: "Kelola API keys 4 provider (CB/RC/AF/UN). User hanya lihat display name + short code.", en: "Manage 4 provider API keys (CB/RC/AF/UN). Users see only display name + short code." },
  "models.api_keys": { id: "API Keys Management (4 Providers)", en: "API Keys Management (4 Providers)" },
  "models.new_key": { id: "API Key baru", en: "New API Key" },
  "models.base_url": { id: "Base URL (editable)", en: "Base URL (editable)" },
  "models.save_key": { id: "Simpan Key and URL", en: "Save Key and URL" },
  "models.providers": { id: "Providers", en: "Providers" },
  "models.add_manual": { id: "Tambah Model Manual", en: "Add Model Manually" },
  "models.model_id_ph": { id: "model id real, contoh gpt-image-2", en: "real model id, e.g. gpt-image-2" },
  "models.display_name_ph": { id: "Display name user-facing", en: "User-facing display name" },
  "models.provider": { id: "Provider", en: "Provider" },
  "models.desc_ph": { id: "Description optional", en: "Optional description" },
  "models.active": { id: "Aktif", en: "Active" },
  "models.create": { id: "Buat Model", en: "Create Model" },
  "models.list": { id: "Models List", en: "Models List" },
  "models.no_models": { id: "Belum ada model. Isi API key di atas lalu Sync, atau tambah manual.", en: "No models yet. Set API key above then Sync, or add manually." },
  "models.delete_title": { id: "Hapus Model", en: "Delete Model" },
  "models.delete_yes": { id: "Ya, Hapus", en: "Yes, Delete" },
  "models.delete_desc": { id: "Yakin mau hapus model {id}? Aksi ini tidak bisa dibatalkan.", en: "Are you sure to delete model {id}? Cannot be undone." },
  "models.sync": { id: "Sync", en: "Sync" },
  "models.toggle": { id: "Toggle", en: "Toggle" },
  "models.default_set": { id: "Default diatur", en: "Default set" },
  "models.loading": { id: "Memuat...", en: "Loading..." },

  // Plans
  "plans.title": { id: "Paket Premium", en: "Premium Plans" },
  "plans.sub": { id: "Kelola paket & harga upgrade", en: "Manage upgrade plans & pricing" },
  "plans.add": { id: "Tambah", en: "Add" },
  "plans.empty": { id: "Belum ada paket. Tekan Tambah.", en: "No plans yet. Click Add." },
  "plans.edit": { id: "Edit Paket", en: "Edit Plan" },
  "plans.add_title": { id: "Tambah Paket", en: "Add Plan" },
  "plans.name": { id: "Nama Paket", en: "Plan Name" },
  "plans.name_ph": { id: "Premium / VIP", en: "Premium / VIP" },
  "plans.price": { id: "Harga (Rp)", en: "Price (Rp)" },
  "plans.duration": { id: "Masa Aktif (hari)", en: "Duration (days)" },
  "plans.quota": { id: "Kuota Harian (0 = unlimited)", en: "Daily Quota (0 = unlimited)" },
  "plans.desc": { id: "Deskripsi (opsional)", en: "Description (optional)" },
  "plans.desc_ph": { id: "Keterangan singkat paket", en: "Short description" },
  "plans.active": { id: "Status Aktif", en: "Active Status" },
  "plans.save": { id: "Simpan", en: "Save" },
  "plans.saving": { id: "Menyimpan...", en: "Saving..." },
  "plans.quota_label": { id: "Kuota: {v}", en: "Quota: {v}" },
  "plans.unlimited": { id: "Unlimited", en: "Unlimited" },
  "plans.per_day": { id: "/hari", en: "/day" },
  "plans.active_days": { id: "Masa aktif: {n} hari", en: "Active: {n} days" },
  "plans.delete_title": { id: "Hapus Paket Premium", en: "Delete Premium Plan" },
  "plans.delete_desc": { id: "Yakin mau hapus paket \"{name}\"? Aksi ini tidak bisa dibatalkan.", en: "Delete plan \"{name}\"? Cannot be undone." },

  // Payments
  "payments.title": { id: "Metode Pembayaran", en: "Payment Methods" },
  "payments.sub": { id: "Kelola rekening & channel pembayaran", en: "Manage accounts & payment channels" },
  "payments.add": { id: "Tambah", en: "Add" },
  "payments.empty": { id: "Belum ada metode. Tekan Tambah.", en: "No methods yet. Click Add." },
  "payments.edit": { id: "Edit Metode", en: "Edit Method" },
  "payments.add_title": { id: "Tambah Metode", en: "Add Method" },
  "payments.type": { id: "Jenis", en: "Type" },
  "payments.type.bank": { id: "Bank Transfer", en: "Bank Transfer" },
  "payments.type.ewallet": { id: "E-Wallet", en: "E-Wallet" },
  "payments.type.qris": { id: "QRIS", en: "QRIS" },
  "payments.type.other": { id: "Lainnya", en: "Other" },
  "payments.name": { id: "Nama", en: "Name" },
  "payments.name_ph": { id: "BCA / DANA / QRIS", en: "BCA / DANA / QRIS" },
  "payments.number": { id: "Nomor / ID (rekening, no HP, dll)", en: "Number / ID" },
  "payments.holder": { id: "Atas Nama", en: "Holder Name" },
  "payments.holder_ph": { id: "Nama pemilik", en: "Holder name" },
  "payments.instructions": { id: "Instruksi Tambahan (opsional)", en: "Additional Instructions (optional)" },
  "payments.instructions_ph": { id: "Catatan buat user", en: "Note for user" },
  "payments.qr": { id: "QR Image file_id (opsional, dari Telegram)", en: "QR Image file_id (optional, from Telegram)" },
  "payments.active": { id: "Status Aktif", en: "Active Status" },
  "payments.save": { id: "Simpan", en: "Save" },
  "payments.saving": { id: "Menyimpan...", en: "Saving..." },
  "payments.qr_saved": { id: "QR image tersimpan", en: "QR image saved" },
  "payments.delete_title": { id: "Hapus Metode Pembayaran", en: "Delete Payment Method" },
  "payments.delete_desc": { id: "Yakin mau hapus metode \"{name}\"?", en: "Delete method \"{name}\"?" },

  // Orders
  "orders.title": { id: "Pesanan Premium", en: "Premium Orders" },
  "orders.sub": { id: "Verifikasi pembayaran & aktivasi", en: "Verify payments & activation" },
  "orders.active_premium": { id: "Premium Aktif", en: "Active Premium" },
  "orders.pending": { id: "Menunggu", en: "Pending" },
  "orders.approved": { id: "Disetujui", en: "Approved" },
  "orders.rejected": { id: "Ditolak", en: "Rejected" },
  "orders.approve": { id: "Setujui", en: "Approve" },
  "orders.reject": { id: "Tolak", en: "Reject" },
  "orders.proof": { id: "Bukti", en: "Proof" },
  "orders.no_proof": { id: "no bukti", en: "no proof" },
  "orders.empty": { id: "Tidak ada pesanan {status}.", en: "No {status} orders." },
  "orders.proof_title": { id: "Bukti Pembayaran", en: "Payment Proof" },
  "orders.open_new_tab": { id: "Buka di tab baru", en: "Open in new tab" },
  "orders.reject_title": { id: "Tolak Pembayaran", en: "Reject Payment" },
  "orders.reject_reason": { id: "Alasan penolakan (opsional, dikirim ke user):", en: "Rejection reason (optional, sent to user):" },
  "orders.reject_ph": { id: "mis. Nominal tidak sesuai / bukti tidak valid", en: "e.g. Amount mismatch / invalid proof" },
  "orders.cancel": { id: "Batal", en: "Cancel" },
  "orders.approve_title": { id: "Setujui Pembayaran", en: "Approve Payment" },
  "orders.approve_desc": { id: "Setujui pembayaran ini? Premium user akan langsung aktif dan mereka akan diberi tahu lewat bot.", en: "Approve this payment? Premium will activate instantly." },
  "orders.approve_yes": { id: "Ya, Setujui", en: "Yes, Approve" },
  "orders.total_approved": { id: "Total Approved", en: "Total Approved" },
  "orders.total_revenue": { id: "Total Pendapatan", en: "Total Revenue" },

  // Deposits
  "deposits.title": { id: "Deposit Saldo", en: "Balance Deposits" },
  "deposits.sub": { id: "Verifikasi top up saldo user", en: "Verify user balance top-ups" },
  "deposits.pending": { id: "Menunggu", en: "Pending" },
  "deposits.approved": { id: "Disetujui", en: "Approved" },
  "deposits.rejected": { id: "Ditolak", en: "Rejected" },
  "deposits.total_approved": { id: "Total Approved", en: "Total Approved" },
  "deposits.total_in": { id: "Total Masuk", en: "Total In" },
  "deposits.total_outstanding": { id: "Total Saldo Beredar", en: "Total Balance Outstanding" },
  "deposits.empty": { id: "Tidak ada deposit {status}.", en: "No {status} deposits." },

  // Referral
  "referral.title": { id: "Referral", en: "Referral" },
  "referral.sub": { id: "Kelola sistem ajak teman & bonusnya — semua bisa diubah tanpa sentuh kode", en: "Manage invite friends & bonuses — no code needed" },
  "referral.total": { id: "Total Referral", en: "Total Referrals" },
  "referral.rewarded": { id: "Sudah Dapat Bonus", en: "Rewarded" },
  "referral.pending": { id: "Menunggu Join Channel", en: "Waiting Join" },
  "referral.balance_paid": { id: "Total Saldo Terbagi", en: "Total Balance Shared" },
  "referral.settings": { id: "Pengaturan Bonus Referral", en: "Referral Bonus Settings" },
  "referral.enable": { id: "Aktifkan Sistem Referral", en: "Enable Referral System" },
  "referral.enable_desc": { id: "Jika nonaktif, link referral baru tidak akan dicatat lagi", en: "If disabled, new referral links won't be recorded" },
  "referral.bonus_type": { id: "Jenis Bonus untuk Pengundang (Referrer)", en: "Bonus Type for Referrer" },
  "referral.add_balance": { id: "Tambah Saldo", en: "Add Balance" },
  "referral.add_quota": { id: "Tambah Kuota Gambar", en: "Add Image Quota" },
  "referral.amount_balance": { id: "Nominal Saldo per Referral Berhasil", en: "Balance Amount per Successful Referral" },
  "referral.amount_quota": { id: "Jumlah Kuota Gambar per Referral Berhasil", en: "Image Quota per Successful Referral" },
  "referral.amount_balance_desc": { id: "Setiap referral berhasil (teman join channel), pengundang dapat {amount} saldo otomatis.", en: "Each successful referral (friend joins channel), referrer gets {amount} balance automatically." },
  "referral.amount_quota_desc": { id: "Setiap referral berhasil (teman join channel), pengundang dapat {amount} kuota gambar tambahan.", en: "Each successful referral, referrer gets {amount} extra image quota." },
  "referral.save": { id: "Simpan Pengaturan", en: "Save Settings" },
  "referral.saving": { id: "Menyimpan...", en: "Saving..." },
  "referral.saved": { id: "Pengaturan referral disimpan", en: "Referral settings saved" },
  "referral.top": { id: "Top Pengundang", en: "Top Referrers" },
  "referral.history": { id: "Riwayat Referral", en: "Referral History" },
  "referral.no_referral": { id: "Belum ada referral", en: "No referrals yet" },
  "referral.invited": { id: "mengundang", en: "invited" },
  "referral.success": { id: "berhasil", en: "success" },
  "referral.waiting": { id: "menunggu join", en: "waiting join" },
  "referral.bonus": { id: "Bonus: {v}", en: "Bonus: {v}" },
  "referral.how": { id: "Cara Kerja", en: "How it Works" },
  "referral.how1": { id: "Setiap user punya link referral unik (menu Ajak Teman di bot), format https://t.me/nama_bot?start=ref_ID.", en: "Each user has unique referral link (Invite Friends menu), format https://t.me/bot_name?start=ref_ID." },
  "referral.how2": { id: "Bonus ke pengundang dicairkan otomatis begitu teman yang diundang join channel wajib untuk pertama kali.", en: "Referrer bonus is auto-released when invited friend joins required channel first time." },
  "referral.how3": { id: "Jenis bonus bisa diatur di sini: saldo atau kuota gambar.", en: "Bonus type can be set here: balance or image quota." },

  // Balance settings
  "balance.title": { id: "Pengaturan Saldo", en: "Balance Settings" },
  "balance.sub": { id: "Kelola fitur deposit & top up saldo — semua bisa diubah di sini tanpa perlu ubah kode", en: "Manage deposit & top-up features — no code needed" },
  "balance.feature": { id: "Fitur Saldo", en: "Balance Feature" },
  "balance.enable_topup": { id: "Aktifkan Top Up Saldo", en: "Enable Top-Up" },
  "balance.enable_desc": { id: "Jika nonaktif, tombol top up di bot disembunyikan/nonaktif", en: "If disabled, top-up button hidden in bot" },
  "balance.min": { id: "Nominal Minimum", en: "Minimum Amount" },
  "balance.max": { id: "Nominal Maksimum", en: "Maximum Amount" },
  "balance.quick": { id: "Pilihan Nominal Cepat (quick amount) di bot", en: "Quick Amount Options in Bot" },
  "balance.quick_empty": { id: "Belum ada nominal cepat.", en: "No quick amounts yet." },
  "balance.add": { id: "Tambah", en: "Add" },
  "balance.save": { id: "Simpan Pengaturan", en: "Save Settings" },
  "balance.saving": { id: "Menyimpan...", en: "Saving..." },
  "balance.saved": { id: "Pengaturan saldo disimpan", en: "Balance settings saved" },
  "balance.how": { id: "Cara Kerja", en: "How it Works" },
  "balance.how1": { id: "User top up saldo lewat bot: pilih nominal (quick amount atau custom) → pilih metode pembayaran → upload bukti transfer.", en: "User tops up via bot: pick amount → payment method → upload proof." },
  "balance.how2": { id: "Admin verifikasi bukti di menu Deposit, saldo user bertambah otomatis setelah disetujui.", en: "Admin verifies proof in Deposits menu, balance increases automatically." },
  "balance.how3": { id: "Saldo dipakai user untuk beli paket Premium secara instan (potong saldo otomatis, tanpa perlu upload bukti lagi).", en: "Balance used to buy Premium instantly (auto-deduct, no proof needed)." },

  "common.loading": { id: "Memuat...", en: "Loading..." },
  "common.save": { id: "Simpan", en: "Save" },
  "common.saved": { id: "Tersimpan", en: "Saved" },
  "common.delete": { id: "Hapus", en: "Delete" },
  "common.cancel": { id: "Batal", en: "Cancel" },
  "common.add": { id: "Tambah", en: "Add" },
  "common.edit": { id: "Edit", en: "Edit" },
  "common.no_data": { id: "Belum ada data", en: "No data" },
  "common.yes_delete": { id: "Ya, Hapus", en: "Yes, Delete" },
  "common.search": { id: "Cari...", en: "Search..." },

  // Live Logs
  "logs.title": { id: "Live Logs", en: "Live Logs" },
  "logs.sub": { id: "Tail log bot/api/postgres - docker logs atau fallback DB", en: "Tail bot/api/postgres logs - docker logs or DB fallback" },
  "nav.logs": { id: "Live Logs", en: "Live Logs" },
};

function getSavedLang(): Lang {
  if (typeof window === "undefined") return "id";
  const v = localStorage.getItem("admin_lang") as Lang | null;
  return v === "en" || v === "id" ? v : "id";
}

type CtxType = {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
};

const Ctx = createContext<CtxType>({
  lang: "id",
  setLang: () => {},
  t: (k) => k,
});

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("id");
  useEffect(() => {
    setLangState(getSavedLang());
  }, []);
  const setLang = (l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem("admin_lang", l);
    } catch {}
  };
  const t = (key: string, vars?: Record<string, string | number>) => {
    const entry = TRANSLATIONS[key];
    let raw = entry ? (entry[lang] || entry.id) : key;
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        raw = raw.replaceAll(`{${k}}`, String(v));
      }
    }
    return raw;
  };
  return <Ctx.Provider value={{ lang, setLang, t }}>{children}</Ctx.Provider>;
}

export function useLang() {
  return useContext(Ctx);
}

// SVG Flags — no emoji
export function FlagID({ className = "h-4 w-6" }: { className?: string }) {
  return (
    <svg viewBox="0 0 6 4" className={className} aria-label="ID flag">
      <rect width="6" height="2" y="0" fill="#ED1C24" />
      <rect width="6" height="2" y="2" fill="#FFFFFF" />
    </svg>
  );
}

export function FlagEN({ className = "h-4 w-6" }: { className?: string }) {
  return (
    <svg viewBox="0 0 60 30" className={className} aria-label="EN flag">
      <clipPath id="en-c"><path d="M0 0 h60 v30 H0 z" /></clipPath>
      <g clipPath="url(#en-c)">
        <path d="M0 0 h60 v30 H0 z" fill="#012169" />
        <path d="M0 0 L60 30 M60 0 L0 30" stroke="#FFFFFF" strokeWidth="6" />
        <path d="M0 0 L60 30 M60 0 L0 30" stroke="#C8102E" strokeWidth="3.5" />
        <path d="M30 0 V30 M0 15 H60" stroke="#FFFFFF" strokeWidth="10" />
        <path d="M30 0 V30 M0 15 H60" stroke="#C8102E" strokeWidth="6" />
      </g>
    </svg>
  );
}
