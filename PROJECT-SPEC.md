# 📜 PROJECT SPEC — IMGBOT @imgaai_bot — LOCK PRODUCTION + ANTI-RUSAK

> **File ini adalah single source of truth untuk AI sesi baru, human dev, dan future feature. WAJIB dibaca sebelum sentuh code. Melanggar = bug produksi.**

---

## 1) IDENTITAS PROJEK

- **Bot**: @imgaai_bot — `Free Image Generator` — Telegram AI image gen + edit
- **Repo**: `github.com/kiosapi/img-ai-bot` — main branch = production truth, wajib push tiap selesai fitur/bugfix
- **VPS**: `43.163.114.44 ubuntu@~/imgbot` SSH `~/.ssh/imgbot_vps` — `docker compose up -d --build` (api, bot, web, postgres)
- **Stack**: Python 3.11 aiogram 3.x + FastAPI + asyncpg + Next.js 16.2.10 + Tailwind + Postgres 16 + Docker Compose
- **Providers**: 4 aktif `apikeyfun (api.apikey.fun/v1)` + `cubence (api-dmit.cubence.com)` + `rightcodes (right.codes/draw)` + `unity2 (api.unity2.ai/v1)` — OpenAI-compat b64 image
- **Models**: 5 aktif, `ai_models` table `provider_id + is_active + is_default`, sync via `/api/models` + `/api/providers/{id}/sync-models` (SSRF guard `_is_safe_url https only`)

---

## 2) ATURAN EMAS — 0 TOLERANSI

### 2.1 Emoji Rules
- **Dashboard admin (`web/src/**/*`)**: **ZERO emoji** — semua icon via `lucide-react` only. Search `grep -rn "✅\|❌\|⚠️\|🎨\|✨\|🔥" web/src` must return empty. Pelanggaran = build masih pass tapi UX ancur per client request. Violations previously found and fixed: `✅ tidak ada stuck`, `✅ real/⚠️ fallback` → replaced with `<CheckCircle2> + <AlertTriangle>` lucide.
- **Bot Telegram (`bot/*`)**: Emoji **ALLOWED** — Telegram UX relies on emoji. But NO emoji as icon replacement for logic, only decor. All `i18n.py` texts use emoji.
- **API (`api/main.py`)**: No emoji in responses (JSON clean).

### 2.2 Bilingual ID/EN Rules
- **Dashboard**: 100% wajib bilingual via `web/src/lib/i18n.tsx`:
  ```ts
  TRANSLATIONS = { "nav.dashboard": {id:"Dashboard", en:"Dashboard"}, ... }
  useLang() { lang, setLang, t }
  FlagID = red #ED1C24 white rect SVG, FlagEN = Union Jack #012169 #C8102E SVG — NO emoji flag.
  localStorage key admin_lang persists.
  ```
  Every page title, filter, button, empty state, toast must use `lang === "id" ? "ID" : "EN"` or `t(key)`. Hardcoded string `"No data"` alone = bug.
- **Bot**: i18n via `bot/i18n.py` TEXTS dict id/en, fallback id. `t(key, lang, **kwargs)` format. User lang stored `users.lang`.

### 2.3 Realtime & Accurate Data — NO FAKE
- **System Monitor** `/api/system/stats`:
  - CPU/RAM/Disk via `psutil` in `run_in_executor` non-blocking, cpu_percent interval 0.3
  - Postgres row_counts via live SQL `SELECT count(*)`, pg_total_relation_size, pg_stat_activity real
  - Docker/processes via `/var/run/docker.sock` HTTP GET `/containers/json` + top 30 psutil if no docker
  - Frontend poll 10s, lastUpdate timestamp, pulse emerald dot, badge REALTIME
- **Bot Health** `/api/health/bot`:
  - `bot_last_heartbeat` settings table, bot `main.py` `_heartbeat_loop()` every 60s `set_setting("bot_last_heartbeat", now UTC iso)`, online if age <120s
  - gen_per_hour = `count where created_at > now()-1h`, today_gen, active_users_5m distinct, queue_stuck aiogram_states >5m, total_users — ALL live DB
  - last_generation = latest row + prompt preview 80 char real
