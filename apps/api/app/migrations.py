from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from .config import settings


def run_migrations() -> None:
    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url_alchemy)
    command.upgrade(config, "head")
