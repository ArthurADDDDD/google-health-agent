# Google Health Claude Bridge

> Bring device-recorded Google Health data into Claude conversations through a self-hosted, read-only MCP service.

[中文说明](README.md)

Google Health Claude Bridge reads Google Health API v4 data, stores it on your own server, and exposes bounded read-only MCP tools to Claude. It is designed for Google Health, Fitbit, and Pixel Watch users who want Claude to understand sleep, activity, recovery, and long-term trends.

It is not an Apple Health importer, a medical device, or a diagnostic service.

## Supported data

- Sleep records and duration
- Steps, activity minutes, sedentary time, and exercise
- HRV, resting heart rate, SpO2, respiratory rate
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
Your server and database
        ↓
Read-only MCP
        ↓
Claude web / mobile / Desktop / Claude Code
```

## Plan availability

Claude remote custom connectors are available on Free, Pro, Max, Team, and Enterprise plans. Free users can add one custom connector.

Official documentation: <https://support.claude.com/en/articles/11175166>

ChatGPT is a secondary compatible client. OpenAI's current plan table lists Custom MCP for Plus and higher plans, although availability can vary by account, region, and product mode.

Official documentation: <https://help.openai.com/en/articles/11487775-connectors-in>

## Recommended production architecture

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

This keeps the MCP origin on localhost, avoids exposing port 8000, and lets Cloudflare Access provide OAuth authentication for Claude remote connectors.

Do not expose real health data through an unauthenticated public MCP endpoint.

# Deployment: Linux server, domain, and Cloudflare

## 1. Install the project

Requirements: Linux, Python 3.12+, Git, a Google Cloud project, Google Health API access, and a domain managed by Cloudflare.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.profile

sudo mkdir -p /opt/google-health-claude-bridge
sudo chown "$USER":"$USER" /opt/google-health-claude-bridge

git clone https://github.com/ArthurADDDDD/google-health-claude-bridge.git \
  /opt/google-health-claude-bridge
cd /opt/google-health-claude-bridge

uv sync --locked
mkdir -p data credentials reports
chmod 700 data credentials reports
```

## 2. Configure Google OAuth

In Google Cloud:

1. Enable Google Health API.
2. Configure an External OAuth consent screen.
3. Add your Google account as a test user when the app is in testing mode.
4. Create a Web application OAuth client.
5. Add this redirect URI:

```text
https://health.example.com/oauth/google-health/callback
```

The project requests only these scopes:

```text
https://www.googleapis.com/auth/googlehealth.sleep.readonly
https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly
https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly
```

Google documentation: <https://developers.google.com/health/get-started>

## 3. Generate the token-encryption key

```bash
cd /opt/google-health-claude-bridge
uv run python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

Store this value securely and never commit it to Git.

## 4. Create `.env`

```bash
cd /opt/google-health-claude-bridge
cp .env.example .env
chmod 600 .env
```

Example configuration:

```dotenv
APP_ENV=production
HEALTH_PROVIDER=google
DATABASE_URL=sqlite:////opt/google-health-claude-bridge/data/health.sqlite

MCP_HOST=127.0.0.1
MCP_PORT=8000
MCP_AUTH_ENABLED=false
HEALTH_MCP_TOKEN=
HEALTH_MCP_TOKENS=
MCP_ALLOWED_HOSTS=
MCP_ALLOWED_ORIGINS=

PREFERRED_STEP_SOURCE=

GOOGLE_CLIENT_ID=YOUR_GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET=YOUR_GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI=https://health.example.com/oauth/google-health/callback
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

Application bearer authentication is disabled here because the service is bound to localhost and Cloudflare Access handles public authentication. Never use this configuration with an unprotected public route.

## 5. Test locally

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

## 6. Run with systemd

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

## 7. Create a Cloudflare Tunnel

In Cloudflare Dashboard:

