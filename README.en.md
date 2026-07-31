# Google Health Claude Bridge

> Bring device-recorded Google Health data into Claude conversations through a self-hosted, read-only MCP service.

[中文说明](README.md)

Google Health Claude Bridge reads Google Health API v4 data, stores it on your own machine or server, and exposes bounded read-only MCP tools to Claude. It is designed for Google Health, Fitbit, and Pixel Watch users who want Claude to understand sleep, activity, recovery, and long-term trends.

It is not an Apple Health importer, a medical device, or a diagnostic service.

## Supported data

- Sleep records and duration
- Steps, activity minutes, sedentary time, and exercise
- HRV, resting heart rate, SpO2, and respiratory rate
- Sleep temperature derivations
- Weight
- Period comparisons, data-quality warnings, source overlap, and timezone changes

## MCP tools

- `get_health_overview`
- `get_sleep`
- `get_recovery`
- `get_activity`
- `get_metric`
- `compare_periods`
- `get_data_quality`
- `get_daily_brief_context`

```text
Google Health API v4
        ↓
Your machine, server, and database
        ↓
Read-only MCP
        ↓
Claude web / mobile / Desktop / Claude Code
```

## Plan availability

Claude remote custom connectors are currently available on Free, Pro, Max, Team, and Enterprise plans. Free users can add one custom connector.

Official documentation: <https://support.claude.com/en/articles/11175166>

ChatGPT and Codex are secondary compatible clients. Their plan requirements and MCP availability may vary by account, region, and product mode; refer to the current OpenAI documentation and your account interface.

Official documentation: <https://help.openai.com/en/articles/11487775-connectors-in>

---

# Choose a deployment mode first

The project does **not** inherently require Linux, a domain, or Cloudflare. It is a Python 3.12+ service and can also run on macOS, Windows, a NAS, or a container-capable system.

The commands below use an **Ubuntu/Debian Linux server** as the reference environment because it is the most common choice for long-running deployments. Other systems need equivalent paths, permissions, and service management.

| Mode | Public IP | Domain | Cloudflare | Claude web/mobile | Claude Code/Codex |
| --- | --- | --- | --- | --- | --- |
| Local or SSH tunnel | No | No | No | No remote access | Yes |
| Direct public deployment | Yes | Required for production | No | Yes, with HTTPS and an OAuth gateway | Yes |
| Cloudflare Tunnel | No | Required for production | Yes | Yes, easiest remote setup | Yes |
| Quick Tunnel test | No | No | Yes | Temporary testing only | Temporary testing only |

Key points:

- Linux is the example environment, not a hard dependency.
- Cloudflare is optional. A server with a public IP can use Nginx, Caddy, Traefik, or an existing reverse proxy.
- A public IP can replace Cloudflare Tunnel, but it does not fully replace a stable production hostname. Google OAuth callbacks and remote Claude connectors should use a stable HTTPS hostname rather than a raw IP.
- Claude Code, Codex, and other local MCP clients can work through an SSH tunnel without a domain, Cloudflare, or a public web endpoint.
- Never expose real health data through an unauthenticated public MCP endpoint.

Recommended choices:

- Claude Code on your own computer: use the **local/SSH tunnel** mode.
- Existing public server, domain, TLS, and identity gateway: use **direct public deployment**.
- Claude web or mobile without opening inbound server ports: use **Cloudflare Tunnel + Access**.

---

# Common installation

## 1. Requirements

Base requirements:

- A machine, NAS, or server capable of running Python 3.12+
- Git
- A Google Cloud project
- Google Health API access
- A Google OAuth Web client

The Linux example also uses `systemd`, `curl`, and `uv`.

```bash
python3 --version
git --version

curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.profile
uv --version
```

## 2. Install the project

```bash
sudo mkdir -p /opt/google-health-claude-bridge
sudo chown "$USER":"$USER" /opt/google-health-claude-bridge

git clone https://github.com/ArthurADDDDD/google-health-claude-bridge.git \
  /opt/google-health-claude-bridge
cd /opt/google-health-claude-bridge

uv sync --locked
mkdir -p data credentials reports
chmod 700 data credentials reports
```

