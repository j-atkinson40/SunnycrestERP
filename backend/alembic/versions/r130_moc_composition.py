"""The Map Home campaign — the composition store (commit set 1/5).

`moc_composition`: platform-tier authored compositions, ONE store for both
kinds — `area` (an area overview ponder's philosophy captions, overlaying
the deriver's honest placeholders; keyed by the vocabulary type + vertical)
and `onboarding` (fully-authored beat sequences — a curriculum LIST, not an
engine; `sequence` orders them). Captions follow the task-ponder pattern
(beat_key → authored text, derived fallback never stale).

Revision ID: r130_moc_composition
Revises: r129_workflow_schedule_retired
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r130_moc_composition"
down_revision = "r129_workflow_schedule_retired"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moc_composition",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("vertical", sa.String(50), nullable=True),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("captions", JSONB, nullable=True),
        sa.Column("beats", JSONB, nullable=True),
        sa.Column("sequence", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('area', 'onboarding')", name="ck_moc_composition_kind"),
    )
    op.create_index(
        "ux_moc_composition_kind_key_vertical", "moc_composition",
        ["kind", "key", "vertical"], unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_moc_composition_kind_key_vertical", table_name="moc_composition")
    op.drop_table("moc_composition")
