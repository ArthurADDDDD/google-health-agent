from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DataPointRow(Base):
    __tablename__ = "health_data_points"
    __table_args__ = (UniqueConstraint("external_id", name="uq_health_data_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    metric: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(40))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    utc_offset_minutes: Mapped[int] = mapped_column(Integer)
    civil_date: Mapped[date] = mapped_column(Date, index=True)
    platform: Mapped[str] = mapped_column(String(80))
    source: Mapped[str] = mapped_column(String(160))
    recording_method: Mapped[str] = mapped_column(String(40))
    device: Mapped[str | None] = mapped_column(String(160))
    source_priority: Mapped[int] = mapped_column(Integer)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    synthetic: Mapped[bool]
    tags: Mapped[dict[str, str | int | float | bool]] = mapped_column(JSON)
