"""JSON API for the admin dashboard (FastAPI). Consumed by the Next.js frontend. Hardened prod."""
import asyncio
import os
import secrets
import asyncpg
import httpx
import ipaddress
import re
import html as _html
import time
from contextlib import asynccontextmanager
from typing import Annotated
from fastapi import FastAPI, Request, Response, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator

DATABASE_URL = os.environ["DATABASE_URL"]
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS")
BOT_TOKEN = os.environ["BOT_TOKEN"]
DEFAULT_DAILY_LIMIT = int(os.environ.get("DEFAULT_DAILY_LIMIT", "20"))
REQUIRED_CHANNEL = os.environ.get("REQUIRED_CHANNEL", "")
SESSION_SECRET = os.environ.get("DASH_SECRET", secrets.token_hex(16))
ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

_pool: asyncpg.Pool | None = None
_broadcast_lock = asyncio.Lock()
_last_broadcast_ts = 0.0
_login_attempts: dict[str, list[float]] = {}

# ---------- utils ----------
def _is_safe_url(url: str) -> bool:
    u = url.strip()
    low = u.lower()
    if low.startswith("javascript:") or low.startswith("data:") or low.startswith("vbscript:"):
        return False
    if not (low.startswith("https://") or low.startswith("http://") or low.startswith("t.me/") or low.startswith("https://t.me/") or low.startswith("http://t.me/")):
        return False
    try:
        m = re.search(r"https?://([^/:?#]+)", u, re.I)
        if m:
            host = m.group(1).lower()
            if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
                return False
            if host.startswith("10.") or host.startswith("192.168.") or host.startswith("169.254."):
                return False
            if host.startswith("172."):
                try:
                    second = int(host.split(".")[1])
                    if 16 <= second <= 31:
                        return False
                except Exception:
                    pass
            try:
                ip = ipaddress.ip_address(host)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    return False
            except ValueError:
                pass
    except Exception:
        pass
    return True

def _build_inline_keyboard(button_text: str | None, button_url: str | None) -> str | None:
    if not button_text or not button_url:
        return None
    text = button_text.strip()[:64]
    url = button_url.strip()
    low = url.lower()
    if low.startswith("javascript:") or low.startswith("data:") or low.startswith("vbscript:"):
        return None
    if not (url.startswith("http://") or url.startswith("https://") or url.startswith("t.me/")):
        return None
    if not _is_safe_url(url):
        return None
    if not text:
        return None
    import json
    return json.dumps({"inline_keyboard": [[{"text": text, "url": url}]]})

def _sanitize_html(s: str) -> str:
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"&lt;a\s+[^&]*href\s*=\s*[\"']?\s*(?:javascript|data|vbscript)\s*:[^&]*&gt;", "[link blocked]", s, flags=re.I)
    return (
        s.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
         .replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")
         .replace("&lt;u&gt;", "<u>").replace("&lt;/u&gt;", "</u>")
         .replace("&lt;s&gt;", "<s>").replace("&lt;/s&gt;", "</s>")
         .replace("&lt;code&gt;", "<code>").replace("&lt;/code&gt;", "</code>")
         .replace("&lt;pre&gt;", "<pre>").replace("&lt;/pre&gt;", "</pre>")
    )

def _audience_where(audience: str) -> str:
    if audience == "premium":
        return "WHERE NOT is_banned AND premium_until > now()"
    if audience == "free":
        return "WHERE NOT is_banned AND (premium_until IS NULL OR premium_until <= now())"
    return "WHERE NOT is_banned"

