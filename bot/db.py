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

            CREATE TABLE IF NOT EXISTS broadcast_history (
                id         BIGSERIAL PRIMARY KEY,
                message    TEXT   NOT NULL,
                audience   TEXT   NOT NULL DEFAULT 'all',   -- all|premium|free
                sent       INT    NOT NULL DEFAULT 0,
                total      INT    NOT NULL DEFAULT 0,
                image_file_id TEXT,                          -- optional Telegram photo file_id
                button_text   TEXT,                           -- optional inline button label
                button_url    TEXT,                           -- optional inline button URL
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS deposits (
                id            BIGSERIAL PRIMARY KEY,
                user_id       BIGINT NOT NULL,
                method_id     INT,
                method_name   TEXT,                          -- snapshot
                amount        BIGINT NOT NULL DEFAULT 0,
                proof_file_id TEXT,
                status        TEXT   NOT NULL DEFAULT 'pending', -- pending|approved|rejected
                note          TEXT,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                decided_at    TIMESTAMPTZ
            );

            CREATE TABLE IF NOT EXISTS balance_logs (
                id            BIGSERIAL PRIMARY KEY,
                user_id       BIGINT NOT NULL,
                delta         BIGINT NOT NULL,               -- +topup / -purchase
                balance_after BIGINT NOT NULL,
                reason        TEXT,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS referrals (
                id            BIGSERIAL PRIMARY KEY,
                referrer_id   BIGINT NOT NULL,
                referred_id   BIGINT NOT NULL UNIQUE,        -- a user can only be referred once
                reward_type   TEXT   NOT NULL DEFAULT 'balance', -- 'balance' | 'quota' (snapshot at signup time)
                reward_amount BIGINT NOT NULL DEFAULT 0,         -- snapshot at signup time
                status        TEXT   NOT NULL DEFAULT 'pending', -- pending|rewarded
                created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                rewarded_at   TIMESTAMPTZ
            );
            """
        )
        # migrations for existing DBs
        await con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS pref_size TEXT;")
        await con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS premium_until TIMESTAMPTZ;")
        await con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_id INT;")
        await con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_name TEXT;")
        await con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS balance BIGINT NOT NULL DEFAULT 0;")
        await con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS lang TEXT;")
        await con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by BIGINT;")
        await con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS bonus_quota INT NOT NULL DEFAULT 0;")
        await con.execute("ALTER TABLE broadcast_history ADD COLUMN IF NOT EXISTS image_file_id TEXT;")
        await con.execute("ALTER TABLE broadcast_history ADD COLUMN IF NOT EXISTS button_text TEXT;")
        await con.execute("ALTER TABLE broadcast_history ADD COLUMN IF NOT EXISTS button_url TEXT;")
        await con.execute("ALTER TABLE generations ADD COLUMN IF NOT EXISTS result_file_id TEXT;")
        await con.execute("ALTER TABLE generations ADD COLUMN IF NOT EXISTS style_id TEXT;")
        await con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS pref_style TEXT;")
        # daily check-in + streak
        await con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_checkin DATE;")
        await con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS streak INT NOT NULL DEFAULT 0;")
        await con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS total_checkin INT NOT NULL DEFAULT 0;")
        # aiogram FSM PG persistent storage
        await con.execute("""
            CREATE TABLE IF NOT EXISTS aiogram_states (
                chat_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                state TEXT,
                data JSONB NOT NULL DEFAULT '{}'::jsonb,
                updated TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (chat_id, user_id)
            );
        """)
        await con.execute("ALTER TABLE aiogram_states ADD COLUMN IF NOT EXISTS state TEXT;")
        await con.execute("ALTER TABLE aiogram_states ADD COLUMN IF NOT EXISTS data JSONB NOT NULL DEFAULT '{}'::jsonb;")
        await con.execute("ALTER TABLE aiogram_states ADD COLUMN IF NOT EXISTS updated TIMESTAMPTZ NOT NULL DEFAULT now();")
        # ---- feature 17 sticker packs ----
        await con.execute(
            """
            CREATE TABLE IF NOT EXISTS sticker_packs (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                pack_name TEXT NOT NULL UNIQUE,
                title TEXT,
                created_at TIMESTAMPTZ DEFAULT now(),
                sticker_count INT DEFAULT 0
            );
            """
        )
        await con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_sticker_pack TEXT;")
        # ---- multi-provider system (Cubence + Right Codes) ----
        await con.execute(
            """
            CREATE TABLE IF NOT EXISTS providers (
                id TEXT PRIMARY KEY,               -- slug: cubence, rightcodes
                name TEXT NOT NULL,                -- display hidden from user
                base_url TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )
        await con.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_models (
                id TEXT PRIMARY KEY,                -- internal id = provider_id:external_id  (e.g. cubence:gpt-image-2 , rightcodes:gpt-image-2) no collision
                provider_id TEXT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
                external_id TEXT NOT NULL,          -- real model name sent to upstream API (e.g. gpt-image-2)
                display_name TEXT NOT NULL,         -- shown to user (privacy: no provider)
                description TEXT,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                is_default BOOLEAN NOT NULL DEFAULT FALSE,
                capabilities JSONB NOT NULL DEFAULT '{}'::jsonb,
                sort_order INT NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                UNIQUE(provider_id, external_id)
            );
            """
        )
        await con.execute("ALTER TABLE ai_models ADD COLUMN IF NOT EXISTS external_id TEXT;")
        await con.execute("UPDATE ai_models SET external_id = COALESCE(external_id, id) WHERE external_id IS NULL;")
        # try to ensure id is provider:external format for new collision-safe handling (backfill old rows if needed)
        # If id does NOT contain ':', convert to provider_id:external_id
        # Use DO block to avoid failing on duplicate
        try:
            await con.execute(
                """
                DO $$
                DECLARE r RECORD;
                BEGIN
                  FOR r IN SELECT id, provider_id, external_id FROM ai_models WHERE id NOT LIKE '%:%' LOOP
                    BEGIN
                      UPDATE ai_models SET id = r.provider_id || ':' || r.external_id WHERE ai_models.id = r.id;
                    EXCEPTION WHEN unique_violation THEN
                      -- collision already handled, keep old
                      NULL;
                    END;
                  END LOOP;
                END $$;
                """
            )
        except Exception:
            pass
        await con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS pref_model_id TEXT;")
        await con.execute("ALTER TABLE generations ADD COLUMN IF NOT EXISTS model_id TEXT;")
        # settings for API keys are stored in settings table, but add encrypted helper columns if needed — for now use settings
        # ensure default providers
        await con.execute(
            """
            INSERT INTO providers (id, name, base_url, is_active)
            VALUES ('cubence', 'Cubence', 'https://api-dmit.cubence.com', true)
            ON CONFLICT (id) DO NOTHING;
            """
        )
        await con.execute(
            """
            INSERT INTO providers (id, name, base_url, is_active)
            VALUES ('rightcodes', 'Right Codes', 'https://www.right.codes/draw', false)
            ON CONFLICT (id) DO NOTHING;
            """
        )
        # default model for cubence
        await con.execute(
            """
            INSERT INTO ai_models (id, provider_id, display_name, description, is_active, is_default, sort_order, capabilities)
            VALUES ('gpt-image-2', 'cubence', 'GPT Image 2', 'High quality general purpose', true, true, 0, '{\"txt2img\": true, \"img2img\": true, \"sizes\": [\"1024x1024\", \"1024x1536\", \"1536x1024\"]}'::jsonb)
            ON CONFLICT (id) DO NOTHING;
            """
        )


# ---------- users ----------
async def upsert_user(user_id: int, username: str | None, first_name: str | None, lang_code: str | None = None):
    """lang_code: Telegram's raw language_code (e.g. 'id', 'en-US'); only used to seed lang on first sight.
    Preserves user-chosen lang on conflict — only fills lang if NULL (COALESCE).
    """
    lang = "id" if (lang_code or "").lower().startswith("id") else "en"
    async with _pool.acquire() as con:
        await con.execute(
            """
            INSERT INTO users (user_id, username, first_name, lang)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE
              SET username = EXCLUDED.username,
                  first_name = EXCLUDED.first_name,
                  last_seen = now(),
                  lang = COALESCE(users.lang, EXCLUDED.lang);
            """,
            user_id, username, first_name, lang,
        )


async def user_exists(user_id: int) -> bool:
    async with _pool.acquire() as con:
        return bool(await con.fetchval("SELECT 1 FROM users WHERE user_id=$1", user_id))


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


# ---------- language ----------
async def get_lang(user_id: int) -> str:
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT lang FROM users WHERE user_id=$1", user_id)
        return row["lang"] if row and row["lang"] else "id"


async def set_lang(user_id: int, lang: str):
    async with _pool.acquire() as con:
        await con.execute("UPDATE users SET lang=$2 WHERE user_id=$1", user_id, lang if lang in ("id", "en") else "id")


# ---------- balance / deposits ----------
async def get_balance(user_id: int) -> int:
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT balance FROM users WHERE user_id=$1", user_id)
        return row["balance"] if row else 0


async def adjust_balance(user_id: int, delta: int, reason: str) -> int:
    """Atomically apply delta to a user's balance, log it, and return the new balance."""
    async with _pool.acquire() as con:
        async with con.transaction():
            row = await con.fetchrow(
                "UPDATE users SET balance = balance + $2 WHERE user_id=$1 RETURNING balance",
                user_id, delta)
            if not row:
                # user might not exist yet (edge case) — create then retry
                await con.execute(
                    "INSERT INTO users (user_id, balance) VALUES ($1, $2) "
                    "ON CONFLICT (user_id) DO UPDATE SET balance = users.balance + $2",
                    user_id, delta)
                row = await con.fetchrow("SELECT balance FROM users WHERE user_id=$1", user_id)
            new_balance = row["balance"]
            await con.execute(
                "INSERT INTO balance_logs (user_id, delta, balance_after, reason) VALUES ($1,$2,$3,$4)",
                user_id, delta, new_balance, reason)
            return new_balance


async def get_balance_settings() -> dict:
    """Deposit config: min/max amount, quick-pick amounts, enabled toggle."""
    async with _pool.acquire() as con:
        rows = await con.fetch(
            "SELECT key, value FROM settings WHERE key IN "
            "('balance_enabled','deposit_min','deposit_max','deposit_quick_amounts')")
        s = {r["key"]: r["value"] for r in rows}
        quick_raw = s.get("deposit_quick_amounts", "10000,25000,50000,100000,250000")
        try:
            quick = [int(x) for x in quick_raw.split(",") if x.strip()]
        except ValueError:
            quick = [10000, 25000, 50000, 100000, 250000]
        return {
            "enabled": s.get("balance_enabled", "1") == "1",
            "min_amount": int(s.get("deposit_min", "10000")),
            "max_amount": int(s.get("deposit_max", "5000000")),
            "quick_amounts": quick,
        }


async def create_deposit(user_id: int, amount: int, method: dict) -> int:
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "INSERT INTO deposits (user_id, method_id, method_name, amount) "
            "VALUES ($1,$2,$3,$4) RETURNING id",
            user_id, method["id"], method["name"], amount)
        return row["id"]


async def attach_deposit_proof(deposit_id: int, file_id: str):
    async with _pool.acquire() as con:
        await con.execute("UPDATE deposits SET proof_file_id=$2 WHERE id=$1", deposit_id, file_id)


async def get_pending_deposit(user_id: int) -> dict | None:
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "SELECT * FROM deposits WHERE user_id=$1 AND status='pending' ORDER BY id DESC LIMIT 1",
            user_id)
        return dict(row) if row else None


