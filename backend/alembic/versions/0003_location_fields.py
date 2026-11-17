"""save detected location on the farmer profile and record how farm coordinates were obtained

Revision ID: 0003_location_fields
Revises: 0002_widen_fertilizer_dosage
Create Date: 2026-10-22

GPS coordinates captured by the app were only kept on a farm (and only
when the browser answered within 8 seconds); the farmer profile had no
location at all. This adds the farmer's last detected location to
`users` and a `location_source` / accuracy to `farms`, so the app can
show whether a farm's position came from GPS or from the typed district.
Existing farms that already have coordinates are marked "district",
because before this change GPS and geocoded points were indistinguishable.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0003_location_fields"
down_revision: Union[str, None] = "0002_widen_fertilizer_dosage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("users", sa.Column("longitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("users", sa.Column("location_accuracy_m", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("location_source", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("location_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("farms", sa.Column("location_source", sa.String(20), nullable=True))
    op.add_column("farms", sa.Column("location_accuracy_m", sa.Float(), nullable=True))
    op.execute("UPDATE farms SET location_source = 'district' WHERE latitude IS NOT NULL AND longitude IS NOT NULL")


def downgrade() -> None:
    op.drop_column("farms", "location_accuracy_m")
    op.drop_column("farms", "location_source")
    for col in ("location_updated_at", "location_source", "location_accuracy_m", "longitude", "latitude"):
        op.drop_column("users", col)
