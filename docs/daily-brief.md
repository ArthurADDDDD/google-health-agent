# Daily Brief

The backend does not prewrite health conclusions. It provides a concise task asking an external
agent to start with `get_data_quality` and `get_health_overview`, investigate only useful
details, compare recent history with the personal baseline, and produce Markdown.

`AgentRunner` has Claude, Codex, and Fake implementations. Claude and Codex invoke already
installed non-interactive CLIs and capture exit code, stdout, stderr, timeout, and duration
without printing secrets. FakeRunner is the CI path: it calls the same MCP tools using the
official client and writes an explicitly synthetic, facts-only report.

Reports are stored under gitignored `reports/YYYY-MM-DD/`. ConsoleMailer is the demo default;
SMTPMailer requires all settings. `--dry-run` executes no agent and sends no email. Scheduling
is deliberately external to the app: future deployments can call `healthctl sync` and
`healthctl brief` from systemd or cron.

