# AGENTS.md — Image AI Bot Project

> Konteks buat AI agent (Claude/Kilo/dsb) yang lanjutin kerjaan di project ini di sesi baru.
> Baca file ini dulu sebelum ngerjain apa pun.

## 📌 Ringkasan Project

Bot Telegram generator & editor gambar AI (`@imgaai_bot`, "Free Image Generator") pakai model
**`gpt-image-2`** via **Cubence API**, dilengkapi dashboard admin modern (Next.js) dan sistem
**Premium/VIP dengan pembayaran manual**. Semua jalan di VPS via Docker Compose.

- **Repo GitHub:** https://github.com/kiosapi/img-ai-bot (private)
- **VPS:** `43.163.114.44` (Tencent Cloud), user `ubuntu`, project di `~/imgbot`, SSH key `~/.ssh/imgbot_vps`
- **Dashboard:** http://43.163.114.44:8000 (belum ada domain/HTTPS)
- **Bahasa komunikasi user:** Indonesia, casual/slang ("gua/lo")
- **Prinsip:** selalu pakai versi stable TERBARU dari semua teknologi (binding constraint dari user)

---

## 🏗️ Struktur Folder

```
imgbot/
├── bot/                        # Bot Telegram (aiogram v3, Python 3.11)
│   ├── main.py                 # Entrypoint: init DB, set commands, register routers, polling
│   ├── config.py                # Env vars (BOT_TOKEN, CUBENCE_*, ADMIN_IDS, dll)
│   ├── db.py                    # Layer asyncpg — SEMUA query database bot ada di sini
│   ├── cubence.py               # Client HTTP ke Cubence API (generate/edit image)
│   ├── ui.py                     # SEMUA template teks + inline keyboard bot (pakai i18n.t() untuk bilingual)
│   ├── i18n.py                    # Kamus teks id/en + fungsi t(key, lang, **kwargs) — auto-detect dari Telegram language_code, tersimpan di users.lang
│   ├── handlers/
│   │   ├── start.py             # /start, /help, /menu, /quota, /balance, /lang, navigasi menu utama, switch bahasa
│   │   ├── generate.py          # /generate, ForceReply prompt flow, size selection, check_and_consume()
│   │   ├── edit.py               # Edit foto (kirim foto+caption)
│   │   ├── premium.py           # Flow upgrade: pilih plan → beli INSTAN pakai saldo (potong otomatis, no approval manual)
│   │   └── balance.py            # Flow saldo: /balance → pilih nominal (quick/custom) → pilih metode bayar → upload bukti → nunggu approve admin
│   └── middlewares/
│       └── subscription.py      # Force-subscribe gate (cek user join channel)
│
├── api/                         # Backend JSON API (FastAPI) — dikonsumsi dashboard Next.js
│   └── main.py                  # SEMUA endpoint API ada di 1 file ini (~510 baris)
│
├── web/                         # Dashboard admin (Next.js 16 App Router)
│   └── src/
│       ├── app/
│       │   ├── login/page.tsx
│       │   └── (app)/           # Route group — dibungkus Shell (sidebar/drawer + auth)
│       │       ├── page.tsx               # Dashboard home (stats + chart)
│       │       ├── analytics/page.tsx     # Jam sibuk, success rate, top prompts/users
│       │       ├── users/page.tsx         # List user + search + ban/unban
│       │       ├── users/[id]/page.tsx    # Detail user + riwayat generate
│       │       ├── broadcast/page.tsx     # Kirim pesan ke semua user
│       │       ├── errors/page.tsx        # Log generate gagal + export CSV
│       │       ├── settings/page.tsx      # Daily limit, maintenance toggle
│       │       ├── orders/page.tsx        # Pesanan premium: lihat bukti, approve/reject
│       │       ├── plans/page.tsx         # CRUD paket premium
│       │       ├── payments/page.tsx      # CRUD metode pembayaran (bank/e-wallet/QRIS)
│       │       ├── deposits/page.tsx      # Approve/reject deposit saldo, lihat bukti
│       │       └── balance-settings/page.tsx  # Toggle fitur saldo, min/max nominal, quick amounts
│       └── components/
│           ├── shell.tsx         # Layout utama: sidebar desktop + header/drawer mobile
│           └── ui/                # button, card, controls (Input/Textarea/Badge/Switch), modal
│
├── docker-compose.yml           # postgres + bot + api + web
├── .env / .env.example          # Secrets (JANGAN commit .env asli — sudah di .gitignore)
├── README.md                     # Panduan instalasi publik (untuk orang lain yang clone)
└── AGENTS.md                     # File ini
```

**PENTING:** Folder `dashboard/` (versi lama, FastAPI+Jinja2) SUDAH DIHAPUS — diganti total oleh `api/` + `web/`. Kalau nemu referensi ke `dashboard/` di riwayat chat lama, itu udah obsolete.

