import os
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    return None


def _db_host(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    return parsed.hostname


def _is_supabase_direct(url: str | None) -> bool:
    host = _db_host(url)
    return bool(host and host.startswith("db.") and host.endswith(".supabase.co"))


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
OWNER_ID = os.getenv("OWNER_ID")

# Runtime connection: prefer a Supabase session pooler / pooler URL.
SUPABASE_POOLER_URL = _first_env(
    "SUPABASE_POOLER_URL",
    "SUPABASE_SESSION_POOLER_URL",
    "SUPABASE_CONNECTION_POOLER_URL",
)

# Direct connection: keep this for migrations / admin scripts when explicitly set.
DIRECT_URL = _first_env("DIRECT_URL", "SUPABASE_DIRECT_URL")

# Backward-compatible runtime DB URL used by the app and most scripts.
# Order matters: pooler first, then legacy envs.
DATABASE_URL = SUPABASE_POOLER_URL or _first_env(
    "DATABASE_URL",
    "SUPABASE_DB_URL",
    "BOT_DATABASE_URL",
)

# Preferred URL for schema bootstrap / destructive maintenance tasks.
MIGRATION_DATABASE_URL = DIRECT_URL or DATABASE_URL

SUPABASE_ENDPOINT = os.getenv("SUPABASE_ENDPOINT")
SUPABASE_ACCESS_KEY_ID = os.getenv("SUPABASE_ACCESS_KEY_ID")
SUPABASE_SECRET_ACCESS_KEY = os.getenv("SUPABASE_SECRET_ACCESS_KEY")
SUPABASE_REGION = os.getenv("SUPABASE_REGION")
SUPABASE_BUCKET_NAME = os.getenv("SUPABASE_BUCKET_NAME")

missing_vars = []
for key, value in {
    "DISCORD_TOKEN": DISCORD_TOKEN,
    "OWNER_ID": OWNER_ID,
    "SUPABASE_ENDPOINT": SUPABASE_ENDPOINT,
    "SUPABASE_ACCESS_KEY_ID": SUPABASE_ACCESS_KEY_ID,
    "SUPABASE_SECRET_ACCESS_KEY": SUPABASE_SECRET_ACCESS_KEY,
    "SUPABASE_REGION": SUPABASE_REGION,
    "SUPABASE_BUCKET_NAME": SUPABASE_BUCKET_NAME,
}.items():
    if not value:
        missing_vars.append(key)

if not any([SUPABASE_POOLER_URL, DIRECT_URL, DATABASE_URL]):
    missing_vars.append(
        "one database URL (SUPABASE_POOLER_URL / DATABASE_URL / DIRECT_URL / SUPABASE_DB_URL / BOT_DATABASE_URL)"
    )

if missing_vars:
    raise RuntimeError(
        f"Missing required environment variables: {', '.join(missing_vars)}\n"
        "Please check your .env file."
    )
