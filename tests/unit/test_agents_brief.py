from typer.testing import CliRunner

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