async def cancel_deposit(deposit_id: int):
    async with _pool.acquire() as con:
        await con.execute(
            "UPDATE deposits SET status='rejected', note='dibatalkan user', decided_at=now() "
            "WHERE id=$1 AND status='pending'", deposit_id)


async def get_user_deposits(user_id: int, limit: int = 10) -> list[dict]:
    async with _pool.acquire() as con:
        rows = await con.fetch(
            "SELECT * FROM deposits WHERE user_id=$1 ORDER BY id DESC LIMIT $2", user_id, limit)
        return [dict(r) for r in rows]


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


async def try_consume_daily_quota(user_id: int, limit: int) -> tuple[bool, int]:
    """Atomically try to consume 1 daily quota.
    Returns (allowed, count_after_or_current). limit 0 = unlimited always allowed.
    Uses pg_advisory_xact_lock per user to prevent race on concurrent requests.
    """
    async with _pool.acquire() as con:
        async with con.transaction():
            # Serialize concurrent quota checks for the same user
            await con.execute("SELECT pg_advisory_xact_lock($1)", user_id)
            tday = date.today()
            # Ensure row exists so FOR UPDATE always locks something
            await con.execute(
                "INSERT INTO usage_daily (user_id, day, count) VALUES ($1,$2,0) "
                "ON CONFLICT (user_id, day) DO NOTHING",
                user_id, tday,
            )
            row = await con.fetchrow(
                "SELECT count FROM usage_daily WHERE user_id=$1 AND day=$2 FOR UPDATE",
                user_id, tday,
            )
            current = row["count"] if row else 0
            if limit != 0 and current >= limit:
                return False, current
            new_row = await con.fetchrow(
                "UPDATE usage_daily SET count = count + 1 "
                "WHERE user_id=$1 AND day=$2 RETURNING count",
                user_id, tday,
            )
            return True, new_row["count"]