---

## 🧰 Tech Stack (versi persis yang dipakai)

| Layer | Teknologi | Versi |
|---|---|---|
| Bot | Python | 3.11 |
| Bot | aiogram | 3.13.1 |
| Bot | asyncpg | 0.29.0 |
| Bot | httpx | 0.27.2 |
| API | FastAPI | 0.115.6 |
| API | uvicorn[standard] | 0.34.0 |
| API | asyncpg | 0.30.0 |
| API | pydantic | 2.10.4 |
| Web | Next.js | 16.2.10 (App Router) |
| Web | React | 19.2.7 |
| Web | Tailwind CSS | 4.3.3 (⚠️ jangan pin ke 4.0.0 — ada bug scanner, lihat Pitfalls) |
| Web | recharts | 2.15.4 |
| Web | lucide-react | 1.25.0 |
| Web | next-themes | 0.4.6 |
| Web | sonner (toast) | 2.0.7 |
| DB | PostgreSQL | 16-alpine |
| Infra | Docker Compose, Node 22 (build stage) | — |

Kalau nambah dependency baru: cek versi stable terbaru dulu (`npm view <pkg> version` / PyPI), jangan asal pakai versi yang diingat dari training data — sering udah ketinggalan.

---

## ✅ Fitur yang SUDAH JADI (production, live di VPS)

### Bot Telegram
- Text-to-image (`/generate` atau tombol → ForceReply prompt)
- Image editing (kirim foto + caption instruksi)
- Pilihan ukuran gambar (persegi/potret/lanskap), **persisted per-user di DB** (`users.pref_size`)
- Force-subscribe ke channel (`@imgaai_official`) sebelum bisa pakai bot
- Rate limit harian per user (default 20/hari untuk Free, DB `settings.daily_limit`)
- Menu utama interaktif full inline-keyboard (bukan cuma command polos)
- Maintenance mode toggle (dari dashboard, bot cek `is_maintenance()` sebelum generate/edit)
- **Sistem Premium/VIP:**
  - `/upgrade` atau tombol → pilih paket → **beli instan pakai saldo** (potong otomatis, tanpa approval manual — kalau saldo cukup langsung aktif)
  - Kalau saldo kurang: bot kasih tahu selisihnya + tombol langsung ke Top Up Saldo
  - `/quota` nampilin status Premium (nama paket + tanggal expired) kalau aktif
  - Kuota **premium-aware**: user premium pakai limit dari paketnya (bisa lebih besar / unlimited jika `daily_limit=0`), user free pakai limit global
- **Sistem Saldo Akun (Balance):**
  - `/balance` atau tombol **Saldo Saya** → lihat saldo, riwayat deposit
  - **Top Up**: pilih nominal (quick-amount dari dashboard atau custom) → pilih metode bayar → lihat instruksi rekening/QRIS → upload foto bukti → status `pending`, admin dapat notifikasi Telegram otomatis
  - Admin approve di dashboard (halaman **Deposit**) → saldo user bertambah otomatis + notifikasi Telegram ke user
  - Setiap perubahan saldo (topup/beli paket/adjust manual admin) tercatat di `balance_logs` — bisa dilihat riwayatnya di halaman **User Detail**
  - Admin bisa **manual tambah/kurangi saldo** user langsung dari dashboard (User Detail → Tambah/Kurangi Saldo), dengan catatan opsional
- **Multi-bahasa (ID/EN):**
  - Auto-detect dari `language_code` Telegram user pas `/start` pertama kali → disimpan di `users.lang`
  - User bisa ganti manual kapan saja lewat `/lang` atau tombol **Bahasa** di menu utama
  - Semua teks bot (menu, quota, premium, saldo, error) full bilingual lewat `bot/i18n.py` — dashboard admin TETAP bahasa Indonesia saja (scope i18n cuma bot, bukan dashboard)

