import asyncpg
from config.settings import DATABASE_URL
from utils.logger import get_logger

logger = get_logger(__name__)

_db_pool = None

async def init_db_pool():
    """Initialize the database connection pool (statement cache disabled for pgbouncer)."""
    global _db_pool
    try:
        _db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10,
            command_timeout=60,
            max_queries=50000,
            max_inactive_connection_lifetime=300,
            statement_cache_size=0
        )
        logger.info("Database pool created (statement_cache_size=0)")

        # Verify connection
        async with _db_pool.acquire() as conn:
            await conn.execute("SELECT 1")
        logger.info("Database connection verified")

        return _db_pool
    except Exception as e:
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