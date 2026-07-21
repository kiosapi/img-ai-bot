"""Public user API routes for imgaai web-app (Telegram Login)."""
from __future__ import annotations

import hashlib
import re
import hmac
import os
import secrets
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/user", tags=["user"])

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DEFAULT_DAILY_LIMIT = int(os.environ.get("DEFAULT_DAILY_LIMIT", "20"))
_login_attempts: dict[str, list[float]] = {}


def bind_pool(pool):
    """Called from main.lifespan after pool create."""
    global _pool
    _pool = pool


_pool = None


async def ensure_web_jobs_table(pool) -> None:
    async with pool.acquire() as con:
        await con.execute(
            """
            CREATE TABLE IF NOT EXISTS web_gen_jobs (
                id TEXT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                prompt TEXT NOT NULL,
                size TEXT NOT NULL DEFAULT '1024x1024',
                style_code TEXT,
                status TEXT NOT NULL DEFAULT 'queued',
                position INT DEFAULT 0,
                eta_sec INT DEFAULT 0,
                error TEXT,
                result_b64 TEXT,
                gen_id BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                started_at TIMESTAMPTZ,
                finished_at TIMESTAMPTZ
            )
            """
        )


async def ensure_user_tables(pool) -> None:
    async with pool.acquire() as con:
        await con.execute(
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
                token TEXT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + interval '30 days',
                user_agent TEXT,
                ip TEXT
            )
            """
        )
        await con.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id)"
        )
        await con.execute(
            "DELETE FROM user_sessions WHERE expires_at < now()"
        )
        await con.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS gallery_public BOOLEAN NOT NULL DEFAULT false"
        )
        await ensure_web_jobs_table(pool)


def _verify_telegram_login(data: dict[str, Any]) -> bool:
    """Telegram Login Widget HMAC check.
    https://core.telegram.org/widgets/login#checking-authorization
    """
    recv_hash = data.get("hash")
    if not recv_hash or not BOT_TOKEN:
        return False
    pairs = []
    for k, v in data.items():
        if k == "hash" or v is None or v == "":
            continue
        pairs.append(f"{k}={v}")
    pairs.sort()
    check_string = "\n".join(pairs)
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    calc = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calc, str(recv_hash))


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "global"


async def require_user(request: Request) -> int:
    """Cookie user_session OR Authorization: Bearer <token>."""
    token = request.cookies.get("user_session")
    if not token:
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="unauthorized")
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "SELECT user_id FROM user_sessions WHERE token=$1 AND expires_at > now()",
            token,
        )
        if not row:
            raise HTTPException(status_code=401, detail="unauthorized")
        banned = await con.fetchval(
            "SELECT is_banned FROM users WHERE user_id=$1", row["user_id"]
        )
        if banned:
            raise HTTPException(status_code=403, detail="banned")
        return int(row["user_id"])


class TelegramAuthBody(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str = Field(..., min_length=32, max_length=128)


class MePatchBody(BaseModel):
    lang: str | None = Field(None, pattern="^(id|en)$")
    gallery_public: bool | None = None


def _set_user_cookie(response: Response, token: str) -> None:
    # Cross-site Pages→API needs Secure+None when HTTPS; local dev Lax+non-secure.
    secure = os.environ.get("USER_COOKIE_SECURE", "0") == "1"
    samesite = "none" if secure else "lax"
    response.set_cookie(
        "user_session",
        token,
        httponly=True,
        samesite=samesite,
        secure=secure,
        max_age=86400 * 30,
        path="/",
    )


@router.post("/auth/telegram")
async def auth_telegram(body: TelegramAuthBody, request: Request, response: Response):
    ip = _client_ip(request)
    now = time.time()
    attempts = [t for t in _login_attempts.get(ip, []) if now - t < 60]
    if len(attempts) >= 20:
        raise HTTPException(status_code=429, detail="Too many attempts, wait 1 minute")

    payload = body.model_dump()
    if abs(now - int(body.auth_date)) > 86400:
        attempts.append(now)
        _login_attempts[ip] = attempts
        raise HTTPException(status_code=401, detail="auth_date expired")

    if not _verify_telegram_login(payload):
        attempts.append(now)
        _login_attempts[ip] = attempts
        raise HTTPException(status_code=401, detail="invalid telegram signature")

    _login_attempts[ip] = []
    user_id = int(body.id)
    lang = "id"  # seed; user can change in settings
    async with _pool.acquire() as con:
        await con.execute(
            """
            INSERT INTO users (user_id, username, first_name, lang)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE
              SET username = EXCLUDED.username,
                  first_name = EXCLUDED.first_name,
                  last_seen = now(),
                  lang = COALESCE(users.lang, EXCLUDED.lang)
            """,
            user_id,
            body.username,
            body.first_name,
            lang,
        )
        banned = await con.fetchval(
            "SELECT is_banned FROM users WHERE user_id=$1", user_id
        )
        if banned:
            raise HTTPException(status_code=403, detail="banned")

        token = secrets.token_urlsafe(32)
        ua = (request.headers.get("user-agent") or "")[:300]
        await con.execute(
            """
            INSERT INTO user_sessions (token, user_id, expires_at, user_agent, ip)
            VALUES ($1, $2, now() + interval '30 days', $3, $4)
            """,
            token,
            user_id,
            ua,
            ip[:64],
        )

    _set_user_cookie(response, token)
    return {"ok": True, "token": token, "user_id": user_id}


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("user_session")
    if not token:
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if token:
        async with _pool.acquire() as con:
            await con.execute("DELETE FROM user_sessions WHERE token=$1", token)
    response.delete_cookie("user_session", path="/")
    return {"ok": True}


@router.get("/me")
async def me(user_id: Annotated[int, Depends(require_user)]):
    async with _pool.acquire() as con:
        u = await con.fetchrow(
            """
            SELECT user_id, username, first_name, balance, lang, is_banned,
                   gallery_public, premium_until, plan_name, pref_size,
                   created_at, last_seen
            FROM users WHERE user_id=$1
            """,
            user_id,
        )
        if not u:
            raise HTTPException(status_code=404, detail="user not found")

        daily_limit_raw = await con.fetchval(
            "SELECT value FROM settings WHERE key='daily_limit'"
        )
        free_limit = int(daily_limit_raw) if daily_limit_raw and str(daily_limit_raw).isdigit() else DEFAULT_DAILY_LIMIT

        prem = None
        if u["premium_until"] and u["premium_until"].timestamp() > time.time():
            plan_limit = None
            if u["plan_name"]:
                pl = await con.fetchval(
                    "SELECT daily_limit FROM plans WHERE name=$1 LIMIT 1", u["plan_name"]
                )
                plan_limit = pl
            # prefer plan_id path if exists
            plan_id = await con.fetchval(
                "SELECT plan_id FROM users WHERE user_id=$1", user_id
            )
            if plan_id:
                pl2 = await con.fetchval(
                    "SELECT daily_limit FROM plans WHERE id=$1", plan_id
                )
                if pl2 is not None:
                    plan_limit = pl2
            prem = {
                "plan_name": u["plan_name"],
                "premium_until": u["premium_until"].isoformat(),
                "daily_limit": plan_limit,
            }
            limit = plan_limit if plan_limit is not None else free_limit
        else:
            limit = free_limit

        used = await con.fetchval(
            """
            SELECT count FROM usage_daily
            WHERE user_id=$1 AND day=CURRENT_DATE
            """,
            user_id,
        )
        used = int(used or 0)

        crow = await con.fetchrow(
            "SELECT streak, last_checkin, total_checkin FROM users WHERE user_id=$1",
            user_id,
        )
        checkin = {
            "streak": int(crow["streak"] or 0) if crow else 0,
            "last_checkin": crow["last_checkin"].isoformat() if crow and crow["last_checkin"] else None,
            "total_checkin": int(crow["total_checkin"] or 0) if crow else 0,
        }

    return {
        "user_id": u["user_id"],
        "username": u["username"],
        "first_name": u["first_name"],
        "balance": int(u["balance"] or 0),
        "lang": u["lang"] or "id",
        "gallery_public": bool(u["gallery_public"]),
        "pref_size": u["pref_size"],
        "premium": prem,
        "quota": {"used": used, "limit": int(limit) if limit is not None else free_limit},
        "checkin": checkin,
    }


@router.patch("/me")
async def patch_me(
    body: MePatchBody, user_id: Annotated[int, Depends(require_user)]
):
    if body.lang is None and body.gallery_public is None:
        raise HTTPException(status_code=400, detail="nothing to update")
    async with _pool.acquire() as con:
        if body.lang is not None:
            await con.execute(
                "UPDATE users SET lang=$2 WHERE user_id=$1", user_id, body.lang
            )
        if body.gallery_public is not None:
            await con.execute(
                "UPDATE users SET gallery_public=$2 WHERE user_id=$1",
                user_id,
                body.gallery_public,
            )
    return {"ok": True}


@router.get("/styles")
async def list_styles(user_id: Annotated[int, Depends(require_user)]):
    async with _pool.acquire() as con:
        rows = await con.fetch(
            """
            SELECT code, name, prompt_prefix, thumbnail_url, category, sort_order
            FROM custom_styles
            WHERE is_active = true
            ORDER BY sort_order ASC, id ASC
            """
        )
    return {
        "styles": [
            {
                "code": r["code"],
                "name": r["name"],
                "prompt_prefix": r["prompt_prefix"],
                "thumbnail_url": r["thumbnail_url"],
                "category": r["category"],
            }
            for r in rows
        ]
    }


@router.get("/history")
async def history(
    user_id: Annotated[int, Depends(require_user)],
    limit: int = 20,
    offset: int = 0,
):
    limit = max(1, min(limit, 50))
    offset = max(0, offset)
    async with _pool.acquire() as con:
        rows = await con.fetch(
            """
            SELECT id, prompt, kind, success, size, created_at,
                   result_file_id, ref_file_id
            FROM generations
            WHERE user_id=$1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id,
            limit,
            offset,
        )
        total = await con.fetchval(
            "SELECT count(*) FROM generations WHERE user_id=$1", user_id
        )
    return {
        "total": int(total or 0),
        "items": [
            {
                "id": r["id"],
                "prompt": (r["prompt"] or "")[:500],
                "kind": r["kind"],
                "success": bool(r["success"]),
                "size": r["size"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "has_result": bool(r["result_file_id"]),
            }
            for r in rows
        ],
    }


@router.get("/checkin")
async def checkin_status(user_id: Annotated[int, Depends(require_user)]):
    """Read-only check-in status."""
    import datetime as _dt

    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "SELECT last_checkin, streak, total_checkin FROM users WHERE user_id=$1",
            user_id,
        )
    if not row:
        return {"streak": 0, "last_checkin": None, "total_checkin": 0, "claimable": True}
    today = _dt.date.today()
    last = row["last_checkin"]
    claimable = last != today
    return {
        "streak": int(row["streak"] or 0),
        "last_checkin": last.isoformat() if last else None,
        "total_checkin": int(row["total_checkin"] or 0),
        "claimable": claimable,
    }


