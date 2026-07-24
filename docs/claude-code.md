# Claude Code

Claude Code connects to the Streamable HTTP endpoint and never accesses the database.
The current official [Claude Code MCP guide](https://docs.anthropic.com/en/docs/claude-code/mcp)
supports HTTP servers, headers, project scope, and `${VAR}` / `${VAR:-default}` expansion in
`.mcp.json` URL and header values.

```bash
cp examples/claude/.mcp.json.example .mcp.json
export HEALTH_MCP_URL=http://127.0.0.1:8000/mcp
export HEALTH_MCP_TOKEN=
claude mcp list
```

For a private authenticated deployment, set `HEALTH_MCP_TOKEN` outside the repository. The
non-interactive Daily Brief runner uses the currently documented `claude -p` print mode with
text output and a bounded number of turns. It never installs Claude Code automatically.