- **Provider Latency** `/api/health/providers`:
  - httpx GET base_url 6s timeout connect 3s, **never send api key**, measure ms, status_code, error. 30s cache to avoid hammer. No key leak.
- **Live Logs** `/api/logs/tail`:
  - **MUST** be real docker logs via `asyncio.open_unix_connection /var/run/docker.sock` GET `/containers/{id}/logs?tail=N&stdout=1&stderr=1`, parse multiplexed 8-byte header (type 1 byte + 3 zero + 4 BE length). Source = `docker-socket:real:container` → UI shows ✅ + pulse.
  - docker-compose MUST mount `volumes: - /var/run/docker.sock:/var/run/docker.sock:ro`
  - Fallback DB ONLY if socket fails, must mark clearly `fallback (NOT real logs - docker unavailable)` + amber banner + explanation mount fix.
  - Previously bug `docker: docker binary not found` because python:slim no docker binary — fixed via socket method.
  - Frontend auto-refresh 5s toggle, level filter info/warn/error/debug via keyword classify, search debounce 400ms, lines selector 100/200/300/500, copy clipboard, dark mono viewer bg #0a0a0a

**NO MOCK/FAKE DATA anywhere in dashboard. If data unavailable, show error + reason, not invented number.**

### 2.4 Responsive Mobile-First
- All dashboard pages must work on mobile 320px:
  - `w-full max-w-full overflow-hidden`, `grid-cols-1 md:grid-cols-2 lg:grid-cols-4`, `flex-wrap`, `break-all`, `truncate min-w-0 flex-1`
  - Tabs `rounded-full border overflow-x-auto scrollbar-none shrink-0 px-3 sm:px-4`
  - Cards `p-3 sm:p-4`, text `text-[11px] sm:text-xs`
  - No horizontal overflow — preview on mobile before push.

### 2.5 Command Registry — Single Source of Truth (Critical Anti-Rusak)
**Problem you mentioned**: Admin has command toggle but bot has new command that admin doesn't see → desync.

**Solution — locked spec (must follow for every new command):**
- **Define in `bot/feature_flags.py`**:
  ```py
  _COMMAND_FEAT_DEFAULTS = { "myworks":"1", "batch":"1", "checkin":"1", ... } # 16 cmds min
  COMMAND_DEFS = {
    "myworks": {"group":"core","icon":"Layers","is_core":True,"desc_id":"Lihat gallery karya","desc_en":"View gallery","label":"Karya Saya"},
    ...
  }
  def is_command_enabled(name): get_setting(f"feat_command_{name}_enabled")
  ```
- **Mirror in `api/main.py`** same COMMAND_DEFS (copy, keep sync manually for now, future single JSON file)
- **Helper in `bot/db.py`** `is_command_enabled`, `set_command_enabled`, `get_command_settings_map()`
- **Add check in handler** example `handlers/myworks.py`:
  ```py
  from feature_flags import is_command_enabled
  if not await is_command_enabled("myworks"): await message.answer(feat_disabled_text); return
  ```
  Must check both message and callback entrypoints.
- **Frontend** `commands/page.tsx` auto lists from API `/api/commands` which reads COMMAND_DEFS — no hardcoded list in frontend except icon map CMD_ICON_MAP. So if new command added to backend defs, it auto appears in admin, no extra frontend code.
- **When adding new command** `/newcmd`:
  1. Add `newcmd: "1"` to `_COMMAND_FEAT_DEFAULTS` in `bot/feature_flags.py`
  2. Add entry to `COMMAND_DEFS` in both bot and api (group, icon, desc id/en, is_core)
  3. Add handler `bot/handlers/newcmd.py` with `is_command_enabled("newcmd")` guard
  4. Register router in `bot/main.py`
  5. Frontend auto picks up — no need edit commands/page.tsx except add to CMD_ICON_MAP if new icon needed (fallback to Command icon)
  6. No emoji in dashboard.

If you forget step 1-2, admin toggle won't see it. Test list endpoint after adding.

