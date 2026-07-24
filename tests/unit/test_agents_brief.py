import subprocess

from typer.testing import CliRunner

import google_health_agent.cli as cli_module
from google_health_agent.agents import ClaudeRunner, CodexRunner, FakeRunner
from google_health_agent.brief.workflow import run_brief
from google_health_agent.cli import app
from google_health_agent.config import Settings


def _facts() -> dict[str, object]:
    return {
        "quality": {"completeness": 0.95},
        "overview": {"period": {"end_date": "2026-07-24"}},
        "sleep": {"summaries": {"sleep_minutes": {"median": 440.0}}},
        "recovery": {
            "summaries": {
                "hrv": {"median": 51.0},
                "resting_heart_rate": {"median": 60.0},
            }
        },
        "activity": {"summaries": {"steps": {"median": 9000.0}}},
    }


def test_fake_runner_writes_explicitly_synthetic_brief(tmp_path) -> None:
    output = tmp_path / "fake.md"
    result = FakeRunner(_facts()).run("prompt", output)
    assert result.exit_code == 0
    assert "SYNTHETIC DATA" in output.read_text()
    assert "No medical interpretation" in result.stdout


def test_current_agent_cli_commands_are_non_interactive(tmp_path) -> None:
    claude = ClaudeRunner().command("prompt", tmp_path / "claude.md")
    codex = CodexRunner().command("prompt", tmp_path / "codex.md")
    assert claude[:3] == ["claude", "-p", "--output-format"]
    assert codex[:3] == ["codex", "exec", "--ephemeral"]
    assert "--output-last-message" in codex


def test_agent_timeout_fails_cleanly_without_inventing_output(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda executable: f"/mock/{executable}")

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["claude"],
            timeout=1,
            output="partial synthetic output",
            stderr="mock timeout",
        )

    monkeypatch.setattr("subprocess.run", timeout)
    output = tmp_path / "timeout.md"
    result = ClaudeRunner().run("synthetic prompt", output, timeout_seconds=1)
    assert result.exit_code == 124
    assert result.timed_out is True
    assert result.stdout == "partial synthetic output"
    assert result.stderr == "mock timeout"
    assert not output.exists()


def test_brief_dry_run_does_not_create_report(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    result = run_brief("fake", True, Settings(database_url=f"sqlite:///{tmp_path / 'x.db'}"))
    output = capsys.readouterr().out
    assert result is None
    assert "No agent executed and no email sent." in output
    assert not (tmp_path / "reports").exists()


def test_cli_exposes_required_commands() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("doctor", "demo", "serve", "sync", "status", "analytics", "brief"):
        assert command in result.stdout


def test_doctor_and_status_are_component_complete_and_secret_safe(tmp_path, monkeypatch) -> None:
    secrets = {
        "mcp": "synthetic-mcp-secret",
        "client": "mock-client-id-secret",
        "oauth": "mock-oauth-secret",
        "key": "mock-encryption-key-secret",
        "smtp": "mock-smtp-secret",
    }
    settings = Settings(
        app_env="test",
        health_provider="google",
        database_url=f"sqlite:///{tmp_path / 'doctor.sqlite'}",
        mcp_auth_enabled=True,
        health_mcp_tokens=f'{{"codex":"{secrets["mcp"]}"}}',
        google_client_id=secrets["client"],
        google_client_secret=secrets["oauth"],
        google_redirect_uri="https://health.example.test/oauth/callback",
        google_token_encryption_key=secrets["key"],
        mailer="smtp",
        smtp_host="smtp.example.test",
        smtp_username="mock-user",
        smtp_password=secrets["smtp"],
        mail_from="mock-from",
        mail_to="mock-to",
    )
    monkeypatch.setattr(cli_module, "_settings", lambda: settings)
    for command in ("doctor", "status"):
        result = CliRunner().invoke(app, [command])
        assert result.exit_code == 0
        assert "Provider credentials: configured" in result.stdout
        assert (
            "MCP authentication: configured (1 independent client credential(s))" in result.stdout
        )
        assert "SMTP credentials: configured" in result.stdout
        assert "Scheduler: external" in result.stdout
        assert all(secret not in result.stdout for secret in secrets.values())
