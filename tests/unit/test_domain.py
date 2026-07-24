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


def test_production_mcp_requires_exact_allowlists_and_distinct_client_tokens() -> None:
    with pytest.raises(ConfigurationError, match="exact"):
        Settings(
            app_env="production",
            mcp_host="0.0.0.0",
            mcp_auth_enabled=True,
            health_mcp_token="synthetic-only-token",
            mcp_allowed_hosts="*",
            mcp_allowed_origins="*",
        )
    settings = Settings(
        app_env="production",
        mcp_host="0.0.0.0",
        mcp_auth_enabled=True,
        health_mcp_tokens=('{"claude":"synthetic-claude-token","codex":"synthetic-codex-token"}'),
        mcp_allowed_hosts="health.example.test",
        mcp_allowed_origins="https://health.example.test",
    )
    assert set(settings.mcp_token_map) == {"claude", "codex"}
    assert settings.mcp_token_map["claude"] != settings.mcp_token_map["codex"]

    with pytest.raises(ConfigurationError, match="distinct"):
        Settings(
            mcp_auth_enabled=True,
            health_mcp_tokens='{"claude":"same","codex":"same"}',
        )


def test_production_google_reports_must_not_use_console_mailer() -> None:
    with pytest.raises(ConfigurationError, match="MAILER=smtp"):
        Settings(
            app_env="production",
            health_provider="google",
            google_client_id="mock-client",
            google_client_secret="mock-secret",
            google_redirect_uri="https://health.example.test/oauth/callback",
            google_token_encryption_key="mock-encryption-key",
        )