### 2.6 Dynamic Texts — No Code Edit Content
- Table `settings` generic key-value, 29 keys defined `TEXTS_DEFINITIONS` in api/main.py grouped Welcome/Help/Errors/Checkin/Referral/Premium/Balance/Subscription/Features/Inline
- API `GET /api/texts` merged defaults+settings, `POST /api/texts {key,value}` upsert with XSS block `<script`/`javascript:`, `DELETE`, audit_log
- Bot helper `bot/texts.py` `get_dynamic_text(key, fallback)` via `db.get_setting` no cache instant
- Used in `handlers/start.py` welcome/help dynamic override fallback `ui.welcome`, `generate.py` busy/maintenance/quota, `subscription.py` join_required_msg
- Frontend `texts/page.tsx` grouped textarea auto-grow search preview save toast — ID/EN chrome content user-editable raw (may include HTML <b><i><code>)

### 2.7 Styles Presets — No Code Edit Visuals
- Table `custom_styles` (id, code UNIQUE regex ^[a-z0-9_-]{1,30}$, name max100, prompt_prefix max500, thumbnail_url https safe, category 1-30 alnum_-, is_active bool, sort_order int, created_at)
- Seed 11 from hardcoded styles.py if table empty
- API CRUD + search ILIKE + category/active filter + reorder bulk sort_order + toggle patch
- Frontend grid mobile 2col desktop 4col thumbnail fallback ImageIcon badges active/category/sort, add/edit modal, delete confirm toggle
- Bot `db.get_custom_styles(active_only)` to apply

---

## 3) KONFIGURASI

- `bot/config.py`:
  ALLOWED_SIZES 7: 1024x1024 1:1, 1024x1792 9:16, 1792x1024 16:9, 1024x1536 2:3, 1536x1024 3:2, 1152x1536 3:4, 1536x1152 4:3 + ASPECT_MAP + ALLOWED_BATCHES [1,2,4] DEFAULT_BATCH 1, DEFAULT_NEGATIVE "", DEFAULT_SEED None, IMAGE_MODEL gpt-image-2

- DB `bot/db.py` migrations (ensure tables):
  users(id, username, lang, is_premium, premium_until, is_banned, daily_limit override, created_at), usage_daily(user_id,date,count), generations(id,user_id,prompt,kind,success,created_at,size,batch_id,negative_prompt,seed,ref_file_id,result_file_id), settings(key PK value text), plans, payment_methods, orders, deposits(id,user_id,amount,method_id,status,proof_file_id), balance_logs, referrals, aiogram_states, sticker_packs, providers(id,name,base_url,is_active), ai_models(id,provider_id,name,model_id,is_active,is_default,sort_order), broadcast_history, admin_sessions(id,expires_at), admin_audit(id,ts,action,target,detail), custom_styles

- Feature flags defaults:
  feat_enhance_enabled 1, feat_batch_enabled 1, feat_watermark_enabled 0, feat_sticker_enabled 1, feat_checkin_enabled 1, feat_model_enabled, feat_command_{name}_enabled 1 each

---

## 4) BOT ARSITEKTUR

- Handlers:
  start.py (welcome/menu/help/lang), generate.py (text->image + size/batch/neg/seed/ref atomic check_and_consume_multi + media_group + watermark + bufferedInputFile), edit.py (photo+caption edit + regen/var/hd/editthis/enhance IDOR ownership check gen.user_id==callback.from_user.id + html.escape), sticker.py (convert gen to sticker pack IDOR owner), myworks.py (list text pagination 10 first then view:{id} answer_photo only no media_group auto), batch.py (x4 IDOR owner + atomic quota ALLOWED_BATCHES validation), checkin.py (streak bonus 1/2/5/20), balance.py (topup amount re-validate min/max + pending limit 3 + flood + file_id bot-isolated), premium.py, model.py (pick model), style.py, inline.py (inline_query middleware subscription+ban gate return empty if not, no leak gallery)
