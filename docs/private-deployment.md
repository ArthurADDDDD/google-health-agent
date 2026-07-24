# Private Deployment Phase

This document is planning only. Do not perform these steps until the owner explicitly starts
the Private Deployment Phase.

A future personal deployment will need a Linux server, HTTPS reverse proxy, PostgreSQL, a
Google Cloud Web Application OAuth client, Google Health API access, encrypted token storage,
separate rotating MCP bearer tokens, installed Claude Code and/or Codex CLIs, SMTP, and an
external systemd timer or cron entry.

Example topology:

```text
health.example.com → HTTPS proxy → Google Health Agent → PostgreSQL
                                      ↘ Claude/Codex via MCP
```

Before enabling Google provider: create secrets outside Git, register the exact HTTPS callback,
run database migrations, set least-privilege readonly scopes, establish backup/restore and key
rotation, verify authorization and revocation, and complete a private data-retention review.

