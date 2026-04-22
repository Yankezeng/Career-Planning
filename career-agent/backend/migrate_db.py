"""Run database schema migrations for the configured database.

This script intentionally reads DATABASE_URL from app.core.config instead of
hard-coding a local SQLite path. It can be used for both SQLite and MySQL.
"""
from __future__ import annotations

from app.core.config import get_settings
from app.core.database import init_db


def _mask_database_url(url: str) -> str:
    if "@" not in url or "://" not in url:
        return url

    scheme, rest = url.split("://", 1)
    credentials, host = rest.split("@", 1)
    if ":" not in credentials:
        return f"{scheme}://***@{host}"

    username, _password = credentials.split(":", 1)
    return f"{scheme}://{username}:***@{host}"


def main() -> None:
    settings = get_settings()
    print(f"Running migrations for: {_mask_database_url(settings.DATABASE_URL)}")
    init_db()
    print("Migration completed.")


if __name__ == "__main__":
    main()
