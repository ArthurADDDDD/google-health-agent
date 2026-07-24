from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from google_health_agent.domain import DataSource, HealthDataPoint


def test_datapoint_requires_aware_ordered_timestamps() -> None:
    with pytest.raises(ValidationError):
        HealthDataPoint(
            external_id="x",
            metric="steps",
            value=1,
            unit="count",
            start_time=datetime(2026, 1, 2, tzinfo=UTC),
            end_time=datetime(2026, 1, 1, tzinfo=UTC),
            utc_offset_minutes=480,
            civil_date=date(2026, 1, 1),
            source=DataSource(platform="SYNTHETIC", source="test"),
            ingested_at=datetime.now(UTC),
        )
