# Security design

The public phase contains only code and deterministic synthetic scenarios. `.env`, databases,
raw data, reports, credentials, token files, private keys, and virtual environments are
gitignored. `.env.example` contains empty secrets and safe demo defaults.

MCP is localhost-only by default. Settings reject a non-loopback host unless authentication,
one or more distinct client bearer tokens, and explicit allowed Host and Origin patterns all
exist. Production rejects wildcard allowlists. FastMCP transport security validates those
patterns to mitigate DNS rebinding. Individual Claude and Codex credentials can be revoked or
rotated without resyncing or deleting the database. The server provides no write,
SQL, shell, arbitrary HTTP, or file tools. Requests are bounded to control health-data exposure
and agent context.

Google OAuth follows Web Server flow, validates single-use state, requests readonly scopes,
stores encrypted tokens with mode `0600`, supports revoke/delete and key rotation, and returns
no token to the browser. Logs contain request ID/method/path/status/duration metadata only,
never request headers, query strings, bodies, secrets, full health payloads, or report content.

No Sentry, telemetry, analytics, cloud logging, or external monitoring is enabled. CI uses
synthetic data and requires no secret. `scripts/secret_scan.py` rejects common credentials,
private keys, non-example emails, personal paths, public health-data files, and non-demo IP
addresses before publication.
