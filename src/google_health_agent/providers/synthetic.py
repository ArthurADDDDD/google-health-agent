from datetime import UTC, date, datetime, time, timedelta

import numpy as np

from google_health_agent.domain import DataSource, HealthDataPoint
from google_health_agent.domain.models import RecordingMethod
from google_health_agent.providers.base import HealthProvider

METRIC_UNITS = {
    "sleep_minutes": "min",
    "deep_sleep_minutes": "min",
    "rem_sleep_minutes": "min",
    "light_sleep_minutes": "min",
    "awake_minutes": "min",
    "bedtime_minutes": "min_after_midnight",
    "wake_time_minutes": "min_after_midnight",
    "steps": "count",
    "active_minutes": "min",
    "sedentary_minutes": "min",
    "exercise_minutes": "min",
    "hrv": "ms",
    "resting_heart_rate": "bpm",
    "oxygen_saturation": "percent",
    "respiratory_rate": "breaths/min",
    "temperature_deviation": "celsius",
    "weight": "kg",
}


class SyntheticHealthProvider(HealthProvider):
    name = "synthetic"

    def __init__(self, seed: int = 20260724) -> None:
        self.seed = seed

    async def fetch(self, start_date: date, end_date: date) -> list[HealthDataPoint]:
        rng = np.random.default_rng(self.seed)
        days = (end_date - start_date).days + 1
        values: list[HealthDataPoint] = []
        wearable = DataSource(
            platform="SYNTHETIC",
            source="synthetic-wearable",
            device="Demo Watch",
            priority=10,
        )
        phone = DataSource(
            platform="SYNTHETIC",
            source="synthetic-phone",
            device="Demo Phone",
            recording_method=RecordingMethod.PASSIVE,
            priority=20,
        )

        for index in range(days):
            day = start_date + timedelta(days=index)
            is_weekend = day.weekday() >= 5
            travel = max(0, days - index) in range(72, 78)
            offset = 540 if travel else 480
            not_worn = max(0, days - index) in {48, 47, 46}
            stress_window = max(0, days - index) in range(8, 15)
            source_switch = max(0, days - index) in range(31, 36)
            daily_source = DataSource(
                platform="SYNTHETIC",
                source="synthetic-wearable-v2" if source_switch else wearable.source,
                device="Demo Watch 2" if source_switch else wearable.device,
                priority=wearable.priority,
            )
            if not_worn:
                continue

            sleep = 455 + (35 if is_weekend else 0) + rng.normal(0, 24)
            hrv = 52 + rng.normal(0, 6)
            rhr = 59 + rng.normal(0, 3)
            if stress_window:
                sleep -= 75
                hrv -= 13
                rhr += 8
            steps = max(1000, 8800 + (2200 if is_weekend else 0) + rng.normal(0, 1700))
            if index == days - 22:
                steps = 28000
            active = max(5, 42 + rng.normal(0, 14))
            metrics = {
                "sleep_minutes": sleep,
                "deep_sleep_minutes": sleep * (0.18 + rng.normal(0, 0.015)),
                "rem_sleep_minutes": sleep * (0.22 + rng.normal(0, 0.015)),
                "light_sleep_minutes": sleep * (0.53 + rng.normal(0, 0.02)),
                "awake_minutes": max(8, sleep * 0.07 + rng.normal(0, 4)),
                "bedtime_minutes": 23 * 60 + rng.normal(0, 25),
                "wake_time_minutes": 7 * 60 + rng.normal(0, 22),
                "steps": steps,
                "active_minutes": active,
                "sedentary_minutes": max(300, 900 - active - rng.normal(0, 45)),
                "exercise_minutes": max(0, active * 0.65 + rng.normal(0, 8)),
                "hrv": hrv,
                "resting_heart_rate": rhr,
                "oxygen_saturation": 97.2 + rng.normal(0, 0.45),
                "respiratory_rate": 15.2 + rng.normal(0, 0.7),
                "temperature_deviation": rng.normal(0, 0.18),
                "weight": 72 + rng.normal(0, 0.35),
            }
            # Deliberate sparse/missing points.
            if index % 17 == 0:
                metrics.pop("oxygen_saturation")
            if index % 23 == 0:
                metrics.pop("temperature_deviation")

            start = datetime.combine(day, time(), tzinfo=UTC)
            for metric, raw_value in metrics.items():
                values.append(
                    HealthDataPoint(
                        external_id=f"syn-{day.isoformat()}-{metric}-{daily_source.source}",
                        metric=metric,
                        value=round(float(raw_value), 3),
                        unit=METRIC_UNITS[metric],
                        start_time=start,
                        end_time=start + timedelta(days=1),
                        utc_offset_minutes=offset,
                        civil_date=day,
                        source=daily_source,
                        ingested_at=datetime.now(UTC),
                        tags={
                            "label": "SYNTHETIC DATA",
                            "travel": travel,
                            "stress_test_window": stress_window,
                            "source_switch": source_switch,
                        },
                    )
                )

            # A known overlapping phone step source; analytics must not sum it.
            if index % 11 == 0:
                values.append(
                    HealthDataPoint(
                        external_id=f"syn-{day.isoformat()}-steps-phone",
                        metric="steps",
                        value=round(float(steps * 0.88), 3),
                        unit="count",
                        start_time=start,
                        end_time=start + timedelta(days=1),
                        utc_offset_minutes=offset,
                        civil_date=day,
                        source=phone,
                        ingested_at=datetime.now(UTC),
                        tags={
                            "label": "SYNTHETIC DATA",
                            "overlapping_source": True,
                            "incomplete_day": True,
                            "delayed_sync": True,
                        },
                    )
                )
        return values
