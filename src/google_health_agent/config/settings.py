from functools import lru_cache
from ipaddress import ip_address
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from google_health_agent.errors import ConfigurationError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["demo", "test", "production"] = "demo"
    health_provider: Literal["synthetic", "google"] = "synthetic"
    synthetic_seed: int = 20260724
    database_url: str = "sqlite:///./data/demo.sqlite"
    mcp_host: str = "127.0.0.1"
    mcp_port: int = Field(8000, ge=1, le=65535)
    mcp_auth_enabled: bool = False
    health_mcp_token: SecretStr | None = None
    google_client_id: SecretStr | None = None
    google_client_secret: SecretStr | None = None
    google_redirect_uri: str | None = None
    google_token_encryption_key: SecretStr | None = None
    mailer: Literal["console", "smtp"] = "console"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    mail_from: str | None = None
    mail_to: str | None = None
    daily_brief_agent: Literal["fake", "claude", "codex"] = "fake"

    @model_validator(mode="after")
    def secure_non_local_bind(self) -> "Settings":
        try:
            is_loopback = ip_address(self.mcp_host).is_loopback
        except ValueError:
            is_loopback = self.mcp_host == "localhost"
        if not is_loopback and not self.mcp_auth_enabled:
            raise ConfigurationError("MCP authentication is required for non-localhost binding.")
        if self.mcp_auth_enabled and not self.health_mcp_token:
            raise ConfigurationError(
                "HEALTH_MCP_TOKEN is required when MCP authentication is enabled."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
