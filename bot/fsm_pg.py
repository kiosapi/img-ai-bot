"""
Postgres FSM storage for aiogram 3.x.

Persistent storage replacing MemoryStorage, backed by table aiogram_states.

Table: aiogram_states (chat_id BIGINT, user_id BIGINT, state TEXT, data JSONB, updated TIMESTAMPTZ)
PK = (chat_id, user_id)

Design:
- __init__(pool_getter) where pool_getter is callable returning asyncpg pool,
  or pool directly. Lazy pool resolution to avoid import cycles.
- self-migrating: _ensure_table() called before every op.
- Factory get_fsm_storage() returns PGStorage(lambda: db._pool) for main.py usage.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Mapping, Optional, Union

logger = logging.getLogger(__name__)

try:
    from aiogram.fsm.state import State
    from aiogram.fsm.storage.base import BaseStorage, StorageKey, StateType
except ImportError:  # Allow py_compile even if aiogram not installed in this env
    BaseStorage = object  # type: ignore
    StorageKey = object  # type: ignore
    StateType = str  # type: ignore
    State = None  # type: ignore

# DDL shared with db.py _create_schema - must stay in sync
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS aiogram_states (
    chat_id   BIGINT NOT NULL,
    user_id   BIGINT NOT NULL,
    state     TEXT,
    data      JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (chat_id, user_id)
);
"""

