import asyncio
from datetime import date
from pathlib import Path

import httpx
import typer
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from google_health_agent.agents import AgentRunner, ClaudeRunner, CodexRunner, FakeRunner
from google_health_agent.config import Settings
from google_health_agent.errors import ConfigurationError
from google_health_agent.mail import ConsoleMailer, Mailer, SMTPMailer
from google_health_agent.mcp.server import create_app
from google_health_agent.storage import HealthRepository

DAILY_BRIEF_PROMPT = """Generate today's personal health brief using Google Health Agent.

Use the Google Health Agent MCP tools to retrieve the necessary data.
Start by checking data quality and the health overview.
Investigate additional metrics only when useful.
Focus on last night's sleep, recovery signals, yesterday's activity, the recent
7-day trend, and comparison with the prior personal baseline.
Do not diagnose disease. Clearly separate facts from interpretation.
Keep the brief concise enough to read in an email.
"""


def _mailer(settings: Settings) -> Mailer:
    return ConsoleMailer() if settings.mailer == "console" else SMTPMailer(settings)


async def _fake_facts(settings: Settings) -> dict[str, object]:
    repository = HealthRepository(settings.database_url)
    repository.initialize()
    app = create_app(settings, repository)
    end_date = date.today().isoformat()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url=f"http://{settings.mcp_host}:{settings.mcp_port}",
        ) as client,
        streamable_http_client(
            f"http://{settings.mcp_host}:{settings.mcp_port}/mcp",
            http_client=client,
        ) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        calls = {
            "quality": ("get_data_quality", {"days": 30, "end_date": end_date}),
            "overview": ("get_health_overview", {"days": 30, "end_date": end_date}),
            "sleep": ("get_sleep", {"days": 30, "end_date": end_date}),
            "recovery": ("get_recovery", {"days": 30, "end_date": end_date}),
            "activity": ("get_activity", {"days": 30, "end_date": end_date}),
        }
        facts: dict[str, object] = {}
        for key, (tool_name, arguments) in calls.items():
            result = await session.call_tool(tool_name, arguments)
            if result.isError or not result.structuredContent:
                raise ConfigurationError(f"FakeRunner could not call MCP tool {tool_name}.")
            facts[key] = result.structuredContent
        return facts


def run_brief(agent: str, dry_run: bool, settings: Settings) -> Path | None:
    endpoint = f"http://{settings.mcp_host}:{settings.mcp_port}/mcp"
    output_file = Path("reports") / date.today().isoformat() / f"{agent}.md"
    if dry_run:
        typer.echo(f"Agent: {agent}")
        typer.echo(f"MCP endpoint: {endpoint}")
        typer.echo(f"Task prompt:\n{DAILY_BRIEF_PROMPT}")
        typer.echo(f"Expected output file: {output_file}")
        typer.echo(f"Mailer: {settings.mailer}")
        typer.echo("No agent executed and no email sent.")
        return None

    if agent == "fake":
        runner: AgentRunner = FakeRunner(asyncio.run(_fake_facts(settings)))
    elif agent == "claude":
        runner = ClaudeRunner()
    elif agent == "codex":
        runner = CodexRunner()
    else:
        raise ConfigurationError("Agent must be one of: fake, claude, codex.")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    result = runner.run(DAILY_BRIEF_PROMPT, output_file)
    if result.exit_code != 0:
        raise ConfigurationError(
            f"{agent} failed with exit code {result.exit_code}; inspect secret-safe stderr."
        )
    if agent != "codex":
        output_file.write_text(result.stdout, encoding="utf-8")
    markdown = output_file.read_text(encoding="utf-8")
    _mailer(settings).send(f"Health Brief · {date.today().isoformat()}", markdown)
    return output_file
