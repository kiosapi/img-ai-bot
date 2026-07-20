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
import platform
import psutil
import socket
import datetime as _dt
from pathlib import Path
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

# ---- Bot Health Center (Phase1 fit2) ----
# Bot: heartbeat freshness + last gen + queue stuck + active users
# Providers: latency check per provider (no key leak, just base_url connectivity)
# System: restart-bot flag/trigger

_bot_last_restart_flag_path = Path(os.environ.get("BOT_RESTART_FLAG", "/tmp/imgbot_restart_bot.flag"))
_provider_health_cache: dict = {}
_provider_health_cache_ts: float = 0.0

def _parse_iso(s: str | None) -> _dt.datetime | None:
    if not s:
        return None
    try:
        # normalize Z etc
        txt = s.strip()
        if txt.endswith("Z"):
            txt = txt[:-1] + "+00:00"
        dt = _dt.datetime.fromisoformat(txt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.timezone.utc)
        return dt
    except Exception:
        return None

@app.get("/api/health/bot")
async def health_bot(_: bool = Depends(require_auth)):
    now = _dt.datetime.now(_dt.timezone.utc)
    heartbeat_raw = await get_setting("bot_last_heartbeat", "")
    heartbeat_dt = _parse_iso(heartbeat_raw)
    online = False
    age_sec = None
    if heartbeat_dt:
        age_sec = int((now - heartbeat_dt).total_seconds())
        online = age_sec < 120  # <2m = online

    async with _pool.acquire() as con:
        last_gen = await con.fetchrow("SELECT id, user_id, kind, success, created_at FROM generations ORDER BY id DESC LIMIT 1")
        gen_per_hour = await con.fetchval("SELECT count(*) FROM generations WHERE created_at > now() - interval '1 hour'") or 0
        # queue stuck: generations? project has no queue table – we interpret stuck as:
        # aiogram FSM states lingering >5m OR usage anomaly.
        # For now, count aiogram_states with updated < now()-5m as potential stuck jobs, plus active fsm in memory not available here.
        # So we query aiogram_states older than 5m.
        try:
            stuck_count = await con.fetchval("SELECT count(*) FROM aiogram_states WHERE updated < now() - interval '5 minutes'") or 0
        except Exception:
            stuck_count = 0
        try:
            active_users_5m = await con.fetchval("SELECT count(DISTINCT user_id) FROM generations WHERE created_at > now() - interval '5 minutes'") or 0
        except Exception:
            active_users_5m = 0
        try:
            total_users = await con.fetchval("SELECT count(*) FROM users") or 0
        except Exception:
            total_users = 0
        try:
            today_gen = await con.fetchval("SELECT count(*) FROM generations WHERE created_at::date = CURRENT_DATE") or 0
        except Exception:
            today_gen = 0

    return {
        "status": "online" if online else "offline",
        "online": online,
        "heartbeat_raw": heartbeat_raw or None,
        "heartbeat_at": heartbeat_dt.isoformat() if heartbeat_dt else None,
        "heartbeat_age_sec": age_sec,
        "last_generation": dict(last_gen) if last_gen else None,
        "gen_per_hour": int(gen_per_hour),
        "today_gen": int(today_gen),
        "queue_stuck_count": int(stuck_count),
        "active_users_5m": int(active_users_5m),
        "total_users": int(total_users),
        "checked_at": now.isoformat(),
    }

