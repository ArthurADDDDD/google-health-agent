# Private deployment preparation

Phase 2A prepares a portable deployment without connecting to a private server or authorizing a
Google account. `compose.production.example.yml` is a reviewed configuration template, not a
deployment instruction. Phase 2B remains separately authorized.

## Public source and private overlay

Keep the checkout free of production configuration:

```text
public source
    ↓
private deployment overlay
    ↓
private secrets
    ↓
persistent database, encrypted tokens, reports, backups
```

A conventional Linux layout could use:

```text
/opt/google-health-agent          immutable checkout or image metadata
/etc/google-health-agent          private configuration and secret references
/var/lib/google-health-agent      persistent application state
/var/backups/google-health-agent  database backups
```

These paths are recommendations only. When server access is authorized, inspect its existing
filesystem and service conventions before choosing final locations. Never place a production
`.env`, OAuth client file, token, report, database dump, hostname, or address in the public
checkout.

## PostgreSQL and backup model

Use one application database and one login role. The application role must be
`NOSUPERUSER NOCREATEDB NOCREATEROLE` and own only its application database and schema. Do not
run the service as the PostgreSQL superuser. An administrator performs database/role creation
and restore operations; the application role runs Alembic migrations and normal queries.

Portable logical backup and restore shape:

```bash
pg_dump --format=custom --no-owner --no-acl \
  --dbname "$APP_DATABASE_DSN" --file "$BACKUP_ARCHIVE"

createdb --maintenance-db "$ADMIN_DATABASE_DSN" \
  --owner "$APP_DATABASE_ROLE" "$RESTORE_DATABASE"

pg_restore --exit-on-error --no-owner --no-acl \
  --dbname "$RESTORE_DATABASE_DSN" "$BACKUP_ARCHIVE"
```

Restore into a separate database, compare observation counts, then run analytics, data-quality,
and MCP smoke tests. Do not overwrite the source database to test recovery. The exact commands
must be adjusted after discovering whether the server uses a host PostgreSQL, a container, or a
managed service. CI performs this complete backup/restore procedure against synthetic data.

## Network choices

Choose only after server reconnaissance, in this order:

1. Reuse an existing private overlay network such as Tailscale, WireGuard, or ZeroTier.
2. Keep MCP on localhost and use an SSH tunnel from the client.
3. Use authenticated HTTPS only if the first two are unsuitable.

The HTTPS option requires TLS, independent Bearer credentials, exact Host and Origin allowlists,
and reverse-proxy rate limits. PostgreSQL must not be publicly reachable, and unauthenticated MCP
must never be public. Before changing anything, record listening ports, Docker-published ports,
firewall rules, reverse-proxy routes, and existing services. Back up any shared configuration.

## Secret and key placement

Provide secrets to Compose from a private environment file or a host secret manager outside the
checkout. Limit the file to the service account. Store the OAuth encryption key separately from
the encrypted token file and database backups; otherwise a stolen backup set contains both the
ciphertext and its key. Claude and Codex receive distinct MCP tokens via their own process
environments. Rotation replaces one client token at a time and requires neither a database
rebuild nor a data resync.

Recommended permissions, adjusted for the server's service account and backup tooling:

| Material | Suggested access |
| --- | --- |
| Private configuration directory | owner/service group only (`0750`) |
| Environment and key files | owner only (`0600`) |
| Encrypted OAuth token | owner only (`0600`) |
| Reports and database backups | owner/service group only (`0640`) |
| State, report, backup, and log directories | owner/service group only (`0750`) |

No health-data-related file should be world-readable.

## Resource and log defaults

For a single-user service, begin conservatively: one CPU and about 1 GiB for the MCP container,
a small database connection pool, a five-minute agent timeout, and size-rotated container logs.
The production Compose example applies the container and log limits. Agent CLIs and PostgreSQL
need their own measured budgets. Inspect actual server capacity and existing workloads before
changing these defaults; do not reserve most of a small host without evidence.

Application INFO logs are metadata-only. Keep request IDs, method/path, status, duration, row
count, provider, and success/failure. Never collect authorization headers, OAuth codes or tokens,
database/SMTP passwords, query strings, request bodies, full payloads, or report content.

## Retention policy template

Agree on a private policy before real data exists. A reasonable starting point is:

- daily database backups for 14 days and weekly backups for 8 weeks;
- generated reports for 30 days, extending to 90 only when useful;
- application and proxy logs for 14 days, capped by size and at most 30 days;
- encrypted OAuth tokens only while authorization is active.

Retention jobs must support a dry run, operate only on resolved private directories, and never
follow broad or unresolved paths. Phase 2A does not delete any files.

## Scheduler alternatives

Scheduling remains outside the application. After reconnaissance, use the server's existing
convention. A systemd-oriented host can create a private oneshot service and timer whose
`ExecStart` runs `healthctl sync` followed by `healthctl brief`. A cron-oriented host can run an
equivalent private wrapper:

```cron
# Example only; resolve the private wrapper path after server reconnaissance.
15 6 * * * /opt/google-health-agent/private/run-daily-brief
```

The wrapper must fail on sync errors, use a bounded agent timeout, avoid command-line secrets,
and preserve a generated report if mail delivery fails. Do not install either scheduler until
the server baseline and backup are recorded.

## Phase 2B real-data ramp

Even after explicit OAuth authorization, import only a minimal smoke sample, then 1–3 days,
7 days, 30 days, and 90 days. At every step review source overlap, civil dates/timezone changes,
missing data, delayed sync, and counts. Never sum overlapping Fitbit, phone, and Health Connect
steps without applying the configured source preference.

See [SERVER_DEPLOYMENT_CHECKLIST.md](../SERVER_DEPLOYMENT_CHECKLIST.md) for the ordered handoff.