- Middleware: subscription (check channel join REQUIRED_CHANNEL, dynamic messages, admin bypass), maintenance (feat flag), gen_queue.py GenQueue SimpleQueue anti-spam per user (DO NOT use stdlib queue.SimpleQueue collides asyncio)
- Providers: providers.py router + cubence.py + rightcodes.py + apikeyfun.py + unity2.py (verified POST 200 b64 2.3MB 31s host, GET /v1/models 5 models)
- Watermark v2 premium: text-only @imgaai_bot, no icon/emoji/"Buat di", font stack SpaceGrotesk/Manrope/Satoshi, frosted glass pill blur(18,18,19,196) highlight (255,255,255,22) stroke 28, cap 58% width, enforced via WATERMARK_DEFAULT override DB legacy "Buat di @imgaai_bot"
- Security hardened (19 findings fixed): IDOR ownership all gen_id callbacks, inline bypass middleware gate, batch quota atomic pg_advisory_xact_lock + FOR UPDATE, login bruteforce throttler 10/min 429 cookie samesite=strict httponly, free_text private only, negative strip tags re.sub <[^>]+> + 500 cap seed numeric, size whitelist ALLOWED_SIZES + batch ALLOWED_BATCHES validation, order/deposit proof FOR UPDATE prevent double-spend race, balance TOCTOU, broadcast lock + 30s cooldown + semaphore 20 + _sanitize_html whitelist b,i,u,s,code,pre + scheme https/http/t.me only block javascript:/data:/vbscript:, SSRF base_url whitelist https + domains apikey.fun/cubence/rightcodes/unity2 + regex id ^[a-z0-9_-]{1,50}$, apikeys/providers mask no partial leak, q length le100 anti DoS, upload chat_id whitelist service chat only, XSS broadcast/page.tsx renderPreview javascript: block

- Config ALLOWED_SIZES 7 + ASPECT_MAP + ALLOWED_BATCHES [1,2,4] + batch_id UUID + media_group delay 1.2s anti ratelimit
- i18n bot: emoji allowed, t(key,lang,**kwargs)

---

## 5) ADMIN DASHBOARD

- Stack Next.js 16.2.10 static standalone build, Tailwind, shadcn-like Card/Badge/Button/Switch/ConfirmDialog
- Auth: /api/login throttler 10/min IP list + 429, secure cookie samesite=strict httponly, session admin_sessions expires, me check, logout delete
- Security headers middleware: X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy strict-origin-when-cross-origin, Permissions-Policy camera=(), CSP default-src 'none' frame-ancestors 'none'
- Pages (18):
  / (dashboard stats + chart), /analytics (gen hourly/daily/top prompts/errors robust fallback Array.isArray check), /system (CPU/RAM/Disk/Postgres/docker realtime 10s), /health (bot heartbeat/providers realtime 10s restart ConfirmDialog), /users (ban toggle), /broadcast (HTML sanitize scheme whitelist javascript: block upload silent+delete fix lock+cooldown 30s renderPreview XSS block), /referral (settings), /models (provider + model CRUD + sync-models SSRF guard + active/default toggle + ping), /errors (failed today client calc + XCircle red pill), /logs (docker.sock socket realtime multiplexed stream responsive mobile scrollbar-none rounded-full tabs), /settings (generic settings keys), /audit (audit logs 200 table Badge muted/destructive), /deposits (approve/reject), /orders (approve/reject double-spend FOR UPDATE), /plans, /payments, /balance-settings, /texts (29 keys grouped), /styles-manage (gallery grid), /commands (toggle Switch emerald/muted ON/OFF badge CheckCircle2/XCircle groups CORE)
- All pages ID/EN full via useLang t(), FlagID red/white rect FlagEN Union Jack SVG, toggle localStorage admin_lang, must translate all
- Nav groups in shell.tsx: General (dashboard, analytics, system, health, users, broadcast, referral, models, styles-manage, texts, commands, errors, logs, settings, audit) + Premium (orders, plans, payments) + Balance (deposits, balance-settings)
- Check before commit: grep emoji `CLEAN NO EMOJI` in web/src must be clean after every change (except if in comments explaining emoji block list, still avoid).

---

## 6) DEPLOYMENT + GITHUB SYNC

