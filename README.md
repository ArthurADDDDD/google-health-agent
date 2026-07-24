# Google Health Agent

Google Health data pipeline and MCP server for AI agent analysis with Claude Code and Codex.

> **Public Architecture / Demo Phase:** this repository uses only deterministic
> **SYNTHETIC DATA**. It contains no personal health data or credentials.

Google Health Agent is a local-first, self-hosted, read-only facts and statistics layer. It is
not a chatbot, medical device, diagnostic system, medical advice service, or hosted SaaS.

## Development quick start

```bash
uv sync
uv run healthctl demo
uv run healthctl doctor
uv run healthctl serve
```

The demo MCP endpoint is `http://127.0.0.1:8000/mcp`. Full architecture, agent setup,
security notes, and bilingual documentation are completed as verified milestones in Phase 1.