@app.get("/api/health/providers")
async def health_providers(_: bool = Depends(require_auth)):
    # Ping latency per active provider: SELECT active models + measure httpx HEAD/GET base_url
    # Never expose api keys
    global _provider_health_cache, _provider_health_cache_ts
    now_ts = time.time()
    # optional 30s cache to avoid hammering providers
    if _provider_health_cache and (now_ts - _provider_health_cache_ts) < 30:
        # still return cached but indicate cached_at
        return _provider_health_cache

    async with _pool.acquire() as con:
        prov_rows = await con.fetch("SELECT id, name, base_url, is_active FROM providers ORDER BY id")
        # collect settings base_url overrides
        settings_rows = await con.fetch("SELECT key, value FROM settings WHERE key LIKE '%_base_url'")
        settings_map = {r["key"]: r["value"] for r in settings_rows}
        model_rows = await con.fetch("SELECT provider_id, count(*) as cnt, count(*) FILTER (WHERE is_active) as active_cnt FROM ai_models GROUP BY provider_id")

    model_map = {r["provider_id"]: {"total": r["cnt"], "active": r["active_cnt"]} for r in model_rows}
    results = []
    # measure latency concurrently
    async def _ping_provider(pid: str, base_url: str):
        url = (base_url or "").strip().rstrip("/")
        if not url:
            return {"latency_ms": None, "ok": False, "error": "no base_url"}
        # don't send api key; just simple GET with short timeout, follow redirects
        # try root / health / models endpoint lightweight
        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(6.0, connect=3.0), follow_redirects=True) as client:
                # try HEAD first, then GET /models or base
                try:
                    # lightweight: GET base URL, expect 401/404 quickly still means reachable
                    resp = await client.get(url, headers={"User-Agent": "imgbot-health/1.0"})
                    # Consider reachable if we got any HTTP response (even 401/404)
                    latency = int((time.time() - t0) * 1000)
                    ok = resp.status_code < 500  # <500 reachable
                    return {"latency_ms": latency, "ok": ok, "status_code": resp.status_code, "error": None if ok else f"http {resp.status_code}"}
                except httpx.TimeoutException:
                    return {"latency_ms": None, "ok": False, "error": "timeout"}
                except httpx.ConnectError as ce:
                    return {"latency_ms": None, "ok": False, "error": f"connect {str(ce)[:120]}"}
        except Exception as e:
            return {"latency_ms": None, "ok": False, "error": str(e)[:200]}

    # run pings
    ping_tasks = []
    for p in prov_rows:
        pid = p["id"]
        b_url = settings_map.get(f"{pid}_base_url") or p["base_url"] or ""
        ping_tasks.append((p, _ping_provider(pid, b_url)))

    # sequential to avoid many concurrent outbound? do parallel though
    # gather
    gathered = []
    for prov, coro in ping_tasks:
        try:
            res = await coro
        except Exception as e:
            res = {"latency_ms": None, "ok": False, "error": str(e)[:200]}
        mm = model_map.get(prov["id"], {"total": 0, "active": 0})
        gathered.append({
            "id": prov["id"],
            "name": prov["name"],
            "base_url": prov["base_url"],
            "resolved_base_url": settings_map.get(f"{prov['id']}_base_url") or prov["base_url"],
            "is_active": bool(prov["is_active"]),
            "models_total": int(mm["total"]),
            "models_active": int(mm["active"]),
            **res,
        })

    out = {"providers": gathered, "checked_at": _dt.datetime.now(_dt.timezone.utc).isoformat(), "cached": False}
    _provider_health_cache = out
    _provider_health_cache_ts = now_ts
    return out

