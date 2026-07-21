# PUBLIC WEB APP — imgaai (v1 Model B)

> Spec handoff. Baca sebelum sentuh `web-app/` atau endpoint `/api/user/*`.
> Admin dashboard = `web/` (private). Public app = `web-app/` (CF Pages).

## Locked decisions (2026-07-21)

| Item | Value |
|------|--------|
| Product | **Full web app** (Model B): login + generate di browser; bot Telegram tetap |
| Brand | **imgaai** |
| Host v1 | Cloudflare Pages → `imgaai.pages.dev` (custom domain later) |
| Auth | **Model B deep-link bot** — **bukan** Login Widget |
| Gallery | Opt-in share; **default private** |
| Topup / promo | **v1.1** (bukan v1) |
| Queue | Satu GenQueue shared bot+web via `web_gen_jobs` + bot worker |
| Admin | `web/` + `/api/*` admin cookie — **jangan** expose ke public |
| UI | Dark/clean, **zero emoji**, Lucide only, mobile 320px, ID/EN |
| Stack | Next.js 16 + React 19 + Tailwind 4.3.x (static export) + FastAPI user scope |

## Auth Model B (login via bot)

1. Web `POST /api/user/auth/login-code` → `{ code, deep_link }`
2. User buka `https://t.me/imgaai_bot?start=login_<code>`
3. Bot `/start login_<code>`:
   - belum pernah start → Telegram suruh Start dulu (natural)
   - claim code + insert `user_sessions` + mark `web_login_codes` claimed
   - balas **Berhasil / Gagal** di chat bot
4. Web poll `GET /api/user/auth/login-code/{code}` tiap 2s
5. Status `claimed` + `token` → localStorage Bearer + redirect `/app/`

### Tables
- `user_sessions` — session token 30d (cookie name `user_session` + Bearer)
- `web_login_codes` — one-time code, TTL 5 menit, status `pending|claimed|expired`

### Endpoint map (user)

| Method | Path | Auth | Notes |
|--------|------|------|--------|
| POST | `/api/user/auth/login-code` | no | create deep-link code |
| GET | `/api/user/auth/login-code/{code}` | no | poll pending/claimed/expired |
| POST | `/api/user/auth/telegram` | no | **legacy widget** (kept, not primary UI) |
| POST | `/api/user/logout` | user | clear session |
| GET/PATCH | `/api/user/me` | user | profile + balance + quota |
| GET | `/api/user/styles` | user | active styles |
| GET | `/api/user/history` | user | own generations |
| GET | `/api/user/checkin` | user | streak read |
| POST | `/api/user/generate` | user | enqueue job |
| GET | `/api/user/generate/{id}` | user | poll job + optional b64 |
| DELETE | `/api/user/generate/{id}/image` | user | drop b64 after display |
| GET | `/api/user/health` | no | health |

## CORS

- Env `WEB_CORS_ORIGINS` comma list, e.g. `https://imgaai.pages.dev,http://localhost:3001`
- `allow_credentials=True`, never `*` with credentials

## Deploy

### Frontend (CF Pages)
- Build: `cd web-app && npm ci && npm run build`
- Output: `web-app/out/`
- Project: `imgaai`
- Env: `NEXT_PUBLIC_API_URL` (**must HTTPS** from Pages), `NEXT_PUBLIC_BOT_USERNAME=imgaai_bot`

### API (VPS)
- Same FastAPI; CORS + user routes
- **HTTPS wajib** biar browser Pages gak block mixed content

### HTTPS options (prefer)
1. Cloudflare Tunnel → hostname HTTPS
2. Domain + Caddy/nginx + CF orange cloud
3. Worker proxy **hanya** ke hostname (bukan raw IP — error 1003)

## Security

- Never return provider keys / admin dumps / docker / VPS IP di public README
- Login codes one-time, 5 min TTL, rate-limit create per IP
- Parameterize SQL; validate code charset
- Image b64 only for job owner; clear after client download

## UI rules (public)

- Lucide only, zero emoji
- Empty / loading / error / waiting-login states
- FlagID / FlagEN SVG for lang (settings)

## Phases

| Phase | Deliverable |
|-------|-------------|
| **1** | Spec + sessions + **Model B auth** + `/me` + styles + history + shell |
| **1.5** | Generate job + bot worker + poll UI |
| **1.1** | Topup + promo |
| **2** | Batch, enhance, explore feed |

## Pitfalls

1. Mixed content: Pages HTTPS + API HTTP = dead browser fetch
2. Worker ORIGIN raw IP = CF 1003
3. In-memory GenQueue only in bot process — API uses DB jobs
4. Cookie-only cross-site needs HTTPS API; Bearer primary
5. Widget setdomain **tidak** required untuk Model B
6. Static export = no Next server routes

## Status

- Spec: **LOCKED Model B**
- Code: deep-link auth + full app routes (generate/history/styles/settings)
- Web: https://imgaai.pages.dev
- API user health (HTTP): VPS `:8001` — **HTTPS still open** for browser production
- Bot: `web_jobs` + `/start login_*` claim
- **Tidak** perlu BotFather setdomain untuk login Model B
- **Masih perlu:** HTTPS API (tunnel/domain) + rebuild Pages `NEXT_PUBLIC_API_URL`
