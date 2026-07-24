# Google Health Agent contributor guidance

Google Health Agent is a self-hosted facts and statistics service for read-only AI agent
analysis. Preserve `Provider → Domain → Storage → Analytics → MCP → Agent`.

- Do not bypass provider abstraction or let external JSON leak into storage/analytics.
- Do not add medical judgments, diagnoses, or fixed health recommendations to the backend.
- Never add real credentials, tokens, personal health data, emails, domains, or server details.
- Tests and public fixtures use only clearly labelled synthetic data.
- MCP health tools remain read-only and bounded; never add SQL, shell, arbitrary fetch, or file
  access tools.
- Never log OAuth codes, access/refresh tokens, MCP tokens, SMTP passwords, or full payloads.
- Verify Google Health changes against current official API v4 documentation; never use the
  legacy Fitbit Web API.
- Follow [agent analysis guidelines](docs/agent-analysis-guidelines.md).

## Health Review Workflow

For a request to review health, sleep, recovery, or Fitbit-derived Google Health data:

1. Call `get_data_quality`.
2. Call `get_health_overview`.
3. Request sleep, recovery, or activity details only when useful.
4. Use `get_metric` for bounded deeper history.
5. Compare the recent 7 days with the prior 23 days.
6. Separate facts, statistical changes, possible associations, and suggestions.
7. Do not diagnose disease.
8. State uncertainty and reduce confidence for incomplete data.
9. Never treat missing data as zero.
10. Never treat one unusual day as a long-term trend.