1. Go to **Networking → Tunnels**.
2. Create a tunnel.
3. Run the generated `cloudflared` installation command on the server.
4. Add a public hostname:

```text
Hostname: health.example.com
Service:  http://localhost:8000
```

Cloudflare documentation: <https://developers.cloudflare.com/tunnel/setup/>

## 8. Protect it with Cloudflare Access Managed OAuth

In Cloudflare Zero Trust:

1. Go to **Access controls → Applications**.
2. Create a Self-hosted application for `health.example.com`.
3. Add an Allow policy for your own email address.
4. Enable **Managed OAuth** under Advanced settings.

Documentation: <https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/managed-oauth/>

Opening `https://health.example.com/healthz` should now require Cloudflare Access login.

## 9. Authorize Google Health and sync data

Open:

```text
https://health.example.com/oauth/google-health/login
```

After Google authorization succeeds, run:

```bash
cd /opt/google-health-claude-bridge
uv run healthctl sync --days 7
uv run healthctl status
uv run healthctl analytics --metric hrv --days 30
```

Increase the first import gradually to 30 or 90 days after verifying the initial data.

## 10. Add the connector to Claude

1. Open **Customize → Connectors**.
2. Select **Add custom connector**.
3. Name it `Google Health`.
4. Enter:

```text
https://health.example.com/mcp
```

5. Complete Cloudflare Access OAuth.
6. Enable the connector in a conversation.

Example prompt:

```text
Check data quality first, then summarize my sleep, activity, and recovery trends over the last 30 days. Separate observed facts, statistical comparisons, and hypotheses. Do not diagnose disease.
```

## Claude Code

With Cloudflare Managed OAuth:

```bash
claude mcp add --transport http google-health \
  https://health.example.com/mcp
```

Then run `/mcp` inside Claude Code to complete OAuth.

For a bearer-protected endpoint instead:

```bash
claude mcp add --transport http google-health \
  https://health.example.com/mcp \
  --header "Authorization: Bearer YOUR_TOKEN"
```

Static bearer headers are suitable for Claude Code and Codex, not the preferred path for Claude web custom connectors.

# No-domain testing

A temporary Quick Tunnel can expose localhost without a domain:

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

It returns a random `*.trycloudflare.com` URL. Append `/mcp` for the MCP endpoint.

Quick Tunnels are temporary, change URL after restart, have no uptime guarantee, and should not expose real health data without authentication. Use them only with synthetic data or with Claude Code and application bearer authentication.

Documentation: <https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/>

# PostgreSQL

For PostgreSQL:

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

# Updates

```bash
cd /opt/google-health-claude-bridge
git pull
uv sync --locked
uv run alembic upgrade head  # PostgreSQL deployments
sudo systemctl restart google-health-claude-bridge
```

# Backups

Back up the database and encrypted Google token:

```text
/opt/google-health-claude-bridge/data/health.sqlite
/opt/google-health-claude-bridge/credentials/google-health-token.enc
```

Store `GOOGLE_TOKEN_ENCRYPTION_KEY` separately. Never publish the database, tokens, `.env`, logs, screenshots, or backups.

# Security

- All MCP tools are read-only.
- Google OAuth requests read-only scopes.
- Keep the origin bound to localhost.
- Protect remote access with OAuth, a private network, or another strong authentication layer.
- Do not expose a real-data MCP endpoint without authentication.
- This project provides data and statistics, not medical diagnosis.

## Acknowledgments

This project was inspired by
[Google Health Worker MCP V1](https://github.com/Ring8688/google-health-worker-mcp-V1).
The idea of wrapping Google Health API v4 behind a read-only remote MCP connector for Claude
originated there, and we gratefully acknowledge that contribution.

The two projects take different implementation approaches: this backend runs on your own Linux
server using Python/SQLite (optionally PostgreSQL), protected by Cloudflare Tunnel + Access OAuth,
rather than deploying on Cloudflare Workers.

## License

MIT. See [LICENSE](LICENSE).
