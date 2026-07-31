from collections import defaultdict
from datetime import date, timedelta
from statistics import median
from typing import Any

from google_health_agent.analytics import (
    compare_periods,
    detect_anomalies,
    summarize_metric,
)
from google_health_agent.analytics.quality import assess_quality, preferred_points
from google_health_agent.domain import DataQualityIssue, HealthDataPoint
from google_health_agent.errors import InvalidDateRange
from google_health_agent.storage import HealthRepository

SLEEP_METRICS = (
    "sleep_minutes",
    "bedtime_minutes",
    "wake_time_minutes",
    "deep_sleep_minutes",
    "rem_sleep_minutes",
    "light_sleep_minutes",
    "awake_minutes",
)
RECOVERY_METRICS = (
    "hrv",
    "resting_heart_rate",
    "oxygen_saturation",
    "respiratory_rate",
    "temperature_deviation",
)
ACTIVITY_METRICS = (
    "steps",
    "active_minutes",
    "active_zone_minutes",
    "sedentary_minutes",
    "exercise_minutes",
)
ADDITIVE_METRICS = {
    "sleep_minutes",
    "deep_sleep_minutes",
    "rem_sleep_minutes",
    "light_sleep_minutes",
    "awake_minutes",
    "steps",
    "active_minutes",
    "active_zone_minutes",
    "sedentary_minutes",
    "exercise_minutes",
}


