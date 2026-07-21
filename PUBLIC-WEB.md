# PUBLIC WEB APP — imgaai (v1)

> Spec handoff. Baca sebelum sentuh `web-app/` atau endpoint `/api/user/*`.
> Admin dashboard = `web/` (private). Public app = `web-app/` (CF Pages).

## Locked decisions (2026-07-21)

| Item | Value |
|------|--------|
| Product | Full web app: login + generate di browser; bot Telegram tetap |
| Brand | **imgaai** |
| Host v1 | Cloudflare Pages → `imgaai.pages.dev` (custom domain later) |
| Auth | **Telegram Login Widget only** → same `users.user_id` = Telegram id |
| Gallery | Opt-in share; **default private** |
| Topup / promo | **v1.1** (bukan v1) |
| Queue | Satu GenQueue shared bot+web (FIFO max3) — generate job phase berikutnya |
| Admin | `web/` + `/api/*` admin cookie — **jangan** expose ke public |
| UI | Dark/clean, **zero emoji**, Lucide only, mobile 320px, ID/EN |
| Stack | Next.js 16 + React 19 + Tailwind 4.3.x (static export) + FastAPI user scope |

## Repo layout

```
imgbot/
├── web/                 # Admin dashboard (Docker, standalone)
├── web-app/             # Public user app (CF Pages, output: export)
├── api/main.py          # Admin routes + NEW /api/user/* routes
├── bot/                 # Telegram bot (unchanged ownership of gen core)
├── PUBLIC-WEB.md        # this file
├── PROJECT-SPEC.md      # production lock (admin/bot)
└── AGENTS.md
```

## v1 scope (in)

1. Telegram Login Widget → session cookie `user_session`
2. User home: balance, daily quota used/limit, premium status, check-in status (read)
3. Generate form shell + queue UI placeholder (wire job = next phase if not done same sprint)
4. History list (metadata from `generations`; image via Telegram `file_id` proxy if available)
5. Styles list (active `custom_styles` only — no admin fields)
6. Settings: lang (id/en), gallery privacy flag
7. Watermark policy same as bot (`@imgaai_bot`) when generate ships

## v1 out

- Batch, sticker, enhance, public explore feed
- Email/password auth
- Topup / promo redeem (v1.1)
- Provider names, failover, admin metrics
- VPS IP in public README

## Auth model

### Telegram Login Widget
- Frontend loads `https://telegram.org/js/telegram-widget.js`
- BotFather: `/setdomain` → hostname Pages (e.g. `imgaai.pages.dev`) **required** or widget fails
- POST `/api/user/auth/telegram` body = widget payload (`id`, `first_name`, `username`, `photo_url`, `auth_date`, `hash`)
- Server verifies HMAC-SHA-256 per Telegram docs using `BOT_TOKEN`
- Reject if `auth_date` older than 86400s
- Upsert `users` (same as bot `upsert_user`)
- Reject if `is_banned`
- Issue opaque token → table `user_sessions` (token, user_id, expires_at 30d)
- Cookie: `user_session` HttpOnly; `SameSite=None; Secure` when HTTPS cross-origin (Pages → API)
- Cookie name **must differ** from admin `session`

### Endpoint map (user)

| Method | Path | Auth | Notes |
|--------|------|------|--------|
| POST | `/api/user/auth/telegram` | no | login |
| POST | `/api/user/logout` | user | clear session |
| GET | `/api/user/me` | user | profile + balance + quota + premium |
| PATCH | `/api/user/me` | user | lang, gallery_public |
| GET | `/api/user/styles` | user | active styles public fields only |
| GET | `/api/user/history` | user | own generations paginated |
| GET | `/api/user/checkin` | user | streak status read (claim later) |
| POST | `/api/user/checkin` | user | claim daily (reuse bot rules) |
| POST | `/api/user/generate` | user | **phase 1.5+** shared queue |

Admin routes remain `Depends(require_auth)` on `/api/*` non-user paths.

## CORS

- Env `WEB_CORS_ORIGINS` comma list, e.g. `https://imgaai.pages.dev,http://localhost:3001`
- Only these origins for browser credentialed requests
- No `*` with credentials

## Deploy

### Frontend (CF Pages)
- Build: `cd web-app && npm ci && npm run build`
- Output: `web-app/out/` (`output: "export"`)
- Project name: `imgaai` (confirm wrangler cache after first create)
- Env build: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_BOT_USERNAME=imgaai_bot`

### API (VPS)
- Same FastAPI container; open CORS + user routes
- Prefer reverse proxy HTTPS later; for v1 may use API on VPS port with Secure cookie caveats
- **Ideal:** API behind `api.imgaai.*` HTTPS so `SameSite=None; Secure` works clean from Pages

### Cookie note (cross-site)
Pages (`*.pages.dev`) → API (`IP` or other host) = cross-site. Need:
1. API HTTPS
2. Cookie `Secure; SameSite=None`
3. Frontend `credentials: "include"`
4. CORS `allow_credentials=True` + explicit origin

Until custom domain+HTTPS on API: dev mode may use Bearer token header `Authorization: Bearer <token>` as fallback (also implemented) so CF Pages works without cookie domain hell.

## Security

- Never return provider keys, admin settings dumps, docker, raw logs to `/api/user/*`
- Parameterize SQL; validate all input lengths
- Rate-limit auth attempts per IP (mirror admin login guard)
- No VPS IP / bot token in public README
- Image proxy: only for `user_id` owner of generation

## UI rules (public)

- Lucide only, zero emoji (same as admin)
- CardHeader style can follow admin patterns but lighter marketing chrome on login
- Empty / loading / error states required
- FlagID / FlagEN SVG for lang switch (no emoji flags)

## Phases

| Phase | Deliverable |
|-------|-------------|
| **1** (this sprint) | Spec + `user_sessions` + Telegram auth + `/me` + styles + history read + `web-app` login/home shell + env docs |
| **1.5** | Generate job via shared queue + progress + result delivery path for web |
| **1.1** | Topup + promo (after gen solid) |
| **2** | Batch, enhance, opt-in public gallery feed |

## Pitfalls

1. Widget domain must match BotFather setdomain exactly
2. Do not reuse admin cookie name `session`
3. Images not on disk — history thumbnails need TG file proxy or future R2
4. Shared queue fairness: web must not skip bot FIFO
5. Static export = no Next server routes; all API hits go to FastAPI
6. Tailwind 4.3.x lock both `tailwindcss` + `@tailwindcss/postcss` same version

## Status

- Spec: **LOCKED**
- Code Phase 1: in progress under `web-app/` + `api/main.py` user routes
