# Google Health Agent

面向 Claude Code 与 Codex Agent 分析的 Google Health 数据管道与 MCP Server。

> 当前是 **Public Architecture / Demo Phase**。公开仓库只使用带明显标识、可重复生成的
> **SYNTHETIC DATA**，不包含任何个人健康数据、凭据、Token 或私人服务器信息。

## 项目定位

```text
Google Health → 自托管标准化数据层 → Read-only MCP → Claude Code / Codex
```

Google Health Agent 负责事实、数学统计、来源与数据质量；外部 Agent 负责解释。它不是
chatbot、医疗设备、诊断系统、医疗建议服务或云端 SaaS，也不使用旧 Fitbit Web API。

## 快速开始

需要 Python 3.12+ 与 [uv](https://docs.astral.sh/uv/)。

```bash
uv sync
uv run healthctl demo
uv run healthctl doctor
uv run healthctl serve
```

Demo 会在 gitignored 的 `data/demo.sqlite` 中创建 120 天合成数据，并启动
`http://127.0.0.1:8000/mcp`。另一个终端可运行：

```bash
uv run healthctl analytics --metric hrv --days 30
uv run healthctl brief --agent fake --dry-run
uv run healthctl brief --agent fake
```

FakeRunner 会通过正式 MCP client 取数、生成合成演示 Markdown，并输出到 ConsoleMailer；
不会调用真实模型或发送邮件。

## MCP 工具

- `get_health_overview`
- `get_sleep`
- `get_recovery`
- `get_activity`
- `get_metric`
- `compare_periods`
- `get_data_quality`
- `get_daily_brief_context`

所有工具均为 read-only、结构化输出、限制最大时间范围，并附带必要的数据质量和来源信息。

## Agent 连接

Claude Code 使用 [示例配置](examples/claude/.mcp.json.example)，详见
[Claude 文档](docs/claude-code.md)。Codex 使用
[示例配置](examples/codex/config.toml.example)，详见 [Codex 文档](docs/codex.md)。
两者都只通过 Google Health Agent MCP 获取健康数据，不能直接访问数据库。

## Google Health

Phase 2A 已按当前 Google 官方文档实现 Google Health API v4 请求、Web Server OAuth
Authorization Code Flow、offline refresh、readonly scopes、加密 TokenStore、分页、重试和
mocked integration tests。默认 provider 仍为 `synthetic`，没有执行任何真实 OAuth 或真实
数据访问；Phase 2B 仍需单独授权。详见 [Google Health 文档](docs/google-health.md)。

## 安全

默认 local-first、自托管、read-only、无 telemetry。非 localhost 绑定必须开启 Bearer
认证，并显式设置 `MCP_ALLOWED_HOSTS` 与 `MCP_ALLOWED_ORIGINS` 以防御 DNS rebinding。
公开检查命令：

```bash
uv run python scripts/secret_scan.py
```

详见 [安全设计](docs/security.md) 与 [SECURITY.md](SECURITY.md)。

## 开发检查

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src/google_health_agent
uv run pytest
uv run python scripts/secret_scan.py
```

## Roadmap

1. Phase 1：Synthetic / MCP / Agent Architecture
2. Phase 2A：Private Deployment Preparation（仅 synthetic / mocked）
3. Phase 2B：另行授权的 Private Google Health Deployment
4. Phase 3：Automated Daily Agent Brief
5. Phase 4：Additional Health Providers

MIT License。
