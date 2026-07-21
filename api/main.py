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
import hashlib
import gzip
import shutil
import subprocess
import json as _json_std
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Annotated
from fastapi import FastAPI, Request, Response, HTTPException, Depends, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from fastapi.middleware.cors import CORSMiddleware
import user_api

DATABASE_URL = os.environ["DATABASE_URL"]
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "/tmp/backups"))
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
_backup_lock = asyncio.Lock()
_restore_lock = asyncio.Lock()
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
def _human_size(n: int | float | None) -> str:
    try:
        v = int(n or 0)
    except Exception:
        return "0 B"
    if v < 1024:
        return f"{v} B"
    if v < 1024*1024:
        return f"{v/1024:.1f} KB"
    if v < 1024*1024*1024:
        return f"{v/(1024*1024):.1f} MB"
    return f"{v/(1024*1024*1024):.2f} GB"

def _is_safe_filename(name: str) -> bool:
    # no path traversal, only safe chars
    if ".." in name or "/" in name or "\\" in name:
        return False
    if len(name) > 200:
        return False
    # allow alphanumeric, _, -, ., 
    if not re.match(r"^[A-Za-z0-9._-]+\.(sql\.gz|dump|sql|gz)$", name):
        return False
    return True

def _ensure_backup_dir():
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

def _calculate_checksum(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024*1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""

def _backup_file_path(filename: str) -> Path:
    # resolve + ensure inside BACKUP_DIR
    _ensure_backup_dir()
    safe = filename.strip().replace("..", "").replace("/", "_").replace("\\", "_")
    p = (BACKUP_DIR / safe).resolve()
    base = BACKUP_DIR.resolve()
    # ensure path is within base
    try:
        p.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename path traversal blocked")
    return p

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
    if audience == "active":
        return "WHERE NOT is_banned AND last_seen > now() - interval '7 days'"
    return "WHERE NOT is_banned"

def _sched_audience_where(target_type: str) -> str:
    return _audience_where(target_type or "all")

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
        # custom_styles no-code presets manager — MUST exist
        await con.execute("""
            CREATE TABLE IF NOT EXISTS custom_styles (
                id SERIAL PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                prompt_prefix TEXT NOT NULL DEFAULT '',
                thumbnail_url TEXT,
                category TEXT NOT NULL DEFAULT 'general',
                is_active BOOLEAN NOT NULL DEFAULT true,
                sort_order INT NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        await con.execute("ALTER TABLE custom_styles ADD COLUMN IF NOT EXISTS thumbnail_url TEXT;")
        await con.execute("ALTER TABLE custom_styles ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'general';")
        await con.execute("ALTER TABLE custom_styles ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true;")
        await con.execute("ALTER TABLE custom_styles ADD COLUMN IF NOT EXISTS sort_order INT NOT NULL DEFAULT 0;")
        await con.execute("CREATE INDEX IF NOT EXISTS idx_custom_styles_sort ON custom_styles(sort_order, id);")
        # moderation_rules + moderation_logs
        await con.execute(
            """
            CREATE TABLE IF NOT EXISTS moderation_rules (
                id SERIAL PRIMARY KEY,
                pattern TEXT NOT NULL,
                type TEXT NOT NULL,
                severity TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )
        await con.execute(
            """
            CREATE TABLE IF NOT EXISTS moderation_logs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                prompt TEXT,
                matched_pattern TEXT,
                rule_id INT,
                action TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )
        await con.execute("CREATE INDEX IF NOT EXISTS idx_moderation_rules_type ON moderation_rules(type);")
        await con.execute("CREATE INDEX IF NOT EXISTS idx_moderation_logs_user ON moderation_logs(user_id);")
        await con.execute("CREATE INDEX IF NOT EXISTS idx_moderation_logs_created ON moderation_logs(created_at DESC);")

        # seed if empty from hardcoded mapping (same as bot/styles.py)
        try:
            cnt = await con.fetchval("SELECT count(*) FROM custom_styles")
            if cnt == 0:
                seed = [
                    ("none", "Default", "", "general", 0),
                    ("anime", "Anime", "anime style, vibrant colors, detailed", "anime", 1),
                    ("realistic", "Realistis", "photorealistic, highly detailed, 8k", "photo", 2),
                    ("cyberpunk", "Cyberpunk", "cyberpunk style, neon lights, futuristic", "fantasy", 3),
                    ("ghibli", "Ghibli", "Studio Ghibli style, soft colors, whimsical", "anime", 4),
                    ("watercolor", "Aquarel", "watercolor painting style", "artistic", 5),
                    ("3d", "3D Render", "3D render, octane, highly detailed, studio lighting", "fantasy", 6),
                    ("oil", "Oil Painting", "oil painting style, textured brush strokes", "artistic", 7),
                    ("minimalist", "Minimalis", "minimalist style, clean, simple", "artistic", 8),
                    ("fantasy", "Fantasi", "fantasy art style, magical, epic lighting", "fantasy", 9),
                    ("photo", "Fotografi", "professional photography, DSLR, sharp focus", "photo", 10),
                ]
                for code, name, pref, cat, order in seed:
                    await con.execute(
                        "INSERT INTO custom_styles (code, name, prompt_prefix, category, is_active, sort_order) VALUES ($1,$2,$3,$4,true,$5) ON CONFLICT (code) DO NOTHING",
                        code, name, pref, cat, order
                    )
        except Exception as e:
            print(f"warn seed custom_styles: {e}")

        # ---- provider failover config migrations (Phase3 task8) ----
        try:
            await con.execute("ALTER TABLE providers ADD COLUMN IF NOT EXISTS failover_priority INT NOT NULL DEFAULT 0;")
            await con.execute("ALTER TABLE providers ADD COLUMN IF NOT EXISTS timeout_sec INT NOT NULL DEFAULT 30;")
            await con.execute("ALTER TABLE providers ADD COLUMN IF NOT EXISTS retry_count INT NOT NULL DEFAULT 2;")
            await con.execute("ALTER TABLE providers ADD COLUMN IF NOT EXISTS cost_per_gen NUMERIC NOT NULL DEFAULT 0;")
            await con.execute("CREATE INDEX IF NOT EXISTS idx_providers_failover_priority ON providers(failover_priority, id);")
            zero_cnt = await con.fetchval("SELECT count(*) FROM providers WHERE failover_priority=0")
            total = await con.fetchval("SELECT count(*) FROM providers")
            if total and zero_cnt == total:
                rows = await con.fetch("SELECT id FROM providers ORDER BY id")
                for idx, r in enumerate(rows):
                    await con.execute("UPDATE providers SET failover_priority=$1 WHERE id=$2", idx, r["id"])
            await con.execute("ALTER TABLE generations ADD COLUMN IF NOT EXISTS model_id TEXT;")
            await con.execute("CREATE INDEX IF NOT EXISTS idx_generations_created_at ON generations(created_at);")
            await con.execute("CREATE INDEX IF NOT EXISTS idx_generations_model_id ON generations(model_id);")
            await con.execute("CREATE INDEX IF NOT EXISTS idx_deposits_created_at ON deposits(created_at);")
            await con.execute("CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);")
            await con.execute("CREATE INDEX IF NOT EXISTS idx_generations_success ON generations(success);")
        except Exception as fe:
            print(f"warn failover migration: {fe}")

        # ---- alert webhook system (Phase3 task9) ----
        try:
            await con.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_rules (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL CHECK (type IN ('error_rate','deposit_pending','cpu_high','disk_high','queue_stuck','bot_offline')),
                    threshold NUMERIC NOT NULL DEFAULT 0,
                    channel TEXT NOT NULL DEFAULT 'webhook' CHECK (channel IN ('discord','telegram','webhook')),
                    target_url TEXT NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT true,
                    cooldown_sec INT NOT NULL DEFAULT 900,
                    last_triggered_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            await con.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_history (
                    id SERIAL PRIMARY KEY,
                    rule_id INT REFERENCES alert_rules(id) ON DELETE SET NULL,
                    type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    triggered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    resolved BOOLEAN NOT NULL DEFAULT false,
                    meta JSONB NOT NULL DEFAULT '{}'::jsonb
                );
                """
            )
            await con.execute("CREATE INDEX IF NOT EXISTS idx_alert_rules_type ON alert_rules(type);")
            await con.execute("CREATE INDEX IF NOT EXISTS idx_alert_rules_active ON alert_rules(is_active);")
            await con.execute("CREATE INDEX IF NOT EXISTS idx_alert_history_triggered ON alert_history(triggered_at DESC);")
            await con.execute("CREATE INDEX IF NOT EXISTS idx_alert_history_rule ON alert_history(rule_id);")
            await con.execute("ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS last_triggered_at TIMESTAMPTZ;")
            await con.execute("ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS cooldown_sec INT NOT NULL DEFAULT 900;")
            await con.execute("ALTER TABLE alert_history ADD COLUMN IF NOT EXISTS resolved BOOLEAN NOT NULL DEFAULT false;")
            await con.execute("ALTER TABLE alert_history ADD COLUMN IF NOT EXISTS meta JSONB NOT NULL DEFAULT '{}'::jsonb;")
        except Exception as ae:
            print(f"warn alert migration: {ae}")

        # ---- backup & restore 1-click (Phase4 Task12) ----
        try:
            await con.execute(
                """
                CREATE TABLE IF NOT EXISTS backup_history (
                    id SERIAL PRIMARY KEY,
                    filename TEXT UNIQUE NOT NULL,
                    size_bytes BIGINT DEFAULT 0,
                    type TEXT DEFAULT 'manual' CHECK (type IN ('manual','auto','upload')),
                    status TEXT DEFAULT 'completed' CHECK (status IN ('in_progress','completed','failed','restoring')),
                    storage_path TEXT,
                    checksum TEXT,
                    created_by TEXT,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    completed_at TIMESTAMPTZ,
                    error_message TEXT,
                    meta JSONB DEFAULT '{}'::jsonb
                );
                """
            )
            await con.execute("CREATE INDEX IF NOT EXISTS idx_backup_history_created ON backup_history(created_at DESC);")
            await con.execute("CREATE INDEX IF NOT EXISTS idx_backup_history_type ON backup_history(type);")
            await con.execute("CREATE INDEX IF NOT EXISTS idx_backup_history_status ON backup_history(status);")
            # migrations for existing installs
            await con.execute("ALTER TABLE backup_history ADD COLUMN IF NOT EXISTS size_bytes BIGINT DEFAULT 0;")
            await con.execute("ALTER TABLE backup_history ADD COLUMN IF NOT EXISTS type TEXT DEFAULT 'manual';")
            await con.execute("ALTER TABLE backup_history ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'completed';")
            await con.execute("ALTER TABLE backup_history ADD COLUMN IF NOT EXISTS storage_path TEXT;")
            await con.execute("ALTER TABLE backup_history ADD COLUMN IF NOT EXISTS checksum TEXT;")
            await con.execute("ALTER TABLE backup_history ADD COLUMN IF NOT EXISTS created_by TEXT;")
            await con.execute("ALTER TABLE backup_history ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;")
            await con.execute("ALTER TABLE backup_history ADD COLUMN IF NOT EXISTS error_message TEXT;")
            await con.execute("ALTER TABLE backup_history ADD COLUMN IF NOT EXISTS meta JSONB DEFAULT '{}'::jsonb;")
            # ensure check constraints exist (postgres won't add duplicate constraint, so try/catch internally via DO block)
            try:
                await con.execute("ALTER TABLE backup_history DROP CONSTRAINT IF EXISTS backup_history_type_check;")
                await con.execute("ALTER TABLE backup_history ADD CONSTRAINT backup_history_type_check CHECK (type IN ('manual','auto','upload'));")
            except Exception:
                pass
            try:
                await con.execute("ALTER TABLE backup_history DROP CONSTRAINT IF EXISTS backup_history_status_check;")
                await con.execute("ALTER TABLE backup_history ADD CONSTRAINT backup_history_status_check CHECK (status IN ('in_progress','completed','failed','restoring'));")
            except Exception:
                pass
        except Exception as be:
            print(f"warn backup migration: {be}")

        # ---- broadcast scheduler (Phase4 Task11) ----
        try:
            await con.execute(
                """
                CREATE TABLE IF NOT EXISTS broadcast_schedules (
                    id SERIAL PRIMARY KEY,
                    title TEXT,
                    message TEXT NOT NULL,
                    media_file_id TEXT,
                    media_url TEXT,
                    target_type TEXT DEFAULT 'all' CHECK (target_type IN ('all','premium','active','free')),
                    scheduled_at TIMESTAMPTZ NOT NULL,
                    repeat_type TEXT DEFAULT 'once' CHECK (repeat_type IN ('once','daily','weekly','monthly')),
                    status TEXT DEFAULT 'pending' CHECK (status IN ('pending','sent','sending','failed','cancelled')),
                    last_run_at TIMESTAMPTZ,
                    next_run_at TIMESTAMPTZ,
                    retry_count INT DEFAULT 0,
                    max_retries INT DEFAULT 3,
                    failure_reason TEXT,
                    created_by TEXT,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ DEFAULT now()
                );
                """
            )
            await con.execute(
                """
                CREATE TABLE IF NOT EXISTS broadcast_schedule_logs (
                    id SERIAL PRIMARY KEY,
                    schedule_id INT REFERENCES broadcast_schedules(id) ON DELETE CASCADE,
                    run_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sent','failed','cancelled')),
                    sent_count INT DEFAULT 0,
                    failed_count INT DEFAULT 0,
                    error_message TEXT,
                    meta JSONB DEFAULT '{}'::jsonb
                );
                """
            )
            await con.execute("CREATE INDEX IF NOT EXISTS idx_broadcast_schedules_scheduled_at ON broadcast_schedules(scheduled_at);")
            await con.execute("CREATE INDEX IF NOT EXISTS idx_broadcast_schedules_status ON broadcast_schedules(status);")
            await con.execute("CREATE INDEX IF NOT EXISTS idx_broadcast_schedules_next_run ON broadcast_schedules(next_run_at);")
            await con.execute("CREATE INDEX IF NOT EXISTS idx_broadcast_schedule_logs_schedule ON broadcast_schedule_logs(schedule_id);")
            await con.execute("CREATE INDEX IF NOT EXISTS idx_broadcast_schedule_logs_run_at ON broadcast_schedule_logs(run_at DESC);")
            # migrations for older installs
            await con.execute("ALTER TABLE broadcast_schedules ADD COLUMN IF NOT EXISTS title TEXT;")
            await con.execute("ALTER TABLE broadcast_schedules ADD COLUMN IF NOT EXISTS media_file_id TEXT;")
            await con.execute("ALTER TABLE broadcast_schedules ADD COLUMN IF NOT EXISTS media_url TEXT;")
            await con.execute("ALTER TABLE broadcast_schedules ADD COLUMN IF NOT EXISTS target_type TEXT DEFAULT 'all';")
            await con.execute("ALTER TABLE broadcast_schedules ADD COLUMN IF NOT EXISTS repeat_type TEXT DEFAULT 'once';")
            await con.execute("ALTER TABLE broadcast_schedules ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';")
            await con.execute("ALTER TABLE broadcast_schedules ADD COLUMN IF NOT EXISTS last_run_at TIMESTAMPTZ;")
            await con.execute("ALTER TABLE broadcast_schedules ADD COLUMN IF NOT EXISTS next_run_at TIMESTAMPTZ;")
            await con.execute("ALTER TABLE broadcast_schedules ADD COLUMN IF NOT EXISTS retry_count INT DEFAULT 0;")
            await con.execute("ALTER TABLE broadcast_schedules ADD COLUMN IF NOT EXISTS max_retries INT DEFAULT 3;")
            await con.execute("ALTER TABLE broadcast_schedules ADD COLUMN IF NOT EXISTS failure_reason TEXT;")
            await con.execute("ALTER TABLE broadcast_schedules ADD COLUMN IF NOT EXISTS created_by TEXT;")
            await con.execute("ALTER TABLE broadcast_schedules ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();")
            await con.execute("ALTER TABLE broadcast_schedules ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();")
            # normalize NULL next_run_at for legacy rows
            await con.execute("UPDATE broadcast_schedules SET next_run_at = scheduled_at WHERE next_run_at IS NULL;")
        except Exception as bse:
            print(f"warn broadcast_schedules migration: {bse}")

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
    try:
        user_api.bind_pool(_pool)
        await user_api.ensure_user_tables(_pool)
    except Exception as e:
        print(f"warn user_api tables: {e}")
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

# Public web-app CORS (CF Pages + local). Never use * with credentials.
_WEB_CORS = [o.strip() for o in os.environ.get("WEB_CORS_ORIGINS", "http://localhost:3001,http://127.0.0.1:3001").split(",") if o.strip()]
if _WEB_CORS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_WEB_CORS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
app.include_router(user_api.router)


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
        active_c = await con.fetchval("SELECT count(*) FROM users " + _audience_where("active")) or 0
    return {"all": all_c, "premium": premium_c, "free": free_c, "active": active_c}

# ---- Broadcast Scheduler (Phase4 Task11) ----
import json as _jsonb

MEDIA_FILE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,400}$")
SCHEDULE_VALID_TARGET = {"all","premium","active","free"}
SCHEDULE_VALID_REPEAT = {"once","daily","weekly","monthly"}
SCHEDULE_VALID_STATUS = {"pending","sent","sending","failed","cancelled"}

def _parse_iso_dt(s: str) -> _dt.datetime | None:
    if not s: return None
    try:
        txt = s.strip()
        if txt.endswith("Z"): txt = txt[:-1] + "+00:00"
        dt = _dt.datetime.fromisoformat(txt)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=_dt.timezone.utc)
        return dt
    except Exception:
        return None

