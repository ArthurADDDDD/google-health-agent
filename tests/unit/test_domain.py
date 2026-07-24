from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from google_health_agent.config import Settings
from google_health_agent.domain import DataSource, HealthDataPoint
from google_health_agent.errors import ConfigurationError


def test_datapoint_requires_aware_ordered_timestamps() -> None:
    with pytest.raises(ValidationError):
        HealthDataPoint(
            external_id="x",
            metric="steps",
            value=1,
            unit="count",
            start_time=datetime(2026, 1, 2, tzinfo=UTC),
            end_time=datetime(2026, 1, 1, tzinfo=UTC),
            utc_offset_minutes=480,
            civil_date=date(2026, 1, 1),
            source=DataSource(platform="SYNTHETIC", source="test"),
            ingested_at=datetime.now(UTC),
        )


def test_nonlocal_mcp_requires_auth_and_transport_allowlists() -> None:
    with pytest.raises(ConfigurationError, match="authentication"):
        Settings(mcp_host="0.0.0.0")
    with pytest.raises(ConfigurationError, match="MCP_ALLOWED"):
        Settings(
            mcp_host="0.0.0.0",
            mcp_auth_enabled=True,
            health_mcp_token="test-only",
        )
    settings = Settings(
        mcp_host="0.0.0.0",
        mcp_auth_enabled=True,
        health_mcp_token="test-only",
        mcp_allowed_hosts="localhost:*,127.0.0.1:*",
        mcp_allowed_origins="http://localhost:*",
    )
    assert settings.allowed_host_patterns == ["localhost:*", "127.0.0.1:*"]
