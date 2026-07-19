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
    audience: str = "all"  # all | premium | free


def _audience_where(audience: str) -> str:
    if audience == "premium":
        return "WHERE NOT is_banned AND premium_until > now()"
    if audience == "free":
        return "WHERE NOT is_banned AND (premium_until IS NULL OR premium_until <= now())"
    return "WHERE NOT is_banned"


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
            "SELECT id, message, audience, sent, total, created_at FROM broadcast_history "
            "ORDER BY id DESC LIMIT 20")
    return {"history": [dict(r) for r in rows]}


@app.post("/api/broadcast")
async def broadcast(body: BroadcastBody, _: bool = Depends(require_auth)):
    audience = body.audience if body.audience in ("all", "premium", "free") else "all"
    async with _pool.acquire() as con:
        rows = await con.fetch("SELECT user_id FROM users " + _audience_where(audience))
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
    async with _pool.acquire() as con:
        await con.execute(
            "INSERT INTO broadcast_history (message, audience, sent, total) VALUES ($1,$2,$3,$4)",
            body.message, audience, sent, len(rows))
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

# ---------------- User detail ----------------
@app.get("/api/users/{uid}")
async def user_detail(uid: int, _: bool = Depends(require_auth)):
    async with _pool.acquire() as con:
        u = await con.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)
        if not u:
            raise HTTPException(status_code=404, detail="User tidak ditemukan")
        total = await con.fetchval("SELECT count(*) FROM generations WHERE user_id=$1", uid) or 0
        ok = await con.fetchval("SELECT count(*) FROM generations WHERE user_id=$1 AND success", uid) or 0
        today = await con.fetchval(
            "SELECT count(*) FROM generations WHERE user_id=$1 AND created_at::date=CURRENT_DATE", uid) or 0
        gens = await con.fetch(
            "SELECT kind,prompt,size,success,created_at FROM generations "
            "WHERE user_id=$1 ORDER BY id DESC LIMIT 50", uid)
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
