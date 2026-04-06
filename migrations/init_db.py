import asyncio
import asyncpg
import sys
from pathlib import Path
from config.settings import DATABASE_URL
from utils.logger import get_logger

logger = get_logger(__name__)

async def init():
    """Initialize the database schema from schema.sql."""
    try:
        schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
        if not schema_path.exists():
            logger.error(f"Schema file not found: {schema_path}")
            sys.exit(1)

        logger.info("Connecting to database...")
        conn = await asyncpg.connect(DATABASE_URL)

        with open(schema_path, 'r') as f:
            sql = f.read()

        logger.info("Executing schema...")
        await conn.execute(sql)
        await conn.close()

        logger.info("Database schema initialized successfully.")
        print("✅ Database initialized successfully.")

    except Exception as e:
        logger.exception("Failed to initialize database")
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(init())