async def check_and_consume_atomic(user_id: int, free_fallback: int) -> tuple[bool, int, int, bool]:
    """Atomic wrapper combining limit resolution + bonus fallback.
    Returns (allowed, used, limit, used_bonus_quota).
    """
    # Resolve effective limit (premium-aware)
    # NOTE: effective_daily_limit does its own pool acquire; that's okay
    # because the critical atomic section is inside try_consume_daily_quota
    # which uses advisory lock.
    limit = await effective_daily_limit(user_id, free_fallback)
    if limit != 0:
        allowed, count = await try_consume_daily_quota(user_id, limit)
        if allowed:
            return True, count, limit, False
        # daily exhausted -> try bonus quota
        if await consume_bonus_quota(user_id, 1):
            return True, count, limit, True
        return False, count, limit, False
    else:
        # unlimited plan
        n = await increment_usage(user_id)
        return True, n, limit, False


async def log_generation(user_id, kind, prompt, size, success, result_file_id: str | None = None, style_id: str | None = None):
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "INSERT INTO generations (user_id, kind, prompt, size, success, result_file_id, style_id) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id",
            user_id, kind, prompt, size, success, result_file_id, style_id,
        )
        return row["id"] if row else None


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


# ---------- referral bonus quota (extra images beyond the daily cap) ----------
async def get_bonus_quota(user_id: int) -> int:
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT bonus_quota FROM users WHERE user_id=$1", user_id)
        return row["bonus_quota"] if row else 0


