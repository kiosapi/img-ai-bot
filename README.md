<div align="center">

# Image AI Bot — @imgaai_bot
### Telegram AI Image Generator + Editor + No-Code Admin Dashboard

**Generate & edit images from Telegram — `gpt-image-2`, multi-provider failover, premium, balance, referral, broadcast, observability, monetization.**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=next.js&logoColor=white)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

Live Dashboard: `http://43.163.114.44:8000` · Bot: [@imgaai_bot](https://t.me/imgaai_bot)

</div>

---

## Table of Contents
- [Features](#features)
- [Roadmap 12/12 DONE](#roadmap-1212-done)
- [Architecture](#architecture)
- [Screenshots](#screenshots)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage](#usage)
- [Dashboard Pages](#dashboard-pages)
- [API Reference](#api-reference)
- [Security](#security)
- [PROJECT-SPEC](#project-spec)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Useful Commands](#useful-commands)
- [License](#license)

---

## Features

### Bot Telegram — Core
- **Text→Image** `/generate` — prompt → image, queue per-user rate-limit
- **Image Edit** — kirim foto + caption instruksi → edited (style-aware)
- **Batch [1,2,4]** + **7 sizes** `AUTO 768x1024 1024x768 1024x1024 512x512 1536x1024 1024x1536`
- **Interactive menus** inline keyboard — ukuran, batch, style gallery 2col mobile
- **Force Subscribe** `REQUIRED_CHANNEL` — fail-open, no hard block bug
- **Daily limit per user** + progress bar + auto-reset midnight WIB
- **Premium system** — plans, orders, expiry, quota boost
- **Balance & deposits** — top-up upload bukti, admin approve → saldo auto
- **Referral** — unique link `?start=ref_ID`, bonus saldo/kuota auto on channel join
- **Commands Manager** — 16 commands enable/disable instant tanpa restart
- **Dynamic Texts** — 29 keys bot texts editable dari dashboard tanpa code
- **Custom Styles** — gallery presets CRUD + My Works
- **Moderation / Blocklist** — word/regex/category, severity low/medium/high/block, log
- **Provider Failover** — priority drag up/down, timeout, retry, cost/gen, test ping latency real

### Generation Providers — Multi Failover
| ID | Name | Base URL | Models sync |
|---|---|---|---|
| `apikeyfun` | ApiKeyFun | `api.apikey.fun/v1` | ✅ |
| `cubence` | Cubence | `api-dmit.cubence.com` | ✅ |
| `rightcodes` | RightCodes | `right.codes/draw` | ✅ |
| `unity2` | Unity2 | `api.unity2.ai/v1` | ✅ gpt-image-2 |

- `ai_models` table `provider_id + is_active + is_default` + unique
- Sync via `/api/models` + `/api/providers/{id}/sync-models` SSRF guard `_is_safe_url https only`
- Bot tries providers by `failover_priority ASC`, fallback on timeout/error
- Cost per gen tracked for profit analytics

### Watermark
- Text only `@imgaai_bot`, no icon/emoji/“Buat di”
- Premium rare font stack SpaceGrotesk/Manrope/Satoshi
- Frosted glass pill background blur + soft stroke + highlight overlay
- Position bottom-right, opacity auto

---

## Roadmap 12/12 DONE

| Phase | # | Feature | Status | Proof |
|---|---|---|---:|---|
| **1 Observability** | 1 | **System Monitor** — CPU/RAM/Disk/PG/Uptime realtime via `psutil` non-blocking executor interval 0.3 + pulse + docker via `/var/run/docker.sock` | DONE `beeb5f7` | `GET /api/system/stats` live |
| | 2 | **Bot Health** — online dot pulse `settings bot_last_heartbeat` 60s <120s + last gen + gen/hour/today/active5m/stuck queue + provider latency ping no leak cache 30s | DONE | `GET /api/health/bot` + `providers/ping` |
| | 3 | **Live Logs** — tail via `docker.sock` socket HTTP multiplexed 8-byte BE header parse `docker-socket:real` | DONE `007c3b7` | `GET /api/logs/tail` |
| **2 No-Code** | 4 | **Dynamic Texts** — 29 keys editable `bot/texts.py` `get_dynamic_text` fallback, no restart | DONE `d08a7b2` | `/texts` |
| | 5 | **Styles CRUD** — `custom_styles` 11 seeded, gallery 2col mobile 4col desktop | DONE | `/styles-manage` |
| | 6 | **Command Manager** — 16 commands toggle via `feature_flags` single source truth `COMMAND_DEFS` api+bot, new cmd auto appear toggle | DONE `87e4bd3` | `/commands` |
| **3 Moderation** | 7 | **Moderation Manager** — `moderation_rules` pattern type word/regex/category severity block/warn/high, regex IGNORECASE, log `moderation_logs` user_id + test preview modal | DONE `2459261` | `/moderation` |
| | 8 | **Provider Failover Config** — priority order drag up/down, timeout 5-120 retry 0-5 cost 0-100k, reorder transaction FOR UPDATE unique regex id `^[a-z0-9_-]{1,50}$`, TestPing GET base_url SSRF latency ms success_rate 7d | DONE | `/failover` |
| | 9 | **Alert Webhook** — Discord `discord.com/api/webhooks` Telegram `api.telegram.org/bot` numeric chat_id + generic webhook https only private IP blocked, rules error_rate/deposit_pending/cpu/disk/bot_offline threshold + cooldown 15m + test send + history + evaluate on-demand | DONE | `/alerts` |
| **4 Monetization** | 10 | **Cost Tracker** — profit = revenue (deposits+orders approved) - cost (gen * cost_per_gen) live SQL avg cost/gen provider most expensive/cheapest/highest usage daily chart ResponsiveContainer width 100% + inline edit cost PUT real audit | DONE `098c3d5..9f5aba7` | `/cost` |
| | 11 | **Broadcast Scheduler** — `broadcast_schedules` title message media target_type all/premium/active/free scheduled_at repeat once/daily/weekly/monthly status pending/sent/sending/failed/cancelled next_run_at countdown, logs `broadcast_schedule_logs` FK CASCADE, real send via BOT_TOKEN httpx sendMessage/sendPhoto sem20 429 retry | DONE | `/broadcast-sched` |
| | 12 | **Backup & Restore 1-Klik** — `BACKUP_DIR=/tmp/backups`, `backup_history` filename UNIQUE size type manual/auto/upload status in_progress/completed/failed/restoring, `pg_dump DB_URL | gzip` streaming 1MB chunks `asyncio.to_thread` real dump not fake + sha256 checksum + path traversal guard resolve relative_to, download FileResponse attachment, restore `.sql.gz gunzip|psql .sql psql .dump pg_restore --clean --if-exists` + safety backup option double confirm RESTORE uppercase, upload multipart max 500MB, auto evaluate >24h | DONE `04bd62e` | `/backup` |
| **Fixes** | — | Dropdown transparan bug — CustomSelect opaque `bg-card z-[100] shadow-[0_12px_40px]` Modal `z-[90]/[91] overflow-hidden flex-col`, all native `<select>` → CustomSelect grep CLEAN | DONE `582e6f3..6acc7ae` | all pages |
| | — | Cost/Backup responsive — mobile-first `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`, `w-full max-w-full overflow-hidden min-w-0 truncate`, tables `hidden md:block overflow-x-auto min-w-[700px]` + `md:hidden cards rounded-xl border p-4`, chart `overflow-x-auto scrollbar-thin` | DONE `f708771..04bd62e` | `/cost` `/backup` |
| | — | i18n 441 keys ID/EN full + SVG flags red #ED1C24 white #FFFFFF EN #012169 #C8102E, Lucide only no emoji grep CLEAN, responsive 320px | DONE | all |

Report each phase DONE + commit hash + realtime proof + build Ready in 0ms + VPS Up.

---

## Architecture

```
                 ┌──────────────────┐
 Telegram  ◀──▶  │  bot (aiogram)   │ ─┐
                 │  python:3.11    │  │ asyncpg + GenQueue anti-spam + PGStorage FSM + checkin streak 1/2/5/20
                 └──────────────────┘  │
                                      ▼
                 ┌──────────────────┐  ┌──────────────────┐
 Browser  ◀──▶   │  web (Next.js 16)│◀▶│  PostgreSQL 16   │
                 │  React 19 + TW v4│  │  asyncpg + 50+ tables + indexes + pg_database_size live
                 └──────┬───────────┘  └──────────────────┘
                        │ /api proxy         ▲
                        ▼                    │
                 ┌──────────────────┐         │
                 │  api (FastAPI)  │ ────────┘  (postgresql-client gzip + docker.sock ro + psutil)
                 │  uvicorn + 119 endpoints + SSRF guard + audit_log + security headers DENY nosniff
                 └──────────────────┘

 Providers: apikey.fun / cubence / right.codes / unity2.ai/v1  (OpenAI-compat b64)
```

| Component | Tech | Notes |
|---|---|---|
| **Bot** | Python 3.11, aiogram 3.x, asyncpg, PGStorage states | `bot/db.py` migrations ALL tables, `gen_queue.py` anti-collide `queue.SimpleQueue`, feature_flags 16 cmds |
| **API** | FastAPI + Uvicorn + asyncpg + httpx + psutil + python-multipart | 119 endpoints, `BACKUP_DIR`, docker.sock via `asyncio.open_unix_connection`, `_is_safe_url https only` |
| **Web** | Next.js 16.2.10, React 19, Tailwind v4, shadcn-style, Recharts ResponsiveContainer | 23 pages, shell nav general/observability/no-code/moderation/failover/alerts/cost/backup/sched, CustomSelect opaque, Lucide only |
| **DB** | PostgreSQL 16 Alpine | `pg_dump | gzip`, `pg_database_size` live, indexes + FOR UPDATE txn |
| **Infra** | Docker Compose (api, bot, web, postgres) | `/var/run/docker.sock:ro` real logs parser, `DATABASE_URL ${POSTGRES_PASSWORD}` fixed `***` bug |

---

## Screenshots

- Dashboard home + System Monitor REALTIME pulse + Bot Health online dot + Live Logs docker.sock real
- Cost Tracker daily chart revenue/cost/profit + provider breakdown editable
- Moderation blocklist word/regex + Failover priority drag + Alerts Discord/Telegram
- Backup list + restore double confirm + Broadcast scheduler next_run countdown
- Login ID/EN flags SVG, dark/light, 320px responsive
- Bot @imgaai_bot /start menus, size/batch/style, generate flow

> See live `http://43.163.114.44:8000` for full demo.

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Telegram bot token from [@BotFather](https://t.me/BotFather)
- At least one provider API key (Unity2 recommended `https://api.unity2.ai/v1`)
- VPS / local with port 8000 open

### Steps
```bash
git clone https://github.com/kiosapi/img-ai-bot.git
cd img-ai-bot

cp .env.example .env
nano .env   # fill BOT_TOKEN, PROVIDER keys, ADMIN_IDS, DB passwords

docker compose up -d --build
```

Done:
- Bot live in Telegram — `/start`
- Dashboard: `http://localhost:8000` or `http://IP:8000` — login `ADMIN_USER / ADMIN_PASS`

Update:
```bash
git pull
docker compose up -d --build
```
Data in PG volume persists, not lost.

---

## Configuration

`.env` example:

| Var | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ | Telegram bot token |
| `ADMIN_IDS` | ✅ | Telegram admin IDs comma-separated |
| `REQUIRED_CHANNEL` | ➖ | `@channel` force join, empty = off. Bot must be admin in channel |
| `DEFAULT_DAILY_LIMIT` | ➖ | Default quota/user/day default 20 |
| `PROVIDERS` / `UNITY2_API_KEY` / `CUBENCE_API_KEY` / etc | ✅ at least 1 | Provider API keys, stored in `settings` DB editable via dashboard Failover |
| `DATABASE_URL` | ✅ auto | `postgresql://user:pass@postgres:5432/db` — template `${POSTGRES_PASSWORD}` |
| `POSTGRES_USER/PASSWORD/DB` | ✅ | PG credentials |
| `ADMIN_USER / ADMIN_PASS` | ✅ | Dashboard login |
| `DASH_SECRET` | ✅ | Random session secret `openssl rand -hex 16` |
| `BOT_USERNAME` | ➖ | @imgaai_bot display |

> Generate secrets: `openssl rand -hex 16`

Required channel: if set, bot middleware fail-open — user still recorded even if `get_chat_member` fails on private channel.

---

## Usage

### User (Telegram @imgaai_bot)

| Command | Function |
|---|---|
| `/start` | Main menu |
| `/generate <prompt>` | Text → image |
| Send photo + caption | Edit image by caption instruction |
| `/size` | Pick 7 sizes |
| `/batch` | Pick 1/2/4 |
| `/styles` | Gallery presets |
| `/myworks` | Your generations |
| `/quota` | Remaining quota |
| `/balance` | Saldo + topup |
| `/referral` | Invite link + bonus |
| `/help` | Help |

Generation flow: prompt → moderation check word/regex/category → rate-limit GenQueue → provider tries by failover_priority with timeout/retry → b64 image → watermark overlay text `@imgaai_bot` glass pill frosted blur + stroke → send → log `generations` success/failed + `aiogram_states` 5m stuck tracking.

### Admin (Dashboard)

Open `http://IP:8000` → login → pages:

**General:** Dashboard home stats + Analytics hours/daily + Users search/ban + Broadcast send + Models sync + Errors + Live Logs + Settings limit/maintenance

**Premium:** Orders, Plans, Payments

**Balance:** Deposits approve/reject + Balance Settings min/max quick amounts

**Observability:** System Monitor CPU/RAM/Disk/PG top tables processes docker REALTIME 10s psutil + Bot Health heartbeat polling + queue + provider ping latency + Failover Priority + Alerts Webhook + Cost Tracker

**No-Code:** Styles Manage gallery 11 seeded + Dynamic Texts 29 keys + Commands Manager 16 cmds toggle instant + Moderation Blocklist + Referral + Backup + Broadcast Schedules

All realtime accurate live SQL `pg_database_size` + `pg_stat_activity` + counts + psutil non-blocking interval 0.3 + docker.sock socket HTTP multiplexed 8-byte BE header parser `docker-socket:real:container` not fallback fake. Zero emoji Lucide only, ID/EN full SVG flags, responsive 320px.

---

## Dashboard Pages

| Path | Name | Description | API |
|---|---|---|---|
| `/` | Dashboard | Total users, today gens, active, recent | `/api/stats` |
| `/analytics` | Analytics | Busy hours 30d, success rate 14d, activity type, top prompts/users | `/api/analytics` |
| `/system` | System Monitor | CPU cores per_cpu load, RAM used/total swap, disk, DB size connections top tables, top processes, load, uptime, hostname REALTIME pulse 10s + docker | `/api/system/stats` |
| `/health` | Bot Health | Online dot pulse heartbeat age 60s <120s online, last gen, gen/hour/today/active5m/stuck, queue aiogram_states >5m, provider latency ping cache 30s no leak | `/api/health/bot` + `providers/ping` |
| `/cost` | Cost Tracker | Period 7d/30d/90d/365d, total cost revenue profit margin, avg cost/gen, daily chart ResponsiveContainer revenue green cost amber profit violet/red, daily table, provider breakdown gen_count*cost_per_gen success_rate bar most expensive red cheapest green inline edit cost, model breakdown, revenue split deposit/order, cost vs margin bar, how calc box | `/api/cost/stats?period` + `providers` + `PUT cost/providers/{id}` |
| `/failover` | Failover & Priority | Total/active/avg cost/failover_enabled, list providers order priority drag up/down arrows save order transaction, active toggle, timeout retry cost editable, Test Ping real latency ms status_code ok/error rate 7d, how box | `/providers/failover` + `reorder` + `/{id}/failover-config` + `/{id}/test-ping` |
| `/alerts` | Alert Webhook | Pending deposits, error %, CPU/Disk %, bot online heartbeat live poll system+health, rules list cards name type threshold channel Discord/Telegram/Webhook target cooldown last_triggered active toggle Test Send toast, history table triggered_at message resolved, evaluate, types, how | `/alerts/rules` + `history` + `stats` + `evaluate` + `types` + test |
| `/moderation` | Moderation & Blocklist | Stats total/active/blocks today/high, rules table search filter type word/regex/category severity low/medium/high/block active toggle, add/edit modal pattern 1-200 chars type select severity select active toggle preview test live input regex/word, logs tab user filter, pagination, how | `/moderation/rules?q=&type=&active=` + `logs?user_id=` + `stats` |
| `/users` | Users | Search username/id/name, ban/unban, detail images balance history gen history add/deduct, hint channel gate | `/api/users` |
| `/broadcast` | Broadcast | Audience all/premium/free counts, new message placeholder HTML b i a, image optional pick upload silent, button menu+url, preview, send confirm {count} audience, history, info silent upload | `/api/broadcast` + audience-counts |
| `/broadcast-sched` | Schedules | Total pending/sent/failed/next countdown, list cards title preview 80char target badge scheduled_at repeat badge status emerald/blue/red next_run_at retry actions Edit Cancel RunNow Delete View Logs ConfirmDialog, Add/Edit modal title message textarea HTML preview audience-counts target CustomSelect scheduled datetime-local ISO repeat once/daily/weekly/monthly media file_id preview, search status filter CustomSelect, auto-refresh 15s pending, real send via BOT_TOKEN sem20 | `/api/broadcast-sched/schedules` + `/{id}` + `/{id}/cancel` + `/{id}/run-now` + `/{id}/logs` + `/evaluate` |
| `/backup` | Backup & Restore | Auto-refresh 10s when in_progress, stats total count total size human last backup ago needs_auto pending failed auto_enabled backup_dir, warning amber box restore overwrites strong suggest download safety auto backup, list desktop table hidden md file size type status created by checksum file_exists missing warn + mobile cards rounded-lg border p-4 gap-2.5 + actions DL Restore Delete, download blob createObjectURL, upload FormData max 500MB, restore double confirm Modal step1 warning safety checkbox step2 Input RESTORE uppercase required, evaluate auto >24h, Force Auto | `/api/backup/list` + `stats` + `create` + `/{id}/download` + `DELETE {id}` + `/{id}/restore` + `/upload` + `/evaluate-auto` |
| `/referral` | Referral | Enable toggle, bonus type Add Balance/Add Quota, amount balance/quota per success, top referrers, history invited/success/waiting bonus, how | `/api/referral` |
| `/models` | Models & Provider | List providers base_url active is_default sync button, models per provider active toggle, set default, total/active count | `/api/providers` + `/models` + sync |
| `/styles-manage` | Style Presets | Gallery CRUD 11 seeded, 2col mobile 4col desktop, create/edit name prompt preview | `/api/styles` |
| `/texts` | Dynamic Texts | 29 keys groups search filter all/set/empty CustomSelect, edit textarea placeholder {var} HTML b i code, save/delete fallback default instant no restart via `get_dynamic_text`, how box | `/api/texts` |
| `/commands` | Commands Manager | 16 cmds groups core/premium/social, enable toggle instant via `feature_flags` + `is_command_enabled` handler guard, single source truth `COMMAND_DEFS` api+bot `bot/feature_flags.py` + API, new cmd auto appear | `/api/commands` |
| `/errors` | Error Log | Total failed, failed today, failure list prompt + reason, export CSV users/gens | `/api/errors` |
| `/logs` | Live Logs | Source filter bot/api/postgres Globe/Bot/Server/Database icons, lines 100/200/300/500 CustomSelect, search, Pause/Resume Auto-refresh 10s, Clear, Copy, realtime docker.sock `docker-socket:real:container` banner green pulse, CheckCircle2 AlertTriangle Lucide | `/api/logs/tail?source=&lines=&search=` |
| `/settings` | Settings | Limit & maintenance daily limit, maintenance mode toggle, channel required, model default, core/other features toggle instant, save | `/api/settings` |
| `/audit` | Audit Log | Admin actions log | `/api/audit` |
| `/orders` | Orders | Premium orders list approve/reject | `/api/orders` |
| `/plans` | Plans | Premium plans CRUD | `/api/plans` |
| `/payments` | Payments | Payment methods | `/api/payments` |
| `/deposits` | Deposits | Pending list approve/reject balance auto, stats pending | `/api/deposits` |
| `/balance-settings` | Balance Settings | Enable topup, min max, quick amounts, how | `/api/balance-settings` |

23 pages total, nav general/observability/no-code/premium/balance grouped.

---

## API Reference

**Total 119 endpoints:**

### Auth
- `POST /api/login` — `ADMIN_USER/ADMIN_PASS` + `DASH_SECRET` session cookie httpOnly

### Core
- `GET /api/stats` — dashboard stats total users gens etc live SQL
- `GET /api/analytics` — hours busy, daily trend, top prompts/users
- `GET /api/users?q=&limit=` — search users ILIKE
- `GET /api/models` — list models provider join
- `GET /api/providers` — list providers
- `POST /api/providers/{id}/toggle` — active toggle
- `POST /api/providers/{id}/sync-models` — sync models from provider base_url SSRF guard
- `GET /api/errors` — failed generations
- `GET /api/broadcast/audience-counts` — all/premium/active/free counts live
- `POST /api/broadcast/send` — send broadcast real via BOT_TOKEN httpx sem20

### Observability Phase1
- `GET /api/system/stats` — psutil CPU per_cpu mem disk PG size connections top tables via `pg_database_size` + `pg_stat_activity` live + docker via unix socket, non-blocking executor interval 0.3
- `GET /api/health/bot` — heartbeat `settings bot_last_heartbeat` parse ISO age sec online <120, last gen gen_per_hour today_gen active_5m stuck queue live SQL aiogram_states >5m
- `POST /api/system/bot/restart` — restart bot container via docker.sock? or flag
- `GET /api/providers/ping?provider_id=` + `POST /api/providers/{id}/test-ping` — GET base_url 6s httpx timeout SSRF guard no key leak cache 30s returns latency_ms status_code ok/error avg checked_at
- `GET /api/logs/tail?source=&lines=&search=` — logs via `/var/run/docker.sock` open_unix_connection HTTP multiplexed 8-byte header parse real-time accurate, fallback generations table if docker not available, returns source `docker-socket:real:container`

### No-Code Phase2
- `GET /api/texts?q=&group=&filter=` + `PUT /api/texts/{key}` + `DELETE /api/texts/{key}` — dynamic texts 29 keys `TEXTS_DEFINITIONS` groups
- `GET /api/styles` + `POST /api/styles` + `PUT /api/styles/{id}` + `DELETE /api/styles/{id}` — custom_styles CRUD 11 seeded gallery + reorder
- `GET /api/commands` + `PUT /api/commands/{cmd}` — 16 cmds toggle `feature_flags` table `is_command_enabled` handler guard
- `GET /api/settings` + `PUT /api/settings` — settings key-value typed

### Security Phase3
- `GET /api/moderation/rules?q=&type=&active=&limit=` + `POST /api/moderation/rules {pattern 1-200 type word/regex/category severity low/medium/high/block}` regex compile check max 500 rules + `PUT /{id}` + `DELETE /{id}` + `PATCH /{id}/toggle` + `GET /api/moderation/logs?user_id=&limit=` + `GET /api/moderation/stats` blocks today + `POST /api/moderation/rules/test {pattern type prompt}` live test
- `GET /api/providers/failover` — providers ordered priority ASC + stats total/active/avg_cost/failover_enabled
- `POST /api/providers/failover/reorder {order:[id]}` unique regex `^[a-z0-9_-]{1,50}$` verify exists append remaining transaction priority 0..n audit failover_reorder
- `PUT /api/providers/{id}/failover-config {timeout_sec 5-120 retry_count 0-5 cost_per_gen 0-100000}`
- `GET /api/alerts/rules` + `POST /api/alerts/rules {name type threshold channel discord/telegram/webhook target_url cooldown}` + `PUT /{id}` + `DELETE /{id}` + `PATCH /{id}/toggle` + `POST /{id}/test` + `GET /api/alerts/history?limit=` + `GET /api/alerts/stats` live snapshot collect pending deposits error_rate last hour queue_stuck bot_online heartbeat age cpu disk via psutil + `POST /api/alerts/evaluate` checks triggers sends if threshold + cooldown via `_dispatch_alert` + `GET /api/alerts/types`

### Monetization Phase4
- `GET /api/cost/stats?period=7d|30d|90d|365d` — daily group DATE(created_at) success/failed counts, daily revenue deposits approved + orders approved SUM, totals revenue period SUM, provider breakdown JOIN ai_models model_id grouped provider+model fallback equal distribution active providers if no tracking, weighted avg cost/gen = Σ gen*cost_per_gen / total_gens, daily array fill gaps from today backwards cost=gen_count*per_gen_cost_used profit=revenue-cost, provider_breakdown sorted total_cost desc, model_breakdown sorted gen desc, totals total_cost total_revenue total_profit avg_cost_per_gen deposit/order splits most_expensive/cheapest/highest_usage
- `GET /api/cost/providers` list providers cost float normalized order failover_priority
- `PUT /api/cost/providers/{id} {cost_per_gen 0-100000}` validate id regex update cost_per_gen audit
- `GET /api/broadcast-sched/schedules?status&q&target&repeat&limit` ordered next_run_at ASC counts pending_due next_up + `POST /schedules {title 0-100 message 1-4000 sanitized _sanitize_html future 5m skew max_retries target_type media file_id regex}` + `GET /{id}` + `PUT /{id}` recalc next_run_at + `DELETE /{id}` + `POST /{id}/cancel -> cancelled+log` + `POST /{id}/run-now _broadcast_lock 429 sending->sent/failed/retry repeat reschedule` + `GET /{id}/logs` + `POST /schedules/evaluate` checks next_run_at<=now pending runs
- `GET /api/backup/list` 100 rows DESC + `GET /api/backup/stats` totals human size last_backup pending failed needs_auto >24h last_ago_hours backup_dir + `POST /api/backup/create {type manual/auto}` in_progress insert safety + `GET /api/backup/{id}/download FileResponse attachment validate traversal` + `DELETE /api/backup/{id} file+DB audit` + `POST /api/backup/{id}/restore confirm true safety backup` + `POST /api/backup/upload multipart max 500MB` + `POST /api/backup/evaluate-auto?force`

All endpoints auth via session cookie + `_sanitize_html` XSS + SSRF safe + `require_auth` + `audit_log` + security headers `DENY nosniff`.

See `api/main.py` 5000+ lines for full source.

---

## Security

### Hardening 19 findings FIXED
- SQL injection — all queries parameterized `%s`, no f-string SQL
- XSS — `_sanitize_html` `<script>` `javascript:` blocked + `html.escape`
- SSRF — `_is_safe_url` https only + private IP 127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16 fe80::/10 block, `_is_safe_alert_url` discord `discord.com/api/webhooks` telegram `api.telegram.org` numeric chat_id allow, https only
- IDOR — regex `^[a-z0-9_-]{1,50}$` provider id validation + unique check
- Auth — session httpOnly cookie + `DASH_SECRET` random, unauthorized 401 JSON not redirect
- Headers — `X-Content-Type-Options nosniff` + `X-Frame-Options DENY` +  CSP-ish
- Secrets — no leak in logs + `.env` gitignored + `***` bug fixed shell
- Rate limit — GenQueue per user anti-spam `gen_queue.py` not `queue.py` collide `queue.SimpleQueue` breaks asyncio
- File upload — max 500MB backup + filename `_is_safe_filename` alphanumeric + `resolve relative_to` path traversal guard + checksum sha256
- Docker — `/var/run/docker.sock:ro` read-only mount
- Fail-open vs fail-closed — channel gate fail-open user recorded, moderation fail-open on exception, heartbeat fail-open
- Input validation — pattern 1-200 chars cost 0-100000 timeout 5-120 retry 0-5 threshold numeric + title 0-100 message 1-4000 + file_id regex `^[A-Za-z0-9_-]{10,400}$`
- Audit — `admin_audit` table + `audit_log` action admin_id target_id meta timestamp
- Privacy — generic ID `Layanan gambar sedang sibuk...` no provider leak

### Secrets Management
- `.env` gitignored, `.env.example` template only
- Rotate keys: Unity2 `https://api.unity2.ai/v1 [REDACTED]` exposed previously — rotate immediately
- `BOT_TOKEN` + `DASH_SECRET` via env, not hardcoded

---

## PROJECT-SPEC

Single source of truth `PROJECT-SPEC.md` 215+ lines lock anti-rusak — must read before touching code:

- Stack + VPS + Repo + Providers + Models
- Golden rules: zero emoji dashboard Lucide only `grep -rn "✅|❌|⚠️"` CLEAN, responsive mobile 320px `overflow-x-auto scrollbar-none break-all whitespace-pre-wrap`, CustomSelect opaque `bg-card z-[100] shadow`, Modal `z-[90]/[91] overflow-hidden flex-col`, CardHeader `p-5 pb-3` CardTitle `text-sm font-semibold uppercase tracking-wide` CardContent `p-5 pt-0`, i18n SVG flags #ED1C24 #012169, realtime accurate no fake psutil executor interval 0.3 + heartbeat + docker.sock parser 8-byte BE header, security headers DENY, etc
- Command registry single source truth: add command must update `bot/feature_flags.py _COMMAND_FEAT_DEFAULTS` + `COMMAND_DEFS` api+bot + db helper + handler guard `is_command_enabled` + frontend auto list via API `commands`, no hardcode elsewhere
- Allowed sizes 7 AUTO + batch [1,2,4] + watermark glass pill text only `@imgaai_bot` SpaceGrotesk/Manrope/Satoshi frosted blur + soft stroke
- Roadmap 12/12 proof commits + realtime accuracy proof + build Ready + VPS Up

Violating = production bug. New AI session must read this file first.

See [`PROJECT-SPEC.md`](PROJECT-SPEC.md).

---

## Project Structure

```
img-ai-bot/
├── bot/
│   ├── config.py              # ALLOWED_SIZES + ASPECT_MAP + BATCHES [1,2,4]
│   ├── db.py                  # ALL migrations: admin_audit custom_styles moderation_rules+logs providers failover columns alert_rules+history cost backup_history broadcast_schedules users generations ai_models providers orders plans payments deposits balance_settings referral_settings settings feature_flags...
│   ├── moderation.py          # check_prompt lower contains IGNORECASE regex category + log_moderation user_id prompt matched rule_id action
│   ├── texts.py               # get_dynamic_text fallback
│   ├── feature_flags.py       # _COMMAND_FEAT_DEFAULTS + is_command_enabled 16 commands groups core/premium/social
│   ├── gen_queue.py           # GenQueue anti-spam, NOT queue.py collide stdlib
│   ├── storage.py             # PGStorage aiogram states
│   ├── handlers/
│   │   ├── generate.py        # /generate + queue + moderation guard + failover priority list + watermark overlay
│   │   ├── edit.py            # image edit + moderation guard + texts dynamic
│   │   ├── start.py           # /start menu + referral ?start=ref_ID
│   │   ├── balance.py         # /balance topup + quick amounts + upload proof
│   │   ├── referral.py        # /referral stats bonus
│   │   └── ...
│   └── main.py                # aiogram polling + heartbeat settings bot_last_heartbeat 60s + middleware
├── api/
│   ├── main.py                # 5000+ lines + TEXTS_DEFINITIONS 29 + security headers + audit + system/metrics/docker logs/tail socket + texts/styles/commands/moderation/failover/alerts/cost/backup/scheduler + SSRF safe + sanitize + helpers _human_size _is_safe_filename _calculate_checksum _backup_file_path traversal guard _is_safe_alert_url discord/telegram
│   └── Dockerfile             # python:3.11-slim + postgresql-client gzip + cleanup
├── web/
│   ├── src/
│   │   ├── app/(app)/
│   │   │   ├── cost/page.tsx           # Cost Tracker responsive mobile cards + desktop table ResponsiveContainer
│   │   │   ├── backup/page.tsx         # Backup list desktop table + mobile cards blob download upload restore double confirm
│   │   │   ├── broadcast-sched/page.tsx# Schedules pending/sent/failed countdown real send
│   │   │   ├── moderation/page.tsx     # Moderation word/regex/category severity high stats blocks today
│   │   │   ├── failover/page.tsx       # Failover priority drag up/down timeout retry cost TestPing latency ms
│   │   │   ├── alerts/page.tsx         # Alerts rules Discord/Telegram/webhook test send history evaluate
│   │   │   ├── system/page.tsx         # System 71 lines bilingual REALTIME pulse 10s psutil live + docker
│   │   │   ├── health/page.tsx         # Bot health 76 lines pulse online heartbeat age last gen
│   │   │   ├── logs/page.tsx           # LiveLogs 125 lines responsive real docker.sock CheckCircle2 AlertTriangle Lucide CustomSelect lines filter
│   │   │   ├── texts/                  # Dynamic texts 29 keys groups filter all/set/empty
│   │   │   ├── styles-manage/          # Styles CRUD gallery 2col mobile 4col desktop
│   │   │   ├── commands/               # Commands 16 toggle feature_flags auto list API
│   │   │   ├── broadcast/              # Broadcast send now all/premium/free audience-counts
│   │   │   ├── users/ analytics/ errors/ orders/ plans/ payments/ deposits/ referral/ models/ settings/ audit/
│   │   │   └── page.tsx                # Dashboard home
│   │   ├── components/
│   │   │   ├── shell.tsx               # Nav general observability no-code moderation failover alerts cost backup scheduler + icons Route DollarSign Bell ShieldAlert CalendarRange HardDrive
│   │   │   └── ui/
│   │   │       ├── modal.tsx           # Modal z-[90]/[91] + CustomSelect opaque bg-card z-[100] shadow-[0_12px_40px] + Select
│   │   │       ├── card.tsx            # Card rounded-lg border bg-card CardHeader p-5 pb-3 CardTitle text-sm font-semibold uppercase
│   │   │       ├── button.tsx          # cva variant default destructive success outline secondary ghost + size sm lg icon
│   │   │       ├── controls.tsx        # Input Textarea Badge default success destructive muted secondary outline + Switch onChange/onCheckedChange
│   │   │       └── confirm-dialog.tsx  # ConfirmDialog onClose confirmLabel variant destructive loading
│   │   └── lib/
│   │       ├── i18n.tsx                # 441 keys ID/EN nav.system health logs texts styles_manage commands moderation failover alerts cost backup + FlagID red/white #ED1C24 #FFFFFF FlagEN Union Jack #012169 #C8102E SVG no emoji
│   │       └── utils.ts                # api fetch httpOnly cookie + cn
│   └── Dockerfile                      # node:22-alpine build + runner Next 16
├── docker-compose.yml                  # api bot web postgres + /var/run/docker.sock:ro + DATABASE_URL ${POSTGRES_PASSWORD} fixed *** bug
├── PROJECT-SPEC.md                     # 215+ lines lock anti-rusak single truth
├── .env.example
├── .gitignore                          # deploy_*.tar.gz *.tar.gz .env
└── README.md                           # this file (updated)
```

---

## Troubleshooting

**Bot tidak merespons**
- `docker compose logs bot` — cek BOT_TOKEN valid
- `docker compose ps` — Up?
- Check failover providers active at least 1 + models active
- Moderation not blocking too broad? Check `/moderation` logs

**Force-subscribe tidak berfungsi**
- Bot harus admin di `REQUIRED_CHANNEL`
- Middleware fail-open sekarang: user tetap tercatat walau get_chat_member error private — cek `users` page should have >1

**Dashboard tidak bisa diakses**
- Port 8000 firewall `ufw allow 8000`?
- `docker compose logs web` `api`
- Build fail? Check `sudo docker compose build web` logs Type error
- Native `<select>` bug fixed all to CustomSelect opaque, grep CLEAN 0

**Generate gagal / error API**
- Check `/health` provider latency — Test Ping button real ms
- Validate api key via `/failover` test ping
- Check `/logs` bot logs + `/errors` failed list + `/system` pg stats
- Provider cost_per_gen 0? Set realistic for profit calc
- `docker exec imgbot-postgres-1 psql -U imgbot -c "SELECT model_id, provider_id FROM ai_models WHERE is_active"`

**Cost page Rp 0 all**
- Normal if no deposits/orders approved + cost_per_gen 0 default. Set cost per gen in `/cost` or `/failover` inline edit, create deposit approved.
- `SELECT count(*) FROM generations WHERE success=true` — if >0 but cost 0 => set provider cost
- `SELECT SUM(amount) FROM deposits WHERE status='approved'` — if 0 no revenue yet

**Backup create fail**
- Check API image has `postgresql-client gzip` — Dockerfile must have `apk add postgresql-client gzip` or `apt-get`
- `BACKUP_DIR /tmp/backups` writable? `docker exec imgbot-api-1 ls -lh /tmp/backups`
- `sudo docker logs imgbot-api-1 | grep backup` — pg_dump error
- Download fails traversal? `_backup_file_path resolve relative_to` guard + file_exists check

**Dropdown transparan rusak**
- FIXED: `CustomSelect bg-card opaque z-[100] shadow-[0_12px_40px] rounded-xl backdrop-blur-none` + Modal `z-[90]/[91] overflow-hidden flex-col` header `border-b px-5 py-4` body `overflow-y-auto p-5` — dropdown not clipped
- Ensure no native `<select>` left: `grep -rn "<select" web/src --include="*.tsx" | grep -v CustomSelect` should 0

**i18n raw keys COST.PERIOD cost.sub**
- FIXED: added 69 keys `cost.*` + `mod.*` + `alerts.*` + `backup.*` + `bs.*` in `i18n.tsx` — 441 keys total, hard reload Ctrl+Shift+R

**Emoji violations**
- Zero emoji rule: `grep -rn "✅|❌|⚠️" web/src` CLEAN, use Lucide CheckCircle2 AlertTriangle
- Backup `(missing)` not `⚠`

**Build fail web**
- Type errors common: `Badge variant secondary not allowed` → added to Badge variants, `Button variant muted not allowed` → use `outline`, `Switch onCheckedChange vs onChange` → supports both now, `Modal onOpenChange vs onClose` → use onClose, `ConfirmDialog confirmText vs confirmLabel` → use confirmLabel
- Next build `npm run build` must `Ready in 0ms`, not `Failed to compile`

---

## Useful Commands

```bash
# Logs
docker compose logs -f
docker compose logs -f bot
docker compose logs -f api | grep -E "backup|cost|alert"

# PS
docker compose ps

# Restart single
docker compose restart bot
docker compose restart api
docker compose up -d --build web

# Build check type errors
docker compose build web 2>&1 | grep -A3 "Type error"

# DB checks
docker exec imgbot-postgres-1 psql -U imgbot -d imgbot -c "SELECT pg_size_pretty(pg_database_size(current_database()));"
docker exec imgbot-postgres-1 psql -U imgbot -c "SELECT count(*) FROM generations; SELECT count(*) FROM users;"

# Backup manual outside API (full)
docker exec imgbot-postgres-1 pg_dump -U imgbot imgbot | gzip > backup_$(date +%F).sql.gz

# Deploy tar method (no git on VPS)
tar -czf /tmp/deploy.tar.gz api web/src bot
scp /tmp/deploy.tar.gz ubuntu@43.163.114.44:~/imgbot/
ssh ubuntu@43.163.114.44 'cd ~/imgbot && tar -xzf deploy.tar.gz && sudo docker compose up -d --build'

# Hard checks via audit script
python -m py_compile api/main.py bot/db.py
grep -Rn "<select" web/src --include="*.tsx" | grep -v CustomSelect
grep -Rn "console\.log" web/src --include="*.tsx"
grep -R -P "[\x{1F600}-\x{1F6FF}]" web/src --include="*.tsx"
```

---

## License

MIT — free to use, modify, distribute.

---

<div align="center">

**Made with care — roadmap 12/12 DONE, observability + no-code + moderation + failover + alerts + cost + scheduler + backup, realtime accurate, zero emoji Lucide, responsive 320px, CustomSelect opaque, security 19 fixes.**

⭐ Star if you like it!

</div>