class RestartBotBody(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
    mode: str | None = Field(default="flag", max_length=20)  # flag | docker | log

@app.post("/api/system/restart-bot")
async def restart_bot(body: RestartBotBody | None = None, _: bool = Depends(require_auth)):
    reason = (body.reason if body and body.reason else "admin dashboard restart").strip()[:500]
    mode = (body.mode if body and body.mode else "flag").strip().lower()
    details = []
    flag_written = False
    docker_attempted = False
    docker_ok = False
    docker_err = ""

    # 1) always write flag file – external watcher / bot itself / systemd can poll
    try:
        _bot_last_restart_flag_path.parent.mkdir(parents=True, exist_ok=True)
        content = f"{int(time.time())}\n{reason}\n{mode}\n"
        _bot_last_restart_flag_path.write_text(content, encoding="utf-8")
        flag_written = True
        details.append(f"flag written {_bot_last_restart_flag_path}")
    except Exception as e:
        details.append(f"flag write failed: {e}")

    # 2) try docker restart if mode==docker or auto-detect env var BOT_CONTAINER_NAME
    container_name = os.environ.get("BOT_CONTAINER_NAME", "") or os.environ.get("LOG_CONTAINER_BOT", "imgbot-bot-1")
    # allow comma list
    candidates = [c.strip() for c in container_name.split(",") if c.strip()]
    if mode == "docker" or (os.environ.get("ENABLE_DOCKER_RESTART", "0") == "1"):
        docker_attempted = True
        loop = asyncio.get_running_loop()

        def _try_restart():
            import subprocess as _sp
            for cand in candidates[:3]:
                try:
                    out = _sp.check_output(["docker", "restart", cand], timeout=15, text=True, stderr=_sp.STDOUT)
                    return True, cand, out.strip()[:500]
                except Exception as ex:
                    last = str(ex)[:500]
                    continue
            return False, candidates[0] if candidates else "unknown", last if candidates else "no candidates"

        try:
            docker_ok, used, out_msg = await loop.run_in_executor(None, _try_restart)
            if docker_ok:
                details.append(f"docker restart ok {used}: {out_msg}")
            else:
                docker_err = out_msg if 'out_msg' in locals() else "docker restart failed"
                details.append(f"docker restart fail {used}: {docker_err}")
        except Exception as e:
            docker_err = str(e)[:500]
            details.append(f"docker exec error: {docker_err}")

    await audit_log("bot_restart", "-", f"mode={mode} flag={flag_written} docker_ok={docker_ok} reason={reason}")

    return {
        "ok": True,
        "flag_written": flag_written,
        "flag_path": str(_bot_last_restart_flag_path),
        "docker_attempted": docker_attempted,
        "docker_ok": docker_ok,
        "docker_error": docker_err,
        "details": details,
        "reason": reason,
        "note": "Flag file written. If docker mode, container restart attempted. For prod, ensure docker-compose or watcher monitors flag file and restarts bot service.",
    }

# ---- Live Logs Viewer ----
# ---- Live Logs Viewer (REALTIME via Docker socket, no fake fallback) ----
import subprocess
import shutil

LOG_CONTAINERS = {
    "bot": os.environ.get("LOG_CONTAINER_BOT", "imgbot-bot-1,imgbot_bot_1,bot"),
    "api": os.environ.get("LOG_CONTAINER_API", "imgbot-api-1,imgbot_api_1,api"),
    "postgres": os.environ.get("LOG_CONTAINER_POSTGRES", "imgbot-postgres-1,imgbot_postgres_1,postgres"),
    "web": os.environ.get("LOG_CONTAINER_WEB", "imgbot-web-1,imgbot_web_1,web"),
}

LOG_LEVEL_KEYWORDS = {
    "error": ["error", "exception", "traceback", "failed", "fatal", "critical"],
    "warn": ["warn", "warning", "deprecated"],
    "info": ["info", "success", "started", "connected"],
    "debug": ["debug"],
}

def _classify_level(line: str) -> str:
    low = line.lower()
    for kw in LOG_LEVEL_KEYWORDS["error"]:
        if kw in low:
            return "error"
    for kw in LOG_LEVEL_KEYWORDS["warn"]:
        if kw in low:
            return "warn"
    for kw in LOG_LEVEL_KEYWORDS["debug"]:
        if kw in low:
            return "debug"
    return "info"

async def _docker_logs_via_socket(container_name: str, lines: int) -> tuple[str, str]:
    """Real docker logs via /var/run/docker.sock HTTP API — no binary needed, 100% realtime accurate.
    Returns (text, error)."""
    sock_path = "/var/run/docker.sock"
    if not os.path.exists(sock_path):
        return "", "docker.sock not found — mount /var/run/docker.sock:/var/run/docker.sock:ro in compose"
    try:
        # resolve container id by name via API
        reader, writer = await asyncio.open_unix_connection(sock_path)
        # list containers
        req = f"GET /containers/json?all=1 HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode()
        writer.write(req)
        await writer.drain()
        data = b""
        while True:
            chunk = await writer.read(4096)
            if not chunk:
                break
            data += chunk
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        # parse HTTP response
        if b"\r\n\r\n" in data:
            _, body = data.split(b"\r\n\r\n", 1)
            # handle chunked encoding
            if b'"Id"' in body:
                import json
                text = body.decode("utf-8", errors="ignore")
                # find json array start
                start = text.find("[")
                end = text.rfind("]") + 1
                if start >= 0 and end > start:
                    containers = json.loads(text[start:end])
                    target_id = None
                    search_names = [container_name.strip()]
                    # also try variations
                    for c in containers:
                        names = c.get("Names", [])
                        c_id = c.get("Id", "")
                        for n in names:
                            clean = n.lstrip("/")
                            if clean == container_name or container_name in clean or clean in container_name:
                                target_id = c_id
                                break
                        if c_id[:12] == container_name[:12] or container_name in c_id:
                            target_id = c_id
                        if target_id:
                            break
                    if not target_id:
                        # fallback: if we have exact name list includes, try first container that matches type by label
                        # e.g. find container where image includes 'imgbot-api' etc
                        for c in containers:
                            image = c.get("Image", "")
                            if container_name.replace("-1", "").replace("_1", "") in image:
                                target_id = c.get("Id")
                                if target_id:
                                    break
                    if target_id:
                        # now fetch logs for that id
                        reader2, writer2 = await asyncio.open_unix_connection(sock_path)
                        path = f"/containers/{target_id}/logs?tail={lines}&stdout=1&stderr=1&timestamps=0"
                        req2 = f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode()
                        writer2.write(req2)
                        await writer2.drain()
                        data2 = b""
                        while True:
                            chunk = await writer2.read(8192)
                            if not chunk:
                                break
                            data2 += chunk
                        try:
                            writer2.close()
                            await writer2.wait_closed()
                        except Exception:
                            pass
                        if b"\r\n\r\n" in data2:
                            _, body2 = data2.split(b"\r\n\r\n", 1)
                            # Docker multiplexed stream: each frame 8-byte header
                            out_lines = []
                            buf = body2
                            # if content-type text/plain (non-multiplexed) fallback
                            if body2.startswith(b"\x01") or body2.startswith(b"\x02"):
                                # multiplexed
                                idx = 0
                                while idx + 8 <= len(buf):
                                    # header: stream type 1 byte, 3 zero bytes, 4 byte BE length
                                    length = int.from_bytes(buf[idx+4:idx+8], "big")
                                    frame = buf[idx+8:idx+8+length]
                                    out_lines.append(frame.decode("utf-8", errors="ignore"))
                                    idx += 8 + length
                                text_out = "".join(out_lines)
                            else:
                                # try decode directly (plain text logs non-multiplexed)
                                text_out = buf.decode("utf-8", errors="ignore")
                                # strip chunked encoding numbers if present
                                # chunked format: hex size CRLF data CRLF ... 0 CRLF CRLF
                                if "\r\n" in text_out and text_out[:10].strip().replace("\r\n", "").replace("\n", "").isdigit() == False:
                                    # might be chunked, attempt to strip chunk headers
                                    cleaned = []
                                    for part in text_out.split("\r\n"):
                                        p = part.strip()
                                        if not p:
                                            continue
                                        try:
                                            int(p, 16)
                                            continue
                                        except ValueError:
                                            cleaned.append(part)
                                    if cleaned:
                                        text_out = "\n".join(cleaned)
                            if text_out.strip():
                                return text_out, ""
                            return "", f"container {container_name} logs empty (id {target_id[:12]})"
                        return "", f"failed to parse logs response for {container_name}"
                return "", f"no body in containers list response"
            return "", "no container data in socket response"
        return "", f"no http separator in socket response for {container_name}"
    except FileNotFoundError:
        return "", "docker.sock not found"
    except Exception as e:
        return "", f"socket error {container_name}: {e}"[:300]

def _try_docker_logs_sync(container_names: list[str], lines: int) -> tuple[str, str | None, str]:
    """Fallback sync docker binary if available (local dev)."""
    if not shutil.which("docker"):
        return "", None, "docker binary not found — use docker.sock (mount volume)"
    last_err = ""
    for name in container_names:
        name = name.strip()
        if not name:
            continue
        try:
            result = subprocess.run(["docker", "logs", "--tail", str(lines), name], capture_output=True, text=True, timeout=8)
            combined = (result.stdout + "\n" + result.stderr).strip()
            if combined:
                return combined, name, ""
            if result.returncode == 0:
                return "", name, ""
            last_err = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        except Exception as e:
            last_err = str(e)[:300]
    return "", None, last_err or "no container matched"

@app.get("/api/logs/tail")
async def logs_tail(
    type: str = "bot",
    lines: int = 200,
    level: str = "all",
    search: str = "",
    _: bool = Depends(require_auth),
):
    # validation
    type = (type or "bot").lower().strip()
    if type not in ("bot", "api", "postgres", "web"):
        type = "bot"
    lines = max(1, min(500, int(lines or 200)))
    level = (level or "all").lower().strip()
    if level not in ("all", "info", "warn", "error", "debug"):
        level = "all"
    search = (search or "").strip()[:200]

    container_spec = LOG_CONTAINERS.get(type, "")
    container_list = [c.strip() for c in container_spec.split(",") if c.strip()]

    logs_text = ""
    used_container = None
    source = "docker-socket:real"
    docker_err = ""

    # attempt 1: real docker logs via socket (100% realtime, no fake)
    for cname in container_list:
        txt, err = await _docker_logs_via_socket(cname, lines)
        if txt:
            logs_text = txt
            used_container = cname
            source = f"docker-socket:real:{cname}"
            docker_err = ""
            break
        if err and not docker_err:
            docker_err = err
        # if docker.sock says logs empty but no error, keep trying next name

    # attempt 2: fallback sync docker binary (local dev)
    if not logs_text:
        txt2, used2, err2 = _try_docker_logs_sync(container_list, lines)
        if txt2:
            logs_text = txt2
            used_container = used2
            source = f"docker-binary:real:{used2}"
            docker_err = ""
        elif err2 and not docker_err:
            docker_err = err2

    # attempt 3: fallback DB only if both docker methods fail — clearly marked as DB not real logs
    if not logs_text:
        try:
            async with _pool.acquire() as con:
                if type == "bot":
                    rows = await con.fetch("SELECT id, created_at, user_id, prompt, success FROM generations ORDER BY id DESC LIMIT $1", lines)
                    formatted = []
                    for r in rows:
                        status = "ERROR" if not r["success"] else "INFO"
                        ts = r["created_at"].isoformat() if r["created_at"] else ""
                        prompt_snip = (r["prompt"] or "")[:120]
                        formatted.append(f"{ts} [{status}] user={r['user_id']} kind=gen prompt={prompt_snip} success={r['success']}")
                    logs_text = "\n".join(formatted) if formatted else "no generation logs in DB (DB fallback, not real docker logs)"
                    source = "db:generations-fallback (NOT real logs - docker unavailable)"
                elif type == "api":
                    rows = await con.fetch("SELECT id, ts, action, target, detail FROM admin_audit ORDER BY id DESC LIMIT $1", lines)
                    formatted = []
                    for r in rows:
                        ts = r["ts"].isoformat() if r["ts"] else ""
                        lvl = "WARN" if "fail" in (r["action"] or "").lower() else "INFO"
                        formatted.append(f"{ts} [{lvl}] {r['action']} target={r['target']} detail={r['detail'][:200]}")
                    logs_text = "\n".join(formatted) if formatted else "no audit logs (DB fallback)"
                    source = "db:admin_audit-fallback (NOT real logs)"
                elif type == "postgres":
                    rows = await con.fetch("SELECT pid, query, state, now() - query_start AS dur FROM pg_stat_activity WHERE datname = current_database() AND state != 'idle' ORDER BY query_start DESC LIMIT 20")
                    formatted = [f"[INFO] Postgres activity: {len(rows)} active queries (live pg_stat, real)"]
                    for r in rows:
                        q = (r["query"] or "")[:200].replace("\n", " ")
                        formatted.append(f"pid={r['pid']} dur={r['dur']} state={r['state']} query={q}")
                    logs_text = "\n".join(formatted) if formatted else "postgres stats empty (real pg_stat)"
                    source = "db:pg_stat-real (live)"
                else:
                    rows = await con.fetch("SELECT id, ts, action, detail FROM admin_audit ORDER BY id DESC LIMIT $1", lines)
                    formatted = [f"{r['ts']} [{r['action']}] {str(r['detail'] or '')[:200]}" for r in rows]
                    logs_text = "\n".join(formatted) if formatted else "no web logs fallback"
                    source = "db:fallback (NOT real docker logs)"
        except Exception as e:
            if not logs_text:
                logs_text = f"fallback also failed: {e} | docker_err={docker_err}"
                source = "error"

    # parse into structured lines
    raw_lines = [l for l in logs_text.splitlines() if l.strip() != ""]
    output = []
    for idx, ln in enumerate(raw_lines[-lines:]):
        lvl = _classify_level(ln)
        if level != "all" and lvl != level:
            if not (level == "warn" and lvl == "error"):
                continue
        if search and search.lower() not in ln.lower():
            continue
        output.append({"line": ln[:2000], "level": lvl, "idx": idx})

    return {
        "type": type,
        "lines_requested": lines,
        "lines_returned": len(output),
        "source": source,
        "container": used_container,
        "docker_error": docker_err if not used_container else "",
        "logs": output,
        "raw": logs_text[:20000] if level == "all" and not search else None,
    }

# ---- System Monitor (Phase1 fit1) ----
# Non-blocking psutil via thread executor; never leaks env / BOT_TOKEN / DATABASE_URL
def _sync_psutil_snapshot():
    # blocking-ish calls isolated here to run in executor
    cpu = psutil.cpu_percent(interval=0.3)
    cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    # load avg (optional, not on Windows)
    try:
        load1, load5, load15 = psutil.getloadavg()
    except Exception:
        try:
            import os as _os2
            load1, load5, load15 = _os2.getloadavg()  # type: ignore
        except Exception:
            load1 = load5 = load15 = 0.0
    boot_ts = psutil.boot_time()
    uptime_sec = int(time.time() - boot_ts)
    net = psutil.net_io_counters()
    procs = len(psutil.pids())
    # python process own mem
    self_proc = psutil.Process()
    self_mem = self_proc.memory_info()
    return {
        "cpu_percent": cpu,
        "cpu_per_core": cpu_per_core,
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "memory": {
            "total": vm.total,
            "available": vm.available,
            "used": vm.used,
            "free": vm.free,
            "percent": vm.percent,
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent,
        },
        "load_avg": {"1m": load1, "5m": load5, "15m": load15},
        "boot_time": boot_ts,
        "uptime_seconds": uptime_sec,
        "uptime_human": str(_dt.timedelta(seconds=uptime_sec)),
        "net_io": {"bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv, "packets_sent": net.packets_sent, "packets_recv": net.packets_recv} if net else {},
        "process_count": procs,
        "self_memory": {"rss": self_mem.rss, "vms": self_mem.vms},
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version()[:200],
            "machine": platform.machine(),
            "hostname": socket.gethostname()[:100],
            "python": platform.python_version(),
        },
    }

async def _get_system_metrics_nonblocking() -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_psutil_snapshot)