async def add_bonus_quota(user_id: int, n: int) -> int:
    """Grant (or, with negative n, revoke) bonus quota. Returns new total."""
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "UPDATE users SET bonus_quota = GREATEST(0, bonus_quota + $2) WHERE user_id=$1 RETURNING bonus_quota",
            user_id, n)
        if not row:
            await con.execute(
                "INSERT INTO users (user_id, bonus_quota) VALUES ($1, GREATEST(0,$2)) "
                "ON CONFLICT (user_id) DO UPDATE SET bonus_quota = GREATEST(0, users.bonus_quota + $2)",
                user_id, n)
            row = await con.fetchrow("SELECT bonus_quota FROM users WHERE user_id=$1", user_id)
        return row["bonus_quota"]


async def consume_bonus_quota(user_id: int, n: int = 1) -> bool:
    """Atomically consume n bonus images if available. Returns True if consumed."""
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "UPDATE users SET bonus_quota = bonus_quota - $2 "
            "WHERE user_id=$1 AND bonus_quota >= $2 RETURNING bonus_quota",
            user_id, n)
        return row is not None


# ---------- referral system ----------
async def get_referral_settings() -> dict:
    async with _pool.acquire() as con:
        rows = await con.fetch(
            "SELECT key, value FROM settings WHERE key IN "
            "('referral_enabled','referral_reward_type','referral_reward_amount')")
        s = {r["key"]: r["value"] for r in rows}
        return {
            "enabled": s.get("referral_enabled", "1") == "1",
            "reward_type": s.get("referral_reward_type", "balance") if s.get("referral_reward_type") in ("balance", "quota") else "balance",
            "reward_amount": int(s.get("referral_reward_amount", "5000")),
        }


async def record_referral_signup(referrer_id: int, referred_id: int) -> bool:
    """Called once, right when a brand-new user starts the bot via a referral link.
    Snapshots the current reward config so later admin changes don't retroactively
    affect already-pending referrals. Returns True if recorded.
    """
    if referrer_id == referred_id:
        return False
    settings = await get_referral_settings()
    if not settings["enabled"]:
        return False
    async with _pool.acquire() as con:
        # referrer must actually exist
        exists = await con.fetchval("SELECT 1 FROM users WHERE user_id=$1", referrer_id)
        if not exists:
            return False
        try:
            await con.execute(
                "INSERT INTO referrals (referrer_id, referred_id, reward_type, reward_amount) "
                "VALUES ($1,$2,$3,$4)",
                referrer_id, referred_id, settings["reward_type"], settings["reward_amount"])
            await con.execute("UPDATE users SET referred_by=$2 WHERE user_id=$1", referred_id, referrer_id)
            return True
        except asyncpg.UniqueViolationError:
            return False  # already referred before


