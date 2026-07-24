import io
import logging

import httpx
import pytest

from google_health_agent.config import Settings
from google_health_agent.mcp.server import create_app
from google_health_agent.observability import REDACTED, RedactingFilter


def test_redacting_filter_removes_credentials_and_passwords() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactingFilter(["synthetic-explicit-secret"]))
    logger = logging.getLogger("test-redaction")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.info(
        "Authorization: Bearer synthetic-bearer "
        "access_token=synthetic-access "
        "postgresql://app:synthetic-db-password@db/health "
        "synthetic-explicit-secret"
    )
    output = stream.getvalue()
    assert REDACTED in output
    for forbidden in (
        "synthetic-bearer",
        "synthetic-access",
        "synthetic-db-password",
        "synthetic-explicit-secret",
    ):
        assert forbidden not in output


@pytest.mark.asyncio
async def test_request_logging_never_reads_headers_or_health_payload(tmp_path, caplog) -> None:
    token = "synthetic-request-log-token"
    payload_marker = "synthetic-full-health-payload-marker"
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'logging.sqlite'}",
            mcp_auth_enabled=True,
            health_mcp_token=token,
        )
    )
    with caplog.at_level(logging.INFO, logger="google_health_agent.requests"):
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://127.0.0.1:8000",
            ) as client,
        ):
            await client.post(
                "/mcp",
                headers={"Authorization": f"Bearer {token}"},
                json={"health_data": payload_marker},
            )
    assert "request_id=" in caplog.text
    assert "path=/mcp" in caplog.text
    assert token not in caplog.text
    assert payload_marker not in caplog.text