@app.get("/api/system/metrics")
async def system_metrics(_: bool = Depends(require_auth)):
    # CPU + MEM + DISK + uptime – metric utama dashboard widget
    try:
        snap = await _get_system_metrics_nonblocking()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"psutil failed: {e}")
    return {
        "ok": True,
        "ts": int(time.time()),
        **snap,
    }

async def _get_postgres_stats() -> dict:
    # Never expose connection string or env
    out = {
        "db_size_bytes": 0,
        "db_size_human": "0",
        "tables": {},
        "row_counts": {},
        "pg_stat_activity_count": 0,
        "pg_max_connections": 0,
    }
    try:
        async with _pool.acquire() as con:
            # db size
            db_size = await con.fetchval("SELECT pg_database_size(current_database())")
            out["db_size_bytes"] = int(db_size or 0)
            # human: pg_size_pretty but avoid overhead
            pretty = await con.fetchval("SELECT pg_size_pretty($1)", db_size)
            out["db_size_human"] = pretty or f"{db_size} B"

            # top tables by total size (whitelisted query, no params from user)
            trows = await con.fetch(
                "SELECT relname AS table_name, pg_total_relation_size(c.oid) AS total_bytes, pg_size_pretty(pg_total_relation_size(c.oid)) AS total_pretty, pg_relation_size(c.oid) AS data_bytes "
                "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relkind='r' ORDER BY total_bytes DESC LIMIT 20"
            )
            for r in trows:
                out["tables"][r["table_name"]] = {
                    "total_bytes": int(r["total_bytes"] or 0),
                    "total_pretty": r["total_pretty"],
                    "data_bytes": int(r["data_bytes"] or 0),
                }

            # row counts for key tables – tolerant if table missing
            for tbl in ["users", "generations", "orders", "deposits", "plans", "payment_methods", "balance_logs", "referrals", "usage_daily", "admin_sessions", "broadcast_history", "ai_models", "providers"]:
                try:
                    cnt = await con.fetchval(f"SELECT count(*) FROM {tbl}")
                    out["row_counts"][tbl] = int(cnt or 0)
                except Exception:
                    out["row_counts"][tbl] = -1  # tabel tidak ada

            try:
                conn_cnt = await con.fetchval("SELECT count(*) FROM pg_stat_activity")
                out["pg_stat_activity_count"] = int(conn_cnt or 0)
            except Exception:
                pass
            try:
                max_conn_str = await con.fetchval("SHOW max_connections")
                out["pg_max_connections"] = int(max_conn_str or 0)
            except Exception:
                pass
    except Exception as e:
        out["error"] = str(e)[:300]
    return out