async def try_reward_referral(referred_id: int) -> dict | None:
    """If `referred_id` has a pending referral (i.e. just passed the subscription
    gate for the first time), grant the reward to their referrer and mark it done.
    Returns {referrer_id, reward_type, reward_amount} on success, else None.
    """
    async with _pool.acquire() as con:
        async with con.transaction():
            row = await con.fetchrow(
                "SELECT * FROM referrals WHERE referred_id=$1 AND status='pending' FOR UPDATE",
                referred_id)
            if not row:
                return None
            await con.execute(
                "UPDATE referrals SET status='rewarded', rewarded_at=now() WHERE id=$1", row["id"])
    # apply reward outside the row lock (uses its own connections/transactions)
    if row["reward_type"] == "quota":
        await add_bonus_quota(row["referrer_id"], row["reward_amount"])
    else:
        await adjust_balance(row["referrer_id"], row["reward_amount"], "Bonus referral")
    return {"referrer_id": row["referrer_id"], "reward_type": row["reward_type"], "reward_amount": row["reward_amount"]}


async def get_referral_stats(user_id: int) -> dict:
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "SELECT count(*) AS total, count(*) FILTER (WHERE status='rewarded') AS rewarded "
            "FROM referrals WHERE referrer_id=$1", user_id)
        bonus_quota = await con.fetchval("SELECT bonus_quota FROM users WHERE user_id=$1", user_id) or 0
        return {"total": row["total"] or 0, "rewarded": row["rewarded"] or 0,
                "pending": (row["total"] or 0) - (row["rewarded"] or 0), "bonus_quota": bonus_quota}


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


async def buy_plan_with_balance(user_id: int, plan: dict):
    """Atomically deduct balance and activate premium. Returns (ok, new_until_or_None, new_balance)."""
    from datetime import timedelta
    async with _pool.acquire() as con:
        async with con.transaction():
            row = await con.fetchrow(
                "SELECT balance, premium_until FROM users WHERE user_id=$1 FOR UPDATE", user_id)
            balance = row["balance"] if row else 0
            if balance < plan["price"]:
                return False, None, balance
            new_balance = balance - plan["price"]
            await con.execute("UPDATE users SET balance=$2 WHERE user_id=$1", user_id, new_balance)
            await con.execute(
                "INSERT INTO balance_logs (user_id, delta, balance_after, reason) VALUES ($1,$2,$3,$4)",
                user_id, -plan["price"], new_balance, f"Beli paket {plan['name']}")

            base = _now()
            if row and row["premium_until"] and row["premium_until"] > base:
                base = row["premium_until"]
            new_until = base + timedelta(days=plan["duration_days"])
            await con.execute(
                "UPDATE users SET premium_until=$2, plan_id=$3, plan_name=$4 WHERE user_id=$1",
                user_id, new_until, plan["id"], plan["name"])

            await con.execute(
                "INSERT INTO orders (user_id, plan_id, method_id, plan_name, method_name, amount, "
                "daily_limit, duration_days, status, decided_at) "
                "VALUES ($1,$2,NULL,$3,'Saldo',$4,$5,$6,'approved', now())",
                user_id, plan["id"], plan["name"], plan["price"], plan["daily_limit"], plan["duration_days"])
            return True, new_until, new_balance


