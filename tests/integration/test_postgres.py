from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import date, timedelta

import httpx
import pytest
from alembic.config import Config
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import text

from alembic import command
from google_health_agent.brief.workflow import run_brief
from google_health_agent.config import Settings
from google_health_agent.mcp.server import create_app
from google_health_agent.providers.synthetic import SyntheticHealthProvider
from google_health_agent.service import HealthService
from google_health_agent.storage import HealthRepository

POSTGRES_TEST_URL = os.environ.get("POSTGRES_TEST_URL")
pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not POSTGRES_TEST_URL, reason="isolated PostgreSQL is unavailable"),
]


@asynccontextmanager
async def _session(app):
    headers = {"Authorization": "Bearer synthetic-postgres-mcp-token"}
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://127.0.0.1:8000",
            headers=headers,
        ) as client,
        streamable_http_client("http://127.0.0.1:8000/mcp", http_client=client) as (
            read,
            write,
            _,
        ),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        yield session


@pytest.mark.asyncio
async def test_postgres_migration_storage_analytics_and_mcp(monkeypatch) -> None:
    assert POSTGRES_TEST_URL
    monkeypatch.setenv("DATABASE_URL", POSTGRES_TEST_URL)
    alembic = Config("alembic.ini")
    command.downgrade(alembic, "base")
    command.upgrade(alembic, "head")
    command.upgrade(alembic, "head")

    repository = HealthRepository(POSTGRES_TEST_URL)
    assert repository.engine.dialect.name == "postgresql"
    with repository.engine.connect() as connection:
        role = connection.execute(
            text(
                "SELECT current_user, rolsuper, rolcreatedb, rolcreaterole "
                "FROM pg_roles WHERE rolname = current_user"
            )
        ).one()
    assert role[0] == "google_health_agent_test"
    assert role[1:] == (False, False, False)

    end = date(2026, 7, 24)
    points = await SyntheticHealthProvider(20260724).fetch(end - timedelta(days=119), end)
    repository.upsert(points)
    repository.upsert(points)
    assert repository.count() == len(points)

    service = HealthService(repository)
    overview = service.overview(30, end)
    assert overview["data_label"] == "SYNTHETIC DATA"
    assert overview["summaries"]["steps"]["count"] > 0
    assert service.quality(30, end)["completeness"] > 0

    settings = Settings(
        app_env="test",
        database_url=POSTGRES_TEST_URL,
        mcp_auth_enabled=True,
        health_mcp_token="synthetic-postgres-mcp-token",
    )
    async with _session(create_app(settings, repository)) as session:
        result = await session.call_tool(
            "get_health_overview",
            {"days": 30, "end_date": end.isoformat()},
        )
        assert not result.isError
        assert result.structuredContent
        assert result.structuredContent["data_label"] == "SYNTHETIC DATA"


@pytest.mark.asyncio
async def test_restored_postgres_supports_analytics_and_mcp() -> None:
    restored_url = os.environ.get("POSTGRES_RESTORE_URL")
    if not restored_url:
        pytest.skip("restored PostgreSQL database is unavailable")
    repository = HealthRepository(restored_url)
    assert repository.count() > 0
    end = date(2026, 7, 24)
    overview = HealthService(repository).overview(30, end)
    assert overview["summaries"]["steps"]["count"] > 0

    settings = Settings(
        app_env="test",
        database_url=restored_url,
        mcp_auth_enabled=True,
        health_mcp_token="synthetic-postgres-mcp-token",
    )
    async with _session(create_app(settings, repository)) as session:
        result = await session.call_tool("get_data_quality", {"days": 30, "end_date": "2026-07-24"})
        assert not result.isError
        assert result.structuredContent


def test_postgres_authenticated_fake_daily_brief(tmp_path, monkeypatch, capsys) -> None:
    assert POSTGRES_TEST_URL
    monkeypatch.chdir(tmp_path)
    repository = HealthRepository(POSTGRES_TEST_URL)
    repository.initialize()
    end = date.today()
    import asyncio

    points = asyncio.run(SyntheticHealthProvider(20260724).fetch(end - timedelta(days=119), end))
    repository.replace_synthetic(points)
    settings = Settings(
        app_env="test",
        database_url=POSTGRES_TEST_URL,
        mcp_auth_enabled=True,
        health_mcp_tokens=(
            '{"fake":"synthetic-postgres-fake-token",'
            '"claude":"synthetic-postgres-claude-token",'
            '"codex":"synthetic-postgres-codex-token"}'
        ),
    )
    output = run_brief("fake", False, settings)
    assert output and output.exists()
    report = output.read_text()
    assert "SYNTHETIC DATA" in report
    assert "Data completeness" in report
    assert "Health Brief" in capsys.readouterr().out