# DDL for _create_schema wrapper (single statement variant without NOT NULL on data to avoid conflict on old PG)
CREATE_TABLE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS aiogram_states (
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    state TEXT,
    data JSONB DEFAULT '{}'::jsonb,
    updated TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (chat_id, user_id)
);
"""

# Extra ALTER for pre-existing tables that may have been created with older schema
MIGRATE_SQLS = [
    "ALTER TABLE aiogram_states ADD COLUMN IF NOT EXISTS state TEXT;",
    "ALTER TABLE aiogram_states ADD COLUMN IF NOT EXISTS data JSONB DEFAULT '{}'::jsonb;",
    "ALTER TABLE aiogram_states ADD COLUMN IF NOT EXISTS updated TIMESTAMPTZ NOT NULL DEFAULT now();",
]


async def create_fsm_table(pool=None, con=None):
    """
    Ensure aiogram_states table exists. Called from db.py _create_schema
    OR self-migrate path.
    Accepts either pool (asyncpg Pool) or existing connection.
    """
    if con is not None:
        await con.execute(CREATE_TABLE_SCHEMA_SQL)
        for sql in MIGRATE_SQLS:
            try:
                await con.execute(sql)
            except Exception:
                pass
        return
    if pool is None:
        # lazy import db pool
        try:
            import db as _db
            pool = getattr(_db, "_pool", None)
        except Exception:
            pool = None
    if pool is None:
        return
    async with pool.acquire() as c:
        await c.execute(CREATE_TABLE_SCHEMA_SQL)
        for sql in MIGRATE_SQLS:
            try:
                await c.execute(sql)
            except Exception:
                pass


def _resolve_state_value(state: Any) -> Optional[str]:
    """Normalize State / str / None to str|None as aiogram expects in storage."""
    if state is None:
        return None
    if isinstance(state, str):
        return state
    # aiogram State instance
    try:
        # State.state property or str()
        if hasattr(state, "state"):
            return state.state
        return str(state)
    except Exception:
        return str(state)


class PGStorage(BaseStorage):
    """
    Postgres-backed FSM storage.

    pool_getter: Callable[[], asyncpg.Pool] | asyncpg.Pool
        e.g. lambda: db._pool  (lazy) or directly db._pool / pool object.
    """

    def __init__(self, pool_getter: Union[Callable[[], Any], Any]):
        self._pool_getter = pool_getter
        self._table_ensured = False

    # ---- internal helpers ----

    def _get_pool(self):
        pool = self._pool_getter
        if callable(pool):
            try:
                pool = pool()
            except Exception as e:
                logger.warning("PGStorage pool_getter callable failed: %s", e)
                return None
        return pool

    async def _ensure_table(self):
        """Create/migrate aiogram_states. Idempotent. Skips if ensured already and pool ok."""
        pool = self._get_pool()
        if pool is None:
            return
        # avoid spamming DDL on every request after first success, but retry on failure
        # We still set ensured=True after first success; if DDL failed we keep False to retry.
        try:
            async with pool.acquire() as con:
                await con.execute(CREATE_TABLE_SQL)
                for sql in MIGRATE_SQLS:
                    try:
                        await con.execute(sql)
                    except Exception as e:
                        # ignore add column if exists etc
                        logger.debug("Migrate skipped %s: %s", sql, e)
            self._table_ensured = True
        except Exception as e:
            logger.warning("PGStorage _ensure_table failed (will retry): %s", e)
            # don't mark as ensured

    async def _fetch_row(self, key: StorageKey):
        pool = self._get_pool()
        if pool is None:
            return None
        await self._ensure_table()
        try:
            async with pool.acquire() as con:
                row = await con.fetchrow(
                    "SELECT state, data FROM aiogram_states WHERE chat_id=$1 AND user_id=$2",
                    key.chat_id,
                    key.user_id,
                )
                return row
        except Exception as e:
            # If table doesn't exist yet (race), try ensure again once
            if "does not exist" in str(e) or "UndefinedTable" in type(e).__name__:
                if not self._table_ensured:
                    await self._ensure_table()
                    try:
                        async with pool.acquire() as con:
                            row = await con.fetchrow(
                                "SELECT state, data FROM aiogram_states WHERE chat_id=$1 AND user_id=$2",
                                key.chat_id,
                                key.user_id,
                            )
                            return row
                    except Exception:
                        pass
            logger.warning("PGStorage _fetch_row error: %s", e)
            return None

    # ---- BaseStorage API ----

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        pool = self._get_pool()
        if pool is None:
            return
        await self._ensure_table()
        st = _resolve_state_value(state)
        try:
            async with pool.acquire() as con:
                if st is None:
                    # set state null but keep row for data? aiogram MemoryStorage keeps row?
                    # We preserve data if exists, set state NULL. If row doesn't exist and state None => no-op
                    # Actually for delete semantics, if both state None and data empty, we could delete,
                    # but aiogram expects set_state(None) to clear state but not data.
                    # So upsert with state NULL.
                    await con.execute(
                        """
                        INSERT INTO aiogram_states (chat_id, user_id, state, data, updated)
                        VALUES ($1, $2, $3, '{}'::jsonb, now())
                        ON CONFLICT (chat_id, user_id)
                        DO UPDATE SET state = EXCLUDED.state, updated = now()
                        """,
                        key.chat_id,
                        key.user_id,
                        st,
                    )
                else:
                    await con.execute(
                        """
                        INSERT INTO aiogram_states (chat_id, user_id, state, data, updated)
                        VALUES ($1, $2, $3, '{}'::jsonb, now())
                        ON CONFLICT (chat_id, user_id)
                        DO UPDATE SET state = EXCLUDED.state, updated = now()
                        """,
                        key.chat_id,
                        key.user_id,
                        st,
                    )
        except Exception as e:
            logger.warning("PGStorage set_state error: %s", e)

    async def get_state(self, key: StorageKey) -> Optional[str]:
        row = await self._fetch_row(key)
        if not row:
            return None
        try:
            return row["state"]
        except Exception:
            # row may be tuple-like
            return row[0] if row else None

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        pool = self._get_pool()
        if pool is None:
            return
        await self._ensure_table()
        # aiogram expects data to be JSON serializable
        # Ensure dict
        json_data = dict(data) if data is not None else {}
        try:
            # asyncpg handles jsonb via json dumps? Use python object, asyncpg converts dict to jsonb if codec set,
            # but to be safe pass json string cast? Use json.dumps and let driver.
            # asyncpg default jsonb handling: pass dict as jsonb if codec jsonb registered, else string.
            # Simplest: use json.dumps and ::jsonb cast via parameter? We'll pass as stringified JSON.
            # Using json.dumps and passing as str with execute will work with PG jsonb column if we cast.
            # Instead pass json.dumps and let asyncpg json type handle, or pass dict directly.
            # We'll pass json.dumps and rely on text -> jsonb? Better pass json.dumps(x)
            import json as _json
            data_json = _json.dumps(json_data, ensure_ascii=False)
            async with pool.acquire() as con:
                await con.execute(
                    """
                    INSERT INTO aiogram_states (chat_id, user_id, state, data, updated)
                    VALUES ($1, $2, NULL, $3::jsonb, now())
                    ON CONFLICT (chat_id, user_id)
                    DO UPDATE SET data = EXCLUDED.data, updated = now()
                    """,
                    key.chat_id,
                    key.user_id,
                    data_json,
                )
        except Exception as e:
            logger.warning("PGStorage set_data error: %s", e)

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        row = await self._fetch_row(key)
        if not row:
            return {}
        try:
            raw = row["data"]
        except Exception:
            raw = row[1] if len(row) > 1 else None
        if raw is None:
            return {}
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except Exception:
                return {}
        # asyncpg may return json as str? Already handled
        return dict(raw) if isinstance(raw, Mapping) else {}

    async def update_data(self, key: StorageKey, data: Mapping[str, Any]) -> dict[str, Any]:
        """
        Override for atomicity: fetch, merge, set.
        Uses base logic but keeps single transaction path possible.
        """
        pool = self._get_pool()
        if pool is None:
            # fallback to base impl which calls get_data/set_data (will no-op but return merged)
            try:
                current = await self.get_data(key)
            except Exception:
                current = {}
            current.update(data)
            try:
                await self.set_data(key, current)
            except Exception:
                pass
            return current

        await self._ensure_table()
        try:
            async with pool.acquire() as con:
                async with con.transaction():
                    row = await con.fetchrow(
                        "SELECT data FROM aiogram_states WHERE chat_id=$1 AND user_id=$2 FOR UPDATE",
                        key.chat_id,
                        key.user_id,
                    )
                    if row is None:
                        cur = {}
                    else:
                        raw = row["data"] if "data" in row else row[0]
                        if isinstance(raw, dict):
                            cur = dict(raw)
                        elif isinstance(raw, str):
                            try:
                                cur = json.loads(raw)
                            except Exception:
                                cur = {}
                        elif isinstance(raw, Mapping):
                            cur = dict(raw)
                        else:
                            cur = {}
                    cur.update(data)
                    data_json = json.dumps(cur, ensure_ascii=False)
                    await con.execute(
                        """
                        INSERT INTO aiogram_states (chat_id, user_id, state, data, updated)
                        VALUES ($1, $2, NULL, $3::jsonb, now())
                        ON CONFLICT (chat_id, user_id)
                        DO UPDATE SET data = $3::jsonb, updated = now()
                        """,
                        key.chat_id,
                        key.user_id,
                        data_json,
                    )
                    return cur
        except Exception as e:
            logger.warning("PGStorage update_data failed, falling back: %s", e)
            # fallback
            current = await self.get_data(key)
            current.update(data)
            await self.set_data(key, current)
            return current

    async def close(self) -> None:
        # Pool lifecycle managed by db module, not here
        return

    # Optional helper compatible with some aiogram codepaths that call set_state/get_state with Lock?
    # No lock isolation needed for PG - advisory locks already used elsewhere, but FSM itself is per user.

# ---- public factory ----

def get_fsm_storage(pool_getter=None):
    """
    Factory returning PGStorage.

    Usage:
        from fsm_pg import get_fsm_storage
        storage = get_fsm_storage(lambda: db._pool)
    Or with no arg, lazy-imports db module:
        storage = get_fsm_storage()
    """
    if pool_getter is None:
        # lazy import to avoid cycle
        def _default_getter():
            try:
                import db as _db
                return getattr(_db, "_pool", None)
            except Exception:
                return None

        return PGStorage(_default_getter)
    return PGStorage(pool_getter)
