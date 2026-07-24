from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_alembic_upgrade_creates_storage_schema(tmp_path, monkeypatch) -> None:
    root = Path(__file__).parents[2]
    database_url = f"sqlite:///{tmp_path / 'migration.sqlite'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config(root / "alembic.ini")
    command.upgrade(config, "head")
    tables = inspect(create_engine(database_url)).get_table_names()
    assert "health_data_points" in tables
    assert "alembic_version" in tables