async def _ensure_tables():
    async with _pool.acquire() as con:
        await con.execute(
            "CREATE TABLE IF NOT EXISTS admin_sessions ("
            " token TEXT PRIMARY KEY,"
            " created_at TIMESTAMPTZ NOT NULL DEFAULT now(),"
            " expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + interval '7 days')"
        )
        await con.execute("DELETE FROM admin_sessions WHERE expires_at < now()")
        await con.execute("""
            CREATE TABLE IF NOT EXISTS admin_audit (
                id SERIAL PRIMARY KEY,
                ts TIMESTAMPTZ NOT NULL DEFAULT now(),
                action TEXT NOT NULL,
                target TEXT,
                detail TEXT,
                actor TEXT DEFAULT 'admin'
            )
        """)
        await con.execute("CREATE INDEX IF NOT EXISTS idx_admin_audit_ts ON admin_audit(ts DESC)")
        await con.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_history (
                id SERIAL PRIMARY KEY,
                message TEXT, audience TEXT, sent INT, total INT,
                image_file_id TEXT, button_text TEXT, button_url TEXT,
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """)

async def audit_log(action: str, target: str | None = None, detail: str | None = None):
    try:
        async with _pool.acquire() as con:
            await con.execute("INSERT INTO admin_audit (action, target, detail) VALUES ($1,$2,$3)", action, str(target or "")[:200], str(detail or "")[:1000])
    except Exception:
        pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    try:
        await _ensure_tables()
    except Exception as e:
        print(f"warn ensure tables: {e}")
    # env migrate
    try:
        async with _pool.acquire() as con:
            for k, env_keys, default_val in [
                ("cubence_api_key", ["CUBENCE_API_KEY"], None),
                ("cubence_base_url", ["CUBENCE_BASE_URL"], "https://api-dmit.cubence.com"),
                ("rightcodes_api_key", ["RIGHTCODES_API_KEY", "RIGHT_CODES_API_KEY"], None),
                ("rightcodes_base_url", ["RIGHTCODES_BASE_URL", "RIGHT_CODES_BASE_URL"], "https://www.right.codes/draw"),
                ("apikeyfun_api_key", ["APIKEYFUN_API_KEY", "APIKEY_FUN_API_KEY"], None),
                ("apikeyfun_base_url", ["APIKEYFUN_BASE_URL", "APIKEY_FUN_BASE_URL"], "https://api.apikey.fun/v1"),
                ("unity2_api_key", ["UNITY2_API_KEY", "UNITY2_API_KEY_"], None),
                ("unity2_base_url", ["UNITY2_BASE_URL"], "https://api.unity2.ai/v1"),
            ]:
                val = ""
                for ek in env_keys:
                    v = os.environ.get(ek, "").strip()
                    if v:
                        val = v
                        break
                if val:
                    await con.execute("INSERT INTO settings (key,value) VALUES ($1,$2) ON CONFLICT (key) DO NOTHING", k, val)
                if default_val and k.endswith("_base_url"):
                    await con.execute("INSERT INTO settings (key,value) VALUES ($1,$2) ON CONFLICT (key) DO NOTHING", k, default_val)
            await con.execute("ALTER TABLE ai_models ADD COLUMN IF NOT EXISTS external_id TEXT;")
            await con.execute("UPDATE ai_models SET external_id = id WHERE external_id IS NULL;")
            await con.execute("UPDATE providers SET base_url = COALESCE((SELECT value FROM settings WHERE key = providers.id || '_base_url'), base_url) WHERE base_url IS NULL OR base_url = ''")
            await con.execute("INSERT INTO providers (id, name, base_url, is_active) VALUES ('apikeyfun','ApiKeyFun','https://api.apikey.fun/v1', false) ON CONFLICT (id) DO NOTHING")
            await con.execute("INSERT INTO providers (id, name, base_url, is_active) VALUES ('unity2','Unity2','https://api.unity2.ai/v1', false) ON CONFLICT (id) DO NOTHING")
    except Exception as e:
        print(f"warn lifespan migration: {e}")
    yield
    if _pool:
        await _pool.close()

app = FastAPI(title="ImageBot Admin API", lifespan=lifespan)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["X-XSS-Protection"] = "0"
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/api/"):
        resp.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return resp

async def require_auth(request: Request):
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="unauthorized")
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT 1 FROM admin_sessions WHERE token=$1 AND expires_at > now()", token)
    if not row:
        raise HTTPException(status_code=401, detail="unauthorized")
    return True

async def get_setting(key, default=None):
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT value FROM settings WHERE key=$1", key)
        return row["value"] if row else default

async def set_setting(key, value):
    async with _pool.acquire() as con:
        await con.execute("INSERT INTO settings (key,value) VALUES ($1,$2) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value", key, str(value))

# ---- Auth with audit + bruteforce guard ----
class LoginBody(BaseModel):
    username: str = Field(..., max_length=100)
    password: str = Field(..., max_length=200)

@app.post("/api/login")
async def login(body: LoginBody, response: Response, request: Request):
    key = request.client.host if request.client else "global"
    now = time.time()
    attempts = [t for t in _login_attempts.get(key, []) if now - t < 60]
    if len(attempts) >= 10:
        raise HTTPException(status_code=429, detail="Terlalu banyak percobaan, tunggu 1 menit")
    ok = secrets.compare_digest(body.username, ADMIN_USER) and secrets.compare_digest(body.password, ADMIN_PASS)
    if not ok:
        attempts.append(now)
        _login_attempts[key] = attempts
        await audit_log("login_failed", body.username, f"ip={key}")
        raise HTTPException(status_code=401, detail="Username atau password salah")
    _login_attempts[key] = []
    token = secrets.token_urlsafe(32)
    async with _pool.acquire() as con:
        await con.execute("INSERT INTO admin_sessions (token, expires_at) VALUES ($1, now() + interval '7 days')", token)
    response.set_cookie("session", token, httponly=True, samesite="strict", secure=False, max_age=86400*7)
    await audit_log("login_ok", body.username, f"ip={key}")
    return {"ok": True}

@app.post("/api/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session")
    if token:
        async with _pool.acquire() as con:
            await con.execute("DELETE FROM admin_sessions WHERE token=$1", token)
    response.delete_cookie("session")
    await audit_log("logout", "-", "-")
    return {"ok": True}

@app.get("/api/me")
async def me(_: bool = Depends(require_auth)):
    return {"user": ADMIN_USER}

# ---- Stats ----
@app.get("/api/stats")
async def stats(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        total_users = await con.fetchval("SELECT count(*) FROM users") or 0
        today_gen = await con.fetchval("SELECT count(*) FROM generations WHERE created_at::date=CURRENT_DATE") or 0
        total_gen = await con.fetchval("SELECT count(*) FROM generations") or 0
        active_today = await con.fetchval("SELECT count(DISTINCT user_id) FROM generations WHERE created_at::date=CURRENT_DATE") or 0
        banned = await con.fetchval("SELECT count(*) FROM users WHERE is_banned") or 0
        success_rate = await con.fetchval("SELECT ROUND(100.0*count(*) FILTER (WHERE success)/NULLIF(count(*),0)) FROM generations") or 0
        recent = await con.fetch("SELECT g.user_id,g.kind,g.prompt,g.success,g.created_at,u.username FROM generations g LEFT JOIN users u ON u.user_id=g.user_id ORDER BY g.id DESC LIMIT 12")
    return {"total_users": total_users, "today_gen": today_gen, "total_gen": total_gen, "active_today": active_today, "banned": banned, "success_rate": int(success_rate), "recent": [dict(r) for r in recent]}

@app.get("/api/chart")
async def chart(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch("SELECT d::date AS day, COALESCE((SELECT count(*) FROM generations g WHERE g.created_at::date=d::date),0) AS gen, COALESCE((SELECT count(DISTINCT user_id) FROM generations g WHERE g.created_at::date=d::date),0) AS users FROM generate_series(CURRENT_DATE-6, CURRENT_DATE, '1 day') d ORDER BY day")
    return [{"day": r["day"].strftime("%d/%m"), "gen": r["gen"], "users": r["users"]} for r in rows]

@app.get("/api/users")
async def list_users(q: str = "", _: bool = Depends(require_auth)):
    q = (q or "").strip()[:100]
    async with _pool.acquire() as con:
        if q:
            like = f"%{q}%"
            rows = await con.fetch("SELECT u.user_id, u.username, u.first_name, u.is_banned, u.created_at, u.last_seen, u.balance, u.lang, (SELECT count(*) FROM generations g WHERE g.user_id = u.user_id) AS gen_count FROM users u WHERE u.username ILIKE $1 OR u.first_name ILIKE $1 OR CAST(u.user_id AS TEXT) ILIKE $1 ORDER BY COALESCE(u.last_seen, u.created_at) DESC, u.created_at DESC LIMIT 300", like)
        else:
            rows = await con.fetch("SELECT u.user_id, u.username, u.first_name, u.is_banned, u.created_at, u.last_seen, u.balance, u.lang, (SELECT count(*) FROM generations g WHERE g.user_id = u.user_id) AS gen_count FROM users u ORDER BY COALESCE(u.last_seen, u.created_at) DESC, u.created_at DESC LIMIT 300")
    return [dict(r) for r in rows]

class BanBody(BaseModel):
    user_id: int = Field(..., ge=1)
    banned: bool

@app.post("/api/users/ban")
async def ban_user(body: BanBody, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        await con.execute("UPDATE users SET is_banned=$2 WHERE user_id=$1", body.user_id, body.banned)
    await audit_log("ban_toggle", str(body.user_id), f"banned={body.banned}")
    return {"ok": True}

# ---- Broadcast hardened ----
class BroadcastBody(BaseModel):
    message: str = Field(..., min_length=3, max_length=4096)
    audience: str = "all"
    image_file_id: str | None = Field(default=None, max_length=400)
    button_text: str | None = Field(default=None, max_length=64)
    button_url: str | None = Field(default=None, max_length=500)

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
        rows = await con.fetch("SELECT id, message, audience, sent, total, image_file_id, button_text, button_url, created_at FROM broadcast_history ORDER BY id DESC LIMIT 20")
    return {"history": [dict(r) for r in rows]}

@app.post("/api/broadcast/upload-image")
async def broadcast_upload_image(request: Request, _: bool = Depends(require_auth)):
    if not ADMIN_IDS:
        raise HTTPException(status_code=400, detail="ADMIN_IDS belum diset")
    target_chat = ADMIN_IDS[0]
    form = await request.form()
    upload = form.get("file")
    if not upload or not getattr(upload, "file", None):
        raise HTTPException(status_code=400, detail="File gambar wajib diisi")
    contents = await upload.read()
    if not contents or len(contents) > 10*1024*1024:
        raise HTTPException(status_code=400, detail="File kosong atau >10MB")
    ctype = (getattr(upload, "content_type", "") or "").lower()
    if not any(x in ctype for x in ("image/", "jpeg", "png", "webp", "jpg")):
        # fallback magic check
        if not (contents[:8].startswith(b"\x89PNG") or contents[:2]==b"\xff\xd8" or contents[:6] in (b"GIF87a", b"GIF89a")):
            raise HTTPException(status_code=400, detail="File harus gambar")
    async with httpx.AsyncClient(timeout=60) as client:
        files = {"photo": (upload.filename or "broadcast.jpg", contents, upload.content_type or "image/jpeg")}
        resp = await client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto", data={"chat_id": str(target_chat), "disable_notification": "true"}, files=files)
    try:
        data = resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Telegram response invalid")
    if not data.get("ok"):
        raise HTTPException(status_code=400, detail=f"Telegram menolak upload: {data.get('description','unknown')}")
    photo = data["result"]["photo"][-1]
    msg_id = data["result"]["message_id"]
    try:
        async with httpx.AsyncClient(timeout=15) as c2:
            await c2.post(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage", json={"chat_id": str(target_chat), "message_id": msg_id})
    except Exception:
        pass
    await audit_log("broadcast_upload", str(target_chat), f"file_id={photo['file_id'][:20]}")
    return {"ok": True, "file_id": photo["file_id"], "width": photo.get("width"), "height": photo.get("height")}

@app.post("/api/broadcast")
async def broadcast(body: BroadcastBody, _: bool = Depends(require_auth)):
    global _last_broadcast_ts
    if _broadcast_lock.locked():
        raise HTTPException(status_code=429, detail="Broadcast sedang berjalan")
    now_ts = time.time()
    if now_ts - _last_broadcast_ts < 30:
        raise HTTPException(status_code=429, detail=f"Tunggu {int(30-(now_ts-_last_broadcast_ts))} detik")
    if body.image_file_id:
        import re as _re
        if not _re.match(r"^[A-Za-z0-9_-]{20,400}$", body.image_file_id.strip()):
            raise HTTPException(status_code=400, detail="file_id format tidak valid")
    reply_markup = _build_inline_keyboard(body.button_text, body.button_url)
    audience = body.audience if body.audience in ("all","premium","free") else "all"
    text = _sanitize_html(body.message)[:4096]
    has_image = bool(body.image_file_id)
    async with _broadcast_lock:
        async with _pool.acquire() as con:
            rows = await con.fetch("SELECT user_id FROM users " + _audience_where(audience))
        if not rows:
            async with _pool.acquire() as con:
                await con.execute("INSERT INTO broadcast_history (message, audience, sent, total, image_file_id, button_text, button_url) VALUES ($1,$2,$3,$4,$5,$6,$7)", body.message, audience, 0,0, body.image_file_id, body.button_text, body.button_url)
            return {"ok": True, "sent": 0, "total": 0}
        sem = asyncio.Semaphore(20)
        sent_counter=0
        lock=asyncio.Lock()
        async def _send_one(client: httpx.AsyncClient, uid: int):
            nonlocal sent_counter
            async with sem:
                try:
                    if has_image:
                        payload={"chat_id":uid,"photo":body.image_file_id,"caption":text,"parse_mode":"HTML"}
                        method="sendPhoto"
                    else:
                        payload={"chat_id":uid,"text":text,"parse_mode":"HTML"}
                        method="sendMessage"
                    if reply_markup:
                        payload["reply_markup"]=reply_markup
                    resp=await client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", json=payload)
                    if resp.status_code==200 and resp.json().get("ok"):
                        async with lock:
                            sent_counter+=1
                    elif resp.status_code==429:
                        try:
                            retry_after=resp.json().get("parameters",{}).get("retry_after",1)
                        except Exception:
                            retry_after=1
                        await asyncio.sleep(float(retry_after))
                except Exception:
                    pass
        async with httpx.AsyncClient(timeout=30, limits=httpx.Limits(max_connections=30)) as client:
            await asyncio.gather(*[_send_one(client, r["user_id"]) for r in rows])
        async with _pool.acquire() as con:
            await con.execute("INSERT INTO broadcast_history (message, audience, sent, total, image_file_id, button_text, button_url) VALUES ($1,$2,$3,$4,$5,$6,$7)", body.message, audience, sent_counter, len(rows), body.image_file_id, body.button_text, body.button_url)
        _last_broadcast_ts=time.time()
        await audit_log("broadcast", audience, f"sent={sent_counter}/{len(rows)} msg={body.message[:50]}")
    return {"ok": True, "sent": sent_counter, "total": len(rows)}

# ---- Settings ----
@app.get("/api/settings")
async def get_settings(_: bool = Depends(require_auth)):
    limit = await get_setting("daily_limit", str(DEFAULT_DAILY_LIMIT))
    maint = await get_setting("maintenance", "0")
    ff_keys = ["feat_enhance_enabled","feat_batch_enabled","feat_watermark_enabled","watermark_text","watermark_free_only","enhance_model","batch_limit_free","batch_limit_premium","feat_sticker_enabled","sticker_max_per_pack","feat_checkin_enabled","feat_inline_enabled","feat_myworks_enabled","feat_style_enabled","feat_queue_enabled"]
    ff_vals = {k: await get_setting(k, "") for k in ff_keys}
    return {"daily_limit": int(limit), "maintenance": maint == "1", "channel": REQUIRED_CHANNEL, "model": "gpt-image-2", "features": ff_vals}

class SettingsBody(BaseModel):
    daily_limit: int = Field(..., ge=0, le=10000)
    maintenance: bool

@app.post("/api/settings")
async def save_settings(body: SettingsBody, _: bool = Depends(require_auth)):
    await set_setting("daily_limit", max(0, body.daily_limit))
    await set_setting("maintenance", "1" if body.maintenance else "0")
    await audit_log("settings_save", "-", f"daily={body.daily_limit} maint={body.maintenance}")
    return {"ok": True}

class FeatureFlagsBody(BaseModel):
    feat_enhance_enabled: str | None = Field(default=None, max_length=5)
    feat_batch_enabled: str | None = Field(default=None, max_length=5)
    feat_watermark_enabled: str | None = Field(default=None, max_length=5)
    watermark_text: str | None = Field(default=None, max_length=200)
    watermark_free_only: str | None = Field(default=None, max_length=5)
    enhance_model: str | None = Field(default=None, max_length=100)
    batch_limit_free: str | None = Field(default=None, max_length=5)
    batch_limit_premium: str | None = Field(default=None, max_length=5)
    feat_sticker_enabled: str | None = Field(default=None, max_length=5)
    sticker_max_per_pack: str | None = Field(default=None, max_length=10)
    feat_checkin_enabled: str | None = Field(default=None, max_length=5)
    feat_inline_enabled: str | None = Field(default=None, max_length=5)
    feat_myworks_enabled: str | None = Field(default=None, max_length=5)
    feat_style_enabled: str | None = Field(default=None, max_length=5)
    feat_queue_enabled: str | None = Field(default=None, max_length=5)

@app.get("/api/features")
async def get_features(_: bool = Depends(require_auth)):
    defaults = {"feat_enhance_enabled":"1","feat_batch_enabled":"1","feat_watermark_enabled":"0","watermark_text":"Buat di @imgaai_bot","watermark_free_only":"1","enhance_model":"gpt-4o-mini","batch_limit_free":"1","batch_limit_premium":"4","feat_sticker_enabled":"1","sticker_max_per_pack":"10","feat_checkin_enabled":"1","feat_inline_enabled":"1","feat_myworks_enabled":"1","feat_style_enabled":"1","feat_queue_enabled":"1"}
    out={}
    for k,dv in defaults.items():
        v=await get_setting(k, dv)
        out[k]=v if v not in (None,"") else dv
    return out

@app.post("/api/features")
async def save_features(body: FeatureFlagsBody, _: bool = Depends(require_auth)):
    data=body.model_dump(exclude_none=True)
    for k,v in data.items():
        sv=str(v).strip()[:500]
        await set_setting(k, sv)
    await audit_log("features_save", ",".join(data.keys()), str(data)[:500])
    return {"ok": True, "saved": list(data.keys())}

# ---- Providers & Models ----
class ProviderSaveBody(BaseModel):
    id: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9_-]{1,50}$")
    name: str | None = Field(default=None, max_length=100)
    base_url: str = Field(..., max_length=200)
    is_active: bool = True

class ApiKeySaveBody(BaseModel):
    provider_id: str = Field(..., max_length=20)
    api_key: str = Field(..., max_length=500)
    base_url: str | None = Field(default=None, max_length=200)

class ModelSaveBody(BaseModel):
    id: str = Field(..., min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._:-]{1,100}$")
    provider_id: str = Field(..., max_length=30)
    display_name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = True
    is_default: bool = False
    sort_order: int = Field(default=0, ge=0, le=10000)
    capabilities: dict | None = None
    external_id: str | None = Field(default=None, max_length=100)

def _normalize_model_ids(raw_id: str, provider_id: str, external_id: str | None = None):
    ext = external_id or raw_id
    if ":" in raw_id:
        parts = raw_id.split(":",1)
        if parts[0]==provider_id:
            return raw_id, parts[1]
    ext_clean = ext.split(":",1)[-1] if ":" in ext else ext
    internal = f"{provider_id}:{ext_clean}"
    return internal, ext_clean

@app.get("/api/providers")
async def api_list_providers(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch("SELECT * FROM providers ORDER BY id")
        srows = await con.fetch("SELECT key, value FROM settings WHERE key LIKE '%_api_key' OR key LIKE '%_base_url'")
        smap={r["key"]:r["value"] for r in srows}
    out=[]
    for r in rows:
        d=dict(r)
        pid=d["id"]
        out.append({**d, "has_api_key": bool(smap.get(f"{pid}_api_key","")), "api_key_setting_key": f"{pid}_api_key", "base_url_setting": smap.get(f"{pid}_base_url", d.get("base_url",""))})
    return out

@app.post("/api/providers")
async def api_save_provider(body: ProviderSaveBody, _: bool = Depends(require_auth)):
    if body.base_url and not _is_safe_url(body.base_url):
        raise HTTPException(status_code=400, detail="base_url tidak aman")
    if body.base_url and not body.base_url.lower().startswith("https://"):
        raise HTTPException(status_code=400, detail="base_url harus https://")
    async with _pool.acquire() as con:
        await con.execute("INSERT INTO providers (id, name, base_url, is_active, updated_at) VALUES ($1,$2,$3,$4, now()) ON CONFLICT (id) DO UPDATE SET name=COALESCE(EXCLUDED.name, providers.name), base_url=$3, is_active=$4, updated_at=now()", body.id, body.name or body.id, body.base_url, body.is_active)
    await audit_log("provider_save", body.id, body.base_url)
    return {"ok": True}

@app.get("/api/models")
async def api_list_models(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch("SELECT m.*, p.name as provider_name, p.is_active as provider_active FROM ai_models m LEFT JOIN providers p ON p.id=m.provider_id ORDER BY p.id, m.sort_order, m.display_name")
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
        await con.execute("INSERT INTO ai_models (id, provider_id, external_id, display_name, description, is_active, is_default, sort_order, capabilities, updated_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb, now()) ON CONFLICT (id) DO UPDATE SET provider_id=$2, external_id=$3, display_name=$4, description=$5, is_active=$6, is_default=$7, sort_order=$8, capabilities=$9::jsonb, updated_at=now()", internal_id, body.provider_id, external_id, body.display_name, body.description, body.is_active, body.is_default, body.sort_order, _json.dumps(body.capabilities or {}))
    await audit_log("model_save", internal_id, body.display_name)
    return {"ok": True, "id": internal_id, "external_id": external_id}

@app.delete("/api/models/{model_id}")
async def api_delete_model(model_id: str, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        await con.execute("DELETE FROM ai_models WHERE id=$1", model_id)
    await audit_log("model_delete", model_id, "")
    return {"ok": True}

@app.post("/api/models/{model_id}/default")
async def api_set_default_model(model_id: str, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT provider_id FROM ai_models WHERE id=$1", model_id)
        if not row:
            raise HTTPException(status_code=404, detail="Model not found")
        pid=row["provider_id"]
        await con.execute("UPDATE ai_models SET is_default=false WHERE provider_id=$1", pid)
        await con.execute("UPDATE ai_models SET is_default=true WHERE id=$1", model_id)
    await audit_log("model_default", model_id, "")
    return {"ok": True}

@app.post("/api/models/{model_id}/toggle")
async def api_toggle_model(model_id: str, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        await con.execute("UPDATE ai_models SET is_active = NOT is_active WHERE id=$1", model_id)
        row = await con.fetchrow("SELECT is_active FROM ai_models WHERE id=$1", model_id)
    await audit_log("model_toggle", model_id, str(row["is_active"] if row else ""))
    return {"ok": True, "is_active": row["is_active"] if row else False}

@app.post("/api/providers/{provider_id}/toggle")
async def api_toggle_provider(provider_id: str, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        await con.execute("UPDATE providers SET is_active = NOT is_active, updated_at=now() WHERE id=$1", provider_id)
        row = await con.fetchrow("SELECT is_active FROM providers WHERE id=$1", provider_id)
    await audit_log("provider_toggle", provider_id, str(row["is_active"] if row else ""))
    return {"ok": True, "is_active": row["is_active"] if row else False}

@app.get("/api/apikeys")
async def api_list_apikeys(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch("SELECT key, value FROM settings WHERE key IN ('cubence_api_key','cubence_base_url','rightcodes_api_key','rightcodes_base_url','apikeyfun_api_key','apikeyfun_base_url','unity2_api_key','unity2_base_url')")
    smap={r["key"]:r["value"] for r in rows}
    out=[]
    for pid in ["cubence","rightcodes","apikeyfun","unity2"]:
        out.append({"provider_id": pid, "has_key": bool(smap.get(f"{pid}_api_key","")), "base_url": smap.get(f"{pid}_base_url","")})
    return out

@app.post("/api/apikeys")
async def api_save_apikey(body: ApiKeySaveBody, _: bool = Depends(require_auth)):
    if body.provider_id not in ("cubence","rightcodes","apikeyfun","unity2"):
        raise HTTPException(status_code=400, detail="provider_id must be cubence, rightcodes, apikeyfun, or unity2")
    if body.base_url:
        if not _is_safe_url(body.base_url):
            raise HTTPException(status_code=400, detail="base_url tidak aman — private IP diblokir")
        if not body.base_url.lower().startswith("https://"):
            raise HTTPException(status_code=400, detail="base_url harus https://")
    if body.api_key and body.api_key != "***":
        if len(body.api_key)>500:
            raise HTTPException(status_code=400, detail="api_key terlalu panjang")
        await set_setting(f"{body.provider_id}_api_key", body.api_key.strip())
    if body.base_url:
        await set_setting(f"{body.provider_id}_base_url", body.base_url.strip().rstrip("/"))
    await audit_log("apikey_save", body.provider_id, body.base_url or "")
    return {"ok": True}

@app.post("/api/providers/{provider_id}/sync-models")
async def api_sync_models(provider_id: str, _: bool = Depends(require_auth)):
    if provider_id not in ("cubence","rightcodes","apikeyfun","unity2"):
        raise HTTPException(status_code=400, detail="Unknown provider")
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT value FROM settings WHERE key=$1", f"{provider_id}_api_key")
        api_key = row["value"] if row else ""
        row2 = await con.fetchrow("SELECT value FROM settings WHERE key=$1", f"{provider_id}_base_url")
        default_bases = {"cubence":"https://api-dmit.cubence.com","rightcodes":"https://www.right.codes/draw","apikeyfun":"https://api.apikey.fun/v1","unity2":"https://api.unity2.ai/v1"}
        base_url = row2["value"] if row2 and row2["value"] else default_bases.get(provider_id,"")
        if not api_key:
            import os as _os
            api_key = _os.environ.get(f"{provider_id.upper()}_API_KEY","") or _os.environ.get("CUBENCE_API_KEY","") if provider_id=="cubence" else ""
            if provider_id=="apikeyfun":
                api_key = _os.environ.get("APIKEYFUN_API_KEY","") or _os.environ.get("APIKEY_FUN_API_KEY","")
            if provider_id=="unity2":
                api_key = _os.environ.get("UNITY2_API_KEY","") or _os.environ.get("UNITY2_API_KEY_","")
            if not api_key:
                raise HTTPException(status_code=400, detail=f"API key {provider_id} belum di-set")
    if not _is_safe_url(base_url):
        raise HTTPException(status_code=400, detail="base_url tidak aman — SSRF blocked")
    import httpx as _httpx
    def _site_base(b: str) -> str:
        bb=b.rstrip("/")
        if bb.endswith("/draw"):
            return bb[:-5]
        if "/draw" in bb:
            return bb.split("/draw")[0]
        return bb
    draw_base=base_url.rstrip("/")
    if provider_id=="rightcodes" and not draw_base.endswith("/draw") and "/draw" not in draw_base:
        draw_base=draw_base+"/draw"
    site_base=_site_base(draw_base)
    candidates=[]
    if provider_id=="cubence":
        candidates=[f"{base_url.rstrip('/')}/v1/models"]
    elif provider_id in ("apikeyfun","unity2"):
        candidates=[f"{base_url.rstrip('/')}/models", f"{base_url.rstrip('/')}/v1/models"]
    else:
        candidates=[f"{draw_base}/v1/models", f"{site_base}/v1/models"]
    headers={"Authorization": f"Bearer {api_key}"}
    remote_models: list[dict]=[]
    last_err=""
    async with _httpx.AsyncClient(timeout=15.0) as client:
        for url in candidates:
            if not _is_safe_url(url):
                continue
            try:
                resp=await client.get(url, headers=headers)
                if resp.status_code==200:
                    j=resp.json()
                    if isinstance(j, dict) and "data" in j and isinstance(j["data"], list):
                        remote_models=j["data"]; break
                    elif isinstance(j, list):
                        remote_models=j; break
                    else:
                        remote_models=[j]; break
                last_err=f"{url} {resp.status_code} {resp.text[:200]}"
            except Exception as e:
                last_err=f"{url} {e}"
                continue
    if provider_id in ("apikeyfun","unity2"):
        IMAGE_KW=["gpt-image","dall-e","dalle","flux","imagen","stable","sdxl","midjourney","image","nano-banana"]
        FALLBACK=[{"id":"gpt-image-1","display_name":"GPT Image 1"}, {"id":"gpt-image-1-mini","display_name":"GPT Image 1 Mini"}, {"id":"gpt-image-2","display_name":"GPT Image 2"}]
        def _is_img(mid: str) -> bool:
            return any(k in mid.lower() for k in IMAGE_KW)
        filtered=[m for m in remote_models if _is_img(m.get("id") or m.get("model") or m.get("name") or "")]
        if filtered:
            remote_models=filtered
        elif not remote_models or len(remote_models)<=20:
            remote_models=FALLBACK
    if not remote_models:
        raise HTTPException(status_code=400, detail=f"Gagal sync models: {last_err or 'no models'}")
    synced=0
    async with _pool.acquire() as con:
        for m in remote_models:
            mid=m.get("id") or m.get("model") or m.get("name")
            if not mid:
                continue
            internal_id, external_id = _normalize_model_ids(mid, provider_id, None)
            existing = await con.fetchrow("SELECT id, is_active, is_default FROM ai_models WHERE id=$1 OR (provider_id=$2 AND external_id=$3)", internal_id, provider_id, external_id)
            is_active = existing["is_active"] if existing else False
            is_default = existing["is_default"] if existing else False
            display = m.get("display_name") or m.get("id") or mid
            desc = m.get("description") or m.get("owned_by") or ""
            await con.execute("INSERT INTO ai_models (id, provider_id, external_id, display_name, description, is_active, is_default, sort_order, capabilities, updated_at) VALUES ($1,$2,$3,$4,$5,$6,$7,0,'{}'::jsonb, now()) ON CONFLICT (id) DO UPDATE SET provider_id=$2, external_id=$3, display_name=COALESCE(EXCLUDED.display_name, ai_models.display_name), description=COALESCE(EXCLUDED.description, ai_models.description), updated_at=now()", internal_id, provider_id, external_id, display, desc, is_active, is_default)
            synced+=1
    await audit_log("models_sync", provider_id, f"synced={synced}")
    return {"ok": True, "synced": synced, "models": [m.get("id") for m in remote_models[:100]]}

# ---- Users + Plans + Orders + Deposits + Balance + Referral + Audit ----
@app.get("/api/users/{uid}")
async def user_detail(uid: str, _: bool = Depends(require_auth)):
    try:
        uid_int=int(str(uid).strip())
    except Exception:
        raise HTTPException(status_code=400, detail="User ID tidak valid")
    if uid_int<1 or uid_int>9_000_000_000_000:
        raise HTTPException(status_code=400, detail="User ID out of range")
    async with _pool.acquire() as con:
        u = await con.fetchrow("SELECT * FROM users WHERE user_id=$1", uid_int)
        if not u:
            raise HTTPException(status_code=404, detail=f"User {uid_int} tidak ditemukan")
        total = await con.fetchval("SELECT count(*) FROM generations WHERE user_id=$1", uid_int) or 0
        ok = await con.fetchval("SELECT count(*) FROM generations WHERE user_id=$1 AND success", uid_int) or 0
        today = await con.fetchval("SELECT count(*) FROM generations WHERE user_id=$1 AND created_at::date=CURRENT_DATE", uid_int) or 0
        gens = await con.fetch("SELECT kind,prompt,size,success,created_at FROM generations WHERE user_id=$1 ORDER BY id DESC LIMIT 50", uid_int)
    return {"user": dict(u), "total": total, "success": ok, "failed": total-ok, "today": today, "generations": [dict(g) for g in gens]}

@app.get("/api/analytics")
async def analytics(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        hours = await con.fetch("SELECT EXTRACT(HOUR FROM created_at)::int AS h, count(*) AS c FROM generations WHERE created_at > now()-interval '30 days' GROUP BY h ORDER BY h")
        top_prompts = await con.fetch("SELECT prompt, count(*) c FROM generations WHERE created_at > now()-interval '30 days' GROUP BY prompt ORDER BY c DESC LIMIT 20")
        errors = await con.fetch("SELECT prompt, created_at FROM generations WHERE success=false ORDER BY id DESC LIMIT 20")
        daily = await con.fetch("SELECT d::date AS day, count(*) AS gen FROM generate_series(CURRENT_DATE-29, CURRENT_DATE, '1 day') d LEFT JOIN generations g ON g.created_at::date=d::date GROUP BY d ORDER BY d")
    return {"hours": [dict(r) for r in hours], "top_prompts": [dict(r) for r in top_prompts], "errors": [dict(r) for r in errors], "daily": [{"day": r["day"].strftime("%Y-%m-%d") if r["day"] else "", "gen": r["gen"]} for r in daily]}

@app.get("/api/errors")
async def error_list(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch("SELECT id, user_id, prompt, created_at FROM generations WHERE success=false ORDER BY id DESC LIMIT 100")
    return {"errors": [dict(r) for r in rows]}

class PlanBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    daily_limit: int = Field(default=100, ge=0, le=10000)
    price: int = Field(default=0, ge=0, le=100_000_000)
    duration_days: int = Field(default=30, ge=1, le=3650)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=10000)

@app.get("/api/plans")
async def list_plans(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch("SELECT * FROM plans ORDER BY sort_order, id")
    return {"plans": [dict(r) for r in rows]}

@app.post("/api/plans")
async def create_plan(body: PlanBody, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        row = await con.fetchrow("INSERT INTO plans (name,daily_limit,price,duration_days,description,is_active,sort_order) VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id", body.name, body.daily_limit, body.price, body.duration_days, body.description, body.is_active, body.sort_order)
    await audit_log("plan_create", str(row["id"]), body.name)
    return {"ok": True, "id": row["id"]}

@app.put("/api/plans/{pid}")
async def update_plan(pid: int, body: PlanBody, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        await con.execute("UPDATE plans SET name=$2,daily_limit=$3,price=$4,duration_days=$5,description=$6,is_active=$7,sort_order=$8 WHERE id=$1", pid, body.name, body.daily_limit, body.price, body.duration_days, body.description, body.is_active, body.sort_order)
    await audit_log("plan_update", str(pid), body.name)
    return {"ok": True}

@app.delete("/api/plans/{pid}")
async def delete_plan(pid: int, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        await con.execute("DELETE FROM plans WHERE id=$1", pid)
    await audit_log("plan_delete", str(pid), "")
    return {"ok": True}

class MethodBody(BaseModel):
    type: str = Field(default="bank", max_length=20)
    name: str = Field(..., min_length=1, max_length=100)
    account_name: str | None = Field(default=None, max_length=100)
    account_number: str | None = Field(default=None, max_length=50)
    instructions: str | None = Field(default=None, max_length=1000)
    qr_image: str | None = Field(default=None, max_length=200)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=10000)

@app.get("/api/methods")
async def list_methods(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch("SELECT * FROM payment_methods ORDER BY sort_order, id")
    return {"methods": [dict(r) for r in rows]}

@app.post("/api/methods")
async def create_method(body: MethodBody, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        row = await con.fetchrow("INSERT INTO payment_methods (type,name,account_name,account_number,instructions,qr_image,is_active,sort_order) VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id", body.type, body.name, body.account_name, body.account_number, body.instructions, body.qr_image, body.is_active, body.sort_order)
    await audit_log("method_create", str(row["id"]), body.name)
    return {"ok": True, "id": row["id"]}

@app.put("/api/methods/{mid}")
async def update_method(mid: int, body: MethodBody, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        await con.execute("UPDATE payment_methods SET type=$2,name=$3,account_name=$4,account_number=$5,instructions=$6,qr_image=$7,is_active=$8,sort_order=$9 WHERE id=$1", mid, body.type, body.name, body.account_name, body.account_number, body.instructions, body.qr_image, body.is_active, body.sort_order)
    await audit_log("method_update", str(mid), body.name)
    return {"ok": True}

@app.delete("/api/methods/{mid}")
async def delete_method(mid: int, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        await con.execute("DELETE FROM payment_methods WHERE id=$1", mid)
    await audit_log("method_delete", str(mid), "")
    return {"ok": True}

@app.get("/api/orders")
async def list_orders(status: str = "", _: bool = Depends(require_auth)):
    q = "SELECT o.*, u.username, u.first_name FROM orders o LEFT JOIN users u ON u.user_id=o.user_id "
    args=[]
    if status in ("pending","approved","rejected"):
        q+="WHERE o.status=$1 "; args.append(status)
    q+="ORDER BY o.id DESC LIMIT 200"
    async with _pool.acquire() as con:
        rows = await con.fetch(q, *args)
        counts = await con.fetch("SELECT status, count(*) c FROM orders GROUP BY status")
    cmap={r["status"]:r["c"] for r in counts}
    return {"orders": [dict(r) for r in rows], "counts": {"pending": cmap.get("pending",0), "approved": cmap.get("approved",0), "rejected": cmap.get("rejected",0)}}

@app.get("/api/orders/{oid}/proof")
async def order_proof(oid: int, _: bool = Depends(require_auth)):
    from fastapi.responses import Response as FResponse
    async with _pool.acquire() as con:
        fid = await con.fetchval("SELECT proof_file_id FROM orders WHERE id=$1", oid)
    if not fid:
        raise HTTPException(status_code=404, detail="Belum ada bukti")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile", params={"file_id": fid})
            r.raise_for_status()
            j=r.json()
            if not j.get("ok"):
                raise HTTPException(status_code=404, detail="File tidak ditemukan Telegram")
            path=j.get("result",{}).get("file_path")
            if not path:
                raise HTTPException(status_code=404, detail="file_path kosong")
            img=await client.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}")
            img.raise_for_status()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Gagal ambil file Telegram")
    return FResponse(content=img.content, media_type="image/jpeg")

class DecisionBody(BaseModel):
    note: str | None = Field(default=None, max_length=500)

async def _notify_user(user_id: int, text: str):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": user_id, "text": text, "parse_mode": "HTML"})
    except Exception:
        pass

def _rupiah(n) -> str:
    try:
        return "Rp" + f"{int(n):,}".replace(",", ".")
    except Exception:
        return f"Rp{n}"

@app.post("/api/orders/{oid}/approve")
async def approve_order(oid: int, _: bool = Depends(require_auth)):
    from datetime import datetime, timezone, timedelta
    async with _pool.acquire() as con:
        async with con.transaction():
            o = await con.fetchrow("SELECT * FROM orders WHERE id=$1 FOR UPDATE", oid)
            if not o:
                raise HTTPException(status_code=404, detail="Order tidak ditemukan")
            if o["status"]!="pending":
                raise HTTPException(status_code=400, detail="Order sudah diproses")
            base=datetime.now(timezone.utc)
            cur=await con.fetchval("SELECT premium_until FROM users WHERE user_id=$1 FOR UPDATE", o["user_id"])
            if cur and cur>base:
                base=cur
            until=base+timedelta(days=o["duration_days"])
            await con.execute("UPDATE users SET premium_until=$2, plan_id=$3, plan_name=$4 WHERE user_id=$1", o["user_id"], until, o["plan_id"], o["plan_name"])
            await con.execute("UPDATE orders SET status='approved', decided_at=now() WHERE id=$1", oid)
    lim="♾️ Unlimited" if o["daily_limit"]==0 else f"{o['daily_limit']} gambar/hari"
    await _notify_user(o["user_id"], f"🎉 <b>Selamat! Premium kamu aktif!</b>\n\n💎 Paket: <b>{o['plan_name']}</b>\n📊 Kuota: <b>{lim}</b>\n⏳ Berlaku s/d: <b>{until.strftime('%d %b %Y')}</b>\n\nTerima kasih sudah upgrade! Selamat berkreasi 🎨")
    await audit_log("order_approve", str(oid), f"user={o['user_id']} plan={o['plan_name']}")
    return {"ok": True, "premium_until": until.isoformat()}

@app.post("/api/orders/{oid}/reject")
async def reject_order(oid: int, body: DecisionBody, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        async with con.transaction():
            o=await con.fetchrow("SELECT * FROM orders WHERE id=$1 FOR UPDATE", oid)
            if not o:
                raise HTTPException(status_code=404, detail="Order tidak ditemukan")
            if o["status"]!="pending":
                raise HTTPException(status_code=400, detail="Order sudah diproses")
            await con.execute("UPDATE orders SET status='rejected', note=$2, decided_at=now() WHERE id=$1", oid, body.note)
    txt="❌ <b>Pembayaran ditolak</b>\n\nMaaf, pembayaranmu tidak dapat diverifikasi."
    if body.note:
        txt+=f"\n\n📝 Catatan admin: <i>{_html.escape(body.note)}</i>"
    txt+="\n\nSilakan coba lagi atau hubungi admin ya 🙏"
    await _notify_user(o["user_id"], txt)
    await audit_log("order_reject", str(oid), body.note or "")
    return {"ok": True}

@app.get("/api/premium/stats")
async def premium_stats(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        active=await con.fetchval("SELECT count(*) FROM users WHERE premium_until > now()") or 0
        pending=await con.fetchval("SELECT count(*) FROM orders WHERE status='pending'") or 0
        revenue=await con.fetchval("SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='approved'") or 0
        approved=await con.fetchval("SELECT count(*) FROM orders WHERE status='approved'") or 0
    return {"active_premium": active, "pending_orders": pending, "total_revenue": revenue, "total_approved": approved}

class BalanceSettingsBody(BaseModel):
    enabled: bool=True
    min_amount: int=Field(default=10000, ge=0, le=100_000_000)
    max_amount: int=Field(default=5000000, ge=0, le=100_000_000)
    quick_amounts: list[int]=Field(default=[10000,25000,50000,100000,250000], max_length=10)
    @field_validator("quick_amounts")
    @classmethod
    def validate_quick(cls, v):
        if len(v)>10:
            raise ValueError("max 10 quick amounts")
        for x in v:
            if x<0 or x>100_000_000:
                raise ValueError("quick amount out of range")
        return v

@app.get("/api/balance/settings")
async def get_balance_settings(_: bool = Depends(require_auth)):
    enabled=await get_setting("balance_enabled","1")
    min_amount=await get_setting("deposit_min","10000")
    max_amount=await get_setting("deposit_max","5000000")
    quick_raw=await get_setting("deposit_quick_amounts","10000,25000,50000,100000,250000")
    try:
        quick=[int(x) for x in quick_raw.split(",") if x.strip()]
    except ValueError:
        quick=[10000,25000,50000,100000,250000]
    return {"enabled": enabled=="1", "min_amount": int(min_amount), "max_amount": int(max_amount), "quick_amounts": quick}

@app.post("/api/balance/settings")
async def save_balance_settings(body: BalanceSettingsBody, _: bool = Depends(require_auth)):
    if body.min_amount<0 or body.max_amount<body.min_amount:
        raise HTTPException(status_code=400, detail="Rentang nominal tidak valid")
    await set_setting("balance_enabled","1" if body.enabled else "0")
    await set_setting("deposit_min", max(0, body.min_amount))
    await set_setting("deposit_max", max(0, body.max_amount))
    quick=sorted({int(x) for x in body.quick_amounts if x>0})
    await set_setting("deposit_quick_amounts", ",".join(str(x) for x in quick))
    await audit_log("balance_settings", "-", f"min={body.min_amount} max={body.max_amount}")
    return {"ok": True}

@app.get("/api/deposits")
async def list_deposits(status: str = "", _: bool = Depends(require_auth)):
    q="SELECT d.*, u.username, u.first_name FROM deposits d LEFT JOIN users u ON u.user_id=d.user_id "
    args=[]
    if status in ("pending","approved","rejected"):
        q+="WHERE d.status=$1 "; args.append(status)
    q+="ORDER BY d.id DESC LIMIT 200"
    async with _pool.acquire() as con:
        rows=await con.fetch(q, *args)
        counts=await con.fetch("SELECT status, count(*) c FROM deposits GROUP BY status")
    cmap={r["status"]:r["c"] for r in counts}
    return {"deposits": [dict(r) for r in rows], "counts": {"pending": cmap.get("pending",0), "approved": cmap.get("approved",0), "rejected": cmap.get("rejected",0)}}

@app.get("/api/deposits/stats")
async def deposit_stats(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        pending=await con.fetchval("SELECT count(*) FROM deposits WHERE status='pending'") or 0
        total_in=await con.fetchval("SELECT COALESCE(SUM(amount),0) FROM deposits WHERE status='approved'") or 0
        approved=await con.fetchval("SELECT count(*) FROM deposits WHERE status='approved'") or 0
        total_balance=await con.fetchval("SELECT COALESCE(SUM(balance),0) FROM users") or 0
    return {"pending_deposits": pending, "total_deposited": total_in, "total_approved": approved, "total_balance_outstanding": total_balance}

@app.get("/api/deposits/{did}/proof")
async def deposit_proof(did: int, _: bool = Depends(require_auth)):
    from fastapi.responses import Response as FResponse
    async with _pool.acquire() as con:
        fid=await con.fetchval("SELECT proof_file_id FROM deposits WHERE id=$1", did)
    if not fid:
        raise HTTPException(status_code=404, detail="Belum ada bukti")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r=await client.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile", params={"file_id": fid})
            r.raise_for_status()
            j=r.json()
            if not j.get("ok"):
                raise HTTPException(status_code=404, detail="File tidak ditemukan Telegram")
            path=j.get("result",{}).get("file_path")
            if not path:
                raise HTTPException(status_code=404, detail="file_path kosong")
            img=await client.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}")
            img.raise_for_status()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Gagal ambil file Telegram")
    return FResponse(content=img.content, media_type="image/jpeg")

@app.post("/api/deposits/{did}/approve")
async def approve_deposit(did: int, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        async with con.transaction():
            d=await con.fetchrow("SELECT * FROM deposits WHERE id=$1 FOR UPDATE", did)
            if not d:
                raise HTTPException(status_code=404, detail="Deposit tidak ditemukan")
            if d["status"]!="pending":
                raise HTTPException(status_code=400, detail="Deposit sudah diproses")
            new_balance_row=await con.fetchrow("UPDATE users SET balance = balance + $2 WHERE user_id=$1 RETURNING balance", d["user_id"], d["amount"])
            if not new_balance_row:
                await con.execute("INSERT INTO users (user_id, balance) VALUES ($1,$2) ON CONFLICT (user_id) DO UPDATE SET balance = users.balance + $2", d["user_id"], d["amount"])
                new_balance_row=await con.fetchrow("SELECT balance FROM users WHERE user_id=$1", d["user_id"])
            new_balance=new_balance_row["balance"]
            await con.execute("INSERT INTO balance_logs (user_id, delta, balance_after, reason) VALUES ($1,$2,$3,$4)", d["user_id"], d["amount"], new_balance, f"Deposit #{did} disetujui")
            await con.execute("UPDATE deposits SET status='approved', decided_at=now() WHERE id=$1", did)
    await _notify_user(d["user_id"], f"🎉 <b>Top up berhasil!</b>\n\n💰 Nominal: <b>{_rupiah(d['amount'])}</b>\n💳 Saldo sekarang: <b>{_rupiah(new_balance)}</b>\n\nTerima kasih! 🙏")
    await audit_log("deposit_approve", str(did), f"user={d['user_id']} amount={d['amount']}")
    return {"ok": True, "new_balance": new_balance}

@app.post("/api/deposits/{did}/reject")
async def reject_deposit(did: int, body: DecisionBody, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        async with con.transaction():
            d=await con.fetchrow("SELECT * FROM deposits WHERE id=$1 FOR UPDATE", did)
            if not d:
                raise HTTPException(status_code=404, detail="Deposit tidak ditemukan")
            if d["status"]!="pending":
                raise HTTPException(status_code=400, detail="Deposit sudah diproses")
            await con.execute("UPDATE deposits SET status='rejected', note=$2, decided_at=now() WHERE id=$1", did, body.note)
    txt="❌ <b>Deposit ditolak</b>\n\nMaaf, top up tidak dapat diverifikasi."
    if body.note:
        txt+=f"\n\n📝 Catatan admin: <i>{_html.escape(body.note)}</i>"
    txt+="\n\nSilakan coba lagi atau hubungi admin ya 🙏"
    await _notify_user(d["user_id"], txt)
    await audit_log("deposit_reject", str(did), body.note or "")
    return {"ok": True}

class BalanceAdjustBody(BaseModel):
    user_id: int=Field(..., ge=1)
    delta: int=Field(..., ge=-1_000_000_000, le=1_000_000_000)
    reason: str=Field(default="Penyesuaian manual admin", max_length=500)
    notify: bool=True

@app.post("/api/users/balance/adjust")
async def adjust_user_balance(body: BalanceAdjustBody, _: bool = Depends(require_auth)):
    if body.delta==0:
        raise HTTPException(status_code=400, detail="Nilai penyesuaian tidak boleh 0")
    async with _pool.acquire() as con:
        async with con.transaction():
            row=await con.fetchrow("SELECT balance FROM users WHERE user_id=$1 FOR UPDATE", body.user_id)
            if not row:
                raise HTTPException(status_code=404, detail="User tidak ditemukan")
            if row["balance"]+body.delta<0:
                raise HTTPException(status_code=400, detail="Saldo tidak boleh negatif")
            new_row=await con.fetchrow("UPDATE users SET balance = balance + $2 WHERE user_id=$1 RETURNING balance", body.user_id, body.delta)
            new_balance=new_row["balance"]
            await con.execute("INSERT INTO balance_logs (user_id, delta, balance_after, reason) VALUES ($1,$2,$3,$4)", body.user_id, body.delta, new_balance, body.reason)
    if body.notify:
        sign="+" if body.delta>0 else ""
        await _notify_user(body.user_id, f"ℹ️ <b>Saldo kamu disesuaikan admin</b>\n\nPerubahan: <b>{sign}{_rupiah(body.delta)}</b>\nSaldo sekarang: <b>{_rupiah(new_balance)}</b>\nCatatan: <i>{_html.escape(body.reason)}</i>")
    await audit_log("balance_adjust", str(body.user_id), f"delta={body.delta} reason={body.reason}")
    return {"ok": True, "new_balance": new_balance}

@app.get("/api/users/{uid}/balance/logs")
async def user_balance_logs(uid: int, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows=await con.fetch("SELECT id, delta, balance_after, reason, created_at FROM balance_logs WHERE user_id=$1 ORDER BY id DESC LIMIT 50", uid)
    return {"logs": [dict(r) for r in rows]}

class ReferralSettingsBody(BaseModel):
    enabled: bool=True
    reward_type: str=Field(default="balance", max_length=20)
    reward_amount: int=Field(default=5000, ge=0, le=10_000_000)

@app.get("/api/referral/settings")
async def get_referral_settings_ep(_: bool = Depends(require_auth)):
    enabled=await get_setting("referral_enabled","1")
    reward_type=await get_setting("referral_reward_type","balance")
    reward_amount=await get_setting("referral_reward_amount","5000")
    return {"enabled": enabled=="1", "reward_type": reward_type if reward_type in ("balance","quota") else "balance", "reward_amount": int(reward_amount)}

@app.post("/api/referral/settings")
async def save_referral_settings_ep(body: ReferralSettingsBody, _: bool = Depends(require_auth)):
    if body.reward_type not in ("balance","quota"):
        raise HTTPException(status_code=400, detail="reward_type harus 'balance' atau 'quota'")
    await set_setting("referral_enabled","1" if body.enabled else "0")
    await set_setting("referral_reward_type", body.reward_type)
    await set_setting("referral_reward_amount", int(body.reward_amount))
    await audit_log("referral_settings", "-", f"type={body.reward_type} amount={body.reward_amount}")
    return {"ok": True}

@app.get("/api/referral/stats")
async def referral_stats(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        total=await con.fetchval("SELECT count(*) FROM referrals") or 0
        rewarded=await con.fetchval("SELECT count(*) FROM referrals WHERE status='rewarded'") or 0
        pending=total-rewarded
        balance_paid=await con.fetchval("SELECT COALESCE(SUM(reward_amount),0) FROM referrals WHERE status='rewarded' AND reward_type='balance'") or 0
        quota_paid=await con.fetchval("SELECT COALESCE(SUM(reward_amount),0) FROM referrals WHERE status='rewarded' AND reward_type='quota'") or 0
        top=await con.fetch("SELECT r.referrer_id, u.username, u.first_name, count(*) AS total, count(*) FILTER (WHERE r.status='rewarded') AS rewarded FROM referrals r LEFT JOIN users u ON u.user_id=r.referrer_id GROUP BY r.referrer_id, u.username, u.first_name ORDER BY rewarded DESC, total DESC LIMIT 10")
    return {"total": total, "rewarded": rewarded, "pending": pending, "balance_paid": balance_paid, "quota_paid": quota_paid, "top_referrers": [dict(r) for r in top]}

@app.get("/api/referral/list")
async def referral_list(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows=await con.fetch("SELECT r.*, ru.username AS referrer_username, ru.first_name AS referrer_first_name, rd.username AS referred_username, rd.first_name AS referred_first_name FROM referrals r LEFT JOIN users ru ON ru.user_id=r.referrer_id LEFT JOIN users rd ON rd.user_id=r.referred_id ORDER BY r.id DESC LIMIT 200")
    return {"referrals": [dict(r) for r in rows]}

@app.get("/api/audit/logs")
async def audit_logs(limit: int = 100, _: bool = Depends(require_auth)):
    limit = max(1, min(200, limit))
    async with _pool.acquire() as con:
        rows = await con.fetch("SELECT * FROM admin_audit ORDER BY id DESC LIMIT $1", limit)
    return {"logs": [dict(r) for r in rows]}
