from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from cryptography.fernet import Fernet

from google_health_agent.config import Settings
from google_health_agent.mcp.server import create_app


@pytest.mark.asyncio
@respx.mock
async def test_oauth_web_server_routes_store_encrypted_tokens(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "route-mock-access",
                "refresh_token": "route-mock-refresh",
                "expires_in": 3600,
            },
        )
    )
    settings = Settings(
        health_provider="google",
        database_url=f"sqlite:///{tmp_path / 'oauth.sqlite'}",
        google_client_id="route-mock-client",
        google_client_secret="route-mock-secret",
        google_redirect_uri="http://127.0.0.1:8000/oauth/google-health/callback",
        google_token_encryption_key=Fernet.generate_key().decode(),
    )
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://127.0.0.1:8000",
            follow_redirects=False,
        ) as client,
    ):
        login = await client.get("/oauth/google-health/login")
        assert login.status_code in {302, 307}
        query = parse_qs(urlparse(login.headers["location"]).query)
        assert query["access_type"] == ["offline"]
        callback = await client.get(
            "/oauth/google-health/callback",
            params={"code": "route-mock-code", "state": query["state"][0]},
        )
        assert callback.status_code == 200
        assert "access_token" not in callback.text
        assert "refresh_token" not in callback.text

    encrypted = (tmp_path / "credentials/google-health-token.enc").read_bytes()
    assert b"route-mock-access" not in encrypted
    assert b"route-mock-refresh" not in encrypted
