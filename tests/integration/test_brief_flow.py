import asyncio
from datetime import date, timedelta

import pytest

import google_health_agent.brief.workflow as workflow
from google_health_agent.brief.workflow import run_brief
from google_health_agent.config import Settings
from google_health_agent.errors import DataUnavailable, ProviderUnavailable
from google_health_agent.mail import Mailer
from google_health_agent.providers.synthetic import SyntheticHealthProvider
from google_health_agent.storage import HealthRepository


def test_fake_runner_uses_mcp_and_console_mailer(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    database_url = f"sqlite:///{tmp_path / 'brief.sqlite'}"
    repository = HealthRepository(database_url)
    repository.initialize()
    end = date.today()
    points = asyncio.run(SyntheticHealthProvider(100).fetch(end - timedelta(days=119), end))
    missing_day = end - timedelta(days=3)
    points = [point for point in points if point.civil_date != missing_day]
    repository.upsert(points)
    output = run_brief("fake", False, Settings(database_url=database_url))
    assert output
    assert output.exists()
    assert output.stat().st_mode & 0o777 == 0o600
    assert output.parent.stat().st_mode & 0o777 == 0o700
    text = output.read_text()
    assert "SYNTHETIC DATA" in text
    assert "Data completeness" in text
    assert "Completeness: 1.0" not in text
    assert "Health Brief" in capsys.readouterr().out


def test_authenticated_fake_runner_uses_mcp(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    database_url = f"sqlite:///{tmp_path / 'authenticated.sqlite'}"
    repository = HealthRepository(database_url)
    repository.initialize()
    end = date.today()
    points = asyncio.run(SyntheticHealthProvider(101).fetch(end - timedelta(days=119), end))
    repository.upsert(points)
    settings = Settings(
        database_url=database_url,
        mcp_auth_enabled=True,
        health_mcp_tokens='{"fake":"synthetic-fake-token","codex":"synthetic-codex-token"}',
    )
    output = run_brief("fake", False, settings)
    assert output and "SYNTHETIC DATA" in output.read_text()


def test_production_fake_runner_uses_exact_allowed_host(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    database_url = f"sqlite:///{tmp_path / 'production-host.sqlite'}"
    repository = HealthRepository(database_url)
    repository.initialize()
    end = date.today()
    points = asyncio.run(SyntheticHealthProvider(103).fetch(end - timedelta(days=119), end))
    repository.upsert(points)
    settings = Settings(
        app_env="production",
        health_provider="synthetic",
        database_url=database_url,
        mcp_host="0.0.0.0",
        mcp_port=8000,
        mcp_auth_enabled=True,
        health_mcp_tokens='{"fake":"synthetic-production-fake-token"}',
        mcp_allowed_hosts="127.0.0.1:18000,localhost:18000",
        mcp_allowed_origins="http://127.0.0.1:18000,http://localhost:18000",
    )
    output = run_brief("fake", False, settings)
    assert output and "SYNTHETIC DATA" in output.read_text()


def test_empty_database_does_not_generate_or_mail_brief(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    database_url = f"sqlite:///{tmp_path / 'empty.sqlite'}"
    HealthRepository(database_url).initialize()

    class MustNotSend(Mailer):
        def send(self, subject: str, markdown: str) -> None:
            raise AssertionError("empty data must not be mailed")

    monkeypatch.setattr(workflow, "_mailer", lambda settings: MustNotSend())
    with pytest.raises(DataUnavailable, match="no report or email"):
        run_brief("fake", False, Settings(database_url=database_url))
    assert not (tmp_path / "reports").exists()


def test_mcp_or_provider_failure_cannot_generate_brief(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    async def unavailable(settings):
        raise ProviderUnavailable("mock MCP/provider unavailable")

    monkeypatch.setattr(workflow, "_fake_facts", unavailable)
    with pytest.raises(ProviderUnavailable, match="mock MCP/provider"):
        run_brief(
            "fake",
            False,
            Settings(database_url=f"sqlite:///{tmp_path / 'unavailable.sqlite'}"),
        )
    assert not (tmp_path / "reports").exists()


def test_mail_failure_retains_generated_report(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    database_url = f"sqlite:///{tmp_path / 'mail-failure.sqlite'}"
    repository = HealthRepository(database_url)
    repository.initialize()
    end = date.today()
    repository.upsert(
        asyncio.run(SyntheticHealthProvider(102).fetch(end - timedelta(days=119), end))
    )

    class FailingMailer(Mailer):
        def send(self, subject: str, markdown: str) -> None:
            raise RuntimeError("mock delivery failure")

    monkeypatch.setattr(workflow, "_mailer", lambda settings: FailingMailer())
    with pytest.raises(RuntimeError, match="mock delivery failure"):
        run_brief("fake", False, Settings(database_url=database_url))
    reports = list((tmp_path / "reports").rglob("fake.md"))
    assert len(reports) == 1
    assert "SYNTHETIC DATA" in reports[0].read_text()
