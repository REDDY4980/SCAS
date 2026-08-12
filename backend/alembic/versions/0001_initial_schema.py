"""initial schema - all AIB Vol 5.3 tables

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-09

AIB v1.0 Vol 5.3 (Database Engineering): users, farms, soil_reports,
soil_parameters, weather_snapshots, recommendations,
fertilizer_recommendations, user_settings.
Vol 5.5: UUID primary keys, enforced foreign keys, unique email/phone.
Vol 5.6: indexes on email, phone, farm_id, report_id, created_at and
recommendation lookup fields.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("phone", name="uq_users_phone"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_phone", "users", ["phone"])

    op.create_table(
        "farms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("farm_name", sa.String(150), nullable=False),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("district", sa.String(100), nullable=False),
        sa.Column("village", sa.String(150), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("soil_type", sa.String(50), nullable=True),
        sa.Column("area_acres", sa.Numeric(8, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_farms_user_id", "farms", ["user_id"])

    op.create_table(
        "soil_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "farm_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(10), nullable=False),
        sa.Column("ocr_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_soil_reports_farm_id", "soil_reports", ["farm_id"])

    op.create_table(
        "soil_parameters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("soil_reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ph", sa.Float(), nullable=True),
        sa.Column("ec", sa.Float(), nullable=True),
        sa.Column("organic_carbon", sa.Float(), nullable=True),
        sa.Column("nitrogen", sa.Float(), nullable=True),
        sa.Column("phosphorus", sa.Float(), nullable=True),
        sa.Column("potassium", sa.Float(), nullable=True),
        sa.Column("zinc", sa.Float(), nullable=True),
        sa.Column("iron", sa.Float(), nullable=True),
        sa.Column("manganese", sa.Float(), nullable=True),
        sa.Column("copper", sa.Float(), nullable=True),
        sa.Column("boron", sa.Float(), nullable=True),
        sa.UniqueConstraint("report_id", name="uq_soil_parameters_report_id"),
    )
    op.create_index("ix_soil_parameters_report_id", "soil_parameters", ["report_id"])

    op.create_table(
        "weather_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "farm_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("humidity", sa.Float(), nullable=True),
        sa.Column("rainfall", sa.Float(), nullable=True),
        sa.Column("wind_speed", sa.Float(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_weather_snapshots_farm_id", "weather_snapshots", ["farm_id"])

    op.create_table(
        "recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "farm_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("soil_reports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "weather_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("weather_snapshots.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("recommended_crop", sa.String(100), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_recommendations_farm_id", "recommendations", ["farm_id"])
    op.create_index("ix_recommendations_report_id", "recommendations", ["report_id"])
    op.create_index("ix_recommendations_created_at", "recommendations", ["created_at"])

    op.create_table(
        "fertilizer_recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "recommendation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recommendations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fertilizer_name", sa.String(150), nullable=False),
        sa.Column("dosage", sa.String(150), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_fertilizer_recommendations_recommendation_id",
        "fertilizer_recommendations",
        ["recommendation_id"],
    )

    op.create_table(
        "user_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("theme", sa.String(10), nullable=False, server_default="system"),
        sa.Column("notifications", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("user_id", name="uq_user_settings_user_id"),
    )
    op.create_index("ix_user_settings_user_id", "user_settings", ["user_id"])


def downgrade() -> None:
    op.drop_table("user_settings")
    op.drop_table("fertilizer_recommendations")
    op.drop_table("recommendations")
    op.drop_table("weather_snapshots")
    op.drop_table("soil_parameters")
    op.drop_table("soil_reports")
    op.drop_table("farms")
    op.drop_table("users")