On Windows, macOS, or a NAS, use any writable project directory instead of `/opt`.

## 3. Choose the Google OAuth redirect URI

Local or SSH tunnel:

```text
http://localhost:8000/oauth/google-health/callback
```

Direct public deployment or Cloudflare Tunnel:

```text
https://health.example.com/oauth/google-health/callback
```

Replace `health.example.com` with your real hostname.

## 4. Configure Google OAuth

In Google Cloud:

1. Enable Google Health API.
2. Configure an External OAuth consent screen.
3. Add your Google account as a test user while the app is in testing mode.
4. Create a Web application OAuth client.
5. Add the exact redirect URI selected above to Authorized redirect URIs.

The project requests only these scopes:

```text
https://www.googleapis.com/auth/googlehealth.sleep.readonly
https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly
https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly
```

Google documentation: <https://developers.google.com/health/get-started>

## 5. Generate the token-encryption key

```bash
cd /opt/google-health-claude-bridge
uv run python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

Store this value securely and never commit it to Git.

## 6. Create `.env`

```bash
cd /opt/google-health-claude-bridge
cp .env.example .env
chmod 600 .env
```

Base configuration:

```dotenv
APP_ENV=production
HEALTH_PROVIDER=google
DATABASE_URL=sqlite:////opt/google-health-claude-bridge/data/health.sqlite

MCP_HOST=127.0.0.1
MCP_PORT=8000
PREFERRED_STEP_SOURCE=

GOOGLE_CLIENT_ID=YOUR_GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET=YOUR_GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI=THE_EXACT_REDIRECT_URI_SELECTED_ABOVE
GOOGLE_TOKEN_ENCRYPTION_KEY=YOUR_FERNET_KEY

# The current production validator requires a non-console mailer.
# If Daily Brief is not used, keep smtp selected and leave SMTP fields empty.
MAILER=smtp
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
MAIL_FROM=
MAIL_TO=
DAILY_BRIEF_AGENT=claude
```

For local or SSH-tunnel use:

```dotenv
MCP_AUTH_ENABLED=false
HEALTH_MCP_TOKEN=
HEALTH_MCP_TOKENS=
MCP_ALLOWED_HOSTS=
MCP_ALLOWED_ORIGINS=
```

For a public route protected by Cloudflare Access or another trusted identity gateway, the same values can be used because the origin remains on localhost. The external gateway must protect the whole host, including `/mcp` and `/oauth/google-health/login`.

For a CLI-only remote endpoint using the built-in bearer token:

```dotenv
MCP_AUTH_ENABLED=true
HEALTH_MCP_TOKEN=REPLACE_WITH_A_LONG_RANDOM_TOKEN
HEALTH_MCP_TOKENS=
MCP_ALLOWED_HOSTS=
MCP_ALLOWED_ORIGINS=
```

The built-in bearer middleware protects MCP traffic only. It does not replace whole-site protection for the Google OAuth routes.

## 7. Test locally

```bash
cd /opt/google-health-claude-bridge
uv run healthctl doctor
uv run healthctl serve
```

In another shell:

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
```

## 8. Run with systemd (Linux example)

Create `/etc/systemd/system/google-health-claude-bridge.service` and replace `YOUR_USER`:

```ini
[Unit]
Description=Google Health Claude Bridge
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/opt/google-health-claude-bridge
EnvironmentFile=/opt/google-health-claude-bridge/.env
ExecStart=/opt/google-health-claude-bridge/.venv/bin/healthctl serve
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now google-health-claude-bridge
sudo systemctl status google-health-claude-bridge
```

Use the equivalent service manager on macOS, Windows, NAS, or container platforms.

---

# Mode A: local or SSH tunnel

This mode is intended for Claude Code, Codex, MCP Inspector, and other local MCP clients.

