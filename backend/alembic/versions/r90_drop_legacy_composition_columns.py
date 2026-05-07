"""Phase R-3.2 — drop legacy focus_compositions.placements column.

R-3.0 introduced the canonical `rows` JSONB column on
`focus_compositions` and retained the legacy flat `placements` column
"for one-release grace". App code post-R-3.0 reads/writes only `rows`
— `placements` was kept solely as a defensive backstop in case a
downgrade to pre-R-3.0 code was needed.

R-3.1 + R-3.1.2 + R-3.1.3 stabilized the rows-shape contract end-to-end
(visual editor authoring, Playwright specs 17-20, merge migration,
fail-loud deploy gate). The grace period closes with R-3.2.

Schema changes:
  - Drop `focus_compositions.placements` column.
  - `canvas_config` JSONB column STAYS — still actively used for
    cosmetic settings (gap_size, background_treatment, padding). The
    legacy keys investigation showed `total_columns`, `row_height`
    (canvas-level), and `responsive_breakpoints` are not present in
    any seeded DB row, so no JSONB key cleanup is required.

Data:
  - Pre-R-3.0 flat-placements data was migrated to `rows` via r88's
    backfill helper. Post-R-3.0 rows always have `placements=[]`
    (defensive empty write). No data is lost on drop.

Downgrade:
  - Restores `placements` as nullable JSONB. Pre-R-3.0 flat-shape
    data is NOT recoverable from rows-shape (rows-shape is more
    expressive; a downgrade after rows-aware authoring would lose
    information). The downgrade exists for migration-tooling
    completeness, not as an operational rollback path.

Revision ID: r90_drop_legacy_composition_columns
Revises: r89_merge_r48_fh_email_tld_into_r88
Create Date: 2026-05-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "r90_drop_legacy_composition_columns"
down_revision: Union[str, Sequence[str], None] = (
    "r89_merge_r48_fh_email_tld_into_r88"
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("focus_compositions", "placements")


def downgrade() -> None:
    # Best-effort reversibility — column shape restored, data not
    # recoverable from rows. Nullable so downgrade-then-insert paths
    # don't trip on missing values; pre-R-3.0 callers that wrote
    # placements would still need to populate it explicitly.
    op.add_column(
        "focus_compositions",
        sa.Column(
            "placements",
            JSONB,
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
