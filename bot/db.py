"""Async Postgres layer using asyncpg. Handles users, usage counters, and settings."""
import asyncpg
from datetime import date

_pool: asyncpg.Pool | None = None


async def init_pool(dsn: str):
    global _pool
    _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=10)
    await _create_schema()


async def close_pool():
    if _pool:
        await _pool.close()


async def _create_schema():
    async with _pool.acquire() as con:
        await con.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id     BIGINT PRIMARY KEY,
                username    TEXT,
                first_name  TEXT,
                is_banned   BOOLEAN NOT NULL DEFAULT FALSE,
                pref_size   TEXT,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                last_seen   TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS usage_daily (
                user_id  BIGINT NOT NULL,
                day      DATE   NOT NULL,
                count    INT    NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, day)
            );

            CREATE TABLE IF NOT EXISTS generations (
                id         BIGSERIAL PRIMARY KEY,
                user_id    BIGINT NOT NULL,
                kind       TEXT   NOT NULL,          -- 'generate' | 'edit'
                prompt     TEXT,
                size       TEXT,
                success    BOOLEAN NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS plans (
                id           SERIAL PRIMARY KEY,
                name         TEXT    NOT NULL,
                daily_limit  INT     NOT NULL DEFAULT 100,   -- 0 = unlimited
                price        BIGINT  NOT NULL DEFAULT 0,      -- in IDR
                duration_days INT    NOT NULL DEFAULT 30,
                description  TEXT,
                is_active    BOOLEAN NOT NULL DEFAULT TRUE,
                sort_order   INT     NOT NULL DEFAULT 0,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS payment_methods (
                id           SERIAL PRIMARY KEY,
                type         TEXT    NOT NULL,          -- 'bank' | 'ewallet' | 'qris' | 'other'
                name         TEXT    NOT NULL,          -- e.g. 'BCA', 'DANA', 'QRIS'
                account_name TEXT,                       -- holder name
                account_number TEXT,                     -- number / phone / id
                instructions TEXT,                       -- extra notes
                qr_image     TEXT,                        -- Telegram file_id for QRIS image
                is_active    BOOLEAN NOT NULL DEFAULT TRUE,
                sort_order   INT     NOT NULL DEFAULT 0,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS orders (
                id            BIGSERIAL PRIMARY KEY,
                user_id       BIGINT NOT NULL,
                plan_id       INT,
                method_id     INT,
                plan_name     TEXT,      -- snapshot at order time
                method_name   TEXT,      -- snapshot
                amount        BIGINT NOT NULL DEFAULT 0,
                daily_limit   INT    NOT NULL DEFAULT 0,   -- snapshot of plan limit
                duration_days INT    NOT NULL DEFAULT 30,  -- snapshot
                proof_file_id TEXT,                          -- Telegram photo file_id
                status        TEXT   NOT NULL DEFAULT 'pending', -- pending|approved|rejected
                note          TEXT,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                decided_at    TIMESTAMPTZ
            );
            """
        )
        # migrations for existing DBs
        await con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS pref_size TEXT;")
        await con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS premium_until TIMESTAMPTZ;")
        await con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_id INT;")
        await con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_name TEXT;")


# ---------- users ----------
async def upsert_user(user_id: int, username: str | None, first_name: str | None):
    async with _pool.acquire() as con:
        await con.execute(
            """
            INSERT INTO users (user_id, username, first_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO UPDATE
              SET username = EXCLUDED.username,
                  first_name = EXCLUDED.first_name,
                  last_seen = now();
            """,
            user_id, username, first_name,
        )


async def is_banned(user_id: int) -> bool:
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT is_banned FROM users WHERE user_id=$1", user_id)
        return bool(row and row["is_banned"])


async def set_banned(user_id: int, banned: bool):
    async with _pool.acquire() as con:
        await con.execute("UPDATE users SET is_banned=$2 WHERE user_id=$1", user_id, banned)


async def get_pref_size(user_id: int, default: str) -> str:
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT pref_size FROM users WHERE user_id=$1", user_id)
        return row["pref_size"] if row and row["pref_size"] else default


async def set_pref_size(user_id: int, size: str):
    async with _pool.acquire() as con:
        await con.execute("UPDATE users SET pref_size=$2 WHERE user_id=$1", user_id, size)


# ---------- usage / limits ----------
async def get_today_count(user_id: int) -> int:
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "SELECT count FROM usage_daily WHERE user_id=$1 AND day=$2",
            user_id, date.today(),
        )
        return row["count"] if row else 0


async def increment_usage(user_id: int) -> int:
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            """
            INSERT INTO usage_daily (user_id, day, count)
            VALUES ($1, $2, 1)
            ON CONFLICT (user_id, day) DO UPDATE SET count = usage_daily.count + 1
            RETURNING count;
            """,
            user_id, date.today(),
        )
        return row["count"]


async def log_generation(user_id, kind, prompt, size, success):
    async with _pool.acquire() as con:
        await con.execute(
            "INSERT INTO generations (user_id, kind, prompt, size, success) VALUES ($1,$2,$3,$4,$5)",
            user_id, kind, prompt, size, success,
        )


# ---------- settings ----------
async def get_setting(key: str, default: str | None = None) -> str | None:
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT value FROM settings WHERE key=$1", key)
        return row["value"] if row else default


async def set_setting(key: str, value: str):
    async with _pool.acquire() as con:
        await con.execute(
            """
            INSERT INTO settings (key, value) VALUES ($1, $2)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
            """,
            key, value,
        )


async def get_daily_limit(fallback: int) -> int:
    val = await get_setting("daily_limit")
    try:
        return int(val) if val is not None else fallback
    except ValueError:
        return fallback


# ---------- premium / plans / payments ----------
async def is_premium(user_id: int) -> bool:
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "SELECT premium_until FROM users WHERE user_id=$1", user_id)
        return bool(row and row["premium_until"] and row["premium_until"] > _now())


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


async def get_premium_info(user_id: int) -> dict | None:
    """Returns {plan_name, premium_until, daily_limit} if active premium, else None."""
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "SELECT premium_until, plan_name, plan_id FROM users WHERE user_id=$1", user_id)
        if not (row and row["premium_until"] and row["premium_until"] > _now()):
            return None
        limit = None
        if row["plan_id"]:
            p = await con.fetchrow("SELECT daily_limit FROM plans WHERE id=$1", row["plan_id"])
            limit = p["daily_limit"] if p else None
        return {"plan_name": row["plan_name"], "premium_until": row["premium_until"], "daily_limit": limit}


async def effective_daily_limit(user_id: int, free_fallback: int) -> int:
    """Premium users get their plan's limit; else the global free limit. 0 = unlimited."""
    info = await get_premium_info(user_id)
    if info and info["daily_limit"] is not None:
        return info["daily_limit"]
    return await get_daily_limit(free_fallback)


async def activate_premium(user_id: int, plan_id: int, plan_name: str, duration_days: int):
    from datetime import timedelta
    async with _pool.acquire() as con:
        # Extend from current expiry if still active, else from now.
        row = await con.fetchrow("SELECT premium_until FROM users WHERE user_id=$1", user_id)
        base = _now()
        if row and row["premium_until"] and row["premium_until"] > base:
            base = row["premium_until"]
        new_until = base + timedelta(days=duration_days)
        await con.execute(
            "UPDATE users SET premium_until=$2, plan_id=$3, plan_name=$4 WHERE user_id=$1",
            user_id, new_until, plan_id, plan_name)
        return new_until


# ---- plans (read) ----
async def get_active_plans() -> list[dict]:
    async with _pool.acquire() as con:
        rows = await con.fetch(
            "SELECT * FROM plans WHERE is_active ORDER BY sort_order, price")
        return [dict(r) for r in rows]


async def get_plan(plan_id: int) -> dict | None:
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT * FROM plans WHERE id=$1", plan_id)
        return dict(row) if row else None


# ---- payment methods (read) ----
async def get_active_methods() -> list[dict]:
    async with _pool.acquire() as con:
        rows = await con.fetch(
            "SELECT * FROM payment_methods WHERE is_active ORDER BY sort_order, id")
        return [dict(r) for r in rows]


async def get_method(method_id: int) -> dict | None:
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT * FROM payment_methods WHERE id=$1", method_id)
        return dict(row) if row else None


# ---- orders ----
async def create_order(user_id, plan: dict, method: dict) -> int:
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "INSERT INTO orders (user_id, plan_id, method_id, plan_name, method_name, amount, "
            "daily_limit, duration_days) VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id",
            user_id, plan["id"], method["id"], plan["name"], method["name"],
            plan["price"], plan["daily_limit"], plan["duration_days"])
        return row["id"]


async def attach_proof(order_id: int, file_id: str):
    async with _pool.acquire() as con:
        await con.execute("UPDATE orders SET proof_file_id=$2 WHERE id=$1", order_id, file_id)


async def cancel_order(order_id: int):
    async with _pool.acquire() as con:
        await con.execute(
            "UPDATE orders SET status='rejected', note='dibatalkan user', decided_at=now() "
            "WHERE id=$1 AND status='pending'", order_id)


async def get_pending_order(user_id: int) -> dict | None:
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "SELECT * FROM orders WHERE user_id=$1 AND status='pending' ORDER BY id DESC LIMIT 1",
            user_id)
        return dict(row) if row else None


async def seed_default_plan():
    """Ensure at least one plan exists so admin has a starting point."""
    async with _pool.acquire() as con:
        n = await con.fetchval("SELECT count(*) FROM plans")
        if n == 0:
            await con.execute(
                "INSERT INTO plans (name, daily_limit, price, duration_days, description, sort_order) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "Premium", 100, 20000, 30, "Kuota 100 gambar/hari selama 30 hari", 1)
