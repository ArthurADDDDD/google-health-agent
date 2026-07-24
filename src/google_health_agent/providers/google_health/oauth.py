import json
import secrets
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, SecretStr

from google_health_agent.config import Settings
from google_health_agent.errors import AuthenticationRequired, ConfigurationError

GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_HEALTH_READONLY_SCOPES = (
    "https://www.googleapis.com/auth/googlehealth.sleep.readonly",
    "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
)


class TokenSet(BaseModel):
    access_token: SecretStr
    refresh_token: SecretStr | None = None
    expires_at: datetime
    scope: str = ""
    token_type: str = "Bearer"

    def expired(self, leeway_seconds: int = 60) -> bool:
        return self.expires_at <= datetime.now(UTC) + timedelta(seconds=leeway_seconds)


class TokenStore(ABC):
    @abstractmethod
    def load(self) -> TokenSet | None:
        """Load tokens without logging or exposing plaintext."""

    @abstractmethod
    def save(self, tokens: TokenSet) -> None:
        """Encrypt and persist tokens."""


class EncryptedFileTokenStore(TokenStore):
    def __init__(self, path: Path, encryption_key: SecretStr | str) -> None:
        raw_key = (
            encryption_key.get_secret_value()
            if isinstance(encryption_key, SecretStr)
            else encryption_key
        )
        try:
            self.fernet = Fernet(raw_key.encode())
        except (ValueError, TypeError) as exc:
            raise ConfigurationError("GOOGLE_TOKEN_ENCRYPTION_KEY must be a Fernet key.") from exc
        self.path = path

    def load(self) -> TokenSet | None:
        if not self.path.exists():
            return None
        try:
            plaintext = self.fernet.decrypt(self.path.read_bytes())
            return TokenSet.model_validate_json(plaintext)
        except (InvalidToken, ValueError) as exc:
            raise AuthenticationRequired("Stored Google OAuth token cannot be decrypted.") from exc

    def save(self, tokens: TokenSet) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        plaintext = json.dumps(
            {
                "access_token": tokens.access_token.get_secret_value(),
                "refresh_token": (
                    tokens.refresh_token.get_secret_value() if tokens.refresh_token else None
                ),
                "expires_at": tokens.expires_at.isoformat(),
                "scope": tokens.scope,
                "token_type": tokens.token_type,
            }
        ).encode()
        self.path.write_bytes(self.fernet.encrypt(plaintext))
        self.path.chmod(0o600)


class OAuthStateStore:
    def __init__(self) -> None:
        self._states: set[str] = set()

    def issue(self) -> str:
        state = secrets.token_urlsafe(32)
        self._states.add(state)
        return state

    def consume(self, state: str) -> None:
        if state not in self._states:
            raise AuthenticationRequired("Invalid or expired OAuth state.")
        self._states.remove(state)


class GoogleOAuthClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        required = {
            "GOOGLE_CLIENT_ID": settings.google_client_id,
            "GOOGLE_CLIENT_SECRET": settings.google_client_secret,
            "GOOGLE_REDIRECT_URI": settings.google_redirect_uri,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ConfigurationError(
                f"Google provider requires configuration: {', '.join(missing)}"
            )
        assert settings.google_client_id
        assert settings.google_client_secret
        assert settings.google_redirect_uri
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret
        self.redirect_uri = settings.google_redirect_uri
        self.client = client or httpx.AsyncClient(timeout=20)

    def authorization_url(self, state: str) -> str:
        query = urlencode(
            {
                "client_id": self.client_id.get_secret_value(),
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": " ".join(GOOGLE_HEALTH_READONLY_SCOPES),
                "access_type": "offline",
                "include_granted_scopes": "true",
                "prompt": "consent",
                "state": state,
            }
        )
        return f"{GOOGLE_AUTHORIZATION_ENDPOINT}?{query}"

    async def exchange_code(self, code: str) -> TokenSet:
        return await self._token_request(
            {
                "code": code,
                "client_id": self.client_id.get_secret_value(),
                "client_secret": self.client_secret.get_secret_value(),
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            }
        )

    async def refresh(self, refresh_token: SecretStr) -> TokenSet:
        refreshed = await self._token_request(
            {
                "client_id": self.client_id.get_secret_value(),
                "client_secret": self.client_secret.get_secret_value(),
                "refresh_token": refresh_token.get_secret_value(),
                "grant_type": "refresh_token",
            }
        )
        if refreshed.refresh_token is None:
            refreshed.refresh_token = refresh_token
        return refreshed

    async def _token_request(self, data: dict[str, str]) -> TokenSet:
        try:
            response = await self.client.post(GOOGLE_TOKEN_ENDPOINT, data=data)
        except httpx.HTTPError as exc:
            raise AuthenticationRequired("Google OAuth token endpoint is unavailable.") from exc
        if response.status_code != 200:
            raise AuthenticationRequired("Google OAuth token exchange failed.")
        try:
            payload = response.json()
            access_token = payload["access_token"]
            expires_in = int(payload["expires_in"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AuthenticationRequired(
                "Google OAuth returned a malformed token response."
            ) from exc
        return TokenSet(
            access_token=access_token,
            refresh_token=payload.get("refresh_token"),
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
            scope=str(payload.get("scope", "")),
            token_type=str(payload.get("token_type", "Bearer")),
        )