### Dashboard Admin (Next.js, http://43.163.114.44:8000)
- Login (session cookie based, FastAPI backend)
- **Dashboard** — stat cards + chart aktivitas 7 hari
- **Analytics** — jam sibuk (30 hari), success rate trend (14 hari), breakdown generate/edit, top 10 prompt, top 8 user aktif
- **User** — list + search + ban/unban; klik → **detail user** (riwayat generate, stats)
- **Broadcast** — kirim pesan HTML ke semua user via bot
- **Error log** — daftar generate yang gagal + export CSV (users.csv & generations.csv)
- **Settings** — atur daily limit global, toggle maintenance mode
- **Pesanan (Orders)** — lihat semua order premium per status (pending/approved/rejected), lihat foto bukti transfer (di-proxy dari Telegram file API), tombol **Setujui** (aktivasi premium otomatis + notif user) / **Tolak** (dengan alasan, notif user)
- **Paket (Plans)** — CRUD paket premium: nama, harga (Rp), kuota harian (0=unlimited), masa aktif (hari), deskripsi, aktif/nonaktif
- **Pembayaran (Payments)** — CRUD metode bayar: tipe (bank/e-wallet/qris/lainnya), nama, no rekening/ID, atas nama, instruksi, QR image (file_id Telegram)
- **Deposit** — daftar semua deposit saldo per status (pending/approved/rejected), lihat foto bukti transfer, tombol **Setujui** (saldo user bertambah otomatis + notif) / **Tolak** (dengan alasan, notif user)
- **Pengaturan Saldo** — toggle on/off fitur saldo, atur nominal min/max, kelola daftar quick-amount (chip nominal cepat di bot) — semua editable dari dashboard tanpa sentuh kode
- Dark/Light mode, **SVG icon only (no emoji)**, responsive
- **Mobile nav:** header (hamburger kiri, judul tengah, toggle tema kanan) → tap hamburger buka **slide-out drawer** dari kiri (BUKAN bottom tab bar — user eksplisit minta ini karena 9 menu kepenuhan di bottom bar)
- Desktop: sidebar fixed kiri, grup "Umum" + "Premium"

### Database (PostgreSQL, tabel utama)
- `users` — user_id, username, first_name, is_banned, pref_size, premium_until, plan_id, plan_name, **balance** (saldo, BIGINT IDR), **lang** (id/en), created_at, last_seen
- `usage_daily` — counter generate harian per user
- `generations` — log tiap generate/edit (prompt, size, success, created_at)
- `settings` — key-value (daily_limit, maintenance, `balance_enabled`, `deposit_min`, `deposit_max`, `deposit_quick_amounts`, dll)
- `plans` — paket premium (name, daily_limit, price, duration_days, description, is_active, sort_order)
- `payment_methods` — metode bayar (type, name, account_name, account_number, instructions, qr_image, is_active, sort_order) — dipakai bareng oleh Premium & Deposit
- `orders` — pesanan premium (user_id, plan_id, method_id, snapshot plan/method, amount, proof_file_id, status pending/approved/rejected, note, decided_at). Order yang dibayar pakai saldo otomatis masuk sini dengan `method_name='Saldo'` dan `status='approved'` langsung.
- `deposits` — deposit saldo (user_id, method_id, method_name snapshot, amount, proof_file_id, status pending/approved/rejected, note, decided_at)
- `balance_logs` — audit trail tiap perubahan saldo (user_id, delta, balance_after, reason, created_at) — sumber data halaman "Riwayat" di User Detail

Semua migration pakai `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` di `_create_schema()` — aman dijalankan berkali-kali di DB yang sudah ada data.

---

## 🚧 Yang SEDANG/BELUM dikerjakan

Tidak ada task aktif yang menggantung saat AGENTS.md ini di-update terakhir kali.

Ide fitur yang PERNAH disarankan tapi belum diminta user (JANGAN kerjakan kecuali diminta eksplisit):
- Tombol "Regenerate" (buat ulang dengan prompt sama)
- Style presets (anime/realistis/3D/dll)
- Riwayat "Karya Saya" untuk user (catatan: gambar TIDAK disimpan di VPS — kalau mau fitur ini, pakai `file_id` Telegram, bukan simpan file, biar tetap zero storage cost)
- Sistem referral / bonus kuota ajak teman
- Feedback 👍/👎 di hasil gambar
- Metode top up otomatis (payment gateway/webhook) — saat ini SEMUA top up masih manual (upload bukti → admin approve)

---

## ⚠️ Rules & Pitfalls Penting

1. **Gambar TIDAK disimpan di VPS.** Base64 dari Cubence → decode ke RAM → langsung kirim ke Telegram → dibuang. Storage VPS aman selamanya dari bloat gambar. Kalau user tanya soal ini lagi, itu sudah confirmed behavior, bukan bug.

2. **`.env` JANGAN PERNAH di-commit.** Sudah di `.gitignore`. Kalau nambah env var baru, update juga `.env.example` (placeholder, tanpa nilai asli).

3. **No emoji di dashboard — SVG icon only** (lucide-react). Bot Telegram BOLEH pakai emoji (itu style-nya berbeda, emoji di teks pesan bot itu disengaja).

4. **Mobile nav dashboard = header + drawer, BUKAN bottom tab bar.** User eksplisit minta ini. Jangan balik ke bottom bar walau nav item dikit.

