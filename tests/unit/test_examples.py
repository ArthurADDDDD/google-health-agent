import json
import tomllib
from pathlib import Path


def test_agent_example_configs_parse() -> None:
    root = Path(__file__).parents[2]
    claude = json.loads((root / "examples/claude/.mcp.json.example").read_text())
    server = claude["mcpServers"]["google-health-agent"]
    assert server["type"] == "http"
    assert server["url"].endswith("/mcp}")
    assert "${HEALTH_MCP_CLAUDE_TOKEN}" in server["headers"]["Authorization"]

    codex = tomllib.loads((root / "examples/codex/config.toml.example").read_text())
    configured = codex["mcp_servers"]["google_health_agent"]
    assert configured["url"] == "http://127.0.0.1:8000/mcp"
    assert configured["bearer_token_env_var"] == "HEALTH_MCP_CODEX_TOKEN"


def test_public_environment_has_no_secret_values() -> None:
    root = Path(__file__).parents[2]
    values = {}
    for line in (root / ".env.example").read_text().splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    for key in (
        "HEALTH_MCP_TOKEN",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REDIRECT_URI",
        "GOOGLE_TOKEN_ENCRYPTION_KEY",
        "SMTP_PASSWORD",
        "MAIL_FROM",
        "MAIL_TO",
    ):
        assert values[key] == ""
