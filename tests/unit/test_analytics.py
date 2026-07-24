from datetime import UTC, date, datetime, timedelta

import pytest

from google_health_agent.analytics import compare_periods, detect_anomalies, summarize_metric
from google_health_agent.analytics.quality import assess_quality, preferred_points
from google_health_agent.domain import DataSource, HealthDataPoint
from google_health_agent.providers.synthetic import SyntheticHealthProvider
from google_health_agent.service import HealthService
from google_health_agent.storage import HealthRepository


def _step(
    external_id: str,
    value: float,
    source: str,
    hour: int,
    *,
    priority: int = 100,
    tags: dict[str, str | int | float | bool] | None = None,
) -> HealthDataPoint:
    civil_day = date(2026, 1, 1)
    start = datetime(2026, 1, 1, hour, tzinfo=UTC)
    return HealthDataPoint(
        external_id=external_id,
        metric="steps",
        value=value,
        unit="count",
        start_time=start,
        end_time=start + timedelta(hours=1),
        utc_offset_minutes=0,
        civil_date=civil_day,
        source=DataSource(
            platform="TEST",
            source=source,
            priority=priority,
        ),
        ingested_at=datetime(2026, 1, 2, tzinfo=UTC),
        tags=tags or {},
    )


def test_summary_and_comparison_are_mathematical() -> None:
    summary = summarize_metric("hrv", [1, 2, 3, 4, 100], expected_count=10)
    assert summary.median == 3
    assert summary.q1 == 2
    assert summary.q3 == 4
    assert summary.iqr == 2
    assert summary.mad == 1
    assert summary.missing_rate == 0.5
    comparison = compare_periods("hrv", [10, 11, 12], [8, 9, 10])
    assert comparison.absolute_difference == 2
    assert comparison.percentage_difference == pytest.approx(22.2222, rel=1e-3)


@pytest.mark.asyncio
async def test_quality_and_step_source_priority() -> None:
    start = date(2026, 1, 1)
    end = start + timedelta(days=119)
    points = await SyntheticHealthProvider(7).fetch(start, end)
    selected, overlap = preferred_points(points)
    by_day = {}
    for point in selected:
        if point.metric == "steps":
            assert point.civil_date not in by_day
            by_day[point.civil_date] = point
    assert overlap
    assert all(issue.code == "suspected_step_double_counting" for issue in overlap)
    issues = assess_quality(selected, start, end)
    assert any(issue.code == "missing_data" for issue in issues)
    assert any(issue.code == "timezone_change" for issue in issues)
    assert any(issue.code == "source_change" for issue in issues)


@pytest.mark.asyncio
async def test_transparent_anomaly_detection() -> None:
    start = date(2026, 1, 1)
    points = await SyntheticHealthProvider(9).fetch(start, start + timedelta(days=119))
    step_points, _ = preferred_points([point for point in points if point.metric == "steps"])
    anomalies = detect_anomalies(step_points)
    assert anomalies
    assert all(
        item["description"] == "statistically unusual relative to personal baseline"
        for item in anomalies
    )


def test_preferred_step_source_retains_intraday_intervals_and_aggregates(tmp_path) -> None:
    points = [
        _step("watch-1", 100, "watch", 8, priority=10),
        _step("watch-2", 200, "watch", 9, priority=10),
        _step("phone-1", 900, "phone", 8, priority=20),
    ]
    selected, issues = preferred_points(points, preferred_source="watch")
    assert [point.external_id for point in selected] == ["watch-1", "watch-2"]
    assert issues[0].details["selected_source"] == "watch"

    repository = HealthRepository(f"sqlite:///{tmp_path / 'daily.sqlite'}")
    repository.initialize()
    repository.upsert(points)
    result = HealthService(repository, preferred_step_source="watch").metric(
        "steps", date(2026, 1, 1), date(2026, 1, 1)
    )
    assert result["summary"]["count"] == 1
    assert result["history"][0]["value"] == 300


def test_quality_codes_cover_provider_and_sampling_signals() -> None:
    point = _step(
        "duplicate",
        100,
        "watch",
        8,
        tags={
            "device_not_worn": True,
            "incomplete_day": True,
            "delayed_sync": True,
        },
    )
    overlapping = _step("phone", 50, "phone", 9)
    issues = assess_quality(
        [point, point, overlapping],
        date(2026, 1, 1),
        date(2026, 1, 10),
    )
    codes = {issue.code for issue in issues}
    assert {
        "device_not_worn",
        "incomplete_day",
        "delayed_sync",
        "duplicate_datapoint",
        "low_sample_count",
        "sparse_metric",
        "overlapping_source",
    } <= codes
