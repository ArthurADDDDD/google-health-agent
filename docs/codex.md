# Codex

Codex connects to Google Health Agent through MCP only. The current Codex CLI supports:

```bash
codex mcp add google_health_agent \
  --url http://127.0.0.1:8000/mcp \
  --bearer-token-env-var HEALTH_MCP_CODEX_TOKEN
```

The reviewed TOML form is:

```toml
[mcp_servers.google_health_agent]
url = "http://127.0.0.1:8000/mcp"
bearer_token_env_var = "HEALTH_MCP_CODEX_TOKEN"
```

The URL is literal TOML; this project does not claim environment interpolation for it. The
token value lives only in the named environment variable and should be distinct from the Claude
Code credential. The Daily Brief runner uses the
current non-interactive `codex exec --ephemeral --output-last-message <file>` interface.

See the official [Codex MCP documentation](https://developers.openai.com/codex/mcp/) and
[configuration reference](https://developers.openai.com/codex/config-reference/).
