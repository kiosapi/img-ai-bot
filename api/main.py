"""JSON API for the admin dashboard (FastAPI). Consumed by the Next.js frontend."""
import asyncio
import os
import secrets
import asyncpg
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, HTTPException, Depends
from pydantic import BaseModel

DATABASE_URL = os.environ["DATABASE_URL"]
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ["ADMIN_PASS"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
DEFAULT_DAILY_LIMIT = int(os.environ.get("DEFAULT_DAILY_LIMIT", "20"))
REQUIRED_CHANNEL = os.environ.get("REQUIRED_CHANNEL", "")
SESSION_SECRET = os.environ.get("DASH_SECRET", secrets.token_hex(16))
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]

_pool: asyncpg.Pool | None = None

# ---- DB-backed session table ----

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with _pool.acquire() as con:
        await con.execute(
            "CREATE TABLE IF NOT EXISTS admin_sessions ("
            " token TEXT PRIMARY KEY,"
            " created_at TIMESTAMPTZ NOT NULL DEFAULT now(),"
            " expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + interval '7 days')"
        )
        await con.execute("DELETE FROM admin_sessions WHERE expires_at < now()")
        # --- auto-migrate ENV API keys -> settings table if not present (fix X status) ---
        try:
            env_cub_key = os.environ.get("CUBENCE_API_KEY", "").strip()
            env_cub_base = os.environ.get("CUBENCE_BASE_URL", "").strip()
            if env_cub_key:
                await con.execute(
                    "INSERT INTO settings (key,value) VALUES ('cubence_api_key',$1) ON CONFLICT (key) DO NOTHING",
                    env_cub_key,
                )
            if env_cub_base:
                await con.execute(
                    "INSERT INTO settings (key,value) VALUES ('cubence_base_url',$1) ON CONFLICT (key) DO NOTHING",
                    env_cub_base,
                )
            env_rc_key = os.environ.get("RIGHTCODES_API_KEY", os.environ.get("RIGHT_CODES_API_KEY", "")).strip()
            env_rc_base = os.environ.get("RIGHTCODES_BASE_URL", os.environ.get("RIGHT_CODES_BASE_URL", "")).strip()
            if env_rc_key:
                await con.execute(
                    "INSERT INTO settings (key,value) VALUES ('rightcodes_api_key',$1) ON CONFLICT (key) DO NOTHING",
                    env_rc_key,
                )
            if env_rc_base:
                await con.execute(
                    "INSERT INTO settings (key,value) VALUES ('rightcodes_base_url',$1) ON CONFLICT (key) DO NOTHING",
                    env_rc_base,
                )
            # ensure default base_url settings if missing
            await con.execute(
                "INSERT INTO settings (key,value) VALUES ('rightcodes_base_url','https://www.right.codes/draw') ON CONFLICT (key) DO NOTHING"
            )
            await con.execute(
                "INSERT INTO settings (key,value) VALUES ('cubence_base_url','https://api-dmit.cubence.com') ON CONFLICT (key) DO NOTHING"
            )
            # --- production fix: model ID collision across providers ---
            # add external_id column if missing
            await con.execute("ALTER TABLE ai_models ADD COLUMN IF NOT EXISTS external_id TEXT;")
            # backfill external_id from id for old rows where external_id null
            await con.execute("UPDATE ai_models SET external_id = id WHERE external_id IS NULL;")
            # ensure providers table has base_url fallback from settings
            await con.execute(
                "UPDATE providers SET base_url = COALESCE((SELECT value FROM settings WHERE key = providers.id || '_base_url'), base_url) WHERE base_url IS NULL OR base_url = ''"
            )
        except Exception as _e:
            # don't crash startup
            print(f"warn lifespan migration: {_e}")
    yield
    if _pool:
        await _pool.close()


app = FastAPI(title="ImageBot Admin API", lifespan=lifespan)


async def require_auth(request: Request):
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="unauthorized")
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "SELECT 1 FROM admin_sessions WHERE token=$1 AND expires_at > now()", token)
    if not row:
        raise HTTPException(status_code=401, detail="unauthorized")
    return True


async def get_setting(key, default=None):
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT value FROM settings WHERE key=$1", key)
        return row["value"] if row else default


async def set_setting(key, value):
    async with _pool.acquire() as con:
        await con.execute(
            "INSERT INTO settings (key,value) VALUES ($1,$2) "
            "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
            key, str(value))


# ---------------- Auth ----------------
class LoginBody(BaseModel):
    username: str
    password: str


@app.post("/api/login")
async def login(body: LoginBody, response: Response):
    ok = (secrets.compare_digest(body.username, ADMIN_USER)
          and secrets.compare_digest(body.password, ADMIN_PASS))
    if not ok:
        raise HTTPException(status_code=401, detail="Username atau password salah")
    token = secrets.token_urlsafe(32)
    async with _pool.acquire() as con:
        await con.execute(
            "INSERT INTO admin_sessions (token, expires_at) VALUES ($1, now() + interval '7 days')", token)
    response.set_cookie("session", token, httponly=True, samesite="lax", max_age=86400*7)
    return {"ok": True}


@app.post("/api/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session")
    if token:
        async with _pool.acquire() as con:
            await con.execute("DELETE FROM admin_sessions WHERE token=$1", token)
    response.delete_cookie("session")
    return {"ok": True}


@app.get("/api/me")
async def me(_: bool = Depends(require_auth)):
    return {"user": ADMIN_USER}