class HealthService:
    """Read-only application service used by CLI and MCP boundaries."""

    def __init__(
        self,
        repository: HealthRepository,
        *,
        data_label: str = "SYNTHETIC DATA",
        preferred_step_source: str | None = None,
        synthetic: bool = True,
    ) -> None:
        self.repository = repository
        self.data_label = data_label
        self.preferred_step_source = preferred_step_source
        self.synthetic = synthetic

    @staticmethod
    def _window(days: int, end_date: date | None, maximum: int = 365) -> tuple[date, date]:
        if days < 1 or days > maximum:
            raise InvalidDateRange(f"Please request a smaller date range (1-{maximum} days).")
        end = end_date or date.today()
        return end - timedelta(days=days - 1), end

    def _load(
        self, days: int, end_date: date | None, maximum: int = 365
    ) -> tuple[date, date, list[HealthDataPoint], list[DataQualityIssue]]:
        start, end = self._window(days, end_date, maximum)
        raw = self.repository.query(start, end, synthetic=self.synthetic)
        selected, overlap = preferred_points(raw, self.preferred_step_source)
        points = self._daily_points(selected)
        return start, end, points, assess_quality(raw, start, end) + overlap

    @staticmethod
    def _quality_payload(issues: list[DataQualityIssue]) -> list[dict[str, Any]]:
        return [issue.model_dump(mode="json") for issue in issues]

    @staticmethod
    def _group(points: list[HealthDataPoint]) -> dict[str, list[HealthDataPoint]]:
        grouped: dict[str, list[HealthDataPoint]] = defaultdict(list)
        for point in points:
            grouped[point.metric].append(point)
        return grouped

    @staticmethod
    def _daily_points(points: list[HealthDataPoint]) -> list[HealthDataPoint]:
        grouped: dict[tuple[str, date], list[HealthDataPoint]] = defaultdict(list)
        for point in points:
            grouped[(point.metric, point.civil_date)].append(point)
        daily: list[HealthDataPoint] = []
        for (metric, _), metric_points in sorted(grouped.items()):
            values = [point.value for point in metric_points]
            value = sum(values) if metric in ADDITIVE_METRICS else median(values)
            daily.append(metric_points[0].model_copy(update={"value": value}))
        return daily

    @staticmethod
    def _sources(points: list[HealthDataPoint]) -> list[dict[str, Any]]:
        seen: dict[tuple[str, str, str], dict[str, Any]] = {}
        for point in points:
            key = (
                point.source.platform,
                point.source.source,
                point.source.recording_method.value,
            )
            seen[key] = point.source.model_dump(mode="json")
        return list(seen.values())

    @staticmethod
    def _summary(metric: str, points: list[HealthDataPoint], expected_count: int) -> dict[str, Any]:
        return summarize_metric(
            metric, [point.value for point in points], expected_count
        ).model_dump(mode="json")

    def overview(self, days: int = 30, end_date: date | None = None) -> dict[str, Any]:
        start, end, points, issues = self._load(days, end_date)
        grouped = self._group(points)
        selected_metrics = SLEEP_METRICS[:1] + RECOVERY_METRICS + ACTIVITY_METRICS[:2]
        summaries = {
            metric: self._summary(metric, grouped.get(metric, []), days)
            for metric in selected_metrics
        }
        anomalies = {
            metric: detect_anomalies(grouped.get(metric, []))
            for metric in selected_metrics
            if grouped.get(metric)
        }
        return {
            "data_label": self.data_label,
            "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
            "summaries": summaries,
            "statistically_unusual": anomalies,
            "data_quality": self._quality_payload(issues),
            "sources": self._sources(points),
        }

    def category(
        self,
        metrics: tuple[str, ...],
        days: int = 30,
        end_date: date | None = None,
        include_history: bool = True,
    ) -> dict[str, Any]:
        start, end, points, issues = self._load(days, end_date)
        grouped = self._group([point for point in points if point.metric in metrics])
        payload: dict[str, Any] = {
            "data_label": self.data_label,
            "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
            "summaries": {
                metric: self._summary(metric, grouped.get(metric, []), days) for metric in metrics
            },
            "data_quality": self._quality_payload(issues),
            "sources": self._sources(points),
        }
        if include_history:
            payload["daily_history"] = {
                metric: [
                    {
                        "date": point.civil_date.isoformat(),
                        "value": point.value,
                        "unit": point.unit,
                    }
                    for point in grouped.get(metric, [])
                ]
                for metric in metrics
            }
        return payload

    def metric(
        self,
        metric: str,
        start_date: date,
        end_date: date,
        granularity: str = "daily",
    ) -> dict[str, Any]:
        days = (end_date - start_date).days + 1
        if granularity not in {"daily", "summary"}:
            raise InvalidDateRange("granularity must be 'daily' or 'summary'.")
        if days < 1 or days > 365:
            raise InvalidDateRange("Please request a smaller date range (maximum 365 days).")
        raw = self.repository.query(start_date, end_date, metric, synthetic=self.synthetic)
        selected, issues = preferred_points(raw, self.preferred_step_source)
        points = self._daily_points(selected)
        result: dict[str, Any] = {
            "data_label": self.data_label,
            "metric": metric,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "summary": self._summary(metric, points, days),
            "data_quality": self._quality_payload(
                assess_quality(raw, start_date, end_date) + issues
            ),
            "sources": self._sources(points),
        }
        if granularity == "daily":
            result["history"] = [
                {
                    "date": point.civil_date.isoformat(),
                    "value": point.value,
                    "unit": point.unit,
                }
                for point in points
            ]
        return result

    def compare(
        self,
        metric: str,
        period_a_start: date,
        period_a_end: date,
        period_b_start: date,
        period_b_end: date,
    ) -> dict[str, Any]:
        for start, end in (
            (period_a_start, period_a_end),
            (period_b_start, period_b_end),
        ):
            days = (end - start).days + 1
            if days < 1 or days > 365:
                raise InvalidDateRange("Each comparison period must be 1-365 days.")
        raw_a = self.repository.query(
            period_a_start, period_a_end, metric, synthetic=self.synthetic
        )
        raw_b = self.repository.query(
            period_b_start, period_b_end, metric, synthetic=self.synthetic
        )
        selected_a, _ = preferred_points(raw_a, self.preferred_step_source)
        selected_b, _ = preferred_points(raw_b, self.preferred_step_source)
        values_a = [point.value for point in self._daily_points(selected_a)]
        values_b = [point.value for point in self._daily_points(selected_b)]
        return {
            "data_label": self.data_label,
            "period_a": {
                "start_date": period_a_start.isoformat(),
                "end_date": period_a_end.isoformat(),
            },
            "period_b": {
                "start_date": period_b_start.isoformat(),
                "end_date": period_b_end.isoformat(),
            },
            "comparison": compare_periods(metric, values_a, values_b).model_dump(mode="json"),
        }

    def quality(self, days: int = 30, end_date: date | None = None) -> dict[str, Any]:
        start, end, points, issues = self._load(days, end_date)
        missing_days = sorted(
            issue.date.isoformat()
            for issue in issues
            if issue.code == "missing_data" and issue.date
        )
        codes: defaultdict[str, int] = defaultdict(int)
        for issue in issues:
            codes[issue.code] += 1
        return {
            "data_label": self.data_label,
            "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
            "completeness": round(1 - len(missing_days) / max(1, (end - start).days + 1), 4),
            "missing_days": missing_days,
            "source_changes": codes["source_change"],
            "timezone_changes": codes["timezone_change"],
            "duplicate_warnings": codes["duplicate_datapoint"],
            "suspected_double_counting": codes["suspected_step_double_counting"],
            "sample_counts": {
                metric: len(metric_points) for metric, metric_points in self._group(points).items()
            },
            "issues": self._quality_payload(issues),
        }
