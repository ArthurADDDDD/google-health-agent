# Prior-art review

This project reviewed existing open-source health/fitness MCP work for architecture experience,
not implementation reuse.

## Sources reviewed

- [Pierre Fitness Platform](https://github.com/Async-IO/pierre_mcp_server): provider traits,
  synthetic development, repositories, encrypted tokens, health checks, and structured errors.
- [WHOOP MCP by David Mosiah](https://github.com/davidmosiah/whoop-mcp): local-first OAuth,
  tokens kept away from model context, doctor workflow, summaries, and explicit privacy posture.
- [WHOOP MCP by Jed Patterson](https://github.com/JedPattersonn/whoop-mcp): small overview-first
  tool surface and a single `/mcp` endpoint.
- [Google Health Fitbit MCP](https://github.com/BerkKilicoglu/google-health-fitbit-mcp):
  acknowledgement that Google Health v4 is moving, read-only defaults, local token handling,
  and client examples.

## Experience adopted

- Provider-neutral interfaces and a synthetic provider for CI.
- Overview-first tools with deeper bounded queries.
- OAuth/token handling outside tool results.
- Repository boundaries, health probes, structured errors, and doctor commands.
- Clear local-first/read-only/not-medical positioning.

## Deliberately not adopted

- No copied code, schemas, prompts, or provider-specific business logic.
- No legacy Fitbit API, WHOOP private/reverse-engineered API, or password login.
- No write tools, goal mutation, recommendations engine, chatbot, or intelligence backend.
- No multi-tenant platform, dynamic provider marketplace, SDK bridge, dashboard, or A2A layer.
- No provider score presented as this service's medical or health conclusion.

The governing design remains Google Health API v4, personal self-hosting, normalized factual
data, read-only MCP, and interpretation by Claude Code or Codex.

