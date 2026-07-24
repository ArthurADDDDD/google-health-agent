from contextlib import asynccontextmanager
from datetime import date, timedelta

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import TextContent

from google_health_agent.config import Settings
from google_health_agent.mcp.server import create_app
from google_health_agent.providers.synthetic import SyntheticHealthProvider
from google_health_agent.storage import HealthRepository


@asynccontextmanager
async def mcp_session(app):
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000"
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


@pytest.fixture
async def mcp_app(tmp_path):
    repository = HealthRepository(f"sqlite:///{tmp_path / 'mcp.sqlite'}")
    repository.initialize()
    end = date(2026, 6, 30)
    points = await SyntheticHealthProvider(44).fetch(end - timedelta(days=119), end)
    repository.upsert(points)
    return create_app(
        Settings(database_url=f"sqlite:///{tmp_path / 'mcp.sqlite'}"),
        repository,
    )


@pytest.mark.asyncio
async def test_initialize_list_and_call_every_tool(mcp_app) -> None:
    async with mcp_session(mcp_app) as session:
        listed = await session.list_tools()
        expected = {
            "get_health_overview",
            "get_sleep",
            "get_recovery",
            "get_activity",
            "get_metric",
            "compare_periods",
            "get_data_quality",
            "get_daily_brief_context",
        }
        assert {tool.name for tool in listed.tools} == expected
        for tool in listed.tools:
            assert tool.annotations
            assert tool.annotations.readOnlyHint is True
            assert tool.annotations.destructiveHint is False
            assert tool.outputSchema

        calls = {
            "get_health_overview": {"days": 30, "end_date": "2026-06-30"},
            "get_sleep": {"days": 30, "end_date": "2026-06-30", "include_stages": True},
            "get_recovery": {"days": 30, "end_date": "2026-06-30"},
            "get_activity": {"days": 30, "end_date": "2026-06-30"},
            "get_metric": {
                "metric": "hrv",
                "start_date": "2026-06-01",
                "end_date": "2026-06-30",
                "granularity": "daily",
            },
            "compare_periods": {
                "metric": "hrv",
                "period_a_start": "2026-06-24",
                "period_a_end": "2026-06-30",
                "period_b_start": "2026-06-01",
                "period_b_end": "2026-06-23",
            },
            "get_data_quality": {"days": 30, "end_date": "2026-06-30"},
            "get_daily_brief_context": {"date": "2026-06-30", "lookback_days": 30},
        }
        for name, arguments in calls.items():
            result = await session.call_tool(name, arguments)
            assert not result.isError, (name, result.content)
            assert result.structuredContent
            assert result.structuredContent["data_label"] == "SYNTHETIC DATA"


@pytest.mark.asyncio
async def test_invalid_params_and_range_are_mcp_errors(mcp_app) -> None:
    async with mcp_session(mcp_app) as session:
        invalid = await session.call_tool("get_health_overview", {"days": 0})
        assert invalid.isError
        too_large = await session.call_tool("get_health_overview", {"days": 366})
        assert too_large.isError
        metric = await session.call_tool(
            "get_metric",
            {
                "metric": "hrv",
                "start_date": "2024-01-01",
                "end_date": "2026-01-01",
            },
        )
        assert metric.isError
        assert any(
            "smaller date range" in content.text
            for content in metric.content
            if isinstance(content, TextContent)
        )


@pytest.mark.asyncio
async def test_bearer_authentication(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'auth.sqlite'}"
    app = create_app(
        Settings(
            database_url=database_url,
            mcp_auth_enabled=True,
            health_mcp_token="test-only-bearer",
        )
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000"
        ) as client,
    ):
        rejected = await client.post("/mcp", json={})
        assert rejected.status_code == 401
        accepted = await client.post(
            "/mcp",
            headers={"Authorization": "Bearer test-only-bearer"},
            json={},
        )
        assert accepted.status_code != 401
