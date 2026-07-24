from collections.abc import Sequence

import numpy as np

from google_health_agent.domain import DataQualityIssue, HealthDataPoint, MetricSummary
from google_health_agent.domain.models import PeriodComparison


def summarize_metric(
    metric: str, values: Sequence[float], expected_count: int | None = None
) -> MetricSummary:
    array = np.asarray(values, dtype=float)
    count = int(array.size)
    missing_rate = 0.0
    if expected_count:
        missing_rate = max(0.0, (expected_count - count) / expected_count)
    if count == 0:
        return MetricSummary(
            metric=metric,
            count=0,
            missing_rate=missing_rate,
            mean=None,
            median=None,
            min=None,
            max=None,
            q1=None,
            q3=None,
            iqr=None,
            mad=None,
            standard_deviation=None,
            trend_slope=None,
        )
    median = float(np.median(array))
    q1, q3 = (float(value) for value in np.percentile(array, [25, 75]))
    slope = None
    if count >= 3 and not np.allclose(array, array[0]):
        slope = float(np.polyfit(np.arange(count), array, 1)[0])
    return MetricSummary(
        metric=metric,
        count=count,
        missing_rate=missing_rate,
        mean=float(np.mean(array)),
        median=median,
        min=float(np.min(array)),
        max=float(np.max(array)),
        q1=q1,
        q3=q3,
        iqr=q3 - q1,
        mad=float(np.median(np.abs(array - median))),
        standard_deviation=float(np.std(array, ddof=1)) if count > 1 else 0.0,
        trend_slope=slope,
    )


def compare_periods(
    metric: str, values_a: Sequence[float], values_b: Sequence[float]
) -> PeriodComparison:
    median_a = float(np.median(values_a)) if values_a else None
    median_b = float(np.median(values_b)) if values_b else None
    difference = median_a - median_b if median_a is not None and median_b is not None else None
    percentage = None
    if difference is not None and median_b is not None and median_b != 0:
        percentage = difference / abs(median_b) * 100
    issues: list[DataQualityIssue] = []
    if len(values_a) < 3 or len(values_b) < 3:
        issues.append(
            DataQualityIssue(
                code="low_sample_count",
                message="Comparison has fewer than three observations in at least one period.",
                metric=metric,
            )
        )
    return PeriodComparison(
        metric=metric,
        median_a=median_a,
        median_b=median_b,
        absolute_difference=difference,
        percentage_difference=percentage,
        sample_count_a=len(values_a),
        sample_count_b=len(values_b),
        data_quality=issues,
    )


def detect_anomalies(points: Sequence[HealthDataPoint]) -> list[dict[str, object]]:
    if len(points) < 5:
        return []
    values = np.asarray([point.value for point in points], dtype=float)
    median = np.median(values)
    mad = np.median(np.abs(values - median))
    if mad == 0:
        return []
    scores = 0.6745 * (values - median) / mad
    return [
        {
            "date": point.civil_date.isoformat(),
            "value": point.value,
            "robust_z_score": round(float(score), 3),
            "description": "statistically unusual relative to personal baseline",
        }
        for point, score in zip(points, scores, strict=True)
        if abs(score) > 3.5
    ]
