import asyncio
import asyncpg
import sys
import argparse
from pathlib import Path
from config.settings import DATABASE_URL
from utils.logger import get_logger

logger = get_logger(__name__)

# Tables that can be reset (excludes guild_config, user_roles, staff_member)
RESET_TABLES = [
    "reputation_log",
    "scroll_completion",
    "eviction_report",
    "demolition_request",
    "demolition_report",
    "purchase_invoice",
    "progress_report",
    "recruitment"
]


async def reset_tables(tables: list):
    """Drop and recreate the specified tables."""
    conn = await asyncpg.connect(DATABASE_URL)
    schema_path = Path(__file__).parent / "database" / "schema.sql"

    for table in tables:
        await conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        print(f"Dropped {table}")

    # Recreate schema (only the dropped tables will be recreated)
    with open(schema_path, 'r') as f:
        sql = f.read()
    await conn.execute(sql)
    await conn.close()
    print("[OK] Tables reset complete.")


def interactive_selection():
    """Show interactive menu to select tables."""
    print("Select tables to reset (enter numbers separated by spaces, or 'all'):")
    for idx, table in enumerate(RESET_TABLES, 1):
        print(f"{idx}. {table}")
    choice = input("\nYour choice: ").strip().lower()
    if choice == 'all':
        return RESET_TABLES.copy()
    try:
        indices = [int(x) for x in choice.split()]
        selected = [RESET_TABLES[i-1] for i in indices if 1 <= i <= len(RESET_TABLES)]
        if not selected:
            print("No valid tables selected. Aborting.")
            sys.exit(1)
        return selected
    except ValueError:
        print("Invalid input. Aborting.")
        sys.exit(1)


async def main():
    parser = argparse.ArgumentParser(description="Reset specific form tables in the database.")
    parser.add_argument("--tables", nargs="+", choices=RESET_TABLES,
                        help="List of tables to reset (e.g., --tables recruitment progress_report)")
    parser.add_argument("--all", action="store_true", help="Reset all form tables")
    args = parser.parse_args()

    if args.all:
        tables_to_reset = RESET_TABLES.copy()
    elif args.tables:
        tables_to_reset = args.tables
    else:
        tables_to_reset = interactive_selection()

    print(f"\n⚠️  WARNING: You are about to reset the following tables:")
    for t in tables_to_reset:
        print(f"  - {t}")
    print("Staff roles and member profiles will be preserved.\n")
    confirm = input("Continue? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Aborted.")
        return

    await reset_tables(tables_to_reset)


if __name__ == "__main__":
    asyncio.run(main())