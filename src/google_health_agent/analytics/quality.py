from collections import Counter, defaultdict
from datetime import date, timedelta

from google_health_agent.domain import DataQualityIssue, HealthDataPoint


def preferred_points(
    points: list[HealthDataPoint],
) -> tuple[list[HealthDataPoint], list[DataQualityIssue]]:
    """Select one step source per day; never add overlapping totals."""
    grouped: dict[tuple[str, date], list[HealthDataPoint]] = defaultdict(list)
    others: list[HealthDataPoint] = []
    for point in points:
        if point.metric == "steps":
            grouped[(point.metric, point.civil_date)].append(point)
        else:
            others.append(point)
    selected = list(others)
    issues: list[DataQualityIssue] = []
    for (_, day), candidates in grouped.items():
        candidates.sort(key=lambda point: point.source.priority)
        selected.append(candidates[0])
        if len(candidates) > 1:
            issues.append(
                DataQualityIssue(
                    code="suspected_step_double_counting",
                    message=(
                        "Overlapping step sources detected; the highest-priority source was used."
                    ),
                    metric="steps",
                    date=day,
                    details={"source_count": len(candidates)},
                )
            )
    return selected, issues


def assess_quality(
    points: list[HealthDataPoint], start_date: date, end_date: date
) -> list[DataQualityIssue]:
    issues: list[DataQualityIssue] = []
    days = {start_date + timedelta(days=index) for index in range((end_date - start_date).days + 1)}
    present = {point.civil_date for point in points}
    for day in sorted(days - present):
        issues.append(
            DataQualityIssue(
                code="missing_data",
                message=(
                    "No wearable observations are available for this date; missing is not zero."
                ),
                date=day,
            )
        )
    offsets = {point.utc_offset_minutes for point in points}
    if len(offsets) > 1:
        issues.append(
            DataQualityIssue(
                code="timezone_change",
                message="Multiple UTC offsets occur in the requested period.",
                details={"offset_count": len(offsets)},
            )
        )
    sources = Counter(point.source.source for point in points)
    if len(sources) > 1:
        issues.append(
            DataQualityIssue(
                code="source_change",
                message="Multiple recording sources occur in the requested period.",
                details={"source_count": len(sources)},
            )
        )
    return issues
