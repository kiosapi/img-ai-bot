<div align="center">

# Image AI Bot
**Telegram bot untuk generate & edit gambar dengan AI + dashboard admin modern.**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=next.js&logoColor=white)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

</div>

---

## Fitur

### Bot Telegram
- Text to Image — tulis prompt jadi gambar
- Image Editing — kirim foto + instruksi
- Pilihan ukuran & batch (1/2/4 gambar)
- Style presets & gallery
- Premium system + balance & deposit
- Referral system
- Moderation & rate limit

### Dashboard Admin
- Statistik & analytics aktivitas
- Kelola user & premium & deposit
- Broadcast & jadwal broadcast
- Kelola models & providers
- Kelola konten (teks, style, command)
- System monitor & logs
- Backup & restore

---

## Tech Stack

| Komponen | Teknologi |
|---|---|
| **Bot** | Python 3.11, aiogram 3.x, asyncpg |
| **API** | FastAPI, Uvicorn |
| **Web** | Next.js 16, React 19, Tailwind CSS |
| **Database** | PostgreSQL 16 |
| **Infra** | Docker Compose |

```
                ┌──────────────┐
 Telegram ◀──▶  │ bot          │ ─┐
                └──────────────┘  │
                                  ▼
                ┌──────────────┐  ┌──────────────┐
 Browser  ◀──▶  │ web (Next.js)│◀▶│ PostgreSQL   │
                └──────┬───────┘  └──────────────┘
                       │ /api
                       ▼
                ┌──────────────┐
                │ api (FastAPI)│
                └──────────────┘
```

---

## Instalasi

### Prasyarat
- Docker & Docker Compose
- Token bot dari [@BotFather](https://t.me/BotFather)
- API key image provider

### Langkah

```bash
git clone https://github.com/kiosapi/img-ai-bot.git
cd img-ai-bot

cp .env.example .env
nano .env

docker compose up -d --build
```

- Bot langsung aktif di Telegram
- Dashboard: `http://localhost:8000`

Update:

```bash
git pull
docker compose up -d --build
```

Data di volume PostgreSQL tidak hilang saat update.

---

## Konfigurasi

Isi file `.env`:

| Variable | Keterangan |
|---|---|
| `BOT_TOKEN` | Token bot dari @BotFather |
| `ADMIN_IDS` | ID Telegram admin (cek via @userinfobot) |
| `REQUIRED_CHANNEL` | Channel wajib join, kosongkan untuk nonaktif |
| `POSTGRES_USER / PASSWORD / DB` | Kredensial database |
| `ADMIN_USER / ADMIN_PASS` | Login dashboard |
| `DASH_SECRET` | Secret random, contoh: `openssl rand -hex 16` |
| Provider API keys | Minimal 1 provider aktif |

> Jika pakai force-subscribe, jadikan bot sebagai admin di channel tersebut.

---

## Cara Pakai

### User (Telegram)

| Perintah | Fungsi |
|---|---|
| `/start` | Buka menu utama |
| `/generate <prompt>` | Buat gambar dari teks |
| Kirim foto + caption | Edit gambar |
| `/size` | Pilih ukuran |
| `/quota` | Cek kuota |

### Admin (Dashboard)

Buka `http://localhost:8000`, login dengan `ADMIN_USER / ADMIN_PASS`.

---

## Struktur Project

```
img-ai-bot/
├── bot/                # Telegram bot
│   ├── handlers/       # command handlers
│   ├── db.py           # database layer
│   └── main.py
├── api/                # Backend API
│   └── main.py
├── web/                # Dashboard Next.js
│   └── src/
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Keamanan

- Jangan commit file `.env` (sudah di `.gitignore`)
- Gunakan password kuat & random
- Untuk production, pasang HTTPS via reverse proxy
- Rotasi token & API key berkala

---

## Lisensi

MIT — bebas pakai, modifikasi, distribusi.

---

<div align="center">

**Dibuat dengan fokus stabilitas & kemudahan penggunaan.**

</div>