# ---------------- Stats & chart ----------------
@app.get("/api/stats")
async def stats(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        total_users = await con.fetchval("SELECT count(*) FROM users") or 0
        today_gen = await con.fetchval(
            "SELECT count(*) FROM generations WHERE created_at::date=CURRENT_DATE") or 0
        total_gen = await con.fetchval("SELECT count(*) FROM generations") or 0
        active_today = await con.fetchval(
            "SELECT count(DISTINCT user_id) FROM generations WHERE created_at::date=CURRENT_DATE") or 0
        banned = await con.fetchval("SELECT count(*) FROM users WHERE is_banned") or 0
        success_rate = await con.fetchval(
            "SELECT ROUND(100.0*count(*) FILTER (WHERE success)/NULLIF(count(*),0)) FROM generations") or 0
        recent = await con.fetch(
            "SELECT g.user_id,g.kind,g.prompt,g.success,g.created_at,u.username "
            "FROM generations g LEFT JOIN users u ON u.user_id=g.user_id "
            "ORDER BY g.id DESC LIMIT 12")
    return {
        "total_users": total_users, "today_gen": today_gen, "total_gen": total_gen,
        "active_today": active_today, "banned": banned, "success_rate": int(success_rate),
        "recent": [dict(r) for r in recent],
    }


@app.get("/api/chart")
async def chart(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch(
            "SELECT d::date AS day, "
            "COALESCE((SELECT count(*) FROM generations g WHERE g.created_at::date=d::date),0) AS gen, "
            "COALESCE((SELECT count(DISTINCT user_id) FROM generations g WHERE g.created_at::date=d::date),0) AS users "
            "FROM generate_series(CURRENT_DATE-6, CURRENT_DATE, '1 day') d ORDER BY day")
    return [{"day": r["day"].strftime("%d/%m"), "gen": r["gen"], "users": r["users"]} for r in rows]

# ---------------- Users ----------------
@app.get("/api/users")
async def list_users(q: str = "", _: bool = Depends(require_auth)):
    q = (q or "").strip()
    async with _pool.acquire() as con:
        if q:
            like = f"%{q}%"
            rows = await con.fetch(
                """
                SELECT u.user_id, u.username, u.first_name, u.is_banned, u.created_at, u.balance, u.lang,
                       (SELECT count(*) FROM generations g WHERE g.user_id = u.user_id) AS gen_count
                FROM users u
                WHERE u.username ILIKE $1 OR u.first_name ILIKE $1 OR CAST(u.user_id AS TEXT) LIKE $1
                ORDER BY gen_count DESC, u.created_at DESC
                LIMIT 200
                """,
                like,
            )
        else:
            rows = await con.fetch(
                """
                SELECT u.user_id, u.username, u.first_name, u.is_banned, u.created_at, u.balance, u.lang,
                       (SELECT count(*) FROM generations g WHERE g.user_id = u.user_id) AS gen_count
                FROM users u
                ORDER BY gen_count DESC, u.created_at DESC
                LIMIT 200
                """
            )
    return [dict(r) for r in rows]


class BanBody(BaseModel):
    user_id: int
    banned: bool


@app.post("/api/users/ban")
async def ban_user(body: BanBody, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        await con.execute("UPDATE users SET is_banned=$2 WHERE user_id=$1", body.user_id, body.banned)
    return {"ok": True}


# ---------------- Broadcast ----------------
class BroadcastBody(BaseModel):
    message: str
    audience: str = "all"  # all | premium | free
    image_file_id: str | None = None  # optional Telegram file_id (if provided, sent as photo with caption)
    button_text: str | None = None    # optional inline button label
    button_url: str | None = None     # optional inline button URL (must be http(s)://)


def _audience_where(audience: str) -> str:
    if audience == "premium":
        return "WHERE NOT is_banned AND premium_until > now()"
    if audience == "free":
        return "WHERE NOT is_banned AND (premium_until IS NULL OR premium_until <= now())"
    return "WHERE NOT is_banned"


def _build_inline_keyboard(button_text: str | None, button_url: str | None) -> str | None:
    """Build the JSON-encoded reply_markup that Telegram's API expects. Returns
    None if the button is incomplete/invalid; the caller should treat that as
    'no button' rather than sending a malformed payload to Telegram.
    """
    if not button_text or not button_url:
        return None
    text = button_text.strip()[:64]
    url = button_url.strip()
    if not (url.startswith("http://") or url.startswith("https://") or url.startswith("t.me/")):
        return None
    if not text:
        return None
    import json
    return json.dumps({"inline_keyboard": [[{"text": text, "url": url}]]})


def _sanitize_html(s: str) -> str:
    """Telegram's HTML parser is strict. We only allow <b>, <i>, <u>, <s>, <a>, <code>, <pre>.
    Any other tag gets stripped, plus we always escape & < > first to avoid injection.
    """
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Re-open the small whitelist tags from their escaped form so users can still use them.
    return (
        s.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
         .replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")
         .replace("&lt;u&gt;", "<u>").replace("&lt;/u&gt;", "</u>")
         .replace("&lt;s&gt;", "<s>").replace("&lt;/s&gt;", "</s>")
         .replace("&lt;code&gt;", "<code>").replace("&lt;/code&gt;", "</code>")
         .replace("&lt;pre&gt;", "<pre>").replace("&lt;/pre&gt;", "</pre>")
    )


@app.get("/api/broadcast/audience-counts")
async def broadcast_audience_counts(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        all_c = await con.fetchval("SELECT count(*) FROM users " + _audience_where("all")) or 0
        premium_c = await con.fetchval("SELECT count(*) FROM users " + _audience_where("premium")) or 0
        free_c = await con.fetchval("SELECT count(*) FROM users " + _audience_where("free")) or 0
    return {"all": all_c, "premium": premium_c, "free": free_c}


@app.get("/api/broadcast/history")
async def broadcast_history(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch(
            "SELECT id, message, audience, sent, total, image_file_id, button_text, button_url, created_at "
            "FROM broadcast_history ORDER BY id DESC LIMIT 20")
    return {"history": [dict(r) for r in rows]}


# Accepts an uploaded image and uploads it to the bot's "service" chat so we
# can store a reusable Telegram file_id (no VPS storage of any pixel data,
# consistent with the rest of this project). The file_id can then be used in
# future broadcasts. Requires admin auth.
@app.post("/api/broadcast/upload-image")
async def broadcast_upload_image(request: Request, _: bool = Depends(require_auth)):
    """Upload an image to the bot (stored as Telegram file_id, NOT on VPS).
    Form fields: file (binary image), chat_id (optional target chat for the upload;
    defaults to the first admin's user_id so the image is owned by the bot itself).
    Returns: {ok, file_id, width, height}
    """
    form = await request.form()
    upload = form.get("file")
    if not upload or not getattr(upload, "file", None):
        raise HTTPException(status_code=400, detail="File gambar wajib diisi")
    target_chat = form.get("chat_id")
    if target_chat:
        try:
            target_chat = int(target_chat)
        except (TypeError, ValueError):
            target_chat = None
    if not target_chat:
        if not ADMIN_IDS:
            raise HTTPException(status_code=400,
                detail="ADMIN_IDS belum diset di server, tidak bisa upload gambar broadcast")
        target_chat = ADMIN_IDS[0]
    contents = await upload.read()
    if not contents:
        raise HTTPException(status_code=400, detail="File kosong")
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran gambar maks 10MB")
    async with httpx.AsyncClient(timeout=60) as client:
        files = {"photo": (upload.filename or "broadcast.jpg", contents, upload.content_type or "image/jpeg")}
        resp = await client.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={"chat_id": str(target_chat)},
            files=files)
    data = resp.json()
    if not data.get("ok"):
        raise HTTPException(status_code=400,
            detail=f"Telegram menolak upload: {data.get('description', 'unknown error')}")
    photo = data["result"]["photo"][-1]  # highest resolution variant
    return {"ok": True, "file_id": photo["file_id"],
            "width": photo.get("width"), "height": photo.get("height")}


@app.post("/api/broadcast")
async def broadcast(body: BroadcastBody, _: bool = Depends(require_auth)):
    audience = body.audience if body.audience in ("all", "premium", "free") else "all"
    text = _sanitize_html(body.message)[:4096]
    reply_markup = _build_inline_keyboard(body.button_text, body.button_url)
    has_image = bool(body.image_file_id)
    async with _pool.acquire() as con:
        rows = await con.fetch("SELECT user_id FROM users " + _audience_where(audience))
    if not rows:
        async with _pool.acquire() as con:
            await con.execute(
                "INSERT INTO broadcast_history "
                "(message, audience, sent, total, image_file_id, button_text, button_url) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7)",
                body.message, audience, 0, 0,
                body.image_file_id, body.button_text, body.button_url)
        return {"ok": True, "sent": 0, "total": 0}

    # Parallel send with semaphore (respect Telegram rate limits ~30 msg/sec).
    # Use asyncio with concurrency cap to avoid hammering Telegram / exhausting sockets.
    sem = asyncio.Semaphore(20)
    sent_counter = 0
    lock = asyncio.Lock()

    async def _send_one(client: httpx.AsyncClient, uid: int):
        nonlocal sent_counter
        async with sem:
            try:
                if has_image:
                    payload = {
                        "chat_id": uid, "photo": body.image_file_id,
                        "caption": text, "parse_mode": "HTML",
                    }
                    method = "sendPhoto"
                else:
                    payload = {
                        "chat_id": uid, "text": text, "parse_mode": "HTML",
                    }
                    method = "sendMessage"
                if reply_markup:
                    payload["reply_markup"] = reply_markup
                resp = await client.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", json=payload)
                if resp.status_code == 200 and resp.json().get("ok"):
                    async with lock:
                        sent_counter += 1
                elif resp.status_code == 429:
                    # Telegram rate limit — backoff
                    try:
                        retry_after = resp.json().get("parameters", {}).get("retry_after", 1)
                    except Exception:
                        retry_after = 1
                    await asyncio.sleep(float(retry_after))
            except Exception:
                pass

    async with httpx.AsyncClient(timeout=30, limits=httpx.Limits(max_connections=30)) as client:
        tasks = [_send_one(client, r["user_id"]) for r in rows]
        await asyncio.gather(*tasks)

    sent = sent_counter
    async with _pool.acquire() as con:
        await con.execute(
            "INSERT INTO broadcast_history "
            "(message, audience, sent, total, image_file_id, button_text, button_url) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7)",
            body.message, audience, sent, len(rows),
            body.image_file_id, body.button_text, body.button_url)
    return {"ok": True, "sent": sent, "total": len(rows)}


# ---------------- Settings ----------------
@app.get("/api/settings")
async def get_settings(_: bool = Depends(require_auth)):
    limit = await get_setting("daily_limit", str(DEFAULT_DAILY_LIMIT))
    maint = await get_setting("maintenance", "0")
    # feature flags full set
    ff_keys = ["feat_enhance_enabled","feat_batch_enabled","feat_watermark_enabled","watermark_text","watermark_free_only","enhance_model","batch_limit_free","batch_limit_premium","feat_sticker_enabled","sticker_max_per_pack","feat_checkin_enabled","feat_inline_enabled","feat_myworks_enabled","feat_style_enabled","feat_queue_enabled"]
    ff_vals = {}
    for k in ff_keys:
        v = await get_setting(k, "")
        ff_vals[k] = v
    return {"daily_limit": int(limit), "maintenance": maint == "1",
            "channel": REQUIRED_CHANNEL, "model": "gpt-image-2", "features": ff_vals}


class SettingsBody(BaseModel):
    daily_limit: int
    maintenance: bool


@app.post("/api/settings")
async def save_settings(body: SettingsBody, _: bool = Depends(require_auth)):
    await set_setting("daily_limit", max(0, body.daily_limit))
    await set_setting("maintenance", "1" if body.maintenance else "0")
    return {"ok": True}


# ---------- Feature Flags full control ----------
class FeatureFlagsBody(BaseModel):
    feat_enhance_enabled: str | None = None
    feat_batch_enabled: str | None = None
    feat_watermark_enabled: str | None = None
    watermark_text: str | None = None
    watermark_free_only: str | None = None
    enhance_model: str | None = None
    batch_limit_free: str | None = None
    batch_limit_premium: str | None = None
    feat_sticker_enabled: str | None = None
    sticker_max_per_pack: str | None = None
    feat_checkin_enabled: str | None = None
    feat_inline_enabled: str | None = None
    feat_myworks_enabled: str | None = None
    feat_style_enabled: str | None = None
    feat_queue_enabled: str | None = None


@app.get("/api/features")
async def get_features(_: bool = Depends(require_auth)):
    defaults = {
        "feat_enhance_enabled": "1",
        "feat_batch_enabled": "1",
        "feat_watermark_enabled": "0",
        "watermark_text": "Buat di @imgaai_bot",
        "watermark_free_only": "1",
        "enhance_model": "gpt-4o-mini",
        "batch_limit_free": "1",
        "batch_limit_premium": "4",
        "feat_sticker_enabled": "1",
        "sticker_max_per_pack": "10",
        "feat_checkin_enabled": "1",
        "feat_inline_enabled": "1",
        "feat_myworks_enabled": "1",
        "feat_style_enabled": "1",
        "feat_queue_enabled": "1",
    }
    out = {}
    for k, dv in defaults.items():
        v = await get_setting(k, dv)
        if v is None or v == "":
            v = dv
        out[k] = v
    return out


@app.post("/api/features")
async def save_features(body: FeatureFlagsBody, _: bool = Depends(require_auth)):
    data = body.model_dump(exclude_none=True)
    for k, v in data.items():
        # sanitize: strip
        sv = str(v).strip()[:500]
        await set_setting(k, sv)
    return {"ok": True, "saved": list(data.keys())}


# ---------------- Providers & Models (multi-provider) ----------------
class ProviderSaveBody(BaseModel):
    id: str
    name: str | None = None
    base_url: str
    is_active: bool = True


class ApiKeySaveBody(BaseModel):
    provider_id: str  # cubence | rightcodes
    api_key: str
    base_url: str | None = None


class ModelSaveBody(BaseModel):
    id: str  # can be real model id like gpt-image-2 OR composite cubence:gpt-image-2
    provider_id: str
    display_name: str
    description: str | None = None
    is_active: bool = True
    is_default: bool = False
    sort_order: int = 0
    capabilities: dict | None = None
    external_id: str | None = None  # if not provided, derived from id


def _normalize_model_ids(raw_id: str, provider_id: str, external_id: str | None = None) -> tuple[str, str]:
    """Return (internal_id, external_id) where internal_id = provider:external collision-safe"""
    ext = external_id or raw_id
    # if raw_id already composite provider:ext, keep
    if ":" in raw_id:
        parts = raw_id.split(":", 1)
        # if first part matches provider, use as is
        if parts[0] == provider_id:
            return raw_id, parts[1]
        # else treat raw_id as external anyway
    ext_clean = ext.split(":", 1)[-1] if ":" in ext else ext
    internal = f"{provider_id}:{ext_clean}"
    return internal, ext_clean


@app.get("/api/providers")
async def api_list_providers(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch("SELECT * FROM providers ORDER BY id")
        # also attach apikey existence (masked)
        settings_rows = await con.fetch("SELECT key, value FROM settings WHERE key LIKE '%_api_key' OR key LIKE '%_base_url'")
        smap = {r["key"]: r["value"] for r in settings_rows}
    out = []
    for r in rows:
        d = dict(r)
        pid = d["id"]
        ak_key = f"{pid}_api_key"
        bu_key = f"{pid}_base_url"
        raw_key = smap.get(ak_key, "")
        masked = (raw_key[:6] + "***" + raw_key[-4:]) if len(raw_key) > 10 else ("***" if raw_key else "")
        out.append({**d, "has_api_key": bool(raw_key), "api_key_masked": masked, "api_key_setting_key": ak_key, "base_url_setting": smap.get(bu_key, d.get("base_url", ""))})
    return out


@app.post("/api/providers")
async def api_save_provider(body: ProviderSaveBody, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        await con.execute(
            """
            INSERT INTO providers (id, name, base_url, is_active, updated_at)
            VALUES ($1,$2,$3,$4, now())
            ON CONFLICT (id) DO UPDATE SET name=COALESCE(EXCLUDED.name, providers.name), base_url=$3, is_active=$4, updated_at=now()
            """,
            body.id, body.name or body.id, body.base_url, body.is_active,
        )
    return {"ok": True}


@app.get("/api/models")
async def api_list_models(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch(
            "SELECT m.*, p.name as provider_name, p.is_active as provider_active FROM ai_models m LEFT JOIN providers p ON p.id=m.provider_id ORDER BY p.id, m.sort_order, m.display_name"
        )
    return [dict(r) for r in rows]


@app.post("/api/models")
async def api_save_model(body: ModelSaveBody, _: bool = Depends(require_auth)):
    import json as _json
    async with _pool.acquire() as con:
        prov = await con.fetchrow("SELECT id FROM providers WHERE id=$1", body.provider_id)
        if not prov:
            raise HTTPException(status_code=400, detail=f"Provider {body.provider_id} tidak ditemukan")
        if body.is_default:
            await con.execute("UPDATE ai_models SET is_default=false WHERE provider_id=$1", body.provider_id)
        internal_id, external_id = _normalize_model_ids(body.id, body.provider_id, body.external_id)
        await con.execute(
            """
            INSERT INTO ai_models (id, provider_id, external_id, display_name, description, is_active, is_default, sort_order, capabilities, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb, now())
            ON CONFLICT (id) DO UPDATE SET provider_id=$2, external_id=$3, display_name=$4, description=$5, is_active=$6, is_default=$7, sort_order=$8, capabilities=$9::jsonb, updated_at=now()
            """,
            internal_id, body.provider_id, external_id, body.display_name, body.description, body.is_active, body.is_default, body.sort_order, _json.dumps(body.capabilities or {}),
        )
    return {"ok": True, "id": internal_id, "external_id": external_id}


@app.delete("/api/models/{model_id}")
async def api_delete_model(model_id: str, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        await con.execute("DELETE FROM ai_models WHERE id=$1", model_id)
    return {"ok": True}


@app.post("/api/models/{model_id}/default")
async def api_set_default_model(model_id: str, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT provider_id FROM ai_models WHERE id=$1", model_id)
        if not row:
            raise HTTPException(status_code=404, detail="Model not found")
        pid = row["provider_id"]
        await con.execute("UPDATE ai_models SET is_default=false WHERE provider_id=$1", pid)
        await con.execute("UPDATE ai_models SET is_default=true WHERE id=$1", model_id)
    return {"ok": True}


@app.post("/api/models/{model_id}/toggle")
async def api_toggle_model(model_id: str, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        await con.execute("UPDATE ai_models SET is_active = NOT is_active WHERE id=$1", model_id)
        row = await con.fetchrow("SELECT is_active FROM ai_models WHERE id=$1", model_id)
    return {"ok": True, "is_active": row["is_active"] if row else False}


@app.post("/api/providers/{provider_id}/toggle")
async def api_toggle_provider(provider_id: str, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        await con.execute("UPDATE providers SET is_active = NOT is_active, updated_at=now() WHERE id=$1", provider_id)
        row = await con.fetchrow("SELECT is_active FROM providers WHERE id=$1", provider_id)
    return {"ok": True, "is_active": row["is_active"] if row else False}


@app.get("/api/apikeys")
async def api_list_apikeys(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch("SELECT key, value FROM settings WHERE key IN ('cubence_api_key','cubence_base_url','rightcodes_api_key','rightcodes_base_url')")
    smap = {r["key"]: r["value"] for r in rows}
    out = []
    for pid in ["cubence", "rightcodes"]:
        ak = smap.get(f"{pid}_api_key", "")
        bu = smap.get(f"{pid}_base_url", "")
        masked = (ak[:8] + "***" + ak[-6:]) if len(ak) > 16 else ("***" if ak else "")
        out.append({"provider_id": pid, "has_key": bool(ak), "masked": masked, "base_url": bu, "api_key_length": len(ak)})
    return out


@app.post("/api/apikeys")
async def api_save_apikey(body: ApiKeySaveBody, _: bool = Depends(require_auth)):
    if body.provider_id not in ("cubence", "rightcodes"):
        raise HTTPException(status_code=400, detail="provider_id must be cubence or rightcodes")
    key_name = f"{body.provider_id}_api_key"
    base_name = f"{body.provider_id}_base_url"
    # save
    if body.api_key and body.api_key != "***":
        await set_setting(key_name, body.api_key.strip())
    if body.base_url:
        await set_setting(base_name, body.base_url.strip().rstrip("/"))
    return {"ok": True}


@app.post("/api/providers/{provider_id}/sync-models")
async def api_sync_models(provider_id: str, _: bool = Depends(require_auth)):
    if provider_id not in ("cubence", "rightcodes"):
        raise HTTPException(status_code=400, detail="Unknown provider")
    # resolve credentials from settings
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT value FROM settings WHERE key=$1", f"{provider_id}_api_key")
        api_key = row["value"] if row else ""
        row2 = await con.fetchrow("SELECT value FROM settings WHERE key=$1", f"{provider_id}_base_url")
        base_url = row2["value"] if row2 and row2["value"] else ("https://api-dmit.cubence.com" if provider_id == "cubence" else "https://www.right.codes/draw")
        if not api_key:
            # fallback env for cubence
            if provider_id == "cubence":
                import os
                api_key = os.environ.get("CUBENCE_API_KEY", "")
            if not api_key:
                raise HTTPException(status_code=400, detail=f"API key untuk {provider_id} belum di-set di admin")

    # list remote
    import httpx as _httpx

    def _site_base(b: str) -> str:
        bb = b.rstrip("/")
        if bb.endswith("/draw"):
            return bb[:-5]
        if "/draw" in bb:
            return bb.split("/draw")[0]
        return bb

    draw_base = base_url.rstrip("/")
    if provider_id == "rightcodes" and not draw_base.endswith("/draw") and "/draw" not in draw_base:
        draw_base = draw_base + "/draw"
    site_base = _site_base(draw_base)

    candidates = []
    if provider_id == "cubence":
        candidates = [f"{base_url.rstrip('/')}/v1/models"]
    else:
        candidates = [
            f"{draw_base}/v1/models",
            f"{site_base}/v1/models",
        ]

    headers = {"Authorization": f"Bearer {api_key}"}
    remote_models: list[dict] = []
    last_err = ""
    async with _httpx.AsyncClient(timeout=15.0) as client:
        for url in candidates:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    j = resp.json()
                    if isinstance(j, dict) and "data" in j and isinstance(j["data"], list):
                        remote_models = j["data"]
                        break
                    elif isinstance(j, list):
                        remote_models = j
                        break
                    else:
                        remote_models = [j]
                        break
                last_err = f"{url} {resp.status_code} {resp.text[:200]}"
            except Exception as e:
                last_err = f"{url} {e}"
                continue

    if not remote_models:
        raise HTTPException(status_code=400, detail=f"Gagal sync models: {last_err or 'no models returned'}")

    # upsert into DB as inactive by default except existing active stay active — use composite id provider:external
    synced = 0
    async with _pool.acquire() as con:
        for m in remote_models:
            mid = m.get("id") or m.get("model") or m.get("name")
            if not mid:
                continue
            internal_id, external_id = _normalize_model_ids(mid, provider_id, None)
            existing = await con.fetchrow("SELECT id, is_active, is_default FROM ai_models WHERE id=$1 OR (provider_id=$2 AND external_id=$3)", internal_id, provider_id, external_id)
            is_active = existing["is_active"] if existing else False
            is_default = existing["is_default"] if existing else False
            display = m.get("display_name") or m.get("id") or mid
            desc = m.get("description") or m.get("owned_by") or ""
            await con.execute(
                """
                INSERT INTO ai_models (id, provider_id, external_id, display_name, description, is_active, is_default, sort_order, capabilities, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,0,'{}'::jsonb, now())
                ON CONFLICT (id) DO UPDATE SET provider_id=$2, external_id=$3, display_name=COALESCE(EXCLUDED.display_name, ai_models.display_name), description=COALESCE(EXCLUDED.description, ai_models.description), updated_at=now()
                """,
                internal_id, provider_id, external_id, display, desc, is_active, is_default,
            )
            synced += 1

    return {"ok": True, "synced": synced, "models": [m.get("id") for m in remote_models[:100]]}


# ---------------- User detail ----------------
@app.get("/api/users/{uid}")
async def user_detail(uid: str, _: bool = Depends(require_auth)):
    # uid may come as string from frontend — parse bigint safely
    try:
        uid_int = int(str(uid).strip())
    except Exception:
        raise HTTPException(status_code=400, detail="User ID tidak valid")
    async with _pool.acquire() as con:
        u = await con.fetchrow("SELECT * FROM users WHERE user_id=$1", uid_int)
        if not u:
            raise HTTPException(status_code=404, detail=f"User {uid_int} tidak ditemukan di database ({await con.fetchval('SELECT count(*) FROM users') or 0} total users)")
        total = await con.fetchval("SELECT count(*) FROM generations WHERE user_id=$1", uid_int) or 0
        ok = await con.fetchval("SELECT count(*) FROM generations WHERE user_id=$1 AND success", uid_int) or 0
        today = await con.fetchval(
            "SELECT count(*) FROM generations WHERE user_id=$1 AND created_at::date=CURRENT_DATE", uid_int) or 0
        gens = await con.fetch(
            "SELECT kind,prompt,size,success,created_at FROM generations "
            f"WHERE user_id=$1 ORDER BY id DESC LIMIT 50", uid_int)
    return {
        "user": dict(u), "total": total, "success": ok, "failed": total - ok, "today": today,
        "generations": [dict(g) for g in gens],
    }


# ---------------- Analytics ----------------
@app.get("/api/analytics")
async def analytics(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        # Activity by hour of day (last 30d)
        hours = await con.fetch(
            "SELECT EXTRACT(HOUR FROM created_at)::int AS h, count(*) AS c "
            "FROM generations WHERE created_at > now()-interval '30 days' GROUP BY h ORDER BY h")
        # Top prompts (last 30d)
        top = await con.fetch(
            "SELECT prompt, count(*) AS c FROM generations "
            "WHERE created_at > now()-interval '30 days' AND prompt IS NOT NULL AND prompt <> '' "
            "GROUP BY prompt ORDER BY c DESC LIMIT 10")
        # kind breakdown
        kinds = await con.fetch("SELECT kind, count(*) AS c FROM generations GROUP BY kind")
        # daily success rate (last 14d)
        daily = await con.fetch(
            "SELECT d::date AS day, "
            "COALESCE((SELECT count(*) FROM generations g WHERE g.created_at::date=d::date),0) AS total, "
            "COALESCE((SELECT count(*) FROM generations g WHERE g.created_at::date=d::date AND g.success),0) AS ok "
            "FROM generate_series(CURRENT_DATE-13, CURRENT_DATE, '1 day') d ORDER BY day")
        # top users
        topusers = await con.fetch(
            "SELECT g.user_id, u.username, count(*) AS c FROM generations g "
            "LEFT JOIN users u ON u.user_id=g.user_id GROUP BY g.user_id,u.username ORDER BY c DESC LIMIT 8")
    hour_map = {int(r["h"]): r["c"] for r in hours}
    return {
        "hours": [{"hour": h, "count": hour_map.get(h, 0)} for h in range(24)],
        "top_prompts": [dict(r) for r in top],
        "kinds": [dict(r) for r in kinds],
        "daily_success": [
            {"day": r["day"].strftime("%d/%m"),
             "rate": round(100 * r["ok"] / r["total"]) if r["total"] else 0,
             "total": r["total"]} for r in daily],
        "top_users": [dict(r) for r in topusers],
    }

# ---------------- Errors log ----------------
@app.get("/api/errors")
async def errors(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch(
            "SELECT g.id,g.user_id,g.kind,g.prompt,g.size,g.created_at,u.username "
            "FROM generations g LEFT JOIN users u ON u.user_id=g.user_id "
            "WHERE g.success=false ORDER BY g.id DESC LIMIT 100")
        total_failed = await con.fetchval("SELECT count(*) FROM generations WHERE NOT success") or 0
        failed_today = await con.fetchval(
            "SELECT count(*) FROM generations WHERE NOT success AND created_at::date=CURRENT_DATE") or 0
    return {"total_failed": total_failed, "failed_today": failed_today,
            "errors": [dict(r) for r in rows]}


# ---------------- CSV export ----------------
def _csv_response(rows, headers, filename):
    import csv, io
    from fastapi.responses import StreamingResponse
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for r in rows:
        w.writerow(r)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.get("/api/export/users.csv")
async def export_users(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch(
            "SELECT u.user_id,u.username,u.first_name,u.is_banned,u.created_at,"
            "count(g.id) AS gen_count FROM users u LEFT JOIN generations g ON g.user_id=u.user_id "
            "GROUP BY u.user_id ORDER BY gen_count DESC")
    data = [[r["user_id"], r["username"] or "", r["first_name"] or "",
             "yes" if r["is_banned"] else "no", r["created_at"], r["gen_count"]] for r in rows]
    return _csv_response(data, ["user_id", "username", "first_name", "banned", "created_at", "total_generations"], "users.csv")


@app.get("/api/export/generations.csv")
async def export_generations(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch(
            "SELECT g.id,g.user_id,u.username,g.kind,g.prompt,g.size,g.success,g.created_at "
            "FROM generations g LEFT JOIN users u ON u.user_id=g.user_id ORDER BY g.id DESC LIMIT 10000")
    data = [[r["id"], r["user_id"], r["username"] or "", r["kind"], r["prompt"] or "",
             r["size"] or "", "ok" if r["success"] else "failed", r["created_at"]] for r in rows]
    return _csv_response(data, ["id", "user_id", "username", "kind", "prompt", "size", "status", "created_at"], "generations.csv")

# ==================== PREMIUM: Plans ====================
class PlanBody(BaseModel):
    name: str
    daily_limit: int = 100
    price: int = 0
    duration_days: int = 30
    description: str | None = None
    is_active: bool = True
    sort_order: int = 0


@app.get("/api/plans")
async def list_plans(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch("SELECT * FROM plans ORDER BY sort_order, id")
    return {"plans": [dict(r) for r in rows]}


@app.post("/api/plans")
async def create_plan(body: PlanBody, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "INSERT INTO plans (name,daily_limit,price,duration_days,description,is_active,sort_order) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id",
            body.name, body.daily_limit, body.price, body.duration_days,
            body.description, body.is_active, body.sort_order)
    return {"ok": True, "id": row["id"]}


@app.put("/api/plans/{pid}")
async def update_plan(pid: int, body: PlanBody, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        await con.execute(
            "UPDATE plans SET name=$2,daily_limit=$3,price=$4,duration_days=$5,"
            "description=$6,is_active=$7,sort_order=$8 WHERE id=$1",
            pid, body.name, body.daily_limit, body.price, body.duration_days,
            body.description, body.is_active, body.sort_order)
    return {"ok": True}


@app.delete("/api/plans/{pid}")
async def delete_plan(pid: int, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        await con.execute("DELETE FROM plans WHERE id=$1", pid)
    return {"ok": True}


# ==================== PREMIUM: Payment methods ====================
class MethodBody(BaseModel):
    type: str = "bank"
    name: str
    account_name: str | None = None
    account_number: str | None = None
    instructions: str | None = None
    qr_image: str | None = None
    is_active: bool = True
    sort_order: int = 0


@app.get("/api/methods")
async def list_methods(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch("SELECT * FROM payment_methods ORDER BY sort_order, id")
    return {"methods": [dict(r) for r in rows]}


@app.post("/api/methods")
async def create_method(body: MethodBody, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "INSERT INTO payment_methods (type,name,account_name,account_number,instructions,qr_image,is_active,sort_order) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id",
            body.type, body.name, body.account_name, body.account_number,
            body.instructions, body.qr_image, body.is_active, body.sort_order)
    return {"ok": True, "id": row["id"]}


@app.put("/api/methods/{mid}")
async def update_method(mid: int, body: MethodBody, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        await con.execute(
            "UPDATE payment_methods SET type=$2,name=$3,account_name=$4,account_number=$5,"
            "instructions=$6,qr_image=$7,is_active=$8,sort_order=$9 WHERE id=$1",
            mid, body.type, body.name, body.account_name, body.account_number,
            body.instructions, body.qr_image, body.is_active, body.sort_order)
    return {"ok": True}


@app.delete("/api/methods/{mid}")
async def delete_method(mid: int, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        await con.execute("DELETE FROM payment_methods WHERE id=$1", mid)
    return {"ok": True}

# ==================== PREMIUM: Orders ====================
@app.get("/api/orders")
async def list_orders(status: str = "", _: bool = Depends(require_auth)):
    q = ("SELECT o.*, u.username, u.first_name FROM orders o "
         "LEFT JOIN users u ON u.user_id=o.user_id ")
    args = []
    if status in ("pending", "approved", "rejected"):
        q += "WHERE o.status=$1 "
        args.append(status)
    q += "ORDER BY o.id DESC LIMIT 200"
    async with _pool.acquire() as con:
        rows = await con.fetch(q, *args)
        counts = await con.fetch("SELECT status, count(*) c FROM orders GROUP BY status")
    cmap = {r["status"]: r["c"] for r in counts}
    return {"orders": [dict(r) for r in rows],
            "counts": {"pending": cmap.get("pending", 0), "approved": cmap.get("approved", 0),
                       "rejected": cmap.get("rejected", 0)}}


@app.get("/api/orders/{oid}/proof")
async def order_proof(oid: int, _: bool = Depends(require_auth)):
    """Proxy the Telegram proof photo so the dashboard can display it."""
    from fastapi.responses import Response as FResponse
    async with _pool.acquire() as con:
        fid = await con.fetchval("SELECT proof_file_id FROM orders WHERE id=$1", oid)
    if not fid:
        raise HTTPException(status_code=404, detail="Belum ada bukti")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile", params={"file_id": fid})
        path = r.json()["result"]["file_path"]
        img = await client.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}")
    return FResponse(content=img.content, media_type="image/jpeg")


class DecisionBody(BaseModel):
    note: str | None = None


async def _notify_user(user_id: int, text: str):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": user_id, "text": text, "parse_mode": "HTML"})
    except Exception:
        pass


def _rupiah(n) -> str:
    return "Rp" + f"{int(n):,}".replace(",", ".")


@app.post("/api/orders/{oid}/approve")
async def approve_order(oid: int, _: bool = Depends(require_auth)):
    from datetime import datetime, timezone, timedelta
    async with _pool.acquire() as con:
        o = await con.fetchrow("SELECT * FROM orders WHERE id=$1", oid)
        if not o:
            raise HTTPException(status_code=404, detail="Order tidak ditemukan")
        if o["status"] != "pending":
            raise HTTPException(status_code=400, detail="Order sudah diproses")
        # Activate premium: extend from current expiry if still active.
        base = datetime.now(timezone.utc)
        cur = await con.fetchval("SELECT premium_until FROM users WHERE user_id=$1", o["user_id"])
        if cur and cur > base:
            base = cur
        until = base + timedelta(days=o["duration_days"])
        await con.execute(
            "UPDATE users SET premium_until=$2, plan_id=$3, plan_name=$4 WHERE user_id=$1",
            o["user_id"], until, o["plan_id"], o["plan_name"])
        await con.execute(
            "UPDATE orders SET status='approved', decided_at=now() WHERE id=$1", oid)
    lim = "♾️ Unlimited" if o["daily_limit"] == 0 else f"{o['daily_limit']} gambar/hari"
    await _notify_user(o["user_id"],
        "🎉 <b>Selamat! Premium kamu aktif!</b>\n\n"
        f"💎 Paket: <b>{o['plan_name']}</b>\n"
        f"📊 Kuota: <b>{lim}</b>\n"
        f"⏳ Berlaku s/d: <b>{until.strftime('%d %b %Y')}</b>\n\n"
        "Terima kasih sudah upgrade! Selamat berkreasi 🎨")
    return {"ok": True, "premium_until": until.isoformat()}


@app.post("/api/orders/{oid}/reject")
async def reject_order(oid: int, body: DecisionBody, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        o = await con.fetchrow("SELECT * FROM orders WHERE id=$1", oid)
        if not o:
            raise HTTPException(status_code=404, detail="Order tidak ditemukan")
        if o["status"] != "pending":
            raise HTTPException(status_code=400, detail="Order sudah diproses")
        await con.execute(
            "UPDATE orders SET status='rejected', note=$2, decided_at=now() WHERE id=$1",
            oid, body.note)
    txt = "❌ <b>Pembayaran ditolak</b>\n\nMaaf, pembayaranmu tidak dapat diverifikasi."
    if body.note:
        txt += f"\n\n📝 Catatan admin: <i>{body.note}</i>"
    txt += "\n\nSilakan coba lagi atau hubungi admin ya 🙏"
    await _notify_user(o["user_id"], txt)
    return {"ok": True}


@app.get("/api/premium/stats")
async def premium_stats(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        active = await con.fetchval(
            "SELECT count(*) FROM users WHERE premium_until > now()") or 0
        pending = await con.fetchval("SELECT count(*) FROM orders WHERE status='pending'") or 0
        revenue = await con.fetchval(
            "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='approved'") or 0
        approved = await con.fetchval("SELECT count(*) FROM orders WHERE status='approved'") or 0
    return {"active_premium": active, "pending_orders": pending,
            "total_revenue": revenue, "total_approved": approved}


# ==================== BALANCE: Settings ====================
class BalanceSettingsBody(BaseModel):
    enabled: bool = True
    min_amount: int = 10000
    max_amount: int = 5000000
    quick_amounts: list[int] = [10000, 25000, 50000, 100000, 250000]


@app.get("/api/balance/settings")
async def get_balance_settings(_: bool = Depends(require_auth)):
    enabled = await get_setting("balance_enabled", "1")
    min_amount = await get_setting("deposit_min", "10000")
    max_amount = await get_setting("deposit_max", "5000000")
    quick_raw = await get_setting("deposit_quick_amounts", "10000,25000,50000,100000,250000")
    try:
        quick = [int(x) for x in quick_raw.split(",") if x.strip()]
    except ValueError:
        quick = [10000, 25000, 50000, 100000, 250000]
    return {"enabled": enabled == "1", "min_amount": int(min_amount),
            "max_amount": int(max_amount), "quick_amounts": quick}


@app.post("/api/balance/settings")
async def save_balance_settings(body: BalanceSettingsBody, _: bool = Depends(require_auth)):
    if body.min_amount < 0 or body.max_amount < body.min_amount:
        raise HTTPException(status_code=400, detail="Rentang nominal tidak valid")
    await set_setting("balance_enabled", "1" if body.enabled else "0")
    await set_setting("deposit_min", max(0, body.min_amount))
    await set_setting("deposit_max", max(0, body.max_amount))
    quick = sorted({int(x) for x in body.quick_amounts if x > 0})
    await set_setting("deposit_quick_amounts", ",".join(str(x) for x in quick))
    return {"ok": True}


# ==================== BALANCE: Deposits ====================
@app.get("/api/deposits")
async def list_deposits(status: str = "", _: bool = Depends(require_auth)):
    q = ("SELECT d.*, u.username, u.first_name FROM deposits d "
         "LEFT JOIN users u ON u.user_id=d.user_id ")
    args = []
    if status in ("pending", "approved", "rejected"):
        q += "WHERE d.status=$1 "
        args.append(status)
    q += "ORDER BY d.id DESC LIMIT 200"
    async with _pool.acquire() as con:
        rows = await con.fetch(q, *args)
        counts = await con.fetch("SELECT status, count(*) c FROM deposits GROUP BY status")
    cmap = {r["status"]: r["c"] for r in counts}
    return {"deposits": [dict(r) for r in rows],
            "counts": {"pending": cmap.get("pending", 0), "approved": cmap.get("approved", 0),
                       "rejected": cmap.get("rejected", 0)}}


@app.get("/api/deposits/stats")
async def deposit_stats(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        pending = await con.fetchval("SELECT count(*) FROM deposits WHERE status='pending'") or 0
        total_in = await con.fetchval(
            "SELECT COALESCE(SUM(amount),0) FROM deposits WHERE status='approved'") or 0
        approved = await con.fetchval("SELECT count(*) FROM deposits WHERE status='approved'") or 0
        total_balance = await con.fetchval("SELECT COALESCE(SUM(balance),0) FROM users") or 0
    return {"pending_deposits": pending, "total_deposited": total_in,
            "total_approved": approved, "total_balance_outstanding": total_balance}


@app.get("/api/deposits/{did}/proof")
async def deposit_proof(did: int, _: bool = Depends(require_auth)):
    """Proxy the Telegram proof photo so the dashboard can display it."""
    from fastapi.responses import Response as FResponse
    async with _pool.acquire() as con:
        fid = await con.fetchval("SELECT proof_file_id FROM deposits WHERE id=$1", did)
    if not fid:
        raise HTTPException(status_code=404, detail="Belum ada bukti")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile", params={"file_id": fid})
        path = r.json()["result"]["file_path"]
        img = await client.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}")
    return FResponse(content=img.content, media_type="image/jpeg")


@app.post("/api/deposits/{did}/approve")
async def approve_deposit(did: int, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        async with con.transaction():
            d = await con.fetchrow("SELECT * FROM deposits WHERE id=$1 FOR UPDATE", did)
            if not d:
                raise HTTPException(status_code=404, detail="Deposit tidak ditemukan")
            if d["status"] != "pending":
                raise HTTPException(status_code=400, detail="Deposit sudah diproses")
            new_balance_row = await con.fetchrow(
                "UPDATE users SET balance = balance + $2 WHERE user_id=$1 RETURNING balance",
                d["user_id"], d["amount"])
            if not new_balance_row:
                await con.execute(
                    "INSERT INTO users (user_id, balance) VALUES ($1, $2) "
                    "ON CONFLICT (user_id) DO UPDATE SET balance = users.balance + $2",
                    d["user_id"], d["amount"])
                new_balance_row = await con.fetchrow("SELECT balance FROM users WHERE user_id=$1", d["user_id"])
            new_balance = new_balance_row["balance"]
            await con.execute(
                "INSERT INTO balance_logs (user_id, delta, balance_after, reason) VALUES ($1,$2,$3,$4)",
                d["user_id"], d["amount"], new_balance, f"Deposit #{did} disetujui")
            await con.execute(
                "UPDATE deposits SET status='approved', decided_at=now() WHERE id=$1", did)
    await _notify_user(d["user_id"],
        "🎉 <b>Top up berhasil!</b>\n\n"
        f"💰 Nominal: <b>{_rupiah(d['amount'])}</b>\n"
        f"💳 Saldo sekarang: <b>{_rupiah(new_balance)}</b>\n\n"
        "Terima kasih! 🙏")
    return {"ok": True, "new_balance": new_balance}


@app.post("/api/deposits/{did}/reject")
async def reject_deposit(did: int, body: DecisionBody, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        d = await con.fetchrow("SELECT * FROM deposits WHERE id=$1", did)
        if not d:
            raise HTTPException(status_code=404, detail="Deposit tidak ditemukan")
        if d["status"] != "pending":
            raise HTTPException(status_code=400, detail="Deposit sudah diproses")
        await con.execute(
            "UPDATE deposits SET status='rejected', note=$2, decided_at=now() WHERE id=$1",
            did, body.note)
    txt = "❌ <b>Deposit ditolak</b>\n\nMaaf, top up tidak dapat diverifikasi."
    if body.note:
        txt += f"\n\n📝 Catatan admin: <i>{body.note}</i>"
    txt += "\n\nSilakan coba lagi atau hubungi admin ya 🙏"
    await _notify_user(d["user_id"], txt)
    return {"ok": True}


# ==================== BALANCE: Manual adjust (admin) ====================
class BalanceAdjustBody(BaseModel):
    user_id: int
    delta: int  # positive to add, negative to deduct
    reason: str = "Penyesuaian manual admin"
    notify: bool = True


@app.post("/api/users/balance/adjust")
async def adjust_user_balance(body: BalanceAdjustBody, _: bool = Depends(require_auth)):
    if body.delta == 0:
        raise HTTPException(status_code=400, detail="Nilai penyesuaian tidak boleh 0")
    async with _pool.acquire() as con:
        # Check before transaction to avoid partial rollback confusion
        row = await con.fetchrow(
            "SELECT balance FROM users WHERE user_id=$1", body.user_id)
        if not row:
            raise HTTPException(status_code=404, detail="User tidak ditemukan")
        if row["balance"] + body.delta < 0:
            raise HTTPException(status_code=400, detail="Saldo tidak boleh negatif")
        async with con.transaction():
            new_row = await con.fetchrow(
                "UPDATE users SET balance = balance + $2 WHERE user_id=$1 RETURNING balance",
                body.user_id, body.delta)
            new_balance = new_row["balance"]
            await con.execute(
                "INSERT INTO balance_logs (user_id, delta, balance_after, reason) VALUES ($1,$2,$3,$4)",
                body.user_id, body.delta, new_balance, body.reason)
    if body.notify:
        sign = "+" if body.delta > 0 else ""
        await _notify_user(body.user_id,
            f"ℹ️ <b>Saldo kamu disesuaikan admin</b>\n\n"
            f"Perubahan: <b>{sign}{_rupiah(body.delta)}</b>\n"
            f"Saldo sekarang: <b>{_rupiah(new_balance)}</b>\n"
            f"Catatan: <i>{body.reason}</i>")
    return {"ok": True, "new_balance": new_balance}


@app.get("/api/users/{uid}/balance/logs")
async def user_balance_logs(uid: int, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch(
            "SELECT id, delta, balance_after, reason, created_at FROM balance_logs "
            "WHERE user_id=$1 ORDER BY id DESC LIMIT 50", uid)
    return {"logs": [dict(r) for r in rows]}


# ==================== REFERRAL ====================
class ReferralSettingsBody(BaseModel):
    enabled: bool = True
    reward_type: str = "balance"   # 'balance' | 'quota'
    reward_amount: int = 5000


@app.get("/api/referral/settings")
async def get_referral_settings_ep(_: bool = Depends(require_auth)):
    enabled = await get_setting("referral_enabled", "1")
    reward_type = await get_setting("referral_reward_type", "balance")
    reward_amount = await get_setting("referral_reward_amount", "5000")
    return {
        "enabled": enabled == "1",
        "reward_type": reward_type if reward_type in ("balance", "quota") else "balance",
        "reward_amount": int(reward_amount),
    }


@app.post("/api/referral/settings")
async def save_referral_settings_ep(body: ReferralSettingsBody, _: bool = Depends(require_auth)):
    if body.reward_type not in ("balance", "quota"):
        raise HTTPException(status_code=400, detail="reward_type harus 'balance' atau 'quota'")
    if body.reward_amount < 0:
        raise HTTPException(status_code=400, detail="Nominal bonus tidak valid")
    await set_setting("referral_enabled", "1" if body.enabled else "0")
    await set_setting("referral_reward_type", body.reward_type)
    await set_setting("referral_reward_amount", int(body.reward_amount))
    return {"ok": True}


@app.get("/api/referral/stats")
async def referral_stats(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        total = await con.fetchval("SELECT count(*) FROM referrals") or 0
        rewarded = await con.fetchval("SELECT count(*) FROM referrals WHERE status='rewarded'") or 0
        pending = total - rewarded
        balance_paid = await con.fetchval(
            "SELECT COALESCE(SUM(reward_amount),0) FROM referrals WHERE status='rewarded' AND reward_type='balance'") or 0
        quota_paid = await con.fetchval(
            "SELECT COALESCE(SUM(reward_amount),0) FROM referrals WHERE status='rewarded' AND reward_type='quota'") or 0
        top = await con.fetch(
            "SELECT r.referrer_id, u.username, u.first_name, count(*) AS total, "
            "count(*) FILTER (WHERE r.status='rewarded') AS rewarded "
            "FROM referrals r LEFT JOIN users u ON u.user_id=r.referrer_id "
            "GROUP BY r.referrer_id, u.username, u.first_name "
            "ORDER BY rewarded DESC, total DESC LIMIT 10")
    return {
        "total": total, "rewarded": rewarded, "pending": pending,
        "balance_paid": balance_paid, "quota_paid": quota_paid,
        "top_referrers": [dict(r) for r in top],
    }


@app.get("/api/referral/list")
async def referral_list(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch(
            "SELECT r.*, "
            "ru.username AS referrer_username, ru.first_name AS referrer_first_name, "
            "rd.username AS referred_username, rd.first_name AS referred_first_name "
            "FROM referrals r "
            "LEFT JOIN users ru ON ru.user_id=r.referrer_id "
            "LEFT JOIN users rd ON rd.user_id=r.referred_id "
            "ORDER BY r.id DESC LIMIT 200")
    return {"referrals": [dict(r) for r in rows]}
