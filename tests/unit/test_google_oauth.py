from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.fernet import Fernet

from google_health_agent.config import Settings
from google_health_agent.errors import AuthenticationRequired
from google_health_agent.providers.google_health import (
    GOOGLE_HEALTH_READONLY_SCOPES,
    EncryptedFileTokenStore,
    GoogleOAuthClient,
    OAuthStateStore,
    TokenSet,
)


def _settings() -> Settings:
    return Settings(
        google_client_id="test-client",
        google_client_secret="test-secret",
        google_redirect_uri="https://health.example.com/oauth/google-health/callback",
    )


def test_authorization_url_is_web_server_offline_and_readonly() -> None:
    url = GoogleOAuthClient(_settings(), httpx.AsyncClient()).authorization_url("state")
    query = parse_qs(urlparse(url).query)
    assert query["response_type"] == ["code"]
    assert query["access_type"] == ["offline"]
    assert query["state"] == ["state"]
    assert set(query["scope"][0].split()) == set(GOOGLE_HEALTH_READONLY_SCOPES)
    assert all("write" not in scope for scope in GOOGLE_HEALTH_READONLY_SCOPES)


def test_state_is_single_use() -> None:
    store = OAuthStateStore()
    state = store.issue()
    store.consume(state)
    with pytest.raises(AuthenticationRequired):
        store.consume(state)


def test_encrypted_token_store_never_writes_plaintext(tmp_path) -> None:
    path = tmp_path / "token.enc"
    store = EncryptedFileTokenStore(path, Fernet.generate_key().decode())
    tokens = TokenSet(
        access_token="access-test-value",
        refresh_token="refresh-test-value",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    store.save(tokens)
    raw = path.read_bytes()
    assert b"access-test-value" not in raw
    assert b"refresh-test-value" not in raw
    loaded = store.load()
    assert loaded
    assert loaded.access_token.get_secret_value() == "access-test-value"
    assert path.stat().st_mode & 0o777 == 0o600


def test_encryption_key_rotation_and_local_revocation(tmp_path) -> None:
    path = tmp_path / "token.enc"
    key_a = Fernet.generate_key().decode()
    key_b = Fernet.generate_key().decode()
    store = EncryptedFileTokenStore(path, key_a)
    store.save(
        TokenSet(
            access_token="fake-rotating-access",
            refresh_token="fake-rotating-refresh",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    ciphertext_a = path.read_bytes()
    store.rotate_key(key_b)
    ciphertext_b = path.read_bytes()
    assert ciphertext_b != ciphertext_a
    with pytest.raises(AuthenticationRequired):
        EncryptedFileTokenStore(path, key_a).load()
    loaded = EncryptedFileTokenStore(path, key_b).load()
    assert loaded
    assert loaded.refresh_token
    assert loaded.refresh_token.get_secret_value() == "fake-rotating-refresh"

    store.delete()
    assert store.load() is None
    assert not path.exists()
