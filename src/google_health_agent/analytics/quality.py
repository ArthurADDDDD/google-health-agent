from collections import Counter, defaultdict
from datetime import date, timedelta

from google_health_agent.domain import DataQualityIssue, HealthDataPoint


def preferred_points(
    points: list[HealthDataPoint],
    preferred_source: str | None = None,
) -> tuple[list[HealthDataPoint], list[DataQualityIssue]]:
    """Select one step source per day while retaining all of its intervals."""
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
        by_source: dict[str, list[HealthDataPoint]] = defaultdict(list)
        for candidate in candidates:
            by_source[candidate.source.source].append(candidate)
        chosen_source = min(
            by_source,
            key=lambda source: (
                0 if preferred_source and source == preferred_source else 1,
                min(point.source.priority for point in by_source[source]),
                source,
            ),
        )
        selected.extend(by_source[chosen_source])
        if len(by_source) > 1:
            issues.append(
                DataQualityIssue(
                    code="suspected_step_double_counting",
                    message=(
                        "Overlapping step sources detected; the highest-priority source was used."
                    ),
                    metric="steps",
                    date=day,
                    details={
                        "source_count": len(by_source),
                        "selected_source": chosen_source,
                    },
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
    identifiers = Counter(point.external_id for point in points)
    for duplicate_count in identifiers.values():
        if duplicate_count > 1:
            issues.append(
                DataQualityIssue(
                    code="duplicate_datapoint",
                    message="The same provider data point appears more than once.",
                    details={"duplicate_count": duplicate_count},
                )
            )
    for point in points:
        if point.tags.get("device_not_worn"):
            issues.append(
                DataQualityIssue(
                    code="device_not_worn",
                    message="The source reports that the wearable was not worn.",
                    metric=point.metric,
                    date=point.civil_date,
                )
            )
        if point.tags.get("incomplete_day"):
            issues.append(
                DataQualityIssue(
                    code="incomplete_day",
                    message="The source marks this civil day as incomplete.",
                    metric=point.metric,
                    date=point.civil_date,
                )
            )
        if point.tags.get("delayed_sync"):
            issues.append(
                DataQualityIssue(
                    code="delayed_sync",
                    message="The source reports that this point arrived after a sync delay.",
                    metric=point.metric,
                    date=point.civil_date,
                )
            )
    metric_days: dict[str, set[date]] = defaultdict(set)
    metric_counts: Counter[str] = Counter()
    metric_sources: dict[tuple[str, date], set[str]] = defaultdict(set)
    for point in points:
        metric_days[point.metric].add(point.civil_date)
        metric_counts[point.metric] += 1
        metric_sources[(point.metric, point.civil_date)].add(point.source.source)
    expected_days = max(1, len(days))
    for metric, observed_days in metric_days.items():
        if len(observed_days) < expected_days * 0.8:
            issues.append(
                DataQualityIssue(
                    code="sparse_metric",
                    message="This metric is present on fewer than 80% of requested days.",
                    metric=metric,
                    details={"observed_days": len(observed_days), "expected_days": expected_days},
                )
            )
        if metric_counts[metric] < max(3, expected_days // 2):
            issues.append(
                DataQualityIssue(
                    code="low_sample_count",
                    message="This metric has too few samples for a confident trend.",
                    metric=metric,
                    details={"sample_count": metric_counts[metric]},
                )
            )
    for (metric, civil_day), source_names in metric_sources.items():
        if len(source_names) > 1:
            issues.append(
                DataQualityIssue(
                    code="overlapping_source",
                    message="Multiple sources recorded the same metric on the same civil day.",
                    metric=metric,
                    date=civil_day,
                    details={"source_count": len(source_names)},
                )
            )
    return issues
