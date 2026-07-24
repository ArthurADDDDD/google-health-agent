# MCP contract

The server is named `google-health-agent` and uses the official
[MCP Python SDK](https://py.sdk.modelcontextprotocol.io/) with Streamable HTTP at `/mcp`.
[Streamable HTTP](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
replaces the older HTTP+SSE transport. The server binds to `127.0.0.1` by default and retains
the SDK's Origin/Host protection. A non-loopback bind additionally requires Bearer
authentication and explicit `MCP_ALLOWED_HOSTS` and `MCP_ALLOWED_ORIGINS` patterns.

All eight tools return structured JSON and carry MCP `readOnlyHint=true`,
`destructiveHint=false`, `idempotentHint=true`, and `openWorldHint=false`. These annotations
describe the contract; the absence of mutating handlers is the enforcement.

Overview queries and raw history are bounded to 365 days. Missing data is never represented as
zero. Tool names, required parameters, and output schema are stable interfaces checked through
the official MCP client using initialize, list_tools, and call_tool.

Run the current Inspector:

```bash
npx -y @modelcontextprotocol/inspector
```

Connect to `http://127.0.0.1:8000/mcp`.
