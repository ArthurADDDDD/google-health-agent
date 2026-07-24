from datetime import date, timedelta

import pytest

from google_health_agent.analytics import compare_periods, detect_anomalies, summarize_metric
from google_health_agent.analytics.quality import assess_quality, preferred_points
from google_health_agent.providers.synthetic import SyntheticHealthProvider


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
