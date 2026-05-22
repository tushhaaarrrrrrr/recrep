import asyncpg
from urllib.parse import urlparse

from config.settings import DATABASE_URL, DIRECT_URL, SUPABASE_POOLER_URL
from utils.logger import get_logger

logger = get_logger(__name__)

_db_pool = None


def _db_host(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return urlparse(url).hostname
    except Exception:
        return None


def _looks_like_supabase_direct(url: str | None) -> bool:
    host = _db_host(url)
    return bool(host and host.startswith("db.") and host.endswith(".supabase.co"))


async def init_db_pool():
    """Initialize the database connection pool.

    Runtime connections should use the Supabase session pooler on IPv4-only
    hosts. If a direct Supabase host is configured, fail fast with a clear
    message instead of retrying a connection that cannot succeed here.
    """
    global _db_pool

    db_url = SUPABASE_POOLER_URL or DATABASE_URL or DIRECT_URL
    if not db_url:
        raise RuntimeError(
            "No database URL configured. Set SUPABASE_POOLER_URL (preferred) or DATABASE_URL."
        )

    if _looks_like_supabase_direct(db_url) and not SUPABASE_POOLER_URL:
        raise RuntimeError(
            "DATABASE_URL points to a direct Supabase host (db.<project>.supabase.co), "
            "which is not suitable for this runtime. Set SUPABASE_POOLER_URL to the "
            "Session Pooler connection string from Supabase Dashboard → Connect, then "
            "restart the app."
        )

    try:
        logger.info(
            "Connecting to database using %s",
            "SUPABASE_POOLER_URL" if SUPABASE_POOLER_URL else ("DIRECT_URL" if DIRECT_URL else "DATABASE_URL"),
        )
        _db_pool = await asyncpg.create_pool(
            dsn=db_url,
            min_size=1,
            max_size=10,
            command_timeout=60,
            max_queries=50000,
            max_inactive_connection_lifetime=300,
            statement_cache_size=0,
        )
        logger.info("Database pool created (statement_cache_size=0)")

        async with _db_pool.acquire() as conn:
            await conn.execute("SELECT 1")
        logger.info("Database connection verified")

        return _db_pool
    except Exception:
        logger.exception("Failed to initialize database pool")
        raise


async def get_db_pool():
    """Return the database pool instance (must be initialized first)."""
    if _db_pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db_pool() first.")
    return _db_pool


async def close_db_pool(pool):
    """Close the database connection pool."""
    if pool:
        await pool.close()
        logger.info("Database pool closed")