async def seed_default_plan():
    """Ensure at least one plan exists so admin has a starting point."""
    async with _pool.acquire() as con:
        n = await con.fetchval("SELECT count(*) FROM plans")
        if n == 0:
            await con.execute(
                "INSERT INTO plans (name, daily_limit, price, duration_days, description, sort_order) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                "Premium", 100, 20000, 30, "Kuota 100 gambar/hari selama 30 hari", 1)


# ---------- generation results / feat 2,3,4 ----------
async def save_generation_result(gen_id: int, result_file_id: str):
    async with _pool.acquire() as con:
        await con.execute("UPDATE generations SET result_file_id=$2 WHERE id=$1", gen_id, result_file_id)


async def log_generation_with_result(user_id, kind, prompt, size, success, result_file_id: str | None = None, style_id: str | None = None):
    """Helper alias that inserts with file_id in one go."""
    return await log_generation(user_id, kind, prompt, size, success, result_file_id, style_id)


async def get_user_generations(user_id: int, limit: int = 20, offset: int = 0) -> list[dict]:
    async with _pool.acquire() as con:
        rows = await con.fetch(
            "SELECT * FROM generations WHERE user_id=$1 AND success=TRUE AND result_file_id IS NOT NULL "
            "ORDER BY id DESC LIMIT $2 OFFSET $3",
            user_id, limit, offset,
        )
        return [dict(r) for r in rows]


async def get_generation_by_id(gen_id: int) -> dict | None:
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT * FROM generations WHERE id=$1", gen_id)
        return dict(row) if row else None


async def count_user_generations(user_id: int) -> int:
    async with _pool.acquire() as con:
        cnt = await con.fetchval(
            "SELECT count(*) FROM generations WHERE user_id=$1 AND success=TRUE AND result_file_id IS NOT NULL",
            user_id,
        )
        return int(cnt or 0)


async def get_pref_style(user_id: int, default: str | None = None) -> str | None:
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT pref_style FROM users WHERE user_id=$1", user_id)
        return row["pref_style"] if row and row["pref_style"] else default


async def set_pref_style(user_id: int, style_id: str | None):
    async with _pool.acquire() as con:
        await con.execute("UPDATE users SET pref_style=$2 WHERE user_id=$1", user_id, style_id)


# ---------- daily check-in + streak ----------
async def get_checkin_info(user_id: int) -> dict:
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT last_checkin, streak, total_checkin FROM users WHERE user_id=$1", user_id)
        if not row:
            return {"last_checkin": None, "streak": 0, "total_checkin": 0}
        return dict(row)


async def try_checkin(user_id: int) -> tuple[bool, int, int, int]:
    """
    Attempt daily check-in. Returns (ok, new_streak, total, bonus_quota_added).
    ok=False if already checked in today.
    Bonus: +1 quota, streak 3->+2, 7->+5, 30->+20 extra.
    Uses FOR UPDATE to avoid race.
    """
    from datetime import date, timedelta
    today = date.today()
    async with _pool.acquire() as con:
        async with con.transaction():
            row = await con.fetchrow(
                "SELECT last_checkin, streak, total_checkin FROM users WHERE user_id=$1 FOR UPDATE", user_id)
            if not row:
                return False, 0, 0, 0
            if row["last_checkin"] == today:
                return False, row["streak"], row["total_checkin"], 0
            # determine new streak
            last = row["last_checkin"]
            if last and last == today - timedelta(days=1):
                new_streak = (row["streak"] or 0) + 1
            else:
                new_streak = 1
            new_total = (row["total_checkin"] or 0) + 1
            await con.execute(
                "UPDATE users SET last_checkin=$2, streak=$3, total_checkin=$4 WHERE user_id=$1",
                user_id, today, new_streak, new_total)
            # bonus quota calc
            bonus = 1
            if new_streak == 3:
                bonus = 2
            elif new_streak == 7:
                bonus = 5
            elif new_streak >= 30:
                bonus = 20
            elif new_streak > 7:
                bonus = 2
            await con.execute(
                "UPDATE users SET bonus_quota = bonus_quota + $2 WHERE user_id=$1", user_id, bonus)
            return True, new_streak, new_total, bonus


# ---------- feature flags (10,14,15,17) ----------
# Setting keys:
#   feat_enhance_enabled, feat_batch_enabled, feat_watermark_enabled, feat_sticker_enabled
#   watermark_text, watermark_free_only, enhance_model
#   batch_limit_free, batch_limit_premium, sticker_max_per_pack


async def feat_prompt_enhance_enabled() -> bool:
    v = await get_setting("feat_enhance_enabled", "1")
    return v == "1"


async def feat_batch_enabled() -> bool:
    v = await get_setting("feat_batch_enabled", "1")
    return v == "1"


async def feat_watermark_enabled() -> bool:
    v = await get_setting("feat_watermark_enabled", "0")
    return v == "1"


async def feat_sticker_enabled() -> bool:
    v = await get_setting("feat_sticker_enabled", "1")
    return v == "1"


async def feat_checkin_enabled() -> bool:
    # check-in already exists, keep flag for uniformity
    v = await get_setting("feat_checkin_enabled", "1")
    return v == "1"


async def get_watermark_text() -> str:
    return await get_setting("watermark_text", "Buat di @imgaai_bot") or "Buat di @imgaai_bot"


async def get_watermark_free_only() -> bool:
    v = await get_setting("watermark_free_only", "1")
    return v == "1"


async def get_enhance_model() -> str:
    return await get_setting("enhance_model", "gpt-4o-mini") or "gpt-4o-mini"


async def get_batch_limits() -> tuple[int, int]:
    """Return (free_limit, premium_limit)."""
    free_raw = await get_setting("batch_limit_free", "1")
    prem_raw = await get_setting("batch_limit_premium", "4")
    try:
        free_lim = int(free_raw)
    except (ValueError, TypeError):
        free_lim = 1
    try:
        prem_lim = int(prem_raw)
    except (ValueError, TypeError):
        prem_lim = 4
    # clamp to sane range
    free_lim = max(1, min(free_lim, 10))
    prem_lim = max(1, min(prem_lim, 10))
    return free_lim, prem_lim


async def get_batch_limit_free() -> int:
    f, _ = await get_batch_limits()
    return f


async def get_batch_limit_premium() -> int:
    _, p = await get_batch_limits()
    return p


async def get_sticker_max_per_pack() -> int:
    raw = await get_setting("sticker_max_per_pack", "10")
    try:
        v = int(raw)
    except (ValueError, TypeError):
        v = 10
    return max(1, min(v, 120))


# ---------- sticker packs (feature 17) ----------
async def get_sticker_pack(pack_name: str) -> dict | None:
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT * FROM sticker_packs WHERE pack_name=$1", pack_name)
        return dict(row) if row else None


async def get_user_sticker_packs(user_id: int) -> list[dict]:
    async with _pool.acquire() as con:
        rows = await con.fetch(
            "SELECT * FROM sticker_packs WHERE user_id=$1 ORDER BY created_at DESC", user_id
        )
        return [dict(r) for r in rows]


async def get_user_last_sticker_pack(user_id: int) -> str | None:
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT last_sticker_pack FROM users WHERE user_id=$1", user_id)
        return row["last_sticker_pack"] if row and row["last_sticker_pack"] else None


async def set_user_last_sticker_pack(user_id: int, pack_name: str):
    async with _pool.acquire() as con:
        await con.execute("UPDATE users SET last_sticker_pack=$2 WHERE user_id=$1", user_id, pack_name)


async def create_sticker_pack(user_id: int, pack_name: str, title: str | None = None) -> dict:
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "INSERT INTO sticker_packs (user_id, pack_name, title) VALUES ($1,$2,$3) "
            "ON CONFLICT (pack_name) DO NOTHING RETURNING *",
            user_id, pack_name, title,
        )
        if row:
            return dict(row)
        row2 = await con.fetchrow("SELECT * FROM sticker_packs WHERE pack_name=$1", pack_name)
        return dict(row2) if row2 else {"user_id": user_id, "pack_name": pack_name, "title": title, "sticker_count": 0}


