import asyncio
import asyncpg
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DATABASE_URL
from utils.logger import get_logger

logger = get_logger(__name__)

async def init():
    """Initialize the database schema."""
    try:
        # Ensure the schema.sql file exists
        schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
        if not schema_path.exists():
            logger.error(f"Schema file not found at {schema_path}")
            sys.exit(1)

        # Connect to the database
        logger.info(f"Connecting to database...")
        conn = await asyncpg.connect(DATABASE_URL)

        # Read and execute the schema
        with open(schema_path, 'r') as f:
            sql = f.read()

        logger.info("Executing schema...")
        await conn.execute(sql)
        await conn.close()

        logger.info("✅ Database schema initialized successfully.")
        print("Database initialized successfully.")

    except Exception as e:
        logger.exception("Failed to initialize database")
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(init())