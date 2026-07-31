import json
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
    health_mcp_tokens: SecretStr | None = None
    mcp_allowed_hosts: str = ""
    mcp_allowed_origins: str = ""
    preferred_step_source: str | None = None
    google_client_id: SecretStr | None = None
    google_client_secret: SecretStr | None = None
    google_redirect_uri: str | None = None
    google_token_encryption_key: SecretStr | None = None
    mailer: Literal["console", "disabled", "smtp"] = "console"
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
        if not is_loopback and (
            not self.mcp_allowed_hosts.strip() or not self.mcp_allowed_origins.strip()
        ):
            raise ConfigurationError(
                "MCP_ALLOWED_HOSTS and MCP_ALLOWED_ORIGINS are required for non-localhost binding."
            )
        if self.health_mcp_token and self.health_mcp_tokens:
            raise ConfigurationError("Configure HEALTH_MCP_TOKEN or HEALTH_MCP_TOKENS, not both.")
        if self.mcp_auth_enabled and not self.mcp_token_map:
            raise ConfigurationError(
                "HEALTH_MCP_TOKEN or HEALTH_MCP_TOKENS is required when MCP authentication "
                "is enabled."
            )
        if self.app_env == "production" and (
            any("*" in item for item in self.allowed_host_patterns)
            or any("*" in item for item in self.allowed_origin_patterns)
        ):
            raise ConfigurationError(
                "Production MCP Host and Origin allowlists must use exact values."
            )
        if (
            self.app_env == "production"
            and self.health_provider == "google"
            and self.mailer == "console"
        ):
            raise ConfigurationError(
                "Production Google Health deployments require MAILER=disabled or MAILER=smtp "
                "so private reports are not printed to process output."
            )
        return self

    @property
    def mcp_token_map(self) -> dict[str, str]:
        if self.health_mcp_token:
            return {"default": self.health_mcp_token.get_secret_value()}
        if not self.health_mcp_tokens:
            return {}
        try:
            value = json.loads(self.health_mcp_tokens.get_secret_value())
        except json.JSONDecodeError as exc:
            raise ConfigurationError("HEALTH_MCP_TOKENS must be a JSON object.") from exc
        if not isinstance(value, dict) or not value:
            raise ConfigurationError("HEALTH_MCP_TOKENS must be a non-empty JSON object.")
        if not all(
            isinstance(label, str) and label and isinstance(token, str) and token
            for label, token in value.items()
        ):
            raise ConfigurationError("HEALTH_MCP_TOKENS must map client labels to tokens.")
        if len(set(value.values())) != len(value):
            raise ConfigurationError("Each MCP client must have a distinct token.")
        return value

    @property
    def allowed_host_patterns(self) -> list[str]:
        return [item.strip() for item in self.mcp_allowed_hosts.split(",") if item.strip()]

    @property
    def allowed_origin_patterns(self) -> list[str]:
        return [item.strip() for item in self.mcp_allowed_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
