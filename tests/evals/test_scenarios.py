from datetime import date, timedelta

import pytest

from google_health_agent.analytics import detect_anomalies
from google_health_agent.analytics.quality import assess_quality
from google_health_agent.domain import HealthDataPoint
from google_health_agent.providers.synthetic import SyntheticHealthProvider
from google_health_agent.service import HealthService
from google_health_agent.storage import HealthRepository


async def _base_points() -> tuple[date, date, list[HealthDataPoint]]:
    start = date(2026, 1, 1)
    end = start + timedelta(days=29)
    return start, end, await SyntheticHealthProvider(88).fetch(start, end)


def _service(tmp_path, points: list[HealthDataPoint]) -> HealthService:
    repository = HealthRepository(f"sqlite:///{tmp_path / 'eval.sqlite'}")
    repository.initialize()
    repository.upsert(points)
    return HealthService(repository)


def _change(
    points: list[HealthDataPoint],
    metric: str,
    first_day: date,
    transform,
) -> list[HealthDataPoint]:
    return [
        point.model_copy(update={"value": transform(point.value)})
        if point.metric == metric and point.civil_date >= first_day
        else point
        for point in points
    ]


@pytest.mark.asyncio
async def test_scenario_a_sleep_down_hrv_stable(tmp_path) -> None:
    start, end, points = await _base_points()
    recent = end - timedelta(days=6)
    points = _change(points, "sleep_minutes", recent, lambda value: value - 70)
    service = _service(tmp_path, points)
    sleep = service.compare("sleep_minutes", recent, end, start, recent - timedelta(days=1))
    hrv = service.compare("hrv", recent, end, start, recent - timedelta(days=1))
    assert sleep["comparison"]["absolute_difference"] < -40
    assert abs(hrv["comparison"]["percentage_difference"]) < 20


@pytest.mark.asyncio
async def test_scenario_b_sleep_hrv_down_rhr_up(tmp_path) -> None:
    start, end, points = await _base_points()
    recent = end - timedelta(days=6)
    points = _change(points, "sleep_minutes", recent, lambda value: value - 70)
    points = _change(points, "hrv", recent, lambda value: value - 15)
    points = _change(points, "resting_heart_rate", recent, lambda value: value + 8)
    service = _service(tmp_path, points)
    assert (
        service.compare("sleep_minutes", recent, end, start, recent - timedelta(days=1))[
            "comparison"
        ]["absolute_difference"]
        < 0
    )
    assert (
        service.compare("hrv", recent, end, start, recent - timedelta(days=1))["comparison"][
            "absolute_difference"
        ]
        < 0
    )
    assert (
        service.compare("resting_heart_rate", recent, end, start, recent - timedelta(days=1))[
            "comparison"
        ]["absolute_difference"]
        > 0
    )


@pytest.mark.asyncio
async def test_scenario_c_single_day_hrv_drop_is_visible_not_a_trend() -> None:
    _, end, points = await _base_points()
    points = _change(points, "hrv", end, lambda value: value * 0.2)
    hrv = [point for point in points if point.metric == "hrv"]
    anomalies = detect_anomalies(hrv)
    assert any(item["date"] == end.isoformat() for item in anomalies)
    assert len([point for point in hrv if point.civil_date == end]) == 1


@pytest.mark.asyncio
async def test_scenario_d_missing_wearable_data() -> None:
    start, end, points = await _base_points()
    missing_day = end - timedelta(days=2)
    points = [point for point in points if point.civil_date != missing_day]
    issues = assess_quality(points, start, end)
    assert any(issue.code == "missing_data" and issue.date == missing_day for issue in issues)


@pytest.mark.asyncio
async def test_scenario_e_travel_timezone_shift() -> None:
    start, end, points = await _base_points()
    travel_start = end - timedelta(days=2)
    points = [
        point.model_copy(update={"utc_offset_minutes": 540})
        if point.civil_date >= travel_start
        else point
        for point in points
    ]
    issues = assess_quality(points, start, end)
    assert any(issue.code == "timezone_change" for issue in issues)
