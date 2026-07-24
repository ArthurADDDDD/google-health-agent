"""Create normalized health data point storage."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "health_data_points",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("metric", sa.String(length=80), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("utc_offset_minutes", sa.Integer(), nullable=False),
        sa.Column("civil_date", sa.Date(), nullable=False),
        sa.Column("platform", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=160), nullable=False),
        sa.Column("recording_method", sa.String(length=40), nullable=False),
        sa.Column("device", sa.String(length=160), nullable=True),
        sa.Column("source_priority", sa.Integer(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("synthetic", sa.Boolean(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id", name="uq_health_data_external_id"),
    )
    op.create_index("ix_health_data_points_civil_date", "health_data_points", ["civil_date"])
    op.create_index("ix_health_data_points_metric", "health_data_points", ["metric"])


def downgrade() -> None:
    op.drop_index("ix_health_data_points_metric", table_name="health_data_points")
    op.drop_index("ix_health_data_points_civil_date", table_name="health_data_points")
    op.drop_table("health_data_points")