async def increment_sticker_count(pack_name: str) -> int:
    async with _pool.acquire() as con:
        row = await con.fetchrow(
            "UPDATE sticker_packs SET sticker_count = sticker_count + 1 WHERE pack_name=$1 RETURNING sticker_count",
            pack_name,
        )
        return row["sticker_count"] if row else 0


# ---------- providers + models ----------
async def list_providers() -> list[dict]:
    async with _pool.acquire() as con:
        rows = await con.fetch("SELECT * FROM providers ORDER BY id")
        return [dict(r) for r in rows]


async def get_provider(provider_id: str) -> dict | None:
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT * FROM providers WHERE id=$1", provider_id)
        return dict(row) if row else None


async def upsert_provider(provider_id: str, name: str, base_url: str, is_active: bool = True):
    async with _pool.acquire() as con:
        await con.execute(
            """
            INSERT INTO providers (id, name, base_url, is_active, updated_at)
            VALUES ($1,$2,$3,$4, now())
            ON CONFLICT (id) DO UPDATE SET name=$2, base_url=$3, is_active=$4, updated_at=now()
            """,
            provider_id, name, base_url, is_active,
        )


async def list_models(active_only: bool = False, include_inactive_provider: bool = False) -> list[dict]:
    async with _pool.acquire() as con:
        if active_only:
            q = """
                SELECT m.*, p.is_active as provider_active FROM ai_models m
                JOIN providers p ON p.id = m.provider_id
                WHERE m.is_active = true AND p.is_active = true
                ORDER BY m.sort_order, m.display_name
            """
            rows = await con.fetch(q)
        else:
            if include_inactive_provider:
                rows = await con.fetch("SELECT m.*, p.is_active as provider_active, p.name as provider_name FROM ai_models m JOIN providers p ON p.id=m.provider_id ORDER BY p.id, m.sort_order, m.display_name")
            else:
                rows = await con.fetch("SELECT m.*, p.is_active as provider_active, p.name as provider_name FROM ai_models m LEFT JOIN providers p ON p.id=m.provider_id ORDER BY m.sort_order, m.id")
        raw = [dict(r) for r in rows]
        if active_only:
            # dedupe by id (collision-safe id is provider:external, so no true dupes, but also guard by external lower per provider)
            seen = set()
            out = []
            for r in raw:
                key = r["id"]  # already provider:external
                if key in seen:
                    continue
                seen.add(key)
                out.append(r)
            return out
        return raw