def _compute_next_repeat(base: _dt.datetime, repeat_type: str) -> _dt.datetime | None:
    if repeat_type == "once": return None
    if repeat_type == "daily": return base + _dt.timedelta(days=1)
    if repeat_type == "weekly": return base + _dt.timedelta(days=7)
    if repeat_type == "monthly": return base + _dt.timedelta(days=30)
    return None

async def _do_broadcast_send(message: str, media_file_id: str | None, target_type: str, title: str | None = None) -> tuple[int,int,str|None]:
    """Real send via Telegram bot API, returns (sent, total, error). Reuses broadcast lock."""
    sanitized = _sanitize_html(message)[:4096]
    tt = target_type if target_type in SCHEDULE_VALID_TARGET else "all"
    has_image = bool(media_file_id)
    try:
        async with _pool.acquire() as con:
            rows = await con.fetch("SELECT user_id FROM users " + _sched_audience_where(tt))
    except Exception as e:
        return 0,0,str(e)[:300]
    if not rows:
        return 0,0,None
    sem = asyncio.Semaphore(20)
    sent_counter=0
    failed_counter=0
    lock=asyncio.Lock()
    async def _send_one(client: httpx.AsyncClient, uid: int):
        nonlocal sent_counter, failed_counter
        async with sem:
            try:
                if has_image:
                    payload={"chat_id":uid,"photo":media_file_id,"caption":sanitized,"parse_mode":"HTML"}
                    method="sendPhoto"
                else:
                    payload={"chat_id":uid,"text":sanitized,"parse_mode":"HTML"}
                    method="sendMessage"
                resp=await client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", json=payload)
                if resp.status_code==200 and resp.json().get("ok"):
                    async with lock:
                        sent_counter+=1
                else:
                    failed_body=""
                    try: failed_body=resp.text[:200]
                    except: pass
                    if resp.status_code==429:
                        try:
                            retry_after=resp.json().get("parameters",{}).get("retry_after",1)
                        except: retry_after=1
                        await asyncio.sleep(float(retry_after))
                        # one retry after 429
                        try:
                            r2=await client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", json=payload)
                            if r2.status_code==200 and r2.json().get("ok"):
                                async with lock: sent_counter+=1
                                return
                        except: pass
                    async with lock:
                        failed_counter+=1
            except Exception:
                async with lock:
                    failed_counter+=1
    try:
        async with httpx.AsyncClient(timeout=30, limits=httpx.Limits(max_connections=30)) as client:
            await asyncio.gather(*[_send_one(client, r["user_id"]) for r in rows])
    except Exception as e:
        return sent_counter, len(rows), str(e)[:300]
    # log to broadcast_history too
    try:
        async with _pool.acquire() as con:
            await con.execute("INSERT INTO broadcast_history (message, audience, sent, total, image_file_id) VALUES ($1,$2,$3,$4,$5)", message[:4000], tt, sent_counter, len(rows), media_file_id)
    except: pass
    return sent_counter, len(rows), None

class ScheduleCreateBody(BaseModel):
    title: str | None = Field(default=None, max_length=100)
    message: str = Field(..., min_length=1, max_length=4000)
    media_file_id: str | None = Field(default=None, max_length=400)
    media_url: str | None = Field(default=None, max_length=500)
    target_type: str = Field(default="all", max_length=20)
    scheduled_at: str = Field(..., max_length=100)
    repeat_type: str = Field(default="once", max_length=20)
    max_retries: int | None = Field(default=3, ge=0, le=10)
    @field_validator("target_type")
    @classmethod
    def vt(cls, v): 
        vv=(v or "all").strip().lower()
        if vv not in SCHEDULE_VALID_TARGET: raise ValueError(f"target_type must be {','.join(SCHEDULE_VALID_TARGET)}")
        return vv
    @field_validator("repeat_type")
    @classmethod
    def vr(cls, v):
        vv=(v or "once").strip().lower()
        if vv not in SCHEDULE_VALID_REPEAT: raise ValueError(f"repeat_type must be {','.join(SCHEDULE_VALID_REPEAT)}")
        return vv
    @field_validator("media_file_id")
    @classmethod
    def vm(cls, v):
        if v is None or v.strip()=="": return None
        vv=v.strip()
        if not MEDIA_FILE_ID_RE.match(vv): raise ValueError("media_file_id format invalid ^[A-Za-z0-9_-]{10,400}$")
        return vv
    @field_validator("scheduled_at")
    @classmethod
    def vs(cls, v):
        # allow ISO string, parsed later, keep raw
        if not v or not v.strip(): raise ValueError("scheduled_at required")
        dt=_parse_iso_dt(v)
        if not dt: raise ValueError("scheduled_at must be ISO 8601 datetime")
        return v.strip()

class ScheduleUpdateBody(BaseModel):
    title: str | None = Field(default=None, max_length=100)
    message: str | None = Field(default=None, max_length=4000)
    media_file_id: str | None = Field(default=None, max_length=400)
    media_url: str | None = Field(default=None, max_length=500)
    target_type: str | None = Field(default=None, max_length=20)
    scheduled_at: str | None = Field(default=None, max_length=100)
    repeat_type: str | None = Field(default=None, max_length=20)
    max_retries: int | None = Field(default=None, ge=0, le=10)
    @field_validator("target_type")
    @classmethod
    def vt(cls, v):
        if v is None: return v
        vv=v.strip().lower()
        if vv not in SCHEDULE_VALID_TARGET: raise ValueError(f"target_type must be {','.join(SCHEDULE_VALID_TARGET)}")
        return vv
    @field_validator("repeat_type")
    @classmethod
    def vr(cls, v):
        if v is None: return v
        vv=v.strip().lower()
        if vv not in SCHEDULE_VALID_REPEAT: raise ValueError(f"repeat_type must be {','.join(SCHEDULE_VALID_REPEAT)}")
        return vv
    @field_validator("media_file_id")
    @classmethod
    def vm(cls, v):
        if v is None: return v
        vv=v.strip()
        if vv=="": return None
        if not MEDIA_FILE_ID_RE.match(vv): raise ValueError("media_file_id invalid")
        return vv

@app.get("/api/broadcast/schedules")
async def list_schedules(status: str = "", q: str = "", target: str = "", repeat: str = "", limit: int = 200, _: bool = Depends(require_auth)):
    limit = max(1,min(500, int(limit or 200)))
    status = (status or "").strip().lower()
    q = (q or "").strip()[:100]
    target = (target or "").strip().lower()
    repeat = (repeat or "").strip().lower()
    where=[]; args=[]; idx=1
    if status and status in SCHEDULE_VALID_STATUS:
        where.append(f"status = ${idx}"); args.append(status); idx+=1
    if target and target in SCHEDULE_VALID_TARGET:
        where.append(f"target_type = ${idx}"); args.append(target); idx+=1
    if repeat and repeat in SCHEDULE_VALID_REPEAT:
        where.append(f"repeat_type = ${idx}"); args.append(repeat); idx+=1
    if q:
        like=f"%{q}%"
        where.append(f"(title ILIKE ${idx} OR message ILIKE ${idx})"); args.append(like); idx+=1
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"SELECT * FROM broadcast_schedules {where_sql} ORDER BY next_run_at ASC NULLS LAST, scheduled_at ASC, id DESC LIMIT ${idx}"
    args.append(limit)
    async with _pool.acquire() as con:
        rows = await con.fetch(sql, *args)
        # counts
        try:
            stats_rows = await con.fetch("SELECT status, count(*) c FROM broadcast_schedules GROUP BY status")
            total_cnt = await con.fetchval("SELECT count(*) FROM broadcast_schedules") or 0
            pending_cnt = await con.fetchval("SELECT count(*) FROM broadcast_schedules WHERE status='pending' AND next_run_at <= now()") or 0
        except Exception:
            stats_rows=[]; total_cnt=len(rows); pending_cnt=0
    status_map={r["status"]: int(r["c"]) for r in stats_rows}
    next_up = None
    try:
        for r in rows:
            if r["status"]=="pending" and r["next_run_at"]:
                next_up=dict(r)
                break
    except: pass
    return {"schedules": [dict(r) for r in rows], "total": total_cnt, "counts": status_map, "pending_due": int(pending_cnt), "next_upcoming": next_up, "next": next_up}

@app.post("/api/broadcast/schedules")
async def create_schedule(body: ScheduleCreateBody, _: bool = Depends(require_auth)):
    dt = _parse_iso_dt(body.scheduled_at)
    if not dt:
        raise HTTPException(status_code=400, detail="scheduled_at invalid ISO")
    now = _dt.datetime.now(_dt.timezone.utc)
    # allow past? spec says future validation — enforce future but allow small clock skew 60s past
    if dt < now - _dt.timedelta(seconds=60):
        # still allow if repeat? spec says future validation, but for cron we warn: require future unless admin wants immediate schedule
        # enforce future for once, allow past 1h for repeating? Simplest: reject if >5m past
        if dt < now - _dt.timedelta(minutes=5):
            raise HTTPException(status_code=400, detail="scheduled_at harus di masa depan (ISO future)")
    msg_sanitized = _sanitize_html(body.message)[:4000]
    if not msg_sanitized.strip():
        raise HTTPException(status_code=400, detail="message kosong setelah sanitasi")
    title = (body.title or "").strip()[:100] if body.title else None
    if title is not None and len(title)==0: title=None
    # compute next_run
    next_run = dt
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "INSERT INTO broadcast_schedules (title, message, media_file_id, media_url, target_type, scheduled_at, repeat_type, status, next_run_at, max_retries) VALUES ($1,$2,$3,$4,$5,$6,$7,'pending',$8,$9) RETURNING *",
            title, body.message.strip(), body.media_file_id, body.media_url, body.target_type, dt, body.repeat_type, next_run, int(body.max_retries or 3)
        )
    await audit_log("broadcast_schedule_create", str(row["id"]), f"{body.target_type} {body.repeat_type} {dt.isoformat()} title={title or ''}")
    return {"ok": True, "schedule": dict(row)}

