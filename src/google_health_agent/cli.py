from datetime import date, timedelta
from json import dumps
from shutil import which

import typer

from google_health_agent.config import Settings
from google_health_agent.domain import HealthDataPoint
from google_health_agent.providers.synthetic import SyntheticHealthProvider
from google_health_agent.service import HealthService
from google_health_agent.storage import HealthRepository

app = typer.Typer(help="Google Health Agent administration CLI.", no_args_is_help=True)


def _settings() -> Settings:
    return Settings()


def _repository(settings: Settings) -> HealthRepository:
    repository = HealthRepository(settings.database_url)
    repository.initialize()
    return repository


def _configured(*values: object) -> str:
    return "configured" if all(value is not None and bool(value) for value in values) else "missing"


def _readiness_lines(settings: Settings, repository: HealthRepository) -> list[str]:
    database_kind = "SQLite" if settings.database_url.startswith("sqlite") else "PostgreSQL"
    token_status = (
        f"configured ({len(settings.mcp_token_map)} independent client credential(s))"
        if settings.mcp_auth_enabled
        else "disabled (localhost demo only)"
    )
    google_status = _configured(
        settings.google_client_id,
        settings.google_client_secret,
        settings.google_redirect_uri,
        settings.google_token_encryption_key,
    )
    smtp_status = _configured(
        settings.smtp_host,
        settings.smtp_username,
        settings.smtp_password,
        settings.mail_from,
        settings.mail_to,
    )
    provider_credentials = google_status if settings.health_provider == "google" else "not required"
    return [
        f"Environment: {settings.app_env}",
        f"Provider: {settings.health_provider}",
        f"Provider credentials: {provider_credentials}",
        f"Database: {database_kind}",
        f"Database status: ready ({repository.count()} observations)",
        "MCP transport: Streamable HTTP",
        f"MCP authentication: {token_status}",
        f"Claude CLI: {'installed' if which('claude') else 'not installed'}",
        f"Codex CLI: {'installed' if which('codex') else 'not installed'}",
        f"Daily Brief agent: {settings.daily_brief_agent}",
        f"Mailer: {settings.mailer}",
        f"SMTP credentials: {smtp_status if settings.mailer == 'smtp' else 'not required'}",
        "Scheduler: external (not configured by this application)",
    ]


@app.command()
def doctor() -> None:
    """Report secret-safe environment readiness."""
    settings = _settings()
    repository = _repository(settings)
    typer.echo("Google Health Agent")
    for line in _readiness_lines(settings, repository):
        typer.echo(line)


@app.command()
def demo(days: int = typer.Option(120, min=120, max=365)) -> None:
    """Create deterministic, explicitly synthetic demo data."""
    settings = _settings()
    if settings.health_provider != "synthetic":
        raise typer.BadParameter("Demo requires HEALTH_PROVIDER=synthetic.")
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    provider = SyntheticHealthProvider(settings.synthetic_seed)
    import asyncio

    points = asyncio.run(provider.fetch(start_date, end_date))
    repository = _repository(settings)
    repository.replace_synthetic(points)
    typer.echo("Google Health Agent Demo")
    typer.echo("SYNTHETIC DATA — not personal health information.")
    typer.echo(f"Synthetic health dataset created: {days} days, {len(points)} observations.")
    typer.echo("Database initialized.")
    typer.echo("Provider: synthetic")
    typer.echo(f"MCP server ready at http://{settings.mcp_host}:{settings.mcp_port}/mcp")


@app.command()
def sync(days: int = typer.Option(30, min=1, max=365)) -> None:
    """Fetch and idempotently store provider observations."""
    settings = _settings()
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    import asyncio

    if settings.health_provider == "synthetic":
        provider = SyntheticHealthProvider(settings.synthetic_seed)
        points = asyncio.run(provider.fetch(start_date, end_date))
    else:
        points = asyncio.run(_google_sync(settings, start_date, end_date))
    count = _repository(settings).upsert(points)
    label = "SYNTHETIC DATA" if settings.health_provider == "synthetic" else "private"
    typer.echo(f"Synced {count} {label} observations.")


async def _google_sync(
    settings: Settings, start_date: date, end_date: date
) -> list[HealthDataPoint]:
    from pathlib import Path

    import httpx

    from google_health_agent.errors import ConfigurationError
    from google_health_agent.providers.google_health import (
        EncryptedFileTokenStore,
        GoogleHealthProvider,
        GoogleOAuthClient,
    )

    if settings.google_token_encryption_key is None:
        raise ConfigurationError(
            "GOOGLE_TOKEN_ENCRYPTION_KEY is required when HEALTH_PROVIDER=google."
        )
    async with httpx.AsyncClient(timeout=30) as client:
        store = EncryptedFileTokenStore(
            Path("credentials/google-health-token.enc"),
            settings.google_token_encryption_key,
        )
        provider = GoogleHealthProvider(
            store,
            GoogleOAuthClient(settings, client),
            client,
        )
        return await provider.fetch(start_date, end_date)


@app.command()
def status() -> None:
    """Show component status without exposing configuration values or data payloads."""
    settings = _settings()
    repository = _repository(settings)
    for line in _readiness_lines(settings, repository):
        typer.echo(line)
    label = "SYNTHETIC DATA" if settings.health_provider == "synthetic" else "private"
    typer.echo(f"Data label: {label}")


@app.command("analytics")
def analytics_command(
    metric: str = typer.Option("sleep_minutes"),
    days: int = typer.Option(30, min=1, max=365),
) -> None:
    """Print a mathematical metric summary and data-quality facts."""
    settings = _settings()
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    service = HealthService(
        _repository(settings),
        data_label=(
            "SYNTHETIC DATA" if settings.health_provider == "synthetic" else "PRIVATE DATA"
        ),
        preferred_step_source=settings.preferred_step_source,
    )
    payload = service.metric(metric, start_date, end_date, granularity="summary")
    typer.echo(dumps(payload["summary"], indent=2))
    typer.echo(f"Data quality issues: {len(payload['data_quality'])}")


@app.command()
def serve() -> None:
    """Start the Streamable HTTP MCP service."""
    from google_health_agent.mcp.server import run_server

    run_server(_settings())


@app.command()
def brief(
    agent: str = typer.Option("fake"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Run the Daily Brief workflow."""
    from google_health_agent.brief.workflow import run_brief

    run_brief(agent=agent, dry_run=dry_run, settings=_settings())


if __name__ == "__main__":
    app()
