"""JSON API for the admin dashboard (FastAPI). Consumed by the Next.js frontend."""
import os
import secrets
import asyncpg
import httpx
from fastapi import FastAPI, Request, Response, HTTPException, Depends
from pydantic import BaseModel

DATABASE_URL = os.environ["DATABASE_URL"]
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ["ADMIN_PASS"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
DEFAULT_DAILY_LIMIT = int(os.environ.get("DEFAULT_DAILY_LIMIT", "20"))
REQUIRED_CHANNEL = os.environ.get("REQUIRED_CHANNEL", "")
SESSION_SECRET = os.environ.get("DASH_SECRET", secrets.token_hex(16))

app = FastAPI(title="ImageBot Admin API")
_pool: asyncpg.Pool | None = None

# simple in-memory token store (single admin). token -> True
_tokens: set[str] = set()


@app.on_event("startup")
async def startup():
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)


@app.on_event("shutdown")
async def shutdown():
    if _pool:
        await _pool.close()


def require_auth(request: Request):
    token = request.cookies.get("session")
    if not token or token not in _tokens:
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
    _tokens.add(token)
    response.set_cookie("session", token, httponly=True, samesite="lax", max_age=86400*7)
    return {"ok": True}


@app.post("/api/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session")
    _tokens.discard(token)
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
                "SELECT u.user_id,u.username,u.first_name,u.is_banned,u.created_at,"
                "count(g.id) AS gen_count FROM users u LEFT JOIN generations g ON g.user_id=u.user_id "
                "WHERE u.username ILIKE $1 OR u.first_name ILIKE $1 OR CAST(u.user_id AS TEXT) LIKE $1 "
                "GROUP BY u.user_id ORDER BY gen_count DESC LIMIT 200", like)
        else:
            rows = await con.fetch(
                "SELECT u.user_id,u.username,u.first_name,u.is_banned,u.created_at,"
                "count(g.id) AS gen_count FROM users u LEFT JOIN generations g ON g.user_id=u.user_id "
                "GROUP BY u.user_id ORDER BY gen_count DESC LIMIT 200")
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


@app.post("/api/broadcast")
async def broadcast(body: BroadcastBody, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        rows = await con.fetch("SELECT user_id FROM users WHERE NOT is_banned")
    sent = 0
    async with httpx.AsyncClient(timeout=30) as client:
        for r in rows:
            try:
                resp = await client.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": r["user_id"], "text": body.message, "parse_mode": "HTML"})
                if resp.status_code == 200:
                    sent += 1
            except Exception:
                pass
    return {"ok": True, "sent": sent, "total": len(rows)}


# ---------------- Settings ----------------
@app.get("/api/settings")
async def get_settings(_: bool = Depends(require_auth)):
    limit = await get_setting("daily_limit", str(DEFAULT_DAILY_LIMIT))
    maint = await get_setting("maintenance", "0")
    return {"daily_limit": int(limit), "maintenance": maint == "1",
            "channel": REQUIRED_CHANNEL, "model": "gpt-image-2"}


class SettingsBody(BaseModel):
    daily_limit: int
    maintenance: bool


@app.post("/api/settings")
async def save_settings(body: SettingsBody, _: bool = Depends(require_auth)):
    await set_setting("daily_limit", max(0, body.daily_limit))
    await set_setting("maintenance", "1" if body.maintenance else "0")
    return {"ok": True}