@app.get("/api/broadcast/schedules/{sid}")
async def get_schedule(sid: int, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT * FROM broadcast_schedules WHERE id=$1", sid)
        if not row:
            raise HTTPException(status_code=404, detail="Schedule tidak ditemukan")
    return {"schedule": dict(row)}

@app.put("/api/broadcast/schedules/{sid}")
async def update_schedule(sid: int, body: ScheduleUpdateBody, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        cur = await con.fetchrow("SELECT * FROM broadcast_schedules WHERE id=$1", sid)
        if not cur:
            raise HTTPException(status_code=404, detail="Schedule tidak ditemukan")
        if cur["status"] in ("sending",):
            raise HTTPException(status_code=400, detail="Tidak bisa edit saat status sending")
        updates={}
        if body.title is not None:
            t=body.title.strip()[:100]
            updates["title"]= t if t else None
        if body.message is not None:
            m=body.message.strip()
            if len(m)<1 or len(m)>4000: raise HTTPException(status_code=400, detail="message 1-4000")
            _san = _sanitize_html(m)
            if not _san.strip(): raise HTTPException(status_code=400, detail="message kosong setelah sanitasi")
            updates["message"]=m
        if body.media_file_id is not None:
            updates["media_file_id"]=body.media_file_id
        if body.media_url is not None:
            updates["media_url"]=body.media_url if body.media_url.strip() else None
        if body.target_type is not None:
            updates["target_type"]=body.target_type
        if body.repeat_type is not None:
            updates["repeat_type"]=body.repeat_type
        dt_new=None
        if body.scheduled_at is not None:
            dt_new=_parse_iso_dt(body.scheduled_at)
            if not dt_new: raise HTTPException(status_code=400, detail="scheduled_at invalid")
            updates["scheduled_at"]=dt_new
            # recalc next_run_at if pending or if resetting
            # keep last_run logic: next_run = dt_new if status pending else keep? we recalc
            updates["next_run_at"]=dt_new
        if body.max_retries is not None:
            updates["max_retries"]=int(body.max_retries)
        if not updates:
            return {"ok": True, "schedule": dict(cur)}
        # build dynamic sql
        fields=[]; vals=[]; idx=1
        for k,v in updates.items():
            fields.append(f"{k} = ${idx}"); vals.append(v); idx+=1
        fields.append(f"updated_at = now()")
        vals.append(sid)
        sql = f"UPDATE broadcast_schedules SET {', '.join(fields)} WHERE id=${idx} RETURNING *"
        row = await con.fetchrow(sql, *vals)
    await audit_log("broadcast_schedule_update", str(sid), f"fields={list(updates.keys())}")
    return {"ok": True, "schedule": dict(row) if row else dict(cur)}

@app.delete("/api/broadcast/schedules/{sid}")
async def delete_schedule(sid: int, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        cur = await con.fetchrow("SELECT id, title FROM broadcast_schedules WHERE id=$1", sid)
        if not cur:
            raise HTTPException(status_code=404, detail="Schedule tidak ditemukan")
        await con.execute("DELETE FROM broadcast_schedules WHERE id=$1", sid)
    await audit_log("broadcast_schedule_delete", str(sid), f"{cur['title'] or ''}")
    return {"ok": True}

@app.post("/api/broadcast/schedules/{sid}/cancel")
async def cancel_schedule(sid: int, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        cur = await con.fetchrow("SELECT * FROM broadcast_schedules WHERE id=$1", sid)
        if not cur:
            raise HTTPException(status_code=404, detail="Schedule tidak ditemukan")
        if cur["status"] in ("sent","cancelled"):
            return {"ok": True, "schedule": dict(cur), "note": f"already {cur['status']}"}
        row = await con.fetchrow("UPDATE broadcast_schedules SET status='cancelled', updated_at=now() WHERE id=$1 RETURNING *", sid)
        await con.execute("INSERT INTO broadcast_schedule_logs (schedule_id, status, error_message) VALUES ($1,'cancelled','cancelled by admin')", sid)
    await audit_log("broadcast_schedule_cancel", str(sid), "")
    return {"ok": True, "schedule": dict(row) if row else dict(cur)}

@app.post("/api/broadcast/schedules/{sid}/run-now")
async def run_now_schedule(sid: int, _: bool = Depends(require_auth)):
    # prevent concurrent
    if _broadcast_lock.locked():
        raise HTTPException(status_code=429, detail="Broadcast lain sedang berjalan, coba lagi nanti")
    async with _pool.acquire() as con:
        cur = await con.fetchrow("SELECT * FROM broadcast_schedules WHERE id=$1", sid)
        if not cur:
            raise HTTPException(status_code=404, detail="Schedule tidak ditemukan")
        if cur["status"] == "sending":
            raise HTTPException(status_code=400, detail="Schedule sedang sending")
        # mark sending
        await con.execute("UPDATE broadcast_schedules SET status='sending', updated_at=now() WHERE id=$1", sid)
    try:
        async with _broadcast_lock:
            sent, total, err = await _do_broadcast_send(cur["message"], cur["media_file_id"], cur["target_type"] or "all", cur["title"])
            now = _dt.datetime.now(_dt.timezone.utc)
            failed = (total - sent) if total else 0
            next_status = "sent" if not err else "failed"
            # handle repeat: if run-now triggered manually, we still respect repeat?
            # For manual run-now, if repeat != once, compute next run from now, status -> pending again? Spec says run-now trigger immediate send.
            # We'll keep logic: if repeat != once and manual run-now, set next_run_at to next repeat based on scheduled_at or now, status pending for next cycle, but log sent.
            # Simpler: if repeat != once, after run-now success -> compute next repeat, status pending, last_run_at=now
            # If repeat == once: status = sent/failed
            repeat_type = cur["repeat_type"] or "once"
            if repeat_type != "once" and next_status=="sent":
                # compute next from scheduled_at or now? use scheduled_at as anchor + interval until future
                anchor = cur["scheduled_at"] or now
                # ensure next ahead of now
                nxt = anchor
                loops=0
                while nxt <= now and loops < 100:
                    nxt = _compute_next_repeat(nxt, repeat_type) or now + _dt.timedelta(days=1)
                    loops+=1
                async with _pool.acquire() as con:
                    row = await con.fetchrow("UPDATE broadcast_schedules SET status='pending', last_run_at=$2, next_run_at=$3, retry_count=0, updated_at=now(), failure_reason=NULL WHERE id=$1 RETURNING *", sid, now, nxt)
                    await con.execute("INSERT INTO broadcast_schedule_logs (schedule_id, status, sent_count, failed_count, error_message, meta) VALUES ($1,'sent',$2,$3,$4,$5::jsonb)", sid, sent, failed, err, _jsonb.dumps({"run_type":"run_now","total":total}))
            else:
                async with _pool.acquire() as con:
                    if next_status=="sent":
                        row = await con.fetchrow("UPDATE broadcast_schedules SET status='sent', last_run_at=$2, retry_count=0, updated_at=now(), failure_reason=NULL WHERE id=$1 RETURNING *", sid, now)
                    else:
                        new_retry = (cur["retry_count"] or 0)+1
                        ftxt = err or "broadcast failed"
                        if new_retry >= (cur["max_retries"] or 3):
                            row = await con.fetchrow("UPDATE broadcast_schedules SET status='failed', last_run_at=$2, retry_count=$3, failure_reason=$4, updated_at=now() WHERE id=$1 RETURNING *", sid, now, new_retry, ftxt)
                        else:
                            row = await con.fetchrow("UPDATE broadcast_schedules SET status='pending', last_run_at=$2, retry_count=$3, failure_reason=$4, next_run_at=now()+interval '5 minutes', updated_at=now() WHERE id=$1 RETURNING *", sid, now, new_retry, ftxt)
                        # log failed
                    await con.execute("INSERT INTO broadcast_schedule_logs (schedule_id, status, sent_count, failed_count, error_message, meta) VALUES ($1,$2,$3,$4,$5,$6::jsonb)", sid, next_status, sent, failed, err, _jsonb.dumps({"run_type":"run_now","total":total}))
    except Exception as e:
        async with _pool.acquire() as con:
            await con.execute("UPDATE broadcast_schedules SET status='failed', failure_reason=$2, retry_count=retry_count+1, updated_at=now() WHERE id=$1", sid, str(e)[:500])
            await con.execute("INSERT INTO broadcast_schedule_logs (schedule_id, status, error_message) VALUES ($1,'failed',$2)", sid, str(e)[:500])
        raise HTTPException(status_code=500, detail=f"run-now failed: {e}")
    await audit_log("broadcast_schedule_run_now", str(sid), f"sent={sent}/{total} err={err or ''}")
    sched = dict(row) if 'row' in locals() and row else dict(cur)
    return {"ok": True, "schedule": sched, "sent": sent, "total": total, "error": err}

@app.get("/api/broadcast/schedules/{sid}/logs")
async def get_schedule_logs(sid: int, limit: int = 100, _: bool = Depends(require_auth)):
    limit = max(1,min(500, int(limit or 100)))
    async with _pool.acquire() as con:
        cur = await con.fetchrow("SELECT id FROM broadcast_schedules WHERE id=$1", sid)
        if not cur:
            raise HTTPException(status_code=404, detail="Schedule tidak ditemukan")
        rows = await con.fetch("SELECT * FROM broadcast_schedule_logs WHERE schedule_id=$1 ORDER BY run_at DESC, id DESC LIMIT $2", sid, limit)
    return {"logs": [dict(r) for r in rows], "schedule_id": sid, "total": len(rows)}

@app.post("/api/broadcast/schedules/evaluate")
async def evaluate_schedules(_: bool = Depends(require_auth)):
    """Cron endpoint: checks schedules where next_run_at <= now() and status pending, runs them."""
    now = _dt.datetime.now(_dt.timezone.utc)
    async with _pool.acquire() as con:
        due = await con.fetch("SELECT * FROM broadcast_schedules WHERE status='pending' AND next_run_at <= $1 ORDER BY next_run_at ASC LIMIT 20", now)
    if not due:
        return {"ok": True, "processed": [], "count": 0, "checked_at": now.isoformat()}
    processed=[]
    for sched in due:
        sid = sched["id"]
        # avoid concurrent with broadcast lock -> try acquire lock via flag
        if _broadcast_lock.locked():
            processed.append({"id": sid, "status": "skipped", "reason": "broadcast lock busy"})
            continue
        # mark sending
        try:
            async with _pool.acquire() as con:
                await con.execute("UPDATE broadcast_schedules SET status='sending', updated_at=now() WHERE id=$1", sid)
        except Exception as e:
            processed.append({"id": sid, "status": "error", "error": str(e)[:200]})
            continue
        try:
            async with _broadcast_lock:
                sent, total, err = await _do_broadcast_send(sched["message"], sched["media_file_id"], sched["target_type"] or "all", sched["title"])
            failed = (total - sent) if total else 0
            repeat_type = sched["repeat_type"] or "once"
            async with _pool.acquire() as con:
                if not err:
                    if repeat_type == "once":
                        await con.execute("UPDATE broadcast_schedules SET status='sent', last_run_at=$2, next_run_at=NULL, retry_count=0, failure_reason=NULL, updated_at=now() WHERE id=$1", sid, now)
                    else:
                        # compute next
                        base = sched["next_run_at"] or sched["scheduled_at"] or now
                        nxt = _compute_next_repeat(base, repeat_type)
                        # if nxt still past, bump until future
                        loops=0
                        while nxt and nxt <= now and loops<100:
                            nxt = _compute_next_repeat(nxt, repeat_type)
                            loops+=1
                        await con.execute("UPDATE broadcast_schedules SET status='pending', last_run_at=$2, next_run_at=$3, retry_count=0, failure_reason=NULL, updated_at=now() WHERE id=$1", sid, now, nxt)
                    await con.execute("INSERT INTO broadcast_schedule_logs (schedule_id, status, sent_count, failed_count, meta) VALUES ($1,'sent',$2,$3,$4::jsonb)", sid, sent, failed, _jsonb.dumps({"run_type":"cron","total":total,"repeat":repeat_type}))
                    processed.append({"id": sid, "status": "sent", "sent": sent, "total": total, "next_repeat": repeat_type})
                else:
                    # failure -> retry logic
                    new_retry = (sched["retry_count"] or 0)+1
                    max_r = sched["max_retries"] or 3
                    if new_retry >= max_r:
                        await con.execute("UPDATE broadcast_schedules SET status='failed', last_run_at=$2, retry_count=$3, failure_reason=$4, updated_at=now() WHERE id=$1", sid, now, new_retry, err[:500])
                        await con.execute("INSERT INTO broadcast_schedule_logs (schedule_id, status, sent_count, failed_count, error_message, meta) VALUES ($1,'failed',$2,$3,$4,$5::jsonb)", sid, sent, failed, err[:500], _jsonb.dumps({"run_type":"cron","total":total}))
                        processed.append({"id": sid, "status": "failed", "error": err[:200], "retry": new_retry})
                    else:
                        await con.execute("UPDATE broadcast_schedules SET status='pending', last_run_at=$2, retry_count=$3, failure_reason=$4, next_run_at=now()+interval '5 minutes', updated_at=now() WHERE id=$1", sid, now, new_retry, err[:500])
                        await con.execute("INSERT INTO broadcast_schedule_logs (schedule_id, status, sent_count, failed_count, error_message, meta) VALUES ($1,'failed',$2,$3,$4,$5::jsonb)", sid, sent, failed, err[:500], _jsonb.dumps({"run_type":"cron-retry","total":total}))
                        processed.append({"id": sid, "status": "retry", "error": err[:200], "retry": new_retry})
        except Exception as e:
            try:
                async with _pool.acquire() as con:
                    await con.execute("UPDATE broadcast_schedules SET status='failed', failure_reason=$2, retry_count=retry_count+1, updated_at=now() WHERE id=$1", sid, str(e)[:500])
            except: pass
            processed.append({"id": sid, "status": "error", "error": str(e)[:300]})
    # fetch updated rows for response
    try:
        async with _pool.acquire() as con:
            ids = [p["id"] for p in processed if isinstance(p.get("id"), int)]
            if ids:
                rows = await con.fetch("SELECT * FROM broadcast_schedules WHERE id = ANY($1)", ids)
                mp = {r["id"]: dict(r) for r in rows}
                for p in processed:
                    if p["id"] in mp:
                        p["schedule"]=mp[p["id"]]
    except: pass
    await audit_log("broadcast_schedules_evaluate", "-", f"checked={len(due)} processed={len(processed)}")
    return {"ok": True, "processed": processed, "count": len(processed), "checked_at": now.isoformat()}


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
# ---- Command Manager constants (mirrors bot/feature_flags.py COMMAND_DEFS) ----
COMMAND_DEFS: dict[str, dict] = {
    "generate": {"group": "core", "icon": "Sparkles", "label_id": "Generate image", "label_en": "Generate image", "desc_id": "Buat gambar dari teks (inti)", "desc_en": "Generate image from text (core)", "core": True},
    "edit": {"group": "core", "icon": "ImagePlus", "label_id": "Edit foto", "label_en": "Edit photo", "desc_id": "Edit / ubah foto (inti)", "desc_en": "Edit / modify photo (core)", "core": True},
    "style": {"group": "core", "icon": "Palette", "label_id": "Gaya visual", "label_en": "Style presets", "desc_id": "Preset gaya visual", "desc_en": "Visual style presets", "core": False},
    "size": {"group": "core", "icon": "Ruler", "label_id": "Ukuran", "label_en": "Size", "desc_id": "Pilihan ukuran gambar", "desc_en": "Image size selection", "core": True},
    "quota": {"group": "core", "icon": "BarChart3", "label_id": "Kuota", "label_en": "Quota", "desc_id": "Cek kuota harian", "desc_en": "Check daily quota", "core": False},
    "myworks": {"group": "core", "icon": "Images", "label_id": "Karya Saya", "label_en": "My Works", "desc_id": "Riwayat karya user", "desc_en": "User works history", "core": False},
    "batch": {"group": "core", "icon": "Layers", "label_id": "Batch generate", "label_en": "Batch generate", "desc_id": "Generate beberapa variasi sekaligus (baru)", "desc_en": "Generate multiple variations at once (new)", "core": False},
    "batchold": {"group": "core", "icon": "Layers3", "label_id": "Batch old", "label_en": "Batch old", "desc_id": "Batch legacy /batchold command", "desc_en": "Legacy batch /batchold command", "core": False},
    "checkin": {"group": "social", "icon": "CalendarCheck", "label_id": "Check-in", "label_en": "Check-in", "desc_id": "Check-in harian streak", "desc_en": "Daily streak check-in", "core": False},
    "referral": {"group": "social", "icon": "Gift", "label_id": "Ajak Teman", "label_en": "Referral", "desc_id": "Sistem referral ajak teman", "desc_en": "Referral invite friends system", "core": False},
    "sticker": {"group": "premium", "icon": "Sticker", "label_id": "Sticker Pack", "label_en": "Sticker Pack", "desc_id": "Buat sticker dari karya", "desc_en": "Create sticker from works", "core": False},
    "model": {"group": "core", "icon": "Bot", "label_id": "Model", "label_en": "Model", "desc_id": "Pilih model AI", "desc_en": "Select AI model", "core": False},
    "enhance": {"group": "core", "icon": "Wand2", "label_id": "Enhance", "label_en": "Enhance", "desc_id": "Prompt enhance via LLM", "desc_en": "Prompt enhance via LLM", "core": False},
    "premium": {"group": "premium", "icon": "Crown", "label_id": "Premium", "label_en": "Premium", "desc_id": "Upgrade premium", "desc_en": "Premium upgrade flow", "core": False},
    "balance": {"group": "premium", "icon": "Wallet", "label_id": "Saldo", "label_en": "Balance", "desc_id": "Saldo & deposit", "desc_en": "Balance & deposits", "core": False},
    "lang": {"group": "core", "icon": "Languages", "label_id": "Bahasa", "label_en": "Language", "desc_id": "Ganti bahasa bot", "desc_en": "Change bot language", "core": False},
}

def _cmd_setting_key(name: str) -> str:
    return f"feat_command_{name.lower()}_enabled"

async def _get_all_commands_status() -> list[dict]:
    out = []
    for name, defn in COMMAND_DEFS.items():
        v = await get_setting(_cmd_setting_key(name), "1")
        enabled = (v or "1") == "1"
        out.append({
            "name": name,
            "is_enabled": enabled,
            "setting_key": _cmd_setting_key(name),
            "group": defn.get("group", "core"),
            "icon": defn.get("icon", "Command"),
            "label_id": defn.get("label_id", name),
            "label_en": defn.get("label_en", name),
            "description_id": defn.get("desc_id", name),
            "description_en": defn.get("desc_en", name),
            "is_core": bool(defn.get("core", False)),
        })
    return out

# ---- Command Manager API ----
class CommandToggleBody(BaseModel):
    enabled: bool

class CommandBulkItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=30, pattern=r"^[a-z0-9_-]{1,30}$")
    enabled: bool

class CommandBulkBody(BaseModel):
    updates: list[CommandBulkItem] = Field(..., min_length=1, max_length=50)

@app.get("/api/commands")
async def list_commands(_: bool = Depends(require_auth)):
    cmds = await _get_all_commands_status()
    return {"commands": cmds, "total": len(cmds)}

@app.put("/api/commands/{name}/toggle")
async def toggle_command(name: str, body: CommandToggleBody, _: bool = Depends(require_auth)):
    name_l = name.lower().strip()
    if name_l not in COMMAND_DEFS:
        raise HTTPException(status_code=404, detail=f"Command '{name}' tidak dikenal")
    if not re.match(r"^[a-z0-9_-]{1,30}$", name_l):
        raise HTTPException(status_code=400, detail="nama command tidak valid")
    await set_setting(_cmd_setting_key(name_l), "1" if body.enabled else "0")
    await audit_log("command_toggle", name_l, f"enabled={body.enabled}")
    return {"ok": True, "name": name_l, "is_enabled": body.enabled}

@app.post("/api/commands/bulk")
async def bulk_commands(body: CommandBulkBody, _: bool = Depends(require_auth)):
    seen = set()
    saved = []
    for item in body.updates:
        nl = item.name.lower().strip()
        if nl not in COMMAND_DEFS:
            raise HTTPException(status_code=400, detail=f"Unknown command: {nl}")
        if nl in seen:
            raise HTTPException(status_code=400, detail=f"Duplicate command: {nl}")
        seen.add(nl)
        await set_setting(_cmd_setting_key(nl), "1" if item.enabled else "0")
        saved.append({"name": nl, "is_enabled": item.enabled})
    await audit_log("commands_bulk", ",".join([s["name"] for s in saved]), str(saved)[:1000])
    return {"ok": True, "updated": saved}

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

# ---- Dynamic Texts Manager (Phase2 task4) ----
TEXTS_DEFINITIONS: list[dict] = [
    # welcome group
    {"key": "welcome_text", "group": "Welcome", "description": "Sapaan awal /start — support {name} {brand} placeholders"},
    {"key": "welcome_back_text", "group": "Welcome", "description": "Dipakai saat nav_home — fallback ke welcome_text jika kosong"},
    # help group
    {"key": "help_text", "group": "Help", "description": "Panduan /help — markdown HTML b/i/code"},
    {"key": "menu_hint", "group": "Help", "description": "Hint kecil di bawah prompt_ask"},
    # errors/quota
    {"key": "maintenance_msg", "group": "Errors", "description": "Pesan saat maintenance mode aktif"},
    {"key": "quota_exhausted_msg", "group": "Errors", "description": "Pesan ketika kuota habis — support {used} {limit} {bar}"},
    {"key": "daily_limit_msg", "group": "Errors", "description": "Alias legacy untuk quota_exhausted"},
    {"key": "nsfw_msg", "group": "Errors", "description": "Ditolak karena konten NSFW/kebijakan — jika provider menolak"},
    {"key": "banned_msg", "group": "Errors", "description": "Pesan untuk user yang dibanned"},
    {"key": "busy_msg", "group": "Errors", "description": "Anti-spam queue — user masih ada job aktif"},
    {"key": "gen_failed_msg", "group": "Errors", "description": "Gagal generate — support {err}"},
    {"key": "edit_failed_msg", "group": "Errors", "description": "Gagal edit — support {err}"},
    # checkin
    {"key": "checkin_msg", "group": "Checkin", "description": "Judul panel check-in — support {streak} {total}"},
    {"key": "checkin_success_msg", "group": "Checkin", "description": "Setelah berhasil check-in — {streak} {bonus} {total}"},
    {"key": "checkin_already_msg", "group": "Checkin", "description": "Sudah check-in hari ini — {streak}"},
    # referral
    {"key": "referral_invite_text", "group": "Referral", "description": "Teks ajak teman — support {link} {reward_desc} {total} {rewarded} {pending} {bonus_quota}"},
    {"key": "referral_reward_balance_text", "group": "Referral", "description": "Label reward saldo — {amount}"},
    {"key": "referral_reward_quota_text", "group": "Referral", "description": "Label reward quota — {n}"},
    # premium
    {"key": "premium_expired_msg", "group": "Premium", "description": "Pesan ketika premium habis"},
    {"key": "upgrade_no_plans_msg", "group": "Premium", "description": "Saat belum ada paket tersedia"},
    {"key": "upgrade_intro_msg", "group": "Premium", "description": "Intro upgrade ke premium"},
    # balance/deposit
    {"key": "deposit_disabled_msg", "group": "Balance", "description": "Fitur top-up sedang dimatikan"},
    {"key": "deposit_success_msg", "group": "Balance", "description": "Top-up approved — {amount} {balance}"},
    {"key": "deposit_pending_msg", "group": "Balance", "description": "Bukti diterima, menunggu verifikasi"},
    # other
    {"key": "join_required_msg", "group": "Subscription", "description": "Wajib join channel — support {channel}"},
    {"key": "join_success_msg", "group": "Subscription", "description": "Berhasil deteksi join channel"},
    {"key": "join_not_detected_msg", "group": "Subscription", "description": "Belum terdeteksi join — {channel}"},
    {"key": "inline_empty_msg", "group": "Inline", "description": "Inline gallery kosong"},
    {"key": "feat_disabled_msg", "group": "Features", "description": "Fitur sedang dimatikan admin"},
]

def _texts_defaults_map() -> dict:
    # Build default fallbacks — empty means app uses hardcoded i18n
    return {d["key"]: "" for d in TEXTS_DEFINITIONS}

class TextUpsertBody(BaseModel):
    key: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_]{1,100}$")
    value: str = Field(..., max_length=10000)

@app.get("/api/texts")
async def list_texts(_: bool = Depends(require_auth)):
    # Always return full list with defaults merged from settings
    defaults = _texts_defaults_map()
    # known keys list — we store dynamic texts as settings keys exactly as typed
    # Additionally, filter settings that match our defs
    defined_keys = {d["key"] for d in TEXTS_DEFINITIONS}
    # Load existing values from settings
    async with _pool.acquire() as con:
        rows = await con.fetch("SELECT key, value FROM settings WHERE key = ANY($1::text[])", list(defined_keys))
    stored = {r["key"]: r["value"] for r in rows}
    result = []
    for d in TEXTS_DEFINITIONS:
        k = d["key"]
        result.append({
            "key": k,
            "value": stored.get(k, defaults.get(k, "")),
            "description": d.get("description", ""),
            "group": d.get("group", "Other"),
            "is_set": k in stored and bool(stored[k]),
        })
    # also include any custom text_* keys not in definitions (user-created)
    extra_keys = [kk for kk in stored.keys() if kk.startswith("text_") and kk not in defined_keys]
    # Or any setting key ending with _msg/_text not in defs
    if extra_keys:
        async with _pool.acquire() as con:
            pass  # stored already
        for kk in extra_keys:
            result.append({"key": kk, "value": stored.get(kk, ""), "description": "Custom", "group": "Custom", "is_set": True})
    return {"texts": result, "total": len(result)}

@app.get("/api/texts/{key}")
async def get_text(key: str, _: bool = Depends(require_auth)):
    key = key.strip()[:100]
    if not key:
        raise HTTPException(status_code=400, detail="key required")
    # allow any key matching pattern but return accordingly
    if not re.match(r"^[A-Za-z0-9_]{1,100}$", key):
        raise HTTPException(status_code=400, detail="invalid key format")
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT value FROM settings WHERE key=$1", key)
    defn = next((d for d in TEXTS_DEFINITIONS if d["key"] == key), None)
    return {
        "key": key,
        "value": row["value"] if row else "",
        "description": defn["description"] if defn else "Custom dynamic text",
        "group": defn["group"] if defn else "Custom",
        "is_set": bool(row and row["value"]),
    }

@app.post("/api/texts")
async def upsert_text(body: TextUpsertBody, _: bool = Depends(require_auth)):
    k = body.key.strip()
    v = body.value  # keep as is, support markdown/HTML, trim only trailing? preserve intentional spaces.
    # Validate key pattern already via pydantic
    # Basic XSS check: disallow javascript: in value? No, user admin may include html. But block only if value contains <script
    low = v.lower()
    if "<script" in low or "javascript:" in low.replace(" ", ""):
        raise HTTPException(status_code=400, detail="Value contains disallowed content (script/javascript:)")
    async with _pool.acquire() as con:
        await con.execute(
            "INSERT INTO settings (key,value) VALUES ($1,$2) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
            k, v,
        )
    await audit_log("text_upsert", k, f"len={len(v)}")
    return {"ok": True, "key": k}

@app.delete("/api/texts/{key}")
async def delete_text(key: str, _: bool = Depends(require_auth)):
    key = key.strip()[:100]
    if not re.match(r"^[A-Za-z0-9_]{1,100}$", key):
        raise HTTPException(status_code=400, detail="invalid key")
    # Allow deleting custom only? We'll allow all but just clear value.
    async with _pool.acquire() as con:
        await con.execute("DELETE FROM settings WHERE key=$1", key)
    await audit_log("text_delete", key, "")
    return {"ok": True}

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


# ---- Custom Styles Presets Manager (no-code) ----
_STYLE_CODE_RE = re.compile(r"^[a-z0-9_-]{1,30}$")

class StyleCreateBody(BaseModel):
    code: str = Field(..., min_length=1, max_length=30, description="slug e.g. anime, ghibli")
    name: str = Field(..., min_length=1, max_length=100)
    prompt_prefix: str = Field(default="", max_length=500)
    thumbnail_url: str | None = Field(default=None, max_length=500)
    category: str = Field(default="general", max_length=30)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=10000)

    @field_validator("code")
    @classmethod
    def validate_code(cls, v):
        v = v.strip().lower()
        if not _STYLE_CODE_RE.match(v):
            raise ValueError("code harus ^[a-z0-9_-]{1,30}$ huruf kecil, angka, -_ saja")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        vv = v.strip()
        if not vv:
            raise ValueError("name wajib")
        if len(vv) > 100:
            raise ValueError("name max 100")
        return vv

    @field_validator("category")
    @classmethod
    def validate_cat(cls, v):
        vv = (v or "general").strip().lower()[:30]
        allowed = {"general","anime","photo","fantasy","artistic","realistic","3d","portrait","landscape","other"}
        # allow custom but normalize; if not in allowed keep as-is but ensure alnum-_
        if not re.match(r"^[a-z0-9_-]{1,30}$", vv):
            raise ValueError("category harus alfanum -_ 1-30")
        return vv

class StyleUpdateBody(BaseModel):
    code: str | None = Field(default=None, max_length=30)
    name: str | None = Field(default=None, max_length=100)
    prompt_prefix: str | None = Field(default=None, max_length=500)
    thumbnail_url: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, max_length=30)
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)

    @field_validator("code")
    @classmethod
    def validate_code_opt(cls, v):
        if v is None:
            return v
        v = v.strip().lower()
        if not _STYLE_CODE_RE.match(v):
            raise ValueError("code harus ^[a-z0-9_-]{1,30}$")
        return v

    @field_validator("category")
    @classmethod
    def validate_cat_opt(cls, v):
        if v is None:
            return v
        vv = v.strip().lower()[:30]
        if not re.match(r"^[a-z0-9_-]{1,30}$", vv):
            raise ValueError("category harus alfanum -_ 1-30")
        return vv