@router.get("/health")
async def user_health():
    return {"ok": True, "scope": "user"}



# ---- Web generate jobs (processed by bot web_jobs worker) ----
ALLOWED_SIZES = {
    "1024x1024", "1024x1792", "1792x1024", "1024x1536",
    "1536x1024", "1152x1536", "1536x1152",
}



class GenerateBody(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    size: str = Field(default="1024x1024", max_length=20)
    style_code: str | None = Field(default=None, max_length=30)


@router.post("/generate")
async def create_generate(body: GenerateBody, user_id: Annotated[int, Depends(require_user)]):
    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt required")
    size = body.size if body.size in ALLOWED_SIZES else "1024x1024"
    style = (body.style_code or "").strip() or None
    if style and not re.match(r"^[a-z0-9_-]{1,30}$", style):
        raise HTTPException(status_code=400, detail="invalid style_code")

    async with _pool.acquire() as con:
        maint = await con.fetchval("SELECT value FROM settings WHERE key='maintenance'")
        if maint == "1":
            raise HTTPException(status_code=503, detail="maintenance")
        # one active job per user
        active = await con.fetchval(
            """
            SELECT id FROM web_gen_jobs
            WHERE user_id=$1 AND status IN ('queued','running')
            LIMIT 1
            """,
            user_id,
        )
        if active:
            raise HTTPException(status_code=409, detail=f"job_already_running:{active}")
        job_id = secrets.token_urlsafe(16)
        await con.execute(
            """
            INSERT INTO web_gen_jobs (id, user_id, prompt, size, style_code, status)
            VALUES ($1,$2,$3,$4,$5,'queued')
            """,
            job_id,
            user_id,
            prompt,
            size,
            style,
        )
        waiting = await con.fetchval(
            "SELECT count(*) FROM web_gen_jobs WHERE status IN ('queued','running')"
        ) or 1
    return {
        "ok": True,
        "job_id": job_id,
        "status": "queued",
        "position": max(1, int(waiting)),
        "eta_sec": max(15, int(waiting) * 40),
    }


@router.get("/generate/{job_id}")
async def get_generate(job_id: str, user_id: Annotated[int, Depends(require_user)]):
    if len(job_id) > 64 or not re.match(r"^[A-Za-z0-9_-]+$", job_id):
        raise HTTPException(status_code=400, detail="invalid job_id")
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            """
            SELECT id, user_id, status, position, eta_sec, error, result_b64, gen_id,
                   prompt, size, created_at, finished_at
            FROM web_gen_jobs WHERE id=$1
            """,
            job_id,
        )
    if not row or int(row["user_id"]) != user_id:
        raise HTTPException(status_code=404, detail="not found")
    out = {
        "job_id": row["id"],
        "status": row["status"],
        "position": row["position"],
        "eta_sec": row["eta_sec"],
        "error": row["error"],
        "gen_id": row["gen_id"],
        "size": row["size"],
        "prompt": (row["prompt"] or "")[:200],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "finished_at": row["finished_at"].isoformat() if row["finished_at"] else None,
        "has_image": bool(row["result_b64"]),
    }
    if row["status"] == "done" and row["result_b64"]:
        out["image_base64"] = row["result_b64"]
        out["image_data_url"] = f"data:image/png;base64,{row['result_b64']}"
    return out


@router.delete("/generate/{job_id}/image")
async def clear_generate_image(job_id: str, user_id: Annotated[int, Depends(require_user)]):
    """Drop base64 after client downloaded — save DB size."""
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "SELECT user_id, status FROM web_gen_jobs WHERE id=$1", job_id
        )
        if not row or int(row["user_id"]) != user_id:
            raise HTTPException(status_code=404, detail="not found")
        await con.execute(
            "UPDATE web_gen_jobs SET result_b64=NULL WHERE id=$1", job_id
        )
    return {"ok": True}