It requires no domain, Cloudflare, or public web ports.

If the client and service run on the same machine, use:

```text
http://127.0.0.1:8000/mcp
```

If the service runs on another server, create an SSH tunnel from the client machine:

```bash
ssh -N -L 8000:127.0.0.1:8000 YOUR_USER@YOUR_SERVER_IP
```

Keep the tunnel open, then authorize Google Health from the local browser:

```text
http://localhost:8000/oauth/google-health/login
```

Claude Code:

```bash
claude mcp add --transport http google-health \
  http://127.0.0.1:8000/mcp
```

Codex:

```bash
codex mcp add google_health_agent \
  --url http://127.0.0.1:8000/mcp
```

Claude web and mobile requests originate from Anthropic's cloud and cannot use your local SSH tunnel. Use Mode B or C for remote custom connectors.

---

# Mode B: direct public deployment

This mode is for users who already have:

- A public server IP
- A domain
- Inbound 80/443 access
- Nginx, Caddy, Traefik, or another reverse proxy
- TLS certificates
- An OAuth or identity gateway

Cloudflare is **not required**.

```text
Claude
  ↓ HTTPS + OAuth
Your hostname
  ↓
Nginx / Caddy / Traefik + identity gateway
  ↓
127.0.0.1:8000
  ↓
Google Health Claude Bridge
```

Point the hostname to the server's public IP:

```text
health.example.com → YOUR_PUBLIC_SERVER_IP
```

Minimal Caddy reverse proxy example:

```caddyfile
health.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

This example provides TLS and reverse proxying only. It does **not** provide authentication. Before using real health data, protect the whole host with an OAuth or identity layer such as oauth2-proxy, Keycloak, Auth0, Authelia, Caddy Security, Nginx `auth_request`, or another remote-MCP-compatible gateway.

Public endpoints:

```text
Google OAuth callback: https://health.example.com/oauth/google-health/callback
MCP:                  https://health.example.com/mcp
Health check:         https://health.example.com/healthz
```

---

# Mode C: Cloudflare Tunnel + Access

This is the easiest remote setup for Claude web and mobile, but it remains optional.

Benefits:

- No public server IP is required
- No inbound 8000, 80, or 443 port is required
- The origin stays on `127.0.0.1`
- Cloudflare Access can restrict access to your own email
- Managed OAuth can provide an OAuth login flow for remote Claude connectors

```text
Claude
  ↓ OAuth
Cloudflare Access
  ↓
Cloudflare Tunnel
  ↓
127.0.0.1:8000
  ↓
Google Health Claude Bridge
```

## 1. Create the tunnel

In Cloudflare Dashboard:

1. Open **Networking → Tunnels**.
2. Create a tunnel such as `google-health-claude`.
3. Run the generated `cloudflared` installation command on the server.
4. Add a public hostname:

```text
Hostname: health.example.com
Service:  http://localhost:8000
```

Documentation: <https://developers.cloudflare.com/tunnel/setup/>

## 2. Protect the whole hostname with Access

In Cloudflare Zero Trust:

1. Open **Access controls → Applications**.
2. Create a Self-hosted application for `health.example.com`.
3. Add an Allow policy for your own email address.
4. Enable **Managed OAuth** in Advanced settings.
5. Ensure the Access policy covers the whole host, not only `/mcp`.

Documentation: <https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/managed-oauth/>

Opening `https://health.example.com/healthz` should now require Cloudflare Access login.

---

# Authorize Google Health and sync data

Local or SSH tunnel:

```text
http://localhost:8000/oauth/google-health/login
```

Direct public deployment or Cloudflare Tunnel:

```text
https://health.example.com/oauth/google-health/login
```

After authorization succeeds, start with a small import:

```bash
cd /opt/google-health-claude-bridge
uv run healthctl sync --days 3
uv run healthctl status
uv run healthctl analytics --metric hrv --days 3
```

After verifying source, timezone, and counts, increase gradually:

```bash
uv run healthctl sync --days 7
uv run healthctl sync --days 30
uv run healthctl sync --days 90
```

---

# Add the connector to Claude

For remote Mode B/C deployments:

1. Open **Customize → Connectors**.
2. Select **Add custom connector**.
3. Name it `Google Health`.
4. Enter:

```text
https://health.example.com/mcp
```

5. Complete the identity gateway OAuth flow.
6. Enable the connector in a conversation.

Example prompt:

```text
Check data quality first, then summarize my sleep, activity, and recovery trends over the last 30 days. Separate observed facts, statistical comparisons, and hypotheses. Do not diagnose disease.
```

## Claude Code with a remote endpoint

OAuth-protected endpoint:

```bash
claude mcp add --transport http google-health \
  https://health.example.com/mcp
```

Run `/mcp` inside Claude Code to complete OAuth.

Bearer-protected endpoint:

```bash
claude mcp add --transport http google-health \
  https://health.example.com/mcp \
  --header "Authorization: Bearer YOUR_TOKEN"
```

Static bearer headers are suitable for Claude Code and Codex, not the preferred path for Claude web custom connectors.

---

# No-domain options

## Option 1: local or SSH tunnel

This is the safest no-domain option for real data. It supports local MCP clients, not Claude web or mobile.

## Option 2: Cloudflare Quick Tunnel for temporary testing

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

It returns a random `*.trycloudflare.com` URL. Append `/mcp` for the MCP endpoint.

Quick Tunnels are temporary, may change URL after restart, have no uptime guarantee, are unsuitable as a stable Google OAuth callback, and should not expose real health data without authentication.

Documentation: <https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/>

---

# PostgreSQL

SQLite is normally sufficient for a single user. For PostgreSQL:

```bash
uv sync --locked --extra postgres
```

```dotenv
DATABASE_URL=postgresql+psycopg://health_user:STRONG_PASSWORD@127.0.0.1:5432/google_health
```

```bash
uv run alembic upgrade head
sudo systemctl restart google-health-claude-bridge
```

Use a dedicated non-superuser database role.

---

# Data sync and scheduling

Manual sync:

```bash
cd /opt/google-health-claude-bridge
uv run healthctl sync --days 7
```

Example cron entry for 06:15 every day:

```cron
15 6 * * * cd /opt/google-health-claude-bridge && /opt/google-health-claude-bridge/.venv/bin/healthctl sync --days 7 >> /var/log/google-health-sync.log 2>&1
```

Daily Brief email is optional and does not affect MCP queries from Claude conversations.

---

# Updates

```bash
cd /opt/google-health-claude-bridge
git pull
uv sync --locked
sudo systemctl restart google-health-claude-bridge
sudo systemctl status google-health-claude-bridge
```

For PostgreSQL deployments:

```bash
uv run alembic upgrade head
```

---

# Backups

Back up at least:

```text
/opt/google-health-claude-bridge/data/health.sqlite
/opt/google-health-claude-bridge/credentials/google-health-token.enc
```

Store `GOOGLE_TOKEN_ENCRYPTION_KEY` separately. Never publish the database, tokens, `.env`, logs, screenshots, or backups.

---

# Troubleshooting

See [常见问题 / FAQ](docs/faq.md) (Chinese) for common issues and solutions.

---

# Security

- All MCP tools are read-only.
- Google OAuth requests read-only scopes.
- Keep the origin bound to `127.0.0.1`.
- Protect the whole public hostname with OAuth, an identity gateway, or another strong authentication layer.
- Do not protect only `/mcp` while leaving the Google OAuth routes public.
- Never publish `.env`, OAuth client secrets, databases, tokens, logs, screenshots, or backups.
- Connect only to MCP services you operate and trust.
- Claude output is not a substitute for medical diagnosis.

## Acknowledgments

This project was inspired by
[Google Health Worker MCP V1](https://github.com/Ring8688/google-health-worker-mcp-V1).
We gratefully acknowledge that contribution.

## License

MIT. See [LICENSE](LICENSE).
