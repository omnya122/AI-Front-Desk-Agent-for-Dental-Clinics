"""Thin async Postgres layer (psycopg 3 pool) plus the small operational queries."""
import logging
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .config import get_settings

log = logging.getLogger(__name__)
_pool: AsyncConnectionPool | None = None


async def init_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        # autocommit + dict_row are required by AsyncPostgresSaver as well, so one pool serves both.
        # prepare_threshold=0 keeps it compatible with Supabase's transaction pooler.
        _pool = AsyncConnectionPool(
            get_settings().database_url,
            min_size=1,
            max_size=8,
            open=False,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        )
        await _pool.open(wait=True)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("Database pool not initialised - call db.init_pool() first")
    return _pool


async def fetch(sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
    async with pool().connection() as conn:
        cur = await conn.execute(sql, params)
        return await cur.fetchall()


async def execute(sql: str, params: tuple | None = None) -> None:
    async with pool().connection() as conn:
        await conn.execute(sql, params)


async def run_script(sql: str) -> None:
    """Run a multi-statement SQL script (e.g. schema.sql). Must not be a prepared statement."""
    async with pool().connection() as conn:
        await conn.execute(sql, prepare=False)


def vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"


# --- reliability -----------------------------------------------------------

async def mark_update_seen(update_id: int) -> bool:
    """True the first time an update_id is seen. Telegram redelivers unacknowledged updates."""
    rows = await fetch(
        "INSERT INTO processed_updates (update_id) VALUES (%s) ON CONFLICT DO NOTHING RETURNING update_id",
        (update_id,),
    )
    return bool(rows)


async def hit_rate_limit(chat_id: int, limit: int) -> bool:
    """Sliding one-hour window. Records the event when the message is allowed."""
    rows = await fetch(
        "SELECT count(*) AS n FROM rate_events WHERE chat_id = %s AND ts > now() - interval '1 hour'",
        (chat_id,),
    )
    if rows[0]["n"] >= limit:
        return True
    await execute("INSERT INTO rate_events (chat_id) VALUES (%s)", (chat_id,))
    return False


async def housekeeping() -> None:
    await execute("DELETE FROM rate_events WHERE ts < now() - interval '1 day'")
    await execute("DELETE FROM processed_updates WHERE ts < now() - interval '7 days'")


# --- audit logs ------------------------------------------------------------

async def log_escalation(chat_id: int, question: str, category: str, layer: str, reason: str) -> None:
    await execute(
        "INSERT INTO escalations (chat_id, question, category, layer, reason) VALUES (%s, %s, %s, %s, %s)",
        (chat_id, question, category, layer, reason),
    )


async def log_turn(row: dict[str, Any]) -> None:
    await execute(
        """INSERT INTO turns (chat_id, update_id, question, route, layer, category, confidence,
                              escalated, tokens_in, tokens_out, cost_usd, latency_ms)
           VALUES (%(chat_id)s, %(update_id)s, %(question)s, %(route)s, %(layer)s, %(category)s,
                   %(confidence)s, %(escalated)s, %(tokens_in)s, %(tokens_out)s, %(cost_usd)s,
                   %(latency_ms)s)""",
        row,
    )
