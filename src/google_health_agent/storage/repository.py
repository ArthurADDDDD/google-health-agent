from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from google_health_agent.domain import DataSource, HealthDataPoint
from google_health_agent.domain.models import RecordingMethod
from google_health_agent.storage.models import Base, DataPointRow


class HealthRepository:
    def __init__(self, database_url: str) -> None:
        if database_url.startswith("sqlite:///"):
            Path(database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(database_url)

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)

    def replace_synthetic(self, points: list[HealthDataPoint]) -> int:
        with Session(self.engine) as session:
            session.execute(delete(DataPointRow).where(DataPointRow.synthetic.is_(True)))
            session.commit()
        return self.upsert(points)

    def upsert(self, points: list[HealthDataPoint]) -> int:
        rows = [self._to_row(point) for point in points]
        if not rows:
            return 0
        with Session(self.engine) as session:
            if self.engine.dialect.name == "sqlite":
                statement = sqlite_insert(DataPointRow).values(rows)
                statement = statement.on_conflict_do_update(
                    index_elements=["external_id"],
                    set_={key: getattr(statement.excluded, key) for key in rows[0] if key != "id"},
                )
                session.execute(statement)
            else:
                for row in rows:
                    existing = session.scalar(
                        select(DataPointRow).where(DataPointRow.external_id == row["external_id"])
                    )
                    if existing:
                        for key, value in row.items():
                            setattr(existing, key, value)
                    else:
                        session.add(DataPointRow(**row))
            session.commit()
        return len(rows)

    def query(
        self, start_date: date, end_date: date, metric: str | None = None
    ) -> list[HealthDataPoint]:
        statement = (
            select(DataPointRow)
            .where(DataPointRow.civil_date.between(start_date, end_date))
            .order_by(DataPointRow.civil_date, DataPointRow.metric, DataPointRow.source_priority)
        )
        if metric:
            statement = statement.where(DataPointRow.metric == metric)
        with Session(self.engine) as session:
            return [self._from_row(row) for row in session.scalars(statement)]

    def count(self) -> int:
        with Session(self.engine) as session:
            return int(session.scalar(select(func.count()).select_from(DataPointRow)) or 0)

    def ready(self) -> bool:
        try:
            with self.engine.connect() as connection:
                connection.execute(select(1))
            return True
        except SQLAlchemyError:
            return False

    @staticmethod
    def _to_row(point: HealthDataPoint) -> dict[str, object]:
        return {
            "external_id": point.external_id,
            "metric": point.metric,
            "value": point.value,
            "unit": point.unit,
            "start_time": point.start_time,
            "end_time": point.end_time,
            "utc_offset_minutes": point.utc_offset_minutes,
            "civil_date": point.civil_date,
            "platform": point.source.platform,
            "source": point.source.source,
            "recording_method": point.source.recording_method.value,
            "device": point.source.device,
            "source_priority": point.source.priority,
            "ingested_at": point.ingested_at,
            "synthetic": point.synthetic,
            "tags": point.tags,
        }

    @staticmethod
    def _from_row(row: DataPointRow) -> HealthDataPoint:
        def as_utc(value: datetime) -> datetime:
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value

        return HealthDataPoint(
            external_id=row.external_id,
            metric=row.metric,
            value=row.value,
            unit=row.unit,
            start_time=as_utc(row.start_time),
            end_time=as_utc(row.end_time),
            utc_offset_minutes=row.utc_offset_minutes,
            civil_date=row.civil_date,
            source=DataSource(
                platform=row.platform,
                source=row.source,
                recording_method=RecordingMethod(row.recording_method),
                device=row.device,
                priority=row.source_priority,
            ),
            ingested_at=as_utc(row.ingested_at),
            synthetic=row.synthetic,
            tags=row.tags,
        )
