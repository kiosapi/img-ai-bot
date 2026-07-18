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
            """
        )
        # migration for existing DBs (pre-pref_size)
        await con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS pref_size TEXT;")


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
