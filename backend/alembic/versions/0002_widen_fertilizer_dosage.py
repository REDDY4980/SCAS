"""widen fertilizer_recommendations.dosage to Text

Revision ID: 0002_widen_fertilizer_dosage
Revises: 0001_initial_schema
Create Date: 2026-08-11

The fallback (no-KB-match) dosage value is a full explanatory sentence
("Dosage not available — no source-traceable crop-specific
recommendation exists yet for <crop> in the starter knowledge base.
Consult a local agricultural extension officer or a soil-test-based
(STCR) recommendation before applying.") rather than a short "N kg/ha"
figure — see FertilizerSelector._fallback_recommendation. That message
alone is 200+ characters before the crop name is even substituted in,
so String(150) overflowed on every crop without a curated knowledge-base
entry, causing a hard DB error instead of returning the honest fallback
text. Widened to Text, matching the sibling `reason` column.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_widen_fertilizer_dosage"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "fertilizer_recommendations",
        "dosage",
        existing_type=sa.String(150),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "fertilizer_recommendations",
        "dosage",
        existing_type=sa.Text(),
        type_=sa.String(150),
        existing_nullable=False,
    )
