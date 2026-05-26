import asyncio
import asyncpg
import sys
from pathlib import Path
from config.settings import MIGRATION_DATABASE_URL
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
        conn = await asyncpg.connect(MIGRATION_DATABASE_URL)

        with open(schema_path, 'r') as f:
            sql = f.read()

        logger.info("Executing schema...")
        await conn.execute(sql)
        await conn.execute('ALTER TABLE supplier ADD COLUMN IF NOT EXISTS submitter_display TEXT;')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_recruitment_status ON recruitment(status);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_progress_report_status ON progress_report(status);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_purchase_invoice_status ON purchase_invoice(status);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_mall_shop_status ON mall_shop(status);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_supplier_status ON supplier(status);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_demolition_report_status ON demolition_report(status);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_demolition_request_status ON demolition_request(status);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_eviction_report_status ON eviction_report(status);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_scroll_completion_status ON scroll_completion(status);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_reputation_log_staff_created ON reputation_log(staff_id, created_at DESC);')
        await conn.close()

        logger.info("Database schema initialized successfully.")
        print("✅ Database initialized successfully.")

    except Exception as e:
        logger.exception("Failed to initialize database")
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(init())
