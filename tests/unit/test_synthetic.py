from datetime import date, timedelta

import pytest

from google_health_agent.providers.synthetic import SyntheticHealthProvider


@pytest.mark.asyncio
async def test_synthetic_is_deterministic_and_has_required_scenarios() -> None:
    start = date(2026, 1, 1)
    end = start + timedelta(days=119)
    first = await SyntheticHealthProvider(42).fetch(start, end)
    second = await SyntheticHealthProvider(42).fetch(start, end)
    comparable = [(p.external_id, p.metric, p.value, p.utc_offset_minutes) for p in first]
    assert comparable == [(p.external_id, p.metric, p.value, p.utc_offset_minutes) for p in second]
    assert all(point.synthetic for point in first)
    assert all(point.tags["label"] == "SYNTHETIC DATA" for point in first)
    observed_days = {point.civil_date for point in first}
    assert len(observed_days) == 117  # three device-not-worn days
    assert len({point.utc_offset_minutes for point in first}) == 2
    assert any(point.tags.get("stress_test_window") for point in first)
    assert any(point.tags.get("source_switch") for point in first)
    step_counts: dict[date, int] = {}
    for point in first:
        if point.metric == "steps":
            step_counts[point.civil_date] = step_counts.get(point.civil_date, 0) + 1
    assert any(count > 1 for count in step_counts.values())