- Local: C:\Users\tiwdv\imgbot main branch
- Every fix must `git add -A && git commit -m "feat/fix: ..." && git push origin main` — previously 33 files modified not pushed caught by user, fix by adding *.tar.gz to .gitignore `deploy_*.tar.gz` + `*.tar.gz` not commit
- VPS deploy: tar czf + scp + tar xzf + docker compose up -d --build api bot web (postgres no rebuild unless migration). Verify logs `docker logs --tail 10`.
- Env: .env on VPS contains BOT_TOKEN, DATABASE_URL constructed via ${POSTGRES_PASSWORD} NOT *** (bug previously "***" broke api auth), PROVIDER keys etc
- Always clean tar archives after deploy `rm -f *.tar.gz`

---

## 7) PHASE ROADMAP (12 fitur)

- Phase1 Observability DONE commit beeb5f7..007c3b7 — System Monitor + Bot Health + Live Logs
- Phase2 No-Code Content DONE commit d08a7b2..87e4bd3 — Dynamic Texts 29 keys + Styles CRUD gallery + Command Manager 16 cmds toggle
- Phase3 Security & Failover NEXT:
  7 Blocklist / Moderation Manager — list kata dilarang regex prompt NSFW threshold auto-reject log moderation_logs
  8 Provider Failover Config — drag&drop priority provider + retry count timeout per provider cost per gen + Test Ping button real latency
  9 Alert Webhook — Discord/Telegram alert if error rate >10% / deposit pending >20 / CPU >90%
- Phase4 Monetization:
  10 Cost Tracker — modal per gen per provider profit from deposits/orders chart profit/day model paling boros
  11 Broadcast Scheduler — jadwal kirim cron repeat weekly preview retry failed
  12 Backup & Restore 1-Klik — pg_dump download + auto backup harian ke R2

Report each phase DONE + commit hash + realtime proof.

---

## 8) WHEN ADDING NEW FEATURE — CHECKLIST (ANTI-RUSAK)

- [ ] Zero emoji in web/src — grep.
- [ ] ID/EN full — add keys to i18n.tsx TRANSLATIONS + use lang===id ? ID : EN everywhere, no hardcoded EN/ID string alone.
- [ ] Responsive mobile — test 320px, w-full overflow-hidden break-all truncate flex-wrap grid-cols-1
- [ ] Realtime accurate — no fake mock, if docker/socket needed mount ro + parse real, if DB query live SQL, show source badge + pulse + lastUpdate
- [ ] Lucide icons only — no emoji as icons, import from lucide-react
- [ ] Command registry — if new bot command, add to COMMAND_DEFS bot + api + db + handler guard is_command_enabled, frontend auto lists
- [ ] API validation — Pydantic Field ge/le pattern regex id ^[a-z0-9_-]{1,50}$, q length le100, amount ge0 le100M, base_url https only SSRF safe_url check private IPs block, file_id regex ^[A-Za-z0-9_-]{20,400}$
- [ ] Security — ownership check gen.user_id==callback.from_user.id all gen_id callbacks, rate limit, cookie secure, sanitize HTML whitelist, block javascript:
- [ ] DB migration — CREATE TABLE IF NOT EXISTS in both api/main.py _ensure_settings_table + bot/db.py, seed if empty, index
- [ ] Shell nav + i18n nav key + Icon import (Command, Palette, FileText etc)
- [ ] py_compile bot + api + api compile, Next build `npm run build` passes (no duplicate key duplicate nav.texts etc)
- [ ] Git push origin main immediately after local succeed — git log -1 == remote HEAD
- [ ] VPS deploy tar + scp + docker compose build + logs tail verify healthy
- [ ] Pinned memory? No, skill is procedure — but update this file if architecture changes.

---

## 9) TODOS PENDING (from user)

- Rotasi key unity2 [REDACTED] exposed — must rotate ASAP (user asked, still pending)
- Phase3,4 roadmap remaining
- Optional: Secure cookie True + __Host- prefix behind Cloudflare
- Optional: html.escape first_name welcome

---

## 10) CONTACTS / CHANNELS

- Channel required: @imgaai_official (REQUIRED_CHANNEL env)
- Discord report: 1523578174263267468 (for auto-post etc but this repo bot only)
- User lang: Indonesian informal gua/lo via Discord, wants assistant handle full push+deploy VPS, user just test.

---

END OF SPEC — Any new session must read this first, no excuses.