@app.get("/api/system/stats")
async def system_stats(_: bool = Depends(require_auth)):
    pg = await _get_postgres_stats()
    snap = await _get_system_metrics_nonblocking()
    # ringkas disk/cpu/ram + pg
    return {
        "ok": True,
        "ts": int(time.time()),
        "cpu_percent": snap["cpu_percent"],
        "cpu_per_core": snap["cpu_per_core"],
        "cpu_count": snap["cpu_count_logical"],
        "memory": snap["memory"],
        "disk": snap["disk"],
        "load_avg": snap["load_avg"],
        "uptime_seconds": snap["uptime_seconds"],
        "uptime_human": snap["uptime_human"],
        "boot_time": snap["boot_time"],
        "platform": snap["platform"],
        "postgres": pg,
    }

@app.get("/api/system/docker")
async def system_docker(_: bool = Depends(require_auth)):
    # optional docker socket check; fallback safe if not present
    docker_sock = Path("/var/run/docker.sock")
    items = []
    if docker_sock.exists():
        # try docker via stdlib socket http over unix – best-effort, never crash
        try:
            import json as _json2
            import http.client as _httpc
            conn = _httpc.HTTPConnection("localhost", timeout=2)
            # cannot connect via unix directly with http.client; use raw socket
            # fallback: try listing via 'docker' CLI if installed (non-blocking executor)
            def _list_docker():
                import subprocess, json as jj
                try:
                    out = subprocess.check_output(["docker", "ps", "--format", "{{json .}}"], timeout=5, text=True)
                    rows=[]
                    for line in out.strip().splitlines():
                        if line.strip():
                            try:
                                rows.append(jj.loads(line))
                            except Exception:
                                pass
                    return rows
                except Exception as ex:
                    return [{"error": str(ex)[:300]}]
            loop = asyncio.get_running_loop()
            items = await loop.run_in_executor(None, _list_docker)
            return {"ok": True, "docker_available": True, "containers": items[:50]}
        except Exception as e:
            return {"ok": True, "docker_available": True, "containers": [], "error": str(e)[:300]}
    else:
        # no docker socket – fallback: local process list (top 30 by memory)
        def _top_procs():
            lst=[]
            for p in psutil.process_iter(attrs=["pid","name","memory_percent","cpu_percent"]):
                try:
                    info=p.info
                    lst.append(info)
                except Exception:
                    continue
            lst.sort(key=lambda x: x.get("memory_percent",0), reverse=True)
            return lst[:30]
        loop = asyncio.get_running_loop()
        top = await loop.run_in_executor(None, _top_procs)
        return {"ok": True, "docker_available": False, "fallback": "processes", "top_processes": top}

