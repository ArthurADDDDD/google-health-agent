# Server deployment checklist

This is a portable Phase 2B handoff. It contains no private server details and grants no
authorization for SSH, Google OAuth, real health data, SMTP, DNS, firewall, or scheduler changes.

## 1. Reconnaissance — read only

- [ ] Confirm explicit authorization to access the private server.
- [ ] Record OS/release, CPU, memory, disk capacity, and timezone.
- [ ] Record Docker/Compose versions and existing container conventions.
- [ ] Identify host/container/managed PostgreSQL and its backup convention.
- [ ] Inventory reverse proxy, running services, and the existing Google Home service.
- [ ] Inventory listening ports, Docker-published ports, firewall rules, and proxy routes.
- [ ] Identify an existing Tailscale, WireGuard, ZeroTier, or other private network.
- [ ] Record filesystem, service-account, logging, systemd, and cron conventions.

Stop if access or ownership is unclear. Do not infer a hostname, address, account, or topology.

## 2. Baseline and backup

- [ ] Capture secret-free health/status output for existing shared services.
- [ ] Identify shared configuration that a deployment might affect.
- [ ] Back up shared proxy, Compose, firewall, or service configuration before modification.
- [ ] Record a rollback command and verify the backup is readable.
- [ ] Choose private config, state, report, log, and backup paths outside the public checkout.

## 3. Synthetic deployment

- [ ] Deploy the pinned public commit with `HEALTH_PROVIDER=synthetic`.
- [ ] Verify the container runs non-root with bounded CPU, memory, and logs.
- [ ] Verify `/healthz` and `/readyz` expose no configuration or data.
- [ ] Verify restart persistence and secret-safe logs.
- [ ] Run `healthctl doctor` and `healthctl status`; retain only secret-free evidence.

## 4. PostgreSQL

- [ ] Create a dedicated database and least-privilege non-superuser application role.
- [ ] Run the complete Alembic chain from base to head, then repeat head safely.
- [ ] Sync synthetic data and verify inserts, idempotent upserts, analytics, and data quality.
- [ ] Back up to a private archive and restore into a separate database.
- [ ] Compare row counts and run analytics plus MCP against the restored database.

## 5. Network and MCP

- [ ] Prefer an existing private network; otherwise evaluate an SSH tunnel.
- [ ] Consider authenticated HTTPS only when private-network and tunnel options are unsuitable.
- [ ] Ensure PostgreSQL is not public and MCP is not unauthenticated public.
- [ ] Set exact Host and Origin allowlists for the chosen route; no wildcards.
- [ ] Create distinct random Claude and Codex Bearer credentials outside Git.
- [ ] Verify absent/wrong tokens fail and each valid token succeeds.
- [ ] Rotate and revoke each client independently without database changes or resync.
- [ ] Verify all eight MCP tools remain read-only and bounded.

## 6. Agent, report, and scheduling — synthetic only

- [ ] Configure Claude Code and/or Codex to retrieve synthetic health facts only through MCP.
- [ ] Verify data quality is requested before overview and deeper metrics.
- [ ] Run the FakeRunner Daily Brief through PostgreSQL, MCP, and ConsoleMailer.
- [ ] Validate agent timeout, MCP/provider failure, incomplete data, and mail failure behavior.
- [ ] Configure mocked or approved SMTP only after a separate secrets review.
- [ ] Select systemd or cron based on existing server convention; do not install both.
- [ ] Apply agreed backup, report, and log retention with a dry run first.

## 7. Pre-OAuth gate

- [ ] Re-run pytest, ruff, format, strict mypy, secret/privacy scan, and GitHub CI.
- [ ] Confirm logs, reports, screenshots, and handoff notes contain no private values or data.
- [ ] Confirm the synthetic deployment rollback works.
- [ ] Obtain explicit, separate authorization for Phase 2B Google OAuth and real health data.

Until every preceding item passes, do not create a real OAuth consent session or fetch any real
Google Health data.
