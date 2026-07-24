import asyncio
from datetime import date, timedelta

from google_health_agent.brief.workflow import run_brief
from google_health_agent.config import Settings
from google_health_agent.providers.synthetic import SyntheticHealthProvider
from google_health_agent.storage import HealthRepository


def test_fake_runner_uses_mcp_and_console_mailer(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    database_url = f"sqlite:///{tmp_path / 'brief.sqlite'}"
    repository = HealthRepository(database_url)
    repository.initialize()
    end = date.today()
    points = asyncio.run(SyntheticHealthProvider(100).fetch(end - timedelta(days=119), end))
    repository.upsert(points)
    output = run_brief("fake", False, Settings(database_url=database_url))
    assert output
    assert output.exists()
    text = output.read_text()
    assert "SYNTHETIC DATA" in text
    assert "Data completeness" in text
    assert "Health Brief" in capsys.readouterr().out
