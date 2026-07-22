from pathlib import Path

from alembic.config import Config

from alembic import command
from app.database import ensure_sqlite_parent

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def alembic_config(database_url: str) -> Config:
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def upgrade_database(database_url: str) -> None:
    ensure_sqlite_parent(database_url)
    command.upgrade(alembic_config(database_url), "head")
