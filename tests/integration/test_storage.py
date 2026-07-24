from datetime import date, timedelta

import pytest

from google_health_agent.providers.synthetic import SyntheticHealthProvider
from google_health_agent.storage import HealthRepository


@pytest.mark.asyncio
async def test_storage_upsert_is_idempotent(tmp_path) -> None:
    repository = HealthRepository(f"sqlite:///{tmp_path / 'test.sqlite'}")
    repository.initialize()
    start = date(2026, 1, 1)
    points = await SyntheticHealthProvider(12).fetch(start, start + timedelta(days=3))
    assert repository.upsert(points) == len(points)
    assert repository.upsert(points) == len(points)
    assert repository.count() == len(points)
    queried = repository.query(start, start + timedelta(days=3), "hrv")
    assert len(queried) == 4
    assert queried[0].source.platform == "SYNTHETIC"
