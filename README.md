<div align="center">

# 🎨 Image AI Bot

**Bot Telegram generator & editor gambar berbasis AI, lengkap dengan dashboard admin modern.**

Bikin gambar dari teks dan edit foto langsung dari Telegram — didukung model **`gpt-image-2`** via [Cubence](https://cubence.com).

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=next.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

</div>

---

## ✨ Fitur

### 🤖 Bot Telegram
- **Text-to-Image** — ketik prompt, jadi gambar
- **Image Editing** — kirim foto + instruksi, gambar diedit AI
- **Menu interaktif** — tombol inline, alur mulus tanpa perlu hafal command
- **Pilihan ukuran** — persegi (1:1), potret (2:3), lanskap (3:2), tersimpan per-user
- **Force subscribe** — wajibkan user join channel dulu (opsional)
- **Rate limiting** — batas pemakaian harian per user, progress bar visual
- **Kuota reset otomatis** tiap hari

### 📊 Dashboard Admin
- **Statistik real-time** — total user, gambar hari ini, user aktif, dll
- **Grafik aktivitas** 7 hari terakhir
- **Kelola user** — cari, lihat pemakaian, ban/unban
- **Broadcast** — kirim pesan ke semua user (support HTML)
- **Pengaturan** — atur limit harian & mode maintenance dari UI
- **Dark / Light mode**, responsive (desktop & mobile)

---

## 🏗️ Arsitektur

```
                    ┌─────────────────┐
   Telegram  ◀────▶ │   bot (aiogram) │ ─┐
                    └─────────────────┘  │
                                         ▼
                    ┌─────────────────┐  ┌──────────────┐
   Browser   ◀────▶ │  web (Next.js)  │◀▶│ PostgreSQL 16│
                    └────────┬────────┘  └──────────────┘
                             │ /api proxy      ▲
                             ▼                 │
                    ┌─────────────────┐        │
                    │  api (FastAPI)  │ ───────┘
                    └─────────────────┘
```

| Komponen | Teknologi |
|----------|-----------|
| **Bot** | Python 3.11, aiogram v3, asyncpg |
| **API** | FastAPI, Uvicorn, asyncpg |
| **Web** | Next.js 16, React 19, Tailwind CSS v4, shadcn-style UI, Recharts |
| **Database** | PostgreSQL 16 |
| **Infra** | Docker Compose |

---

## 🚀 Instalasi Cepat

### Prasyarat
- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/) terpasang
- Token bot Telegram — dari [@BotFather](https://t.me/BotFather)
- API key Cubence — dari [cubence.com](https://cubence.com)
- (Opsional) VPS / server untuk hosting 24 jam

### Langkah-langkah

**1. Clone repository**
```bash
git clone https://github.com/kiosapi/img-ai-bot.git
cd img-ai-bot
```

**2. Buat file konfigurasi**
```bash
cp .env.example .env
```

**3. Isi `.env`** dengan editor favoritmu (nano/vim/VSCode):
```bash
nano .env
```
Isi minimal yang wajib: `BOT_TOKEN`, `CUBENCE_API_KEY`, `ADMIN_IDS`, dan semua password.

> 💡 **Generate password/secret acak** dengan:
> ```bash
> openssl rand -hex 16
> ```

**4. Jalankan semua service**
```bash
docker compose up -d --build
```

**5. Selesai! 🎉**
- Bot langsung aktif di Telegram — buka dan ketik `/start`
- Dashboard admin: **http://localhost:8000** (atau `http://IP-SERVER:8000`)

---

## ⚙️ Konfigurasi (.env)

| Variable | Wajib | Keterangan |
|----------|:-----:|------------|
| `BOT_TOKEN` | ✅ | Token bot dari @BotFather |
| `REQUIRED_CHANNEL` | ➖ | Channel wajib di-join (mis. `@channel`). Kosongkan untuk nonaktif |
| `ADMIN_IDS` | ✅ | ID Telegram admin, pisah koma. Cek via [@userinfobot](https://t.me/userinfobot) |
| `CUBENCE_API_KEY` | ✅ | API key dari Cubence |
| `CUBENCE_BASE_URL` | ➖ | Default: `https://api-dmit.cubence.com` |
| `DEFAULT_DAILY_LIMIT` | ➖ | Batas gambar/user/hari (default `20`) |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | ✅ | Kredensial database |
| `ADMIN_USER` / `ADMIN_PASS` | ✅ | Login dashboard admin |
| `DASH_SECRET` | ✅ | Secret acak untuk sesi login |

> ⚠️ **PENTING:** Agar fitur *force-subscribe* berfungsi, jadikan bot kamu sebagai **admin** di channel yang di-set pada `REQUIRED_CHANNEL`.

---

## 📖 Cara Pakai

### Untuk User (di Telegram)
| Perintah | Fungsi |
|----------|--------|
| `/start` | Buka menu utama |
| `/generate <prompt>` | Buat gambar dari teks |
| Kirim foto + caption | Edit gambar sesuai instruksi caption |
| `/size` | Pilih ukuran gambar |
| `/quota` | Cek sisa kuota harian |
| `/help` | Bantuan |

### Untuk Admin (Dashboard)
Buka `http://IP-SERVER:8000`, login pakai `ADMIN_USER` / `ADMIN_PASS`. Dari sini kamu bisa lihat statistik, kelola user, broadcast, dan atur limit/maintenance.

---

## 🔄 Update / Upgrade

Menarik perubahan terbaru dan rebuild:
```bash
git pull
docker compose up -d --build
```

Data (user, riwayat, statistik) tersimpan di volume PostgreSQL dan **tidak hilang** saat update.

---

## 🛠️ Perintah Berguna

```bash
# Lihat log semua service
docker compose logs -f

# Lihat log bot saja
docker compose logs -f bot

# Restart satu service
docker compose restart bot

# Stop semua
docker compose down

# Stop + hapus data (HATI-HATI: menghapus database)
docker compose down -v
```

---

## 🧯 Troubleshooting

<details>
<summary><b>Bot tidak merespons</b></summary>

- Cek log: `docker compose logs bot`
- Pastikan `BOT_TOKEN` benar
- Pastikan container jalan: `docker compose ps`
</details>

<details>
<summary><b>Force-subscribe tidak berfungsi</b></summary>

Bot harus jadi **admin** di channel `REQUIRED_CHANNEL`. Tambahkan bot sebagai admin channel, lalu coba lagi.
</details>

<details>
<summary><b>Dashboard tidak bisa diakses</b></summary>

- Cek port 8000 terbuka di firewall server
- Cek `docker compose logs web` dan `docker compose logs api`
</details>

<details>
<summary><b>Generate gagal / error API</b></summary>

- Pastikan `CUBENCE_API_KEY` valid dan saldo mencukupi
- Cek `docker compose logs bot` untuk pesan error detail
</details>

---

## 📁 Struktur Project

```
img-ai-bot/
├── bot/                  # Bot Telegram (aiogram)
│   ├── handlers/         # /start, generate, edit
│   ├── middlewares/      # Force-subscribe
│   ├── ui.py             # Template pesan & keyboard
│   ├── db.py             # Layer database
│   └── main.py           # Entrypoint
├── api/                  # Backend JSON API (FastAPI)
│   └── main.py
├── web/                  # Dashboard admin (Next.js)
│   └── src/
├── docker-compose.yml    # Orkestrasi semua service
├── .env.example          # Template konfigurasi
└── README.md
```

---

## 🔐 Keamanan

- **Jangan pernah** commit file `.env` (sudah diblokir via `.gitignore`)
- Gunakan password kuat & acak untuk database dan dashboard
- Untuk production, sebaiknya pasang **HTTPS** (reverse proxy Nginx/Caddy) di depan dashboard
- Rotasi token & API key secara berkala

---

## 📄 Lisensi

Dirilis di bawah lisensi [MIT](LICENSE). Bebas digunakan, dimodifikasi, dan didistribusikan.

---

<div align="center">

**Dibuat dengan ❤️ — semoga bermanfaat!**

⭐ Star repo ini kalau kamu suka!

</div>
