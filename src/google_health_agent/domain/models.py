from datetime import date as Date
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecordingMethod(StrEnum):
    PASSIVE = "passively_measured"
    ACTIVE = "actively_measured"
    MANUAL = "manual"
    DERIVED = "derived"


class DataSource(BaseModel):
    platform: str
    source: str
    recording_method: RecordingMethod = RecordingMethod.PASSIVE
    device: str | None = None
    priority: int = 100


class HealthDataPoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    external_id: str
    metric: str
    value: float
    unit: str
    start_time: datetime
    end_time: datetime
    utc_offset_minutes: int = Field(ge=-14 * 60, le=14 * 60)
    civil_date: Date
    source: DataSource
    ingested_at: datetime
    synthetic: bool = True
    tags: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_interval(self) -> "HealthDataPoint":
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        if self.end_time < self.start_time:
            raise ValueError("end_time must not precede start_time")
        return self


class SleepStage(BaseModel):
    stage: str
    start_time: datetime
    end_time: datetime
    duration_minutes: float = Field(ge=0)


class SleepSession(BaseModel):
    external_id: str
    civil_date: Date
    start_time: datetime
    end_time: datetime
    utc_offset_minutes: int
    source: DataSource
    stages: list[SleepStage] = Field(default_factory=list)
    synthetic: bool = True


class DataQualityIssue(BaseModel):
    code: str
    severity: str = "warning"
    message: str
    metric: str | None = None
    date: Date | None = None
    details: dict[str, str | int | float | bool] = Field(default_factory=dict)


class MetricSummary(BaseModel):
    metric: str
    count: int
    missing_rate: float
    mean: float | None
    median: float | None
    min: float | None
    max: float | None
    q1: float | None
    q3: float | None
    iqr: float | None
    mad: float | None
    standard_deviation: float | None
    trend_slope: float | None


class PeriodComparison(BaseModel):
    metric: str
    median_a: float | None
    median_b: float | None
    absolute_difference: float | None
    percentage_difference: float | None
    sample_count_a: int
    sample_count_b: int
    data_quality: list[DataQualityIssue] = Field(default_factory=list)
