# Architecture

Google Health Agent separates collection from interpretation:

```text
Provider → Domain → Storage → Analytics/Data Quality → MCP → External Agent
```

Providers normalize external records into immutable domain points carrying physical UTC time,
UTC offset, civil date, source platform, recording method, device, external ID, and ingestion
time. Storage and analytics never depend on Google JSON. SQLAlchemy isolates SQLite demo/test
storage from PostgreSQL production storage.

The analytics layer returns descriptive statistics, robust personal-baseline comparisons, and
transparent MAD/IQR-based unusual-point flags. It does not use population thresholds or
produce diagnoses. Data quality is first-class: missing days, timezone changes, source changes,
and step overlaps travel with MCP results.

FastMCP exposes only eight bounded read tools over Streamable HTTP. Claude Code and Codex are
external clients; the core does not import either vendor SDK. Daily Brief runners invoke
already-installed CLIs and never give them database access.

Phase 1 is single-person and synthetic-first. Multi-tenant account management, write tools,
model-hosting, and server scheduling are intentionally outside the specification.

