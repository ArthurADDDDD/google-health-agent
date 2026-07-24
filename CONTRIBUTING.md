# Contributing

Use Python 3.12+ and uv. Do not contribute personal health data, credentials, tokens, real
emails, private endpoints, or account identifiers.

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy src/google_health_agent
uv run pytest
uv run python scripts/secret_scan.py
```

Keep provider JSON at the provider boundary, backend analytics mathematical, MCP tools
read-only, and tests synthetic. Changes to tool names, required parameters, or response schemas
are interface changes and require contract-test review. Verify Google Health behavior against
current official Google Health API v4 documentation.