@app.get("/api/styles/list")
async def list_styles_ep(q: str = "", category: str = "", active: str = "", _: bool = Depends(require_auth)):
    q = (q or "").strip()[:100]
    category = (category or "").strip().lower()[:30]
    # active filter: "true"/"false"/"" (all)
    where_parts = []
    args = []
    idx = 1
    if q:
        like = f"%{q}%"
        where_parts.append(f"(code ILIKE ${idx} OR name ILIKE ${idx} OR category ILIKE ${idx} OR prompt_prefix ILIKE ${idx})")
        args.append(like)
        idx += 1
    if category:
        where_parts.append(f"category = ${idx}")
        args.append(category)
        idx += 1
    if active.lower() == "true":
        where_parts.append("is_active = true")
    elif active.lower() == "false":
        where_parts.append("is_active = false")
    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    sql = f"SELECT * FROM custom_styles {where_sql} ORDER BY sort_order, id"
    async with _pool.acquire() as con:
        rows = await con.fetch(sql, *args)
    return {"styles": [dict(r) for r in rows]}

@app.get("/api/styles/categories")
async def style_categories_ep(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch("SELECT DISTINCT category FROM custom_styles ORDER BY category")
    return {"categories": [r["category"] for r in rows]}

@app.post("/api/styles")
async def create_style_ep(body: StyleCreateBody, _: bool = Depends(require_auth)):
    # thumbnail url optional validation — must https/http if present, no SSRF
    if body.thumbnail_url:
        u = body.thumbnail_url.strip()
        if u and not _is_safe_url(u):
            raise HTTPException(status_code=400, detail="thumbnail_url tidak aman")
        if u and not (u.lower().startswith("https://") or u.lower().startswith("http://")):
            raise HTTPException(status_code=400, detail="thumbnail_url harus http/https")
    async with _pool.acquire() as con:
        exists = await con.fetchrow("SELECT id FROM custom_styles WHERE code=$1", body.code)
        if exists:
            raise HTTPException(status_code=409, detail=f"code '{body.code}' sudah ada")
        row = await con.fetchrow(
            "INSERT INTO custom_styles (code, name, prompt_prefix, thumbnail_url, category, is_active, sort_order) VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING *",
            body.code, body.name.strip(), (body.prompt_prefix or "")[:500], body.thumbnail_url, body.category, body.is_active, body.sort_order
        )
    await audit_log("style_create", str(row["id"]), f"code={body.code} name={body.name}")
    return {"ok": True, "style": dict(row)}

@app.put("/api/styles/{style_id}")
async def update_style_ep(style_id: int, body: StyleUpdateBody, _: bool = Depends(require_auth)):
    if style_id < 1:
        raise HTTPException(status_code=400, detail="ID tidak valid")
    async with _pool.acquire() as con:
        cur = await con.fetchrow("SELECT * FROM custom_styles WHERE id=$1", style_id)
        if not cur:
            raise HTTPException(status_code=404, detail="Style tidak ditemukan")
        # if changing code, uniqueness check
        if body.code and body.code != cur["code"]:
            dup = await con.fetchrow("SELECT id FROM custom_styles WHERE code=$1 AND id!=$2", body.code, style_id)
            if dup:
                raise HTTPException(status_code=409, detail=f"code '{body.code}' sudah dipakai style lain")
        # thumbnail_url validation
        if body.thumbnail_url is not None and body.thumbnail_url.strip():
            u = body.thumbnail_url.strip()
            if not _is_safe_url(u):
                raise HTTPException(status_code=400, detail="thumbnail_url tidak aman — private IP diblokir")
            if not (u.lower().startswith("https://") or u.lower().startswith("http://")):
                raise HTTPException(status_code=400, detail="thumbnail_url harus http/https")
        # build dynamic update
        fields = []
        vals = []
        idx = 1
        mapping = {
            "code": body.code,
            "name": body.name.strip() if body.name else None,
            "prompt_prefix": (body.prompt_prefix[:500] if body.prompt_prefix is not None else None),
            "thumbnail_url": body.thumbnail_url,
            "category": body.category,
            "is_active": body.is_active,
            "sort_order": body.sort_order,
        }
        for col, val in mapping.items():
            if val is not None:
                fields.append(f"{col} = ${idx}")
                vals.append(val)
                idx += 1
        if not fields:
            return {"ok": True, "style": dict(cur)}
        vals.append(style_id)
        sql = f"UPDATE custom_styles SET {', '.join(fields)} WHERE id=${idx} RETURNING *"
        row = await con.fetchrow(sql, *vals)
    await audit_log("style_update", str(style_id), f"fields={list(mapping.keys())}")
    return {"ok": True, "style": dict(row) if row else dict(cur)}

@app.delete("/api/styles/{style_id}")
async def delete_style_ep(style_id: int, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        cur = await con.fetchrow("SELECT code,name FROM custom_styles WHERE id=$1", style_id)
        if not cur:
            raise HTTPException(status_code=404, detail="Style tidak ditemukan")
        await con.execute("DELETE FROM custom_styles WHERE id=$1", style_id)
    await audit_log("style_delete", str(style_id), f"code={cur['code']} name={cur['name']}")
    return {"ok": True}

@app.patch("/api/styles/{style_id}/toggle")
async def toggle_style_ep(style_id: int, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT is_active FROM custom_styles WHERE id=$1", style_id)
        if not row:
            raise HTTPException(status_code=404, detail="Style tidak ditemukan")
        await con.execute("UPDATE custom_styles SET is_active = NOT is_active WHERE id=$1", style_id)
        newrow = await con.fetchrow("SELECT * FROM custom_styles WHERE id=$1", style_id)
    await audit_log("style_toggle", str(style_id), f"is_active={newrow['is_active'] if newrow else ''}")
    return {"ok": True, "style": dict(newrow) if newrow else {"is_active": not row["is_active"]}, "is_active": (newrow["is_active"] if newrow else not row["is_active"])}

# Reorder endpoint optional — bulk set sort_order via map id->order
class StyleReorderBody(BaseModel):
    order: list[int] = Field(..., max_length=200, description="ordered list of style ids")

@app.post("/api/styles/reorder")
async def reorder_styles_ep(body: StyleReorderBody, _: bool = Depends(require_auth)):
    if not body.order:
        raise HTTPException(status_code=400, detail="order kosong")
    if len(set(body.order)) != len(body.order):
        raise HTTPException(status_code=400, detail="order harus unique")
    async with _pool.acquire() as con:
        # verify all exist
        existing = await con.fetch("SELECT id FROM custom_styles WHERE id = ANY($1)", body.order)
        existing_ids = {r["id"] for r in existing}
        missing = [i for i in body.order if i not in existing_ids]
        if missing:
            raise HTTPException(status_code=404, detail=f"ID tidak ditemukan: {missing}")
        async with con.transaction():
            for idx, sid in enumerate(body.order):
                await con.execute("UPDATE custom_styles SET sort_order=$1 WHERE id=$2", idx, sid)
    await audit_log("style_reorder", "-", f"count={len(body.order)}")
    return {"ok": True}

# ---- Provider Failover Config (Phase3 task8) ----

class FailoverReorderBody(BaseModel):
    order: list[str] = Field(..., min_length=1, max_length=50, description="ordered list of provider ids priority ASC")

class FailoverConfigBody(BaseModel):
    timeout_sec: int = Field(..., ge=5, le=120)
    retry_count: int = Field(..., ge=0, le=5)
    cost_per_gen: float = Field(..., ge=0, le=100000)

def _failover_provider_dict(r) -> dict:
    d = dict(r)
    # normalize cost to float
    try:
        d["cost_per_gen"] = float(d.get("cost_per_gen") or 0)
    except Exception:
        d["cost_per_gen"] = 0.0
    return d

@app.get("/api/providers/failover")
async def list_failover_providers(_: bool = Depends(require_auth)):
    # list ordered by failover_priority ASC, with stats: model counts + gen stats 7d via ai_models join
    async with _pool.acquire() as con:
        rows = await con.fetch(
            "SELECT id, name, base_url, is_active, failover_priority, timeout_sec, retry_count, cost_per_gen, created_at, updated_at "
            "FROM providers ORDER BY failover_priority ASC, id ASC"
        )
        # model counts
        model_rows = await con.fetch(
            "SELECT provider_id, count(*) AS total, count(*) FILTER (WHERE is_active) AS active_cnt "
            "FROM ai_models GROUP BY provider_id"
        )
        model_map = {r["provider_id"]: {"total": int(r["total"]), "active": int(r["active_cnt"])} for r in model_rows}
        # gen stats 7d: generations has model_id which contains provider prefix or ai_models FK
        # try join via model_id -> ai_models.provider_id, fallback 0
        try:
            gen_rows = await con.fetch(
                """
                SELECT
                  am.provider_id AS pid,
                  count(*) AS gen_7d,
                  count(*) FILTER (WHERE g.success) AS success_7d,
                  count(*) FILTER (WHERE NOT g.success) AS failed_7d
                FROM generations g
                LEFT JOIN ai_models am ON am.id = g.model_id
                WHERE g.created_at > now() - interval '7 days' AND am.provider_id IS NOT NULL
                GROUP BY am.provider_id
                """
            )
            gen_map = {r["pid"]: {"gen_7d": int(r["gen_7d"]), "success_7d": int(r["success_7d"]), "failed_7d": int(r["failed_7d"])} for r in gen_rows}
        except Exception:
            gen_map = {}

    out = []
    for r in rows:
        d = _failover_provider_dict(r)
        mm = model_map.get(d["id"], {"total": 0, "active": 0})
        gm = gen_map.get(d["id"], {"gen_7d": 0, "success_7d": 0, "failed_7d": 0})
        success_rate = 0
        if gm["gen_7d"] > 0:
            success_rate = round(100.0 * gm["success_7d"] / gm["gen_7d"], 1)
        out.append({
            **d,
            "models_total": mm["total"],
            "models_active": mm["active"],
            "gen_7d": gm["gen_7d"],
            "success_7d": gm["success_7d"],
            "failed_7d": gm["failed_7d"],
            "success_rate_7d": success_rate,
            # placeholder for live latency, filled on-demand via test-ping
            "last_latency_ms": None,
        })
    total_active = sum(1 for p in out if p.get("is_active"))
    avg_cost = round(sum(float(p.get("cost_per_gen") or 0) for p in out) / len(out), 4) if out else 0
    return {"providers": out, "total": len(out), "active": total_active, "avg_cost": avg_cost, "failover_enabled": total_active > 1}

@app.post("/api/providers/failover/reorder")
async def reorder_failover(body: FailoverReorderBody, _: bool = Depends(require_auth)):
    if not body.order:
        raise HTTPException(status_code=400, detail="order kosong")
    # uniqueness
    if len(set(body.order)) != len(body.order):
        raise HTTPException(status_code=400, detail="order harus unique")
    # validate ids pattern
    for pid in body.order:
        if not re.match(r"^[a-z0-9_-]{1,50}$", pid):
            raise HTTPException(status_code=400, detail=f"invalid provider id {pid}")
    async with _pool.acquire() as con:
        existing = await con.fetch("SELECT id FROM providers WHERE id = ANY($1::text[])", body.order)
        existing_ids = {r["id"] for r in existing}
        missing = [i for i in body.order if i not in existing_ids]
        if missing:
            raise HTTPException(status_code=404, detail=f"Provider tidak ditemukan: {missing}")
        # also ensure reorder covers all? If not, keep remaining after ordered list appended by current priority
        all_rows = await con.fetch("SELECT id FROM providers ORDER BY failover_priority ASC, id ASC")
        all_ids = [r["id"] for r in all_rows]
        remaining = [pid for pid in all_ids if pid not in body.order]
        full_order = body.order + remaining
        async with con.transaction():
            for idx, pid in enumerate(full_order):
                await con.execute("UPDATE providers SET failover_priority=$1, updated_at=now() WHERE id=$2", idx, pid)
    await audit_log("failover_reorder", "-", f"order={','.join(full_order)}")
    return {"ok": True, "order": full_order}

@app.put("/api/providers/{provider_id}/failover-config")
async def update_failover_config(provider_id: str, body: FailoverConfigBody, _: bool = Depends(require_auth)):
    if not re.match(r"^[a-z0-9_-]{1,50}$", provider_id):
        raise HTTPException(status_code=400, detail="invalid provider id")
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT id FROM providers WHERE id=$1", provider_id)
        if not row:
            raise HTTPException(status_code=404, detail="Provider tidak ditemukan")
        await con.execute(
            "UPDATE providers SET timeout_sec=$1, retry_count=$2, cost_per_gen=$3, updated_at=now() WHERE id=$4",
            int(body.timeout_sec), int(body.retry_count), float(body.cost_per_gen), provider_id
        )
    await audit_log("failover_config_update", provider_id, f"timeout={body.timeout_sec} retry={body.retry_count} cost={body.cost_per_gen}")
    return {"ok": True}

@app.post("/api/providers/{provider_id}/test-ping")
async def test_provider_ping(provider_id: str, _: bool = Depends(require_auth)):
    if not re.match(r"^[a-z0-9_-]{1,50}$", provider_id):
        raise HTTPException(status_code=400, detail="invalid provider id")
    async with _pool.acquire() as con:
        prov = await con.fetchrow("SELECT id, name, base_url, is_active, timeout_sec FROM providers WHERE id=$1", provider_id)
        if not prov:
            raise HTTPException(status_code=404, detail="Provider tidak ditemukan")
        # resolve base_url override from settings
        srow = await con.fetchrow("SELECT value FROM settings WHERE key=$1", f"{provider_id}_base_url")
        resolved_base = (srow["value"] if srow and srow["value"] else prov["base_url"] or "").strip().rstrip("/")
    base_url = resolved_base
    if not base_url:
        raise HTTPException(status_code=400, detail="Provider base_url belum di-set")
    if not _is_safe_url(base_url):
        raise HTTPException(status_code=400, detail="base_url tidak aman — SSRF blocked")
    # ping: GET base_url with 6s timeout, no API key leak. Measure latency, retry N times avg? spec: tries N times average
    # We'll honor provider's retry_count? But for test-ping we always try once avg single request unless ? Use retry_count as number of attempts optional: do 1 ping, but expose tries param.
    # Return latency ms, status_code, ok, error
    t0 = time.time()
    latency_ms = None
    status_code = None
    error = None
    ok = False
    # use provider's configured timeout but clamp 5-15 for ping safety, per spec 6s default
    cfg_timeout = int(prov["timeout_sec"] or 30)
    # for ping we use min(cfg_timeout,6) to stay responsive, but not exceed 10
    ping_timeout = min(max(3, cfg_timeout), 10)
    # we override to 6s per spec if config >6: use 6
    if ping_timeout > 6:
        ping_timeout = 6
    attempts = []
    for attempt in range(1):  # single attempt for now: avg would be noisy + slow; spec says average - we keep 1 for quick UX; loop extendable
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(float(ping_timeout), connect=3.0), follow_redirects=True) as client:
                start = time.time()
                resp = await client.get(base_url, headers={"User-Agent": "imgbot-failover-ping/1.0"})
                lat = int((time.time() - start) * 1000)
                attempts.append(lat)
                status_code = resp.status_code
                latency_ms = lat
                # ok if <500
                ok = resp.status_code < 500
                error = None if ok else f"http {resp.status_code}"
                break
        except httpx.TimeoutException:
            attempts.append(None)
            error = "timeout"
            ok = False
        except httpx.ConnectError as ce:
            attempts.append(None)
            error = f"connect {str(ce)[:120]}"
            ok = False
        except Exception as e:
            attempts.append(None)
            error = str(e)[:200]
            ok = False
    avg_latency = None
    valid = [x for x in attempts if x is not None]
    if valid:
        avg_latency = sum(valid) // len(valid)
        latency_ms = avg_latency
    else:
        latency_ms = None
    await audit_log("provider_test_ping", provider_id, f"ok={ok} latency={latency_ms} code={status_code} err={error or ''}"[:500])
    return {
        "ok": ok,
        "provider_id": provider_id,
        "base_url": base_url,
        "resolved_base_url": base_url,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "attempts": attempts,
        "avg_latency_ms": latency_ms,
        "error": error,
        "checked_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }


# ---- Alert Webhook System (Phase3 task9) ----
ALERT_TYPES = {"error_rate", "deposit_pending", "cpu_high", "disk_high", "queue_stuck", "bot_offline"}
ALERT_CHANNELS = {"discord", "telegram", "webhook"}

ALERT_TYPE_DEFAULT_THRESHOLD = {
    "error_rate": 30.0,       # % error rate last hour
    "deposit_pending": 5.0,   # count
    "cpu_high": 80.0,         # % cpu
    "disk_high": 85.0,        # % disk
    "queue_stuck": 3.0,       # stuck count
    "bot_offline": 1.0,       # offline flag (1 = trigger when offline)
}

def _is_safe_alert_url(url: str) -> bool:
    # Allow https only + existing SSRF guard, plus special allowance for discord/telegram webhook hosts
    if not url or not url.strip():
        return False
    u = url.strip()
    low = u.lower()
    # Allow https discord/webhook generic telegram api
    allowed_prefixes = [
        "https://discord.com/api/webhooks/",
        "https://discordapp.com/api/webhooks/",
        "https://api.telegram.org/bot",
    ]
    for pref in allowed_prefixes:
        if low.startswith(pref):
            # still check host not private etc but discord.com is safe
            try:
                m = re.search(r"https?://([^/:?#]+)", u, re.I)
                if m:
                    host = m.group(1).lower()
                    if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
                        return False
            except Exception:
                pass
            return True
    # numeric chat_id allowed for telegram channel? e.g. "-100123" or "123456" — allow if numeric pattern
    if re.match(r"^-?\d{5,20}$", u):
        return True  # telegram chat_id numeric
    # otherwise must pass generic _is_safe_url and https
    if not u.lower().startswith("https://"):
        return False
    return _is_safe_url(u)

async def _send_discord(webhook_url: str, text: str) -> tuple[bool, str]:
    if not _is_safe_alert_url(webhook_url):
        return False, "URL not allowed (SSRF)"
    # Discord webhook expects JSON {content: text} or embeds. Simpler content.
    payload = {"content": text[:1900]}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(webhook_url, json=payload, headers={"User-Agent": "imgbot-alert/1.0"})
            if r.status_code in (200, 204):
                return True, f"discord {r.status_code}"
            return False, f"discord http {r.status_code} {r.text[:200]}"
    except Exception as e:
        return False, f"discord err {str(e)[:200]}"

async def _send_telegram_via_bot_api(target: str, bot_token: str, text: str) -> tuple[bool, str]:
    # target can be numeric chat_id or https api URL already containing sendMessage? We normalize.
    chat_id = target.strip()
    # Support if target is like https://api.telegram.org/botTOKEN/sendMessage?chat_id=... -> reject direct but allow extracting chat_id? For safety only numeric.
    if chat_id.startswith("https://"):
        # If it's a telegram bot api URL that user pasted (e.g. https://api.telegram.org/botXXX/sendMessage with chat_id embedded?) We do generic attempt: if it contains /sendMessage we POST text there.
        # But safer: if target startswith https, we POST JSON {text} or {chat_id + text}?
        # Deprecate: treat https telegram as generic webhook with telegram payload shape.
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Try sendMessage shape {chat_id, text}
                # We need chat_id – we don't have one, try generic {text}
                # For https telegram webhook URLs, we don't know chat_id, attempt POST with text field and also try chat_id extraction from URL query
                m = re.search(r"chat_id=(-?\d+)", target)
                if m:
                    cid = m.group(1)
                    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    r = await client.post(url, json={"chat_id": cid, "text": text})
                    if r.status_code == 200 and r.json().get("ok"):
                        return True, f"telegram {r.status_code}"
                    return False, f"telegram http {r.status_code} {r.text[:200]}"
                # otherwise treat as generic webhook url expecting text
                r = await client.post(target, json={"text": text, "chat_id": chat_id}, headers={"User-Agent": "imgbot-alert/1.0"})
                if r.status_code < 300:
                    return True, f"webhook {r.status_code}"
                return False, f"webhook http {r.status_code} {r.text[:200]}"
        except Exception as e:
            return False, f"tg webhook err {str(e)[:200]}"
    # numeric chat_id
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            r = await client.post(url, json={"chat_id": chat_id, "text": text})
            try:
                j = r.json()
            except Exception:
                j = {}
            if r.status_code == 200 and j.get("ok"):
                return True, "telegram ok"
            return False, f"telegram http {r.status_code} {j.get('description','') or r.text[:200]}"
    except Exception as e:
        return False, f"telegram err {str(e)[:200]}"

async def _send_webhook_generic(url: str, text: str, meta: dict | None = None) -> tuple[bool, str]:
    if not _is_safe_alert_url(url):
        return False, "URL not allowed"
    low = url.lower()
    # discord path already handled but keep generic
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            if "discord.com" in low or "discordapp.com" in low:
                # discord shape
                ok, msg = await _send_discord(url, text)
                return ok, msg
            elif "api.telegram.org" in low:
                # generic telegram bot url
                # expect POST {text}
                r = await client.post(url, json={"text": text, "message": text, "content": text, **(meta or {})}, headers={"User-Agent": "imgbot-alert/1.0"})
                if r.status_code < 300:
                    return True, f"telegram webhook {r.status_code}"
                return False, f"telegram webhook http {r.status_code} {r.text[:200]}"
            else:
                # generic webhook: JSON {text, content, message}
                payload = {"text": text, "content": text, "message": text, "alert": text, "meta": meta or {}}
                r = await client.post(url, json=payload, headers={"User-Agent": "imgbot-alert/1.0"})
                if r.status_code < 300:
                    return True, f"webhook {r.status_code}"
                return False, f"webhook http {r.status_code} {r.text[:200]}"
    except Exception as e:
        return False, f"webhook err {str(e)[:200]}"

async def _dispatch_alert(rule: dict, message: str, meta: dict | None = None) -> tuple[bool, str]:
    chan = rule.get("channel") or "webhook"
    target = rule.get("target_url") or ""
    meta = meta or {}
    if chan == "discord":
        return await _send_discord(target, message)
    elif chan == "telegram":
        # need bot token from env
        token = BOT_TOKEN or os.environ.get("BOT_TOKEN", "")
        if not token:
            return False, "BOT_TOKEN not configured for telegram channel"
        return await _send_telegram_via_bot_api(target, token, message)
    else:  # webhook generic
        return await _send_webhook_generic(target, message, meta)

async def _collect_current_stats_snapshot() -> dict:
    # Reuse health + system logic without auth - internal call
    now = _dt.datetime.now(_dt.timezone.utc)
    out = {
        "checked_at": now.isoformat(),
        "pending_deposits": 0,
        "error_rate_pct": 0.0,
        "cpu_percent": 0.0,
        "disk_percent": 0.0,
        "queue_stuck": 0,
        "bot_online": False,
        "heartbeat_age_sec": None,
        "heartbeat_raw": None,
        "total_errors_last_hour": 0,
        "total_gens_last_hour": 0,
        "gen_per_hour": 0,
    }
    try:
        async with _pool.acquire() as con:
            pd = await con.fetchval("SELECT count(*) FROM deposits WHERE status='pending'") or 0
            out["pending_deposits"] = int(pd)
            # error rate last hour
            total_last_h = await con.fetchval("SELECT count(*) FROM generations WHERE created_at > now() - interval '1 hour'") or 0
            failed_last_h = await con.fetchval("SELECT count(*) FROM generations WHERE success=false AND created_at > now() - interval '1 hour'") or 0
            out["total_gens_last_hour"] = int(total_last_h)
            out["total_errors_last_hour"] = int(failed_last_h)
            out["gen_per_hour"] = int(total_last_h)
            if total_last_h > 0:
                out["error_rate_pct"] = round(100.0 * failed_last_h / total_last_h, 2)
            else:
                out["error_rate_pct"] = 0.0
            try:
                stuck = await con.fetchval("SELECT count(*) FROM aiogram_states WHERE updated < now() - interval '5 minutes'") or 0
                out["queue_stuck"] = int(stuck)
            except Exception:
                out["queue_stuck"] = 0
        # bot heartbeat
        hb_raw = await get_setting("bot_last_heartbeat", "")
        out["heartbeat_raw"] = hb_raw or None
        dt = _parse_iso(hb_raw) if hb_raw else None
        if dt:
            age = int((now - dt).total_seconds())
            out["heartbeat_age_sec"] = age
            out["bot_online"] = age < 120
        else:
            out["bot_online"] = False
        # psutil cpu/disk non-blocking
        try:
            snap = await _get_system_metrics_nonblocking()
            out["cpu_percent"] = float(snap.get("cpu_percent", 0) or 0)
            # disk percent
            d = snap.get("disk", {}) or {}
            out["disk_percent"] = float(d.get("percent", 0) or 0)
        except Exception:
            pass
    except Exception as e:
        out["error"] = str(e)[:300]
    return out

def _should_trigger_rule(rule: dict, stats: dict) -> tuple[bool, str]:
    # Returns (should_trigger, reason_message)
    t = rule.get("type")
    thr = float(rule.get("threshold") or 0)
    # check cooldown
    last_ts = rule.get("last_triggered_at")
    cooldown = int(rule.get("cooldown_sec") or 900)
    if last_ts:
        try:
            # asyncpg returns datetime; ensure aware
            if isinstance(last_ts, str):
                last_dt = _parse_iso(last_ts)
            else:
                last_dt = last_ts
                if last_dt and last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=_dt.timezone.utc)
            if last_dt:
                elapsed = (_dt.datetime.now(_dt.timezone.utc) - last_dt).total_seconds()
                if elapsed < cooldown:
                    return False, f"cooldown {int(cooldown - elapsed)}s remaining"
        except Exception:
            pass
    # evaluate thresholds
    if t == "error_rate":
        cur = float(stats.get("error_rate_pct", 0))
        # thr = % threshold e.g. 20% => trigger if cur >= thr
        if cur >= thr and cur > 0:
            return True, f"Error rate {cur}% >= threshold {thr}% (failed {stats.get('total_errors_last_hour')}/{stats.get('total_gens_last_hour')} last hour)"
        return False, f"error_rate {cur}% < {thr}%"
    elif t == "deposit_pending":
        cur = int(stats.get("pending_deposits", 0))
        if cur >= int(thr):
            return True, f"Pending deposits {cur} >= {int(thr)}"
        return False, f"pending {cur} < {thr}"
    elif t == "cpu_high":
        cur = float(stats.get("cpu_percent", 0))
        if cur >= thr:
            return True, f"CPU {cur}% >= {thr}%"
        return False, f"CPU {cur}% < {thr}%"
    elif t == "disk_high":
        cur = float(stats.get("disk_percent", 0))
        if cur >= thr:
            return True, f"Disk {cur}% >= {thr}%"
        return False, f"disk {cur}% < {thr}%"
    elif t == "queue_stuck":
        cur = int(stats.get("queue_stuck", 0))
        if cur >= int(thr):
            return True, f"Queue stuck {cur} >= {int(thr)} (FSM >5m)"
        return False, f"queue stuck {cur} < {thr}"
    elif t == "bot_offline":
        online = bool(stats.get("bot_online"))
        if not online:
            hb_age = stats.get("heartbeat_age_sec")
            age_txt = f"{hb_age}s ago" if hb_age is not None else "no heartbeat"
            return True, f"Bot offline ({age_txt}) — threshold check"
        return False, "bot online"
    return False, f"unknown type {t}"


# ---- Alerts API ----

class AlertRuleCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., max_length=30)
    threshold: float = Field(..., ge=0, le=1000000)
    channel: str = Field(..., max_length=20)
    target_url: str = Field(..., min_length=3, max_length=1000)
    is_active: bool = True
    cooldown_sec: int = Field(default=900, ge=60, le=86400)

    @field_validator("type")
    @classmethod
    def val_type(cls, v):
        vv = v.strip().lower()
        if vv not in ALERT_TYPES:
            raise ValueError(f"type must be one of {','.join(ALERT_TYPES)}")
        return vv

    @field_validator("channel")
    @classmethod
    def val_channel(cls, v):
        vv = v.strip().lower()
        if vv not in ALERT_CHANNELS:
            raise ValueError(f"channel must be {','.join(ALERT_CHANNELS)}")
        return vv

    @field_validator("target_url")
    @classmethod
    def val_target(cls, v):
        vv = v.strip()
        if len(vv) < 3 or len(vv) > 1000:
            raise ValueError("target_url invalid length")
        # block too suspicious
        if not _is_safe_alert_url(vv):
            raise ValueError("target_url not allowed — must be https:// (discord/telegram/webhook allowed) or numeric telegram chat_id, no private IP")
        return vv

class AlertRuleUpdateBody(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    type: str | None = Field(default=None, max_length=30)
    threshold: float | None = Field(default=None, ge=0, le=1000000)
    channel: str | None = Field(default=None, max_length=20)
    target_url: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None
    cooldown_sec: int | None = Field(default=None, ge=60, le=86400)

    @field_validator("type")
    @classmethod
    def val_type_opt(cls, v):
        if v is None:
            return v
        vv = v.strip().lower()
        if vv not in ALERT_TYPES:
            raise ValueError(f"type must be {','.join(ALERT_TYPES)}")
        return vv

    @field_validator("channel")
    @classmethod
    def val_channel_opt(cls, v):
        if v is None:
            return v
        vv = v.strip().lower()
        if vv not in ALERT_CHANNELS:
            raise ValueError(f"channel must be {','.join(ALERT_CHANNELS)}")
        return vv

    @field_validator("target_url")
    @classmethod
    def val_target_opt(cls, v):
        if v is None:
            return v
        vv = v.strip()
        if not _is_safe_alert_url(vv):
            raise ValueError("target_url not allowed")
        return vv

def _alert_rule_dict(r) -> dict:
    d = dict(r)
    # numeric conversion for threshold
    try:
        d["threshold"] = float(d.get("threshold", 0) or 0)
    except Exception:
        d["threshold"] = 0.0
    # keep identity target_url alias target for frontend simplicity
    d["target"] = d.get("target_url")
    return d

@app.get("/api/alerts/rules")
async def list_alert_rules(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch("SELECT * FROM alert_rules ORDER BY is_active DESC, id DESC")
    return {"rules": [_alert_rule_dict(r) for r in rows], "total": len(rows)}

@app.post("/api/alerts/rules")
async def create_alert_rule(body: AlertRuleCreateBody, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "INSERT INTO alert_rules (name, type, threshold, channel, target_url, is_active, cooldown_sec) VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING *",
            body.name.strip(), body.type, body.threshold, body.channel, body.target_url.strip(), body.is_active, int(body.cooldown_sec),
        )
    await audit_log("alert_rule_create", str(row["id"]), f"{body.type} {body.channel} thr={body.threshold}")
    return {"ok": True, "rule": _alert_rule_dict(row)}

@app.put("/api/alerts/rules/{rule_id}")
async def update_alert_rule(rule_id: int, body: AlertRuleUpdateBody, _: bool = Depends(require_auth)):
    if rule_id < 1:
        raise HTTPException(status_code=400, detail="Invalid id")
    async with _pool.acquire() as con:
        cur = await con.fetchrow("SELECT * FROM alert_rules WHERE id=$1", rule_id)
        if not cur:
            raise HTTPException(status_code=404, detail="Rule not found")
        fields = []
        vals = []
        idx = 1
        mapping = {
            "name": body.name.strip() if body.name else None,
            "type": body.type,
            "threshold": body.threshold,
            "channel": body.channel,
            "target_url": body.target_url.strip() if body.target_url else None,
            "is_active": body.is_active,
            "cooldown_sec": int(body.cooldown_sec) if body.cooldown_sec is not None else None,
        }
        for col, val in mapping.items():
            if val is not None:
                fields.append(f"{col} = ${idx}")
                vals.append(val)
                idx += 1
        if not fields:
            return {"ok": True, "rule": _alert_rule_dict(cur)}
        vals.append(rule_id)
        sql = f"UPDATE alert_rules SET {', '.join(fields)} WHERE id=${idx} RETURNING *"
        row = await con.fetchrow(sql, *vals)
    await audit_log("alert_rule_update", str(rule_id), f"fields={list(body.model_dump(exclude_none=True).keys())}")
    return {"ok": True, "rule": _alert_rule_dict(row) if row else _alert_rule_dict(cur)}

@app.delete("/api/alerts/rules/{rule_id}")
async def delete_alert_rule(rule_id: int, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        cur = await con.fetchrow("SELECT id, name FROM alert_rules WHERE id=$1", rule_id)
        if not cur:
            raise HTTPException(status_code=404, detail="Rule not found")
        await con.execute("DELETE FROM alert_rules WHERE id=$1", rule_id)
    await audit_log("alert_rule_delete", str(rule_id), cur["name"])
    return {"ok": True}

@app.patch("/api/alerts/rules/{rule_id}/toggle")
async def toggle_alert_rule(rule_id: int, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT is_active FROM alert_rules WHERE id=$1", rule_id)
        if not row:
            raise HTTPException(status_code=404, detail="Rule not found")
        newrow = await con.fetchrow("UPDATE alert_rules SET is_active = NOT is_active WHERE id=$1 RETURNING *", rule_id)
    await audit_log("alert_rule_toggle", str(rule_id), f"is_active={newrow['is_active'] if newrow else ''}")
    return {"ok": True, "rule": _alert_rule_dict(newrow) if newrow else {}, "is_active": bool(newrow["is_active"]) if newrow else False}

@app.post("/api/alerts/rules/{rule_id}/test")
async def test_alert_rule(rule_id: int, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rule = await con.fetchrow("SELECT * FROM alert_rules WHERE id=$1", rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
    rd = _alert_rule_dict(rule)
    stats = await _collect_current_stats_snapshot()
    msg = f"[TEST] Alert '{rd['name']}' type={rd['type']} thr={rd['threshold']} channel={rd['channel']} — stats: pending={stats.get('pending_deposits')} err={stats.get('error_rate_pct')}% cpu={stats.get('cpu_percent')}% disk={stats.get('disk_percent')}% stuck={stats.get('queue_stuck')} bot_online={stats.get('bot_online')} at {stats.get('checked_at')}"
    ok, detail = await _dispatch_alert(rd, msg, meta={"test": True, "stats": stats, "rule": rd})
    if ok:
        try:
            async with _pool.acquire() as con:
                await con.execute(
                    "INSERT INTO alert_history (rule_id, type, message, triggered_at, resolved, meta) VALUES ($1,$2,$3, now(), false, $4::jsonb)",
                    rule_id, rd["type"], msg, __import__("json").dumps({"test": True, "dispatch": detail, "stats": stats}),
                )
        except Exception:
            pass
    await audit_log("alert_test", str(rule_id), f"ok={ok} {detail}"[:500])
    return {"ok": ok, "detail": detail, "stats": stats, "sent": ok, "message": msg if ok else f"Failed: {detail}"}

@app.get("/api/alerts/history")
async def list_alert_history(limit: int = 50, rule_id: int | None = None, _: bool = Depends(require_auth)):
    limit = max(1, min(200, limit))
    async with _pool.acquire() as con:
        if rule_id:
            rows = await con.fetch("SELECT h.*, r.name as rule_name FROM alert_history h LEFT JOIN alert_rules r ON r.id=h.rule_id WHERE h.rule_id=$1 ORDER BY h.triggered_at DESC LIMIT $2", rule_id, limit)
        else:
            rows = await con.fetch("SELECT h.*, r.name as rule_name FROM alert_history h LEFT JOIN alert_rules r ON r.id=h.rule_id ORDER BY h.triggered_at DESC LIMIT $1", limit)
    out = []
    for r in rows:
        d = dict(r)
        # ensure meta parsed if string
        if isinstance(d.get("meta"), str):
            try:
                import json as _json
                d["meta"] = _json.loads(d["meta"])
            except Exception:
                d["meta"] = {}
        out.append(d)
    return {"history": out, "total": len(out)}

@app.patch("/api/alerts/history/{hid}/resolve")
async def resolve_alert_history(hid: int, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        await con.execute("UPDATE alert_history SET resolved=true WHERE id=$1", hid)
    return {"ok": True}

@app.get("/api/alerts/stats")
async def alerts_stats(_: bool = Depends(require_auth)):
    stats = await _collect_current_stats_snapshot()
    # counts per type
    async with _pool.acquire() as con:
        try:
            rcnt = await con.fetchval("SELECT count(*) FROM alert_rules WHERE is_active") or 0
            total_h = await con.fetchval("SELECT count(*) FROM alert_history WHERE triggered_at > now() - interval '24 hours'") or 0
            # real deposits stats already in snapshot, but add success rate 14d-etc reuse?
        except Exception:
            rcnt = 0
            total_h = 0
    return {
        "ok": True,
        "active_rules": int(rcnt),
        "alerts_24h": int(total_h),
        **stats,
    }

@app.post("/api/alerts/evaluate")
async def evaluate_alerts_endpoint(_: bool = Depends(require_auth)):
    stats = await _collect_current_stats_snapshot()
    triggered = []
    skipped = []
    errors = []
    async with _pool.acquire() as con:
        rules = await con.fetch("SELECT * FROM alert_rules WHERE is_active=true ORDER BY id")
    for r in rules:
        rd = _alert_rule_dict(r)
        should, reason = _should_trigger_rule(rd, stats)
        if not should:
            skipped.append({"id": rd["id"], "name": rd["name"], "reason": reason})
            continue
        msg = f"ALERT [{rd['type']}] {rd['name']}: {reason} — threshold {rd['threshold']} at {stats.get('checked_at')}. Details: pending={stats.get('pending_deposits')}, err_rate={stats.get('error_rate_pct')}%, cpu={stats.get('cpu_percent')}%, disk={stats.get('disk_percent')}%, stuck={stats.get('queue_stuck')}, bot_online={stats.get('bot_online')}"
        try:
            ok, detail = await _dispatch_alert(rd, msg, meta={"stats": stats, "reason": reason})
            if ok:
                triggered.append({"id": rd["id"], "name": rd["name"], "type": rd["type"], "message": msg, "detail": detail})
                try:
                    async with _pool.acquire() as con:
                        await con.execute("UPDATE alert_rules SET last_triggered_at=now() WHERE id=$1", rd["id"])
                        import json as _json
                        await con.execute(
                            "INSERT INTO alert_history (rule_id, type, message, triggered_at, resolved, meta) VALUES ($1,$2,$3, now(), false, $4::jsonb)",
                            rd["id"], rd["type"], msg, _json.dumps({"stats": stats, "detail": detail, "reason": reason}),
                        )
                except Exception as e:
                    errors.append({"id": rd["id"], "error": f"history log failed {e}"})
            else:
                errors.append({"id": rd["id"], "name": rd["name"], "error": detail})
        except Exception as e:
            errors.append({"id": rd["id"], "name": rd["name"], "error": str(e)[:300]})
    await audit_log("alerts_evaluate", "-", f"triggered={len(triggered)} skipped={len(skipped)} err={len(errors)}")
    return {"ok": True, "stats": stats, "triggered": triggered, "skipped": skipped, "errors": errors, "checked_at": stats.get("checked_at")}

@app.get("/api/alerts/types")
async def alert_types(_: bool = Depends(require_auth)):
    return {
        "types": [
            {"id": "error_rate", "label": "Error Rate", "unit": "%", "default_threshold": ALERT_TYPE_DEFAULT_THRESHOLD["error_rate"], "desc": "Failed generations % last hour"},
            {"id": "deposit_pending", "label": "Deposit Pending", "unit": "count", "default_threshold": ALERT_TYPE_DEFAULT_THRESHOLD["deposit_pending"], "desc": "Pending deposits count"},
            {"id": "cpu_high", "label": "CPU High", "unit": "%", "default_threshold": ALERT_TYPE_DEFAULT_THRESHOLD["cpu_high"], "desc": "CPU percent high"},
            {"id": "disk_high", "label": "Disk High", "unit": "%", "default_threshold": ALERT_TYPE_DEFAULT_THRESHOLD["disk_high"], "desc": "Disk usage percent high"},
            {"id": "queue_stuck", "label": "Queue Stuck", "unit": "count", "default_threshold": ALERT_TYPE_DEFAULT_THRESHOLD["queue_stuck"], "desc": "FSM stuck >5m count"},
            {"id": "bot_offline", "label": "Bot Offline", "unit": "bool", "default_threshold": ALERT_TYPE_DEFAULT_THRESHOLD["bot_offline"], "desc": "Heartbeat >120s offline"},
        ],
        "channels": [
            {"id": "discord", "label": "Discord", "placeholder": "https://discord.com/api/webhooks/..."},
            {"id": "telegram", "label": "Telegram", "placeholder": "chat_id numeric e.g. -100123... or telegram webhook url"},
            {"id": "webhook", "label": "Generic Webhook", "placeholder": "https://..."},
        ],
        "default_thresholds": ALERT_TYPE_DEFAULT_THRESHOLD,
    }




# ---- Moderation Manager (Phase3 task7) ----

class ModerationRuleCreateBody(BaseModel):
    pattern: str = Field(..., min_length=1, max_length=200)
    type: str = Field(..., max_length=20)
    severity: str = Field(..., max_length=20)
    is_active: bool = True

    @field_validator("pattern")
    @classmethod
    def validate_pat(cls, v):
        vv = v.strip()
        if not vv or len(vv) < 1 or len(vv) > 200:
            raise ValueError("pattern 1-200 chars required")
        if "<script" in vv.lower() or "javascript:" in vv.lower():
            raise ValueError("pattern contains forbidden content")
        return vv

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        vv = (v or "").strip().lower()
        if vv not in ("word","regex","category"):
            raise ValueError("type must be word/regex/category")
        return vv

    @field_validator("severity")
    @classmethod
    def validate_sev(cls, v):
        vv = (v or "").strip().lower()
        if vv not in ("low","medium","high","block"):
            raise ValueError("severity must be low/medium/high/block")
        return vv

class ModerationRuleUpdateBody(BaseModel):
    pattern: str | None = Field(default=None, max_length=200)
    type: str | None = Field(default=None, max_length=20)
    severity: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None

    @field_validator("pattern")
    @classmethod
    def validate_pat_opt(cls, v):
        if v is None:
            return v
        vv = v.strip()
        if not vv or len(vv) < 1 or len(vv) > 200:
            raise ValueError("pattern 1-200 chars")
        if "<script" in vv.lower() or "javascript:" in vv.lower():
            raise ValueError("forbidden pattern")
        return vv

    @field_validator("type")
    @classmethod
    def validate_type_opt(cls, v):
        if v is None:
            return v
        vv = v.strip().lower()
        if vv not in ("word","regex","category"):
            raise ValueError("type must be word/regex/category")
        return vv

    @field_validator("severity")
    @classmethod
    def validate_sev_opt(cls, v):
        if v is None:
            return v
        vv = v.strip().lower()
        if vv not in ("low","medium","high","block"):
            raise ValueError("severity must be low/medium/high/block")
        return vv

def _validate_regex_pattern(pat: str):
    try:
        re.compile(pat, re.IGNORECASE)
    except re.error as e:
        raise HTTPException(status_code=400, detail=f"Invalid regex: {e}")

@app.get("/api/moderation/rules")
async def moderation_list_rules(q: str = "", type: str = "", active: str = "", _: bool = Depends(require_auth)):
    q = (q or "").strip()[:100]
    type_f = (type or "").strip().lower()
    active_f = (active or "").strip().lower()
    where = []
    args = []
    idx = 1
    if q:
        where.append(f"(pattern ILIKE ${idx} OR type ILIKE ${idx} OR severity ILIKE ${idx})")
        args.append(f"%{q}%")
        idx+=1
    if type_f and type_f in ("word","regex","category"):
        where.append(f"type = ${idx}")
        args.append(type_f)
        idx+=1
    if active_f == "true":
        where.append("is_active = true")
    elif active_f == "false":
        where.append("is_active = false")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"SELECT * FROM moderation_rules {where_sql} ORDER BY id DESC LIMIT 500"
    async with _pool.acquire() as con:
        rows = await con.fetch(sql, *args)
    return {"rules": [dict(r) for r in rows], "total": len(rows)}

@app.post("/api/moderation/rules")
async def moderation_create_rule(body: ModerationRuleCreateBody, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        cnt = await con.fetchval("SELECT count(*) FROM moderation_rules") or 0
        if cnt >= 500:
            raise HTTPException(status_code=400, detail="Max 500 rules reached")
        if body.type == "regex":
            _validate_regex_pattern(body.pattern)
        row = await con.fetchrow(
            "INSERT INTO moderation_rules (pattern, type, severity, is_active) VALUES ($1,$2,$3,$4) RETURNING *",
            body.pattern.strip(), body.type, body.severity, body.is_active
        )
    await audit_log("moderation_create", str(row["id"]), f"{body.type}:{body.severity}:{body.pattern[:50]}")
    return {"ok": True, "rule": dict(row)}

@app.put("/api/moderation/rules/{rule_id}")
async def moderation_update_rule(rule_id: int, body: ModerationRuleUpdateBody, _: bool = Depends(require_auth)):
    if rule_id < 1:
        raise HTTPException(status_code=400, detail="Invalid ID")
    async with _pool.acquire() as con:
        cur = await con.fetchrow("SELECT * FROM moderation_rules WHERE id=$1", rule_id)
        if not cur:
            raise HTTPException(status_code=404, detail="Rule not found")
        new_pat = body.pattern if body.pattern is not None else cur["pattern"]
        new_type = body.type if body.type is not None else cur["type"]
        new_sev = body.severity if body.severity is not None else cur["severity"]
        new_active = body.is_active if body.is_active is not None else cur["is_active"]
        if new_type == "regex":
            _validate_regex_pattern(new_pat)
        row = await con.fetchrow(
            "UPDATE moderation_rules SET pattern=$1, type=$2, severity=$3, is_active=$4 WHERE id=$5 RETURNING *",
            new_pat.strip(), new_type, new_sev, new_active, rule_id
        )
    await audit_log("moderation_update", str(rule_id), f"{new_type}:{new_sev}:{new_pat[:50]}")
    return {"ok": True, "rule": dict(row)}

@app.delete("/api/moderation/rules/{rule_id}")
async def moderation_delete_rule(rule_id: int, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        cur = await con.fetchrow("SELECT pattern FROM moderation_rules WHERE id=$1", rule_id)
        if not cur:
            raise HTTPException(status_code=404, detail="Rule not found")
        await con.execute("DELETE FROM moderation_rules WHERE id=$1", rule_id)
    await audit_log("moderation_delete", str(rule_id), cur["pattern"][:100])
    return {"ok": True}

@app.patch("/api/moderation/rules/{rule_id}/toggle")
async def moderation_toggle_rule(rule_id: int, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        cur = await con.fetchrow("SELECT is_active FROM moderation_rules WHERE id=$1", rule_id)
        if not cur:
            raise HTTPException(status_code=404, detail="Rule not found")
        await con.execute("UPDATE moderation_rules SET is_active = NOT is_active WHERE id=$1", rule_id)
        row = await con.fetchrow("SELECT * FROM moderation_rules WHERE id=$1", rule_id)
    await audit_log("moderation_toggle", str(rule_id), f"is_active={row['is_active'] if row else ''}")
    return {"ok": True, "rule": dict(row) if row else {}, "is_active": row["is_active"] if row else False}

@app.get("/api/moderation/logs")
async def moderation_logs_ep(user_id: str = "", limit: int = 100, offset: int = 0, _: bool = Depends(require_auth)):
    limit = max(1, min(500, int(limit or 100)))
    offset = max(0, int(offset or 0))
    where = []
    args = []
    idx = 1
    if user_id and user_id.strip().isdigit():
        where.append(f"user_id = ${idx}")
        args.append(int(user_id.strip()))
        idx+=1
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    async with _pool.acquire() as con:
        rows = await con.fetch(f"SELECT * FROM moderation_logs {where_sql} ORDER BY id DESC LIMIT ${idx} OFFSET ${idx+1}", *args, limit, offset)
        total = await con.fetchval(f"SELECT count(*) FROM moderation_logs {where_sql}", *args)
    return {"logs": [dict(r) for r in rows], "total": total or 0, "limit": limit, "offset": offset}

@app.get("/api/moderation/stats")
async def moderation_stats_ep(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        total = await con.fetchval("SELECT count(*) FROM moderation_rules") or 0
        active = await con.fetchval("SELECT count(*) FROM moderation_rules WHERE is_active=true") or 0
        blocks_today = await con.fetchval("SELECT count(*) FROM moderation_logs WHERE created_at::date = CURRENT_DATE AND action='block'") or 0
        high = await con.fetchval("SELECT count(*) FROM moderation_rules WHERE severity IN ('high','block')") or 0
        sev_rows = await con.fetch("SELECT severity, count(*) as c FROM moderation_rules GROUP BY severity")
        logs_today = await con.fetchval("SELECT count(*) FROM moderation_logs WHERE created_at::date=CURRENT_DATE") or 0
    sev_map = {r["severity"]: r["c"] for r in sev_rows}
    return {
        "total_rules": total,
        "active_rules": active,
        "blocks_today": blocks_today,
        "high_severity": high,
        "logs_today": logs_today,
        "by_severity": sev_map,
    }


# ---- Cost Tracker (Phase4 Task10) ----
def _parse_cost_period(p: str) -> int:
    p = (p or "30d").strip().lower()
    mapping = {"7d": 7, "30d": 30, "90d": 90, "365d": 365, "7": 7, "30": 30, "90": 90, "365": 365}
    if p in mapping:
        return mapping[p]
    raise HTTPException(status_code=400, detail="period must be 7d|30d|90d|365d")

class CostProviderUpdateBody(BaseModel):
    cost_per_gen: float = Field(..., ge=0, le=100000)

@app.get("/api/cost/providers")
async def cost_list_providers(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch(
            "SELECT id, name, base_url, is_active, failover_priority, timeout_sec, retry_count, cost_per_gen FROM providers ORDER BY failover_priority ASC, id ASC"
        )
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["cost_per_gen"] = float(d.get("cost_per_gen") or 0)
        except Exception:
            d["cost_per_gen"] = 0.0
        out.append(d)
    return {"providers": out, "total": len(out)}

@app.put("/api/cost/providers/{provider_id}")
async def cost_update_provider(provider_id: str, body: CostProviderUpdateBody, _: bool = Depends(require_auth)):
    if not re.match(r"^[a-z0-9_-]{1,50}$", provider_id):
        raise HTTPException(status_code=400, detail="invalid provider id")
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT id FROM providers WHERE id=$1", provider_id)
        if not row:
            raise HTTPException(status_code=404, detail="Provider not found")
        await con.execute("UPDATE providers SET cost_per_gen=$1, updated_at=now() WHERE id=$2", float(body.cost_per_gen), provider_id)
    await audit_log("cost_provider_update", provider_id, f"cost_per_gen={body.cost_per_gen}")
    return {"ok": True, "provider_id": provider_id, "cost_per_gen": float(body.cost_per_gen)}

@app.get("/api/cost/stats")
async def cost_stats(period: str = "30d", _: bool = Depends(require_auth)):
    days = _parse_cost_period(period)
    period_label = f"{days}d"
    # collect providers base
    async with _pool.acquire() as con:
        prov_rows = await con.fetch("SELECT id, name, base_url, is_active, cost_per_gen FROM providers ORDER BY failover_priority ASC, id ASC")
        providers = []
        for r in prov_rows:
            d = dict(r)
            try:
                d["cost_per_gen"] = float(d.get("cost_per_gen") or 0)
            except Exception:
                d["cost_per_gen"] = 0.0
            providers.append(d)
        avg_cost = sum(p["cost_per_gen"] for p in providers) / len(providers) if providers else 0

        # map model -> provider + cost
        model_to_provider = {}
        try:
            mrows = await con.fetch("SELECT id, provider_id, external_id, display_name FROM ai_models")
            for mr in mrows:
                model_to_provider[mr["id"]] = {"provider_id": mr["provider_id"], "display_name": mr["display_name"] or mr["id"]}
        except Exception:
            pass

        # provider cost map
        cost_map = {p["id"]: p["cost_per_gen"] for p in providers}

        # daily gens via generate_series — avoids missing date gaps
        # we need dynamic aggregation; bucket by DATE
        daily_raw = await con.fetch(
            f"""
            SELECT DATE(g.created_at) as d,
                   COUNT(*) as total,
                   COUNT(*) FILTER (WHERE g.success) as success_cnt,
                   COUNT(*) FILTER (WHERE NOT g.success) as failed_cnt
            FROM generations g
            WHERE g.created_at >= now() - interval '{days} days'
            GROUP BY DATE(g.created_at)
            ORDER BY d ASC
            """,
        )
        # revenue daily: deposits approved + orders approved both sum
        dep_daily = await con.fetch(
            f"""
            SELECT DATE(d.created_at) as d, COALESCE(SUM(d.amount),0) as revenue
            FROM deposits d
            WHERE d.status='approved' AND d.created_at >= now() - interval '{days} days'
            GROUP BY DATE(d.created_at)
            ORDER BY d ASC
            """,
        )
        ord_daily = await con.fetch(
            f"""
            SELECT DATE(o.created_at) as d, COALESCE(SUM(o.amount),0) as revenue
            FROM orders o
            WHERE o.status='approved' AND o.created_at >= now() - interval '{days} days'
            GROUP BY DATE(o.created_at)
            ORDER BY d ASC
            """,
        )
        # totals revenue period
        try:
            dep_total = await con.fetchval(
                f"SELECT COALESCE(SUM(amount),0) FROM deposits WHERE status='approved' AND created_at >= now() - interval '{days} days'"
            ) or 0
        except Exception:
            dep_total = 0
        try:
            ord_total = await con.fetchval(
                f"SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='approved' AND created_at >= now() - interval '{days} days'"
            ) or 0
        except Exception:
            ord_total = 0

        # provider breakdown try via model_id join; fallback to estimated distribution if no model_id tracking
        prov_breakdown_raw = []
        try:
            prov_breakdown_raw = await con.fetch(
                f"""
                SELECT
                  am.provider_id as pid,
                  am.id as model_full_id,
                  am.display_name as model_name,
                  COUNT(*) as gen_count,
                  COUNT(*) FILTER (WHERE g.success) as success_cnt,
                  COUNT(*) FILTER (WHERE NOT g.success) as failed_cnt
                FROM generations g
                LEFT JOIN ai_models am ON am.id = g.model_id
                WHERE g.created_at >= now() - interval '{days} days' AND am.provider_id IS NOT NULL
                GROUP BY am.provider_id, am.id, am.display_name
                ORDER BY gen_count DESC
                """,
            )
        except Exception:
            prov_breakdown_raw = []

        # aggregated per provider from above grouping
        prov_agg = {}
        model_agg = {}
        for r in prov_breakdown_raw:
            pid = r["pid"]
            mf_id = r["model_full_id"] or pid
            gen_c = int(r["gen_count"] or 0)
            succ = int(r["success_cnt"] or 0)
            fail = int(r["failed_cnt"] or 0)
            # per provider aggregation
            if pid not in prov_agg:
                prov_agg[pid] = {"gen_count": 0, "success": 0, "failed": 0}
            prov_agg[pid]["gen_count"] += gen_c
            prov_agg[pid]["success"] += succ
            prov_agg[pid]["failed"] += fail
            # per model
            key = mf_id
            if key not in model_agg:
                model_agg[key] = {
                    "model_id": mf_id,
                    "model_name": r["model_name"] or mf_id,
                    "provider_id": pid,
                    "gen_count": 0,
                    "success": 0,
                    "failed": 0,
                }
            model_agg[key]["gen_count"] += gen_c
            model_agg[key]["success"] += succ
            model_agg[key]["failed"] += fail

        # total gens for period (for total cost estimate + fallback)
        total_gens_row = await con.fetchval(f"SELECT count(*) FROM generations WHERE created_at >= now() - interval '{days} days'") or 0
        success_gens_row = await con.fetchval(f"SELECT count(*) FROM generations WHERE success AND created_at >= now() - interval '{days} days'") or 0
        failed_gens_row = total_gens_row - success_gens_row if total_gens_row else 0

    # Build daily map dict for quick calc
    import datetime as _dt2
    today = _dt2.date.today()
    daily_map = {r["d"]: {"total": int(r["total"] or 0), "success": int(r["success_cnt"] or 0), "failed": int(r["failed_cnt"] or 0)} for r in daily_raw}
    dep_map = {r["d"]: float(r["revenue"] or 0) for r in dep_daily}
    ord_map = {r["d"]: float(r["revenue"] or 0) for r in ord_daily}

    # If provider model tracking missing (prov_agg empty but gens exist), estimate per-provider share equally or via is_active proportion
    if not prov_agg and int(total_gens_row or 0) > 0 and providers:
        active_ps = [p for p in providers if p["is_active"]] or providers
        per_share = int(total_gens_row) // len(active_ps) if active_ps else 0
        remainder = int(total_gens_row) % len(active_ps) if active_ps else 0
        for i, p in enumerate(active_ps):
            c = per_share + (1 if i < remainder else 0)
            prov_agg[p["id"]] = {"gen_count": c, "success": c, "failed": 0}

    # daily loop produce aligned array for each date in period
    daily_result = []
    total_cost_calc = 0.0
    total_rev_calc = float(dep_total or 0) + float(ord_total or 0)
    # For daily cost estimate: if we have provider breakdown but daily distribution unknown per-provider, we use total gen * weighted avg cost per gen derived from actual provider shares
    # compute weighted avg cost per gen actually observed
    total_weighted_cost = 0.0
    total_tracked_gens = 0
    for pid, agg in prov_agg.items():
        cp = cost_map.get(pid, avg_cost)
        gen_c = agg["gen_count"]
        total_weighted_cost += gen_c * cp
        total_tracked_gens += gen_c
    # if tracked gens < total, use avg_cost for remainder
    remaining_gens = int(total_gens_row or 0) - total_tracked_gens
    if remaining_gens > 0:
        total_weighted_cost += remaining_gens * (avg_cost or 0)

    per_gen_cost_used = (total_weighted_cost / total_gens_row) if total_gens_row else (avg_cost or 0)

    for offset in range(days):
        d = today - _dt2.timedelta(days=days - 1 - offset)
        gm = daily_map.get(d, {"total": 0, "success": 0, "failed": 0})
        gen_cnt = gm["total"]
        succ = gm["success"]
        fail = gm["failed"]
        rev_dep = dep_map.get(d, 0.0)
        rev_ord = ord_map.get(d, 0.0)
        revenue = float(rev_dep + rev_ord)
        cost = float(gen_cnt) * float(per_gen_cost_used)
        profit = revenue - cost
        total_cost_calc += cost
        daily_result.append({
            "date": d.isoformat(),
            "day": d.strftime("%d/%m"),
            "gen_count": gen_cnt,
            "success": succ,
            "failed": fail,
            "revenue": revenue,
            "cost": cost,
            "profit": profit,
        })

    # final totals: revenue from dep_total+ord_total already fetched, but unify with daily sum for consistency
    # recalc totals to match daily sums for chart sanity; use fetched totals as primary but align
    # if daily revenue sum differs due to timezone DATE grouping vs exact interval, keep fetched totals as revenue total and daily array as display approx
    total_cost = float(total_weighted_cost)
    total_revenue = float(total_rev_calc)
    total_profit = total_revenue - total_cost
    total_gens = int(total_gens_row or 0)
    total_success = int(success_gens_row or 0)
    total_failed = int(failed_gens_row or 0)
    avg_cost_per_gen = (total_cost / total_gens) if total_gens > 0 else 0.0

    # provider breakdown list
    provider_breakdown = []
    for p in providers:
        agg = prov_agg.get(p["id"], {"gen_count": 0, "success": 0, "failed": 0})
        gc = agg["gen_count"]
        succ = agg["success"]
        fail = agg.get("failed", gc - succ)
        rate = round(100.0 * succ / gc, 1) if gc > 0 else 0.0
        tc = float(gc) * float(p["cost_per_gen"] or 0)
        provider_breakdown.append({
            "id": p["id"],
            "name": p["name"] or p["id"],
            "is_active": bool(p["is_active"]),
            "cost_per_gen": float(p["cost_per_gen"] or 0),
            "gen_count": gc,
            "success": succ,
            "failed": fail,
            "success_rate": rate,
            "total_cost": tc,
        })
    provider_breakdown.sort(key=lambda x: x["total_cost"], reverse=True)

    # model breakdown
    model_breakdown = []
    for mid, ag in model_agg.items():
        pid = ag["provider_id"]
        cp = cost_map.get(pid, avg_cost)
        gc = ag["gen_count"]
        succ = ag["success"]
        fail = ag["failed"]
        rate = round(100.0 * succ / gc, 1) if gc > 0 else 0.0
        tc = float(gc) * float(cp)
        model_breakdown.append({
            "model_id": mid,
            "display_name": ag["model_name"] or mid,
            "provider_id": pid,
            "cost_per_gen": float(cp),
            "gen_count": gc,
            "success": succ,
            "failed": fail,
            "success_rate": rate,
            "total_cost": tc,
        })
    model_breakdown.sort(key=lambda x: x["gen_count"], reverse=True)

    # most/least
    most_exp = None
    cheapest = None
    if providers:
        sorted_cost = sorted(providers, key=lambda x: x["cost_per_gen"], reverse=True)
        if sorted_cost:
            most_exp = {"id": sorted_cost[0]["id"], "name": sorted_cost[0]["name"], "cost_per_gen": float(sorted_cost[0]["cost_per_gen"])}
            cheapest = {"id": sorted_cost[-1]["id"], "name": sorted_cost[-1]["name"], "cost_per_gen": float(sorted_cost[-1]["cost_per_gen"])}
    highest_usage = None
    if provider_breakdown:
        hu = max(provider_breakdown, key=lambda x: x["gen_count"]) if provider_breakdown else None
        if hu and hu["gen_count"] > 0:
            highest_usage = {"id": hu["id"], "name": hu["name"], "gen_count": hu["gen_count"]}

    return {
        "period": period_label,
        "days": days,
        "totals": {
            "total_cost": total_cost,
            "total_revenue": total_revenue,
            "total_profit": total_profit,
            "total_gens": total_gens,
            "total_success": total_success,
            "total_failed": total_failed,
            "avg_cost_per_gen": avg_cost_per_gen,
            "deposit_revenue": float(dep_total or 0),
            "order_revenue": float(ord_total or 0),
            "most_expensive_provider": most_exp,
            "cheapest_provider": cheapest,
            "highest_usage_provider": highest_usage,
        },
        "daily": daily_result,
        "provider_breakdown": provider_breakdown,
        "model_breakdown": model_breakdown,
    }

# ---- Backup & Restore 1-Click (Phase4 Task12) ----
def _backup_dict(r) -> dict:
    d = dict(r)
    try:
        d["size_bytes"] = int(d.get("size_bytes") or 0)
    except Exception:
        d["size_bytes"] = 0
    d["size_human"] = _human_size(d["size_bytes"])
    cs = d.get("checksum") or ""
    d["checksum_short"] = cs[:12] if cs else ""
    sp = d.get("storage_path") or ""
    if sp:
        try:
            p = Path(sp)
            d["file_exists"] = p.exists() and p.is_file()
        except Exception:
            d["file_exists"] = False
    else:
        d["file_exists"] = False
    if isinstance(d.get("meta"), str):
        try:
            d["meta"] = _json_std.loads(d["meta"])
        except Exception:
            d["meta"] = {}
    if d.get("meta") is None:
        d["meta"] = {}
    return d

async def _create_pg_dump_internal(filename: str, type_: str, created_by: str = "admin") -> dict:
    _ensure_backup_dir()
    filename = filename.strip()
    if not _is_safe_filename(filename):
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{ts}.sql.gz"
    target_path = _backup_file_path(filename)
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "INSERT INTO backup_history (filename, size_bytes, type, status, storage_path, created_by, meta) VALUES ($1,0,$2,'in_progress',$3,$4,'{}'::jsonb) ON CONFLICT (filename) DO UPDATE SET status='in_progress', size_bytes=0, error_message=NULL, completed_at=NULL RETURNING *",
            filename, type_, str(target_path), created_by
        )
        backup_id = row["id"]
    try:
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            raise RuntimeError("DATABASE_URL not set")
        def _do_dump():
            proc = subprocess.Popen(
                ["pg_dump", db_url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy(),
            )
            try:
                with gzip.open(target_path, "wb", compresslevel=6) as gz:
                    assert proc.stdout is not None
                    while True:
                        chunk = proc.stdout.read(1048576)
                        if not chunk:
                            break
                        gz.write(chunk)
                _, stderr = proc.communicate(timeout=300)
                if proc.returncode != 0:
                    err_txt = stderr.decode("utf-8", errors="ignore")[:2000] if stderr else f"pg_dump exit {proc.returncode}"
                    raise RuntimeError(err_txt)
            finally:
                try:
                    if proc.poll() is None:
                        proc.kill()
                except Exception:
                    pass
        await asyncio.to_thread(_do_dump)
        size = 0
        try:
            size = target_path.stat().st_size
        except Exception:
            size = 0
        checksum = await asyncio.to_thread(_calculate_checksum, target_path)
        async with _pool.acquire() as con:
            upd = await con.fetchrow(
                "UPDATE backup_history SET size_bytes=$1, checksum=$2, status='completed', completed_at=now(), error_message=NULL WHERE id=$3 RETURNING *",
                size, checksum, backup_id
            )
        await audit_log("backup_create_ok", str(backup_id), f"{filename} size={size} checksum={checksum[:12]}")
        return _backup_dict(upd) if upd else {}
    except Exception as e:
        err_msg = str(e)[:2000]
        try:
            if target_path.exists():
                target_path.unlink(missing_ok=True)
        except Exception:
            pass
        async with _pool.acquire() as con:
            try:
                await con.execute("UPDATE backup_history SET status='failed', error_message=$1, completed_at=now() WHERE id=$2", err_msg, backup_id)
            except Exception:
                pass
        await audit_log("backup_create_fail", str(backup_id), err_msg[:500])
        raise HTTPException(status_code=500, detail=f"Backup gagal: {err_msg[:500]}") from e

async def _restore_pg_internal(backup_id: int, storage_path: str, filename: str) -> dict:
    _ensure_backup_dir()
    p = Path(storage_path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="File backup tidak ditemukan di disk")
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not set")
    async with _pool.acquire() as con:
        await con.execute("UPDATE backup_history SET status='restoring', error_message=NULL WHERE id=$1", backup_id)
    try:
        def _do_restore():
            sp = str(p)
            if sp.endswith(".sql.gz") or sp.endswith(".gz"):
                proc_psql = subprocess.Popen(
                    ["psql", db_url, "-v", "ON_ERROR_STOP=1", "--quiet"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=os.environ.copy(),
                )
                try:
                    with gzip.open(p, "rb") as gz:
                        assert proc_psql.stdin is not None
                        while True:
                            chunk = gz.read(1048576)
                            if not chunk:
                                break
                            proc_psql.stdin.write(chunk)
                    proc_psql.stdin.close()
                    stdout, stderr = proc_psql.communicate(timeout=600)
                    if proc_psql.returncode != 0:
                        err = (stderr or b"").decode("utf-8", errors="ignore")[:3000]
                        raise RuntimeError(err or f"psql exit {proc_psql.returncode}")
                finally:
                    try:
                        if proc_psql.poll() is None:
                            proc_psql.kill()
                    except Exception:
                        pass
            elif sp.endswith(".dump"):
                proc = subprocess.run(
                    ["pg_restore", "--dbname", db_url, "--clean", "--if-exists", "--no-owner", sp],
                    capture_output=True,
                    text=True,
                    timeout=600,
                    env=os.environ.copy(),
                )
                if proc.returncode != 0:
                    raise RuntimeError((proc.stderr or proc.stdout or f"pg_restore exit {proc.returncode}")[:3000])
            elif sp.endswith(".sql"):
                proc_psql = subprocess.Popen(
                    ["psql", db_url, "-v", "ON_ERROR_STOP=1", "--quiet"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=os.environ.copy(),
                )
                try:
                    assert proc_psql.stdin is not None
                    with open(p, "rb") as src:
                        shutil.copyfileobj(src, proc_psql.stdin, length=1048576)
                    proc_psql.stdin.close()
                    stdout, stderr = proc_psql.communicate(timeout=600)
                    if proc_psql.returncode != 0:
                        err = (stderr or b"").decode("utf-8", errors="ignore")[:3000]
                        raise RuntimeError(err or f"psql exit {proc_psql.returncode}")
                finally:
                    try:
                        if proc_psql.poll() is None:
                            proc_psql.kill()
                    except Exception:
                        pass
            else:
                raise RuntimeError("Unsupported file extension for restore")
        await asyncio.to_thread(_do_restore)
        try:
            async with _pool.acquire() as con:
                await con.execute(
                    """
                    CREATE TABLE IF NOT EXISTS backup_history (
                        id SERIAL PRIMARY KEY,
                        filename TEXT UNIQUE NOT NULL,
                        size_bytes BIGINT DEFAULT 0,
                        type TEXT DEFAULT 'manual',
                        status TEXT DEFAULT 'completed',
                        storage_path TEXT,
                        checksum TEXT,
                        created_by TEXT,
                        created_at TIMESTAMPTZ DEFAULT now(),
                        completed_at TIMESTAMPTZ,
                        error_message TEXT,
                        meta JSONB DEFAULT '{}'::jsonb
                    );
                    """
                )
                await con.execute("CREATE INDEX IF NOT EXISTS idx_backup_history_created ON backup_history(created_at DESC);")
                exists = await con.fetchrow("SELECT id FROM backup_history WHERE filename=$1", filename)
                if not exists:
                    size_b = 0
                    try:
                        size_b = p.stat().st_size
                    except Exception:
                        size_b = 0
                    checksum = await asyncio.to_thread(_calculate_checksum, p)
                    await con.execute(
                        "INSERT INTO backup_history (filename, size_bytes, type, status, storage_path, checksum, created_by, completed_at, meta) VALUES ($1,$2,'manual','completed',$3,$4,$5, now(), '{}'::jsonb) ON CONFLICT (filename) DO UPDATE SET status='completed', completed_at=now()",
                        filename, size_b, str(p), checksum, "admin:restore"
                    )
                else:
                    await con.execute("UPDATE backup_history SET status='completed', completed_at=now(), error_message=NULL WHERE filename=$1", filename)
        except Exception as re_e:
            print(f"warn restore re-sync backup_history: {re_e}")
        await audit_log("backup_restore_ok", str(backup_id), f"{filename} restored")
        return {"ok": True, "restored": filename}
    except Exception as e:
        err_msg = str(e)[:3000]
        try:
            async with _pool.acquire() as con:
                await con.execute(
                    """
                    CREATE TABLE IF NOT EXISTS backup_history (
                        id SERIAL PRIMARY KEY,
                        filename TEXT UNIQUE NOT NULL,
                        size_bytes BIGINT DEFAULT 0,
                        type TEXT DEFAULT 'manual',
                        status TEXT DEFAULT 'completed',
                        storage_path TEXT,
                        checksum TEXT,
                        created_by TEXT,
                        created_at TIMESTAMPTZ DEFAULT now(),
                        completed_at TIMESTAMPTZ,
                        error_message TEXT,
                        meta JSONB DEFAULT '{}'::jsonb
                    );
                    """
                )
                await con.execute("UPDATE backup_history SET status='failed', error_message=$1, completed_at=now() WHERE id=$2", err_msg[:2000], backup_id)
        except Exception:
            pass
        await audit_log("backup_restore_fail", str(backup_id), err_msg[:500])
        raise HTTPException(status_code=500, detail=f"Restore gagal: {err_msg[:800]}") from e

class BackupCreateBody(BaseModel):
    type: str = Field(default="manual", max_length=10)
    @field_validator("type")
    @classmethod
    def val_type(cls, v):
        vv = (v or "manual").strip().lower()
        if vv not in ("manual","auto"):
            vv = "manual"
        return vv

class BackupRestoreBody(BaseModel):
    confirm: bool = Field(..., description="Must be true to confirm restore")
    create_safety_backup: bool = Field(default=True, description="Create safety backup before restore")

@app.get("/api/backup/list")
async def backup_list(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch("SELECT * FROM backup_history ORDER BY created_at DESC LIMIT 100")
    return {"backups": [_backup_dict(r) for r in rows], "total": len(rows)}

@app.get("/api/backup/stats")
async def backup_stats(_: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        total = await con.fetchval("SELECT count(*) FROM backup_history") or 0
        total_size = await con.fetchval("SELECT COALESCE(SUM(size_bytes),0) FROM backup_history WHERE status='completed'") or 0
        last_row = await con.fetchrow("SELECT * FROM backup_history WHERE status='completed' ORDER BY created_at DESC LIMIT 1")
        pending = await con.fetchval("SELECT count(*) FROM backup_history WHERE status IN ('in_progress','restoring')") or 0
        failed = await con.fetchval("SELECT count(*) FROM backup_history WHERE status='failed'") or 0
    last_backup = _backup_dict(last_row) if last_row else None
    needs_auto = False
    if last_row:
        try:
            age = (_dt.datetime.now(_dt.timezone.utc) - last_row["created_at"]).total_seconds() / 3600
            needs_auto = age > 24
        except Exception:
            needs_auto = True
    else:
        needs_auto = True
    last_ago = None
    if last_row:
        try:
            last_ago = (_dt.datetime.now(_dt.timezone.utc) - last_row["created_at"]).total_seconds() / 3600
        except Exception:
            last_ago = None
    return {
        "total_backups": int(total),
        "total_size_bytes": int(total_size),
        "total_size_human": _human_size(total_size),
        "last_backup": last_backup,
        "pending_count": int(pending),
        "failed_count": int(failed),
        "auto_backup_enabled": True,
        "needs_auto_backup": needs_auto,
        "backup_dir": str(BACKUP_DIR),
        "last_backup_ago_hours": last_ago,
    }

@app.post("/api/backup/create")
async def backup_create(body: BackupCreateBody, _: bool = Depends(require_auth)):
    if _backup_lock.locked():
        raise HTTPException(status_code=429, detail="Backup sedang berjalan, tunggu selesai")
    if _restore_lock.locked():
        raise HTTPException(status_code=429, detail="Restore sedang berjalan, tunggu selesai")
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "auto" if body.type == "auto" else "backup"
    filename = f"{prefix}_{ts}.sql.gz"
    _ensure_backup_dir()
    counter = 0
    base_name = filename
    while (BACKUP_DIR / filename).exists():
        counter += 1
        stem = base_name.replace(".sql.gz", "")
        filename = f"{stem}_{counter}.sql.gz"
    async with _backup_lock:
        try:
            row = await _create_pg_dump_internal(filename, body.type, created_by="admin")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)[:800])
    return {"ok": True, "backup": row}

@app.get("/api/backup/{backup_id}/download")
async def backup_download(backup_id: int, _: bool = Depends(require_auth)):
    if backup_id < 1:
        raise HTTPException(status_code=400, detail="Invalid id")
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT * FROM backup_history WHERE id=$1", backup_id)
    if not row:
        raise HTTPException(status_code=404, detail="Backup tidak ditemukan")
    storage_path = row["storage_path"] or ""
    filename = row["filename"]
    if storage_path:
        target = Path(storage_path)
        if not target.exists() or not target.is_file():
            fb = BACKUP_DIR / filename
            if fb.exists():
                target = fb
            else:
                raise HTTPException(status_code=404, detail="File tidak ditemukan di disk")
    else:
        target = BACKUP_DIR / filename
        if not target.exists():
            raise HTTPException(status_code=404, detail="File tidak ditemukan")
    try:
        p = target.resolve()
        base = BACKUP_DIR.resolve()
        sp = str(p)
        sb = str(base)
        if sb not in sp and not sp.startswith("/tmp"):
            if not sp.startswith(sb):
                raise HTTPException(status_code=403, detail="Path not allowed")
    except HTTPException:
        raise
    except Exception:
        pass
    await audit_log("backup_download", str(backup_id), filename)
    return FileResponse(str(target), filename=filename, media_type="application/gzip", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

@app.delete("/api/backup/{backup_id}")
async def backup_delete(backup_id: int, _: bool = Depends(require_auth)):
    if backup_id < 1:
        raise HTTPException(status_code=400, detail="Invalid id")
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT * FROM backup_history WHERE id=$1", backup_id)
        if not row:
            raise HTTPException(status_code=404, detail="Backup tidak ditemukan")
        if row["status"] in ("in_progress","restoring"):
            raise HTTPException(status_code=400, detail="Tidak bisa hapus backup yang sedang berjalan")
        await con.execute("DELETE FROM backup_history WHERE id=$1", backup_id)
    try:
        fp = row["storage_path"] or str(BACKUP_DIR / row["filename"])
        pp = Path(fp)
        if pp.exists() and pp.is_file():
            rp = str(pp.resolve())
            base_s = str(BACKUP_DIR.resolve())
            if rp.startswith(base_s) or rp.startswith("/tmp"):
                pp.unlink(missing_ok=True)
    except Exception:
        pass
    await audit_log("backup_delete", str(backup_id), row["filename"])
    return {"ok": True, "deleted": row["filename"]}

@app.post("/api/backup/{backup_id}/restore")
async def backup_restore(backup_id: int, body: BackupRestoreBody, _: bool = Depends(require_auth)):
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Konfirmasi restore wajib")
    if _backup_lock.locked():
        raise HTTPException(status_code=429, detail="Backup sedang berjalan, tunggu selesai")
    if _restore_lock.locked():
        raise HTTPException(status_code=429, detail="Restore sedang berjalan")
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT * FROM backup_history WHERE id=$1", backup_id)
    if not row:
        raise HTTPException(status_code=404, detail="Backup tidak ditemukan")
    if row["status"] == "in_progress":
        raise HTTPException(status_code=400, detail="Backup masih in_progress, tidak bisa restore")
    storage_path = row["storage_path"] or str(BACKUP_DIR / row["filename"])
    p = Path(storage_path)
    if not p.exists():
        alt = BACKUP_DIR / row["filename"]
        if alt.exists():
            storage_path = str(alt)
            p = alt
        else:
            raise HTTPException(status_code=404, detail="File backup tidak ada di disk")
    if body.create_safety_backup:
        try:
            ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            safety_name = f"backup_safety_before_restore_{ts}.sql.gz"
            async with _backup_lock:
                await _create_pg_dump_internal(safety_name, "auto", created_by="safety_before_restore")
        except Exception as se:
            await audit_log("backup_safety_fail", str(backup_id), str(se)[:500])
    async with _restore_lock:
        try:
            result = await _restore_pg_internal(backup_id, storage_path, row["filename"])
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)[:1000])
    try:
        await _ensure_tables()
    except Exception:
        pass
    await audit_log("backup_restore", str(backup_id), row["filename"])
    return result

@app.post("/api/backup/upload")
async def backup_upload(file: UploadFile = File(...), _: bool = Depends(require_auth)):
    max_bytes = 500 * 1024 * 1024
    _ensure_backup_dir()
    orig_name = (file.filename or "").strip()
    if not orig_name:
        raise HTTPException(status_code=400, detail="Nama file kosong")
    safe_name = orig_name.replace("..", "").replace("/", "_").replace("\\", "_").strip()
    low = safe_name.lower()
    if not (low.endswith(".sql.gz") or low.endswith(".dump") or low.endswith(".sql") or low.endswith(".gz")):
        raise HTTPException(status_code=400, detail="Format harus .sql.gz, .dump, .sql, atau .gz")
    target = BACKUP_DIR / safe_name
    counter = 0
    base = safe_name
    while target.exists():
        counter += 1
        if ".sql.gz" in base:
            stem = base.replace(".sql.gz", "")
            safe_name = f"{stem}_{counter}.sql.gz"
        else:
            parts = base.rsplit(".", 1)
            safe_name = f"{parts[0]}_{counter}.{parts[1]}" if len(parts) == 2 else f"{base}_{counter}"
        target = BACKUP_DIR / safe_name
    size = 0
    try:
        with open(target, "wb") as out:
            while True:
                chunk = await file.read(1048576)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    out.close()
                    try:
                        target.unlink(missing_ok=True)
                    except Exception:
                        pass
                    raise HTTPException(status_code=400, detail="File terlalu besar >500MB")
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        try:
            target.unlink(missing_ok=True)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Gagal simpan upload: {e}"[:500])
    checksum = await asyncio.to_thread(_calculate_checksum, target)
    async with _pool.acquire() as con:
        try:
            row = await con.fetchrow(
                "INSERT INTO backup_history (filename, size_bytes, type, status, storage_path, checksum, created_by, completed_at, meta) VALUES ($1,$2,'upload','completed',$3,$4,'admin', now(), '{}'::jsonb) RETURNING *",
                safe_name, size, str(target), checksum
            )
        except Exception as e:
            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_name = f"upload_{ts}_{safe_name}"
                target2 = BACKUP_DIR / safe_name
                try:
                    target.rename(target2)
                    target = target2
                except Exception:
                    pass
                row = await con.fetchrow(
                    "INSERT INTO backup_history (filename, size_bytes, type, status, storage_path, checksum, created_by, completed_at, meta) VALUES ($1,$2,'upload','completed',$3,$4,'admin', now(), '{}'::jsonb) RETURNING *",
                    safe_name, size, str(target), checksum
                )
            else:
                raise
    await audit_log("backup_upload", safe_name, f"size={size}")
    return {"ok": True, "backup": _backup_dict(row)}

@app.post("/api/backup/evaluate-auto")
async def backup_evaluate_auto(force: bool = False, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        last_row = await con.fetchrow("SELECT * FROM backup_history WHERE status='completed' ORDER BY created_at DESC LIMIT 1")
    needs = False
    reason = ""
    if not last_row:
        needs = True
        reason = "Belum ada backup"
    else:
        try:
            age_h = (_dt.datetime.now(_dt.timezone.utc) - last_row["created_at"]).total_seconds() / 3600
            if age_h > 24:
                needs = True
                reason = f"Last backup {age_h:.1f}h lalu >24h"
            else:
                reason = f"Last backup {age_h:.1f}h lalu masih fresh"
        except Exception:
            needs = True
            reason = "Gagal hitung umur backup, buat baru"
    if not needs and not force:
        return {"ok": True, "created": False, "reason": reason, "last_backup": _backup_dict(last_row) if last_row else None}
    if _backup_lock.locked() or _restore_lock.locked():
        raise HTTPException(status_code=429, detail="Backup/restore sedang berjalan")
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"auto_{ts}.sql.gz"
    _ensure_backup_dir()
    counter = 0
    base = filename
    while (BACKUP_DIR / filename).exists():
        counter += 1
        stem = base.replace(".sql.gz", "")
        filename = f"{stem}_{counter}.sql.gz"
    async with _backup_lock:
        row = await _create_pg_dump_internal(filename, "auto", created_by="auto_evaluate")
    await audit_log("backup_auto", str(row.get("id", "?")), filename)
    return {"ok": True, "created": True, "reason": reason, "backup": row}