5. **Tailwind CSS jangan pin ke v4.0.0** — versi rilis awal itu ada bug (`Missing field 'negated' on ScannerOptions.sources`) karena mismatch `tailwindcss` vs `@tailwindcss/postcss` vs native oxide scanner. Pakai versi yang sama persis untuk `tailwindcss` dan `@tailwindcss/postcss` (sekarang keduanya 4.3.3). Selalu cek `npm view tailwindcss version` sebelum upgrade.

6. **Next.js pakai `output: "standalone"`** di `next.config.ts` + Dockerfile multi-stage (Node 22 alpine). Rewrites `/api/:path*` → proxy ke service `api:8000` di Docker network internal.

7. **Deploy flow:** edit lokal → `scp` ke VPS (folder dgn tanda kurung di path seperti `web/src/app/(app)/...` HARUS lewat `tar` biar aman, scp langsung suka gagal karena escaping parens) → `python3 -m py_compile` buat cek syntax Python di VPS SEBELUM build (sandbox lokal Windows gak ada Python) → `docker compose up -d --build <service>` → verifikasi `curl` semua endpoint/halaman → baru commit+push ke GitHub.

8. **Git workflow:** source of truth ada di 2 tempat — lokal (`~/imgbot` di sandbox, ini yang di-git) dan VPS (`~/imgbot` di server, yang running). SELALU edit di lokal dulu, upload ke VPS buat testing, baru commit+push dari lokal setelah verified working. Jangan commit langsung dari VPS.

9. **Sebelum commit, SELALU cek `git status --short` + pastikan `.env` tidak ke-stage** (`git ls-files --cached | grep -x ".env"` harus kosong).

10. **`read_file` butuh path Windows** (`C:\Users\tiwdv\imgbot\...`), bukan path Git-bash (`/c/...`), saat dipanggil dari tool `read_file`. Tapi `terminal` pakai path Unix-style (`~/imgbot/...`) karena jalan di Git-bash/sandbox Linux-like.

11. **Reminder keamanan yang MASIH BELUM DIKERJAKAN** (tanggung jawab user, jangan lakukan sendiri kecuali diminta):
    - Jadikan `@imgaai_bot` **admin** di channel `@imgaai_official` (biar force-subscribe berfungsi penuh)
    - **Rotate** bot token, Cubence API key, password VPS, password dashboard admin — semua sempat ke-expose di riwayat chat

12. **Repo GitHub masih PRIVATE** (keputusan sadar user). Jangan ubah ke public tanpa diminta eksplisit.

13. **Data test harus dibersihkan setelah verifikasi.** Kalau bikin data dummy buat testing (order, payment method, dll) di VPS, HAPUS lagi setelah selesai verifikasi — jangan biarkan nyampur ke data production.

---

## 🔑 Kredensial & Akses (nilai asli ada di `.env` VPS, JANGAN tulis ulang di sini)

- VPS: `ubuntu@43.163.114.44`, key `~/.ssh/imgbot_vps`, passwordless sudo
- Dashboard: http://43.163.114.44:8000, login admin (lihat `.env` → `ADMIN_USER`/`ADMIN_PASS`)
- Bot: `@imgaai_bot`, admin Telegram ID di `.env` → `ADMIN_IDS`
- Channel wajib join: `@imgaai_official`
- Cubence API: base `https://api-dmit.cubence.com`, model `gpt-image-2`, endpoint `/v1/images/generations` & `/v1/images/edits`
- GitHub: `gh` CLI sudah login sebagai akun `kiosapi` (dipakai buat push, `gh auth setup-git` sudah dijalankan)

---

## 🗒️ Log Perubahan Besar (kronologis singkat)

1. Build awal: bot aiogram + dashboard FastAPI/Jinja2 (v1)
2. Redesign dashboard jadi iOS-style (frosted glass, dark/light, Chart.js) — masih Jinja2
3. Emoji → SVG icon sprite di dashboard lama
4. **Rebuild total dashboard**: Jinja2 → Next.js 16 + React 19 + Tailwind v4 + shadcn-style (arsitektur `web` + `api` terpisah, folder `dashboard/` lama dihapus)
5. Fix bug kedip di halaman Users (double-fetch → single debounced fetch + skeleton loader)
6. Modernisasi tampilan bot Telegram (menu inline keyboard, ForceReply flow, progress bar kuota, tombol hasil "Buat Lagi")
7. Push project ke GitHub (`github.com/kiosapi/img-ai-bot`, private), README lengkap + `.env.example` + LICENSE
8. Tier 3 dashboard: Analytics, User detail, Error log, CSV export
9. **Sistem Premium/VIP + pembayaran manual**: plans/payment_methods/orders di DB, upgrade flow di bot, approve/reject di dashboard, 3 halaman baru (Orders/Plans/Payments)
10. Redesign nav mobile: bottom tab bar (9 item, "berlebihan") → header + slide-out drawer