async def get_model(model_id: str) -> dict | None:
    async with _pool.acquire() as con:
        row = await con.fetchrow("SELECT * FROM ai_models WHERE id=$1", model_id)
        return dict(row) if row else None


async def get_active_model_for_user(user_id: int) -> dict | None:
    """Resolve user's preferred model, fallback to default active model."""
    async with _pool.acquire() as con:
        # user pref
        pref_row = await con.fetchrow("SELECT pref_model_id FROM users WHERE user_id=$1", user_id)
        pref = pref_row["pref_model_id"] if pref_row and pref_row["pref_model_id"] else None
        if pref:
            r = await con.fetchrow(
                "SELECT m.* FROM ai_models m JOIN providers p ON p.id=m.provider_id WHERE m.id=$1 AND m.is_active=true AND p.is_active=true",
                pref,
            )
            if r:
                return dict(r)
        # default
        r = await con.fetchrow(
            "SELECT m.* FROM ai_models m JOIN providers p ON p.id=m.provider_id WHERE m.is_default=true AND m.is_active=true AND p.is_active=true LIMIT 1"
        )
        if r:
            return dict(r)
        # any active
        r = await con.fetchrow(
            "SELECT m.* FROM ai_models m JOIN providers p ON p.id=m.provider_id WHERE m.is_active=true AND p.is_active=true ORDER BY m.sort_order LIMIT 1"
        )
        return dict(r) if r else None


async def get_default_model() -> dict | None:
    async with _pool.acquire() as con:
        r = await con.fetchrow(
            "SELECT m.* FROM ai_models m JOIN providers p ON p.id=m.provider_id WHERE m.is_default=true AND m.is_active=true AND p.is_active=true LIMIT 1"
        )
        if r:
            return dict(r)
        r = await con.fetchrow(
            "SELECT m.* FROM ai_models m JOIN providers p ON p.id=m.provider_id WHERE m.is_active=true AND p.is_active=true ORDER BY m.sort_order LIMIT 1"
        )
        return dict(r) if r else None


async def set_user_model(user_id: int, model_id: str):
    async with _pool.acquire() as con:
        await con.execute("UPDATE users SET pref_model_id=$2 WHERE user_id=$1", user_id, model_id)


async def upsert_model(model_id: str, provider_id: str, display_name: str, description: str | None = None, is_active: bool = True, is_default: bool = False, sort_order: int = 0, capabilities: dict | None = None):
    caps = capabilities or {}
    import json
    async with _pool.acquire() as con:
        if is_default:
            # clear other defaults
            await con.execute("UPDATE ai_models SET is_default=false WHERE provider_id=$1", provider_id)
        await con.execute(
            """
            INSERT INTO ai_models (id, provider_id, display_name, description, is_active, is_default, sort_order, capabilities, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb, now())
            ON CONFLICT (id) DO UPDATE SET provider_id=$2, display_name=$3, description=$4, is_active=$5, is_default=$6, sort_order=$7, capabilities=$8::jsonb, updated_at=now()
            """,
            model_id, provider_id, display_name, description, is_active, is_default, sort_order, json.dumps(caps),
        )


async def delete_model(model_id: str):
    async with _pool.acquire() as con:
        await con.execute("DELETE FROM ai_models WHERE id=$1", model_id)


async def set_default_model(model_id: str):
    async with _pool.acquire() as con:
        # get provider of this model
        row = await con.fetchrow("SELECT provider_id FROM ai_models WHERE id=$1", model_id)
        if not row:
            return
        pid = row["provider_id"]
        await con.execute("UPDATE ai_models SET is_default=false WHERE provider_id=$1", pid)
        await con.execute("UPDATE ai_models SET is_default=true WHERE id=$1", model_id)




