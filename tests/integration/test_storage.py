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


@pytest.mark.asyncio
async def test_storage_query_separates_synthetic_and_private_points(tmp_path) -> None:
    repository = HealthRepository(f"sqlite:///{tmp_path / 'separated.sqlite'}")
    repository.initialize()
    start = date(2026, 1, 1)
    synthetic_points = await SyntheticHealthProvider(12).fetch(start, start)
    private_point = synthetic_points[0].model_copy(
        update={"external_id": "private-point", "synthetic": False}
    )
    repository.upsert([synthetic_points[0], private_point])

    assert [point.synthetic for point in repository.query(start, start)] == [True]
    assert [point.synthetic for point in repository.query(start, start, synthetic=False)] == [False]
