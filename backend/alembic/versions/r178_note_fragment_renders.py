"""note_fragment_renders — the composition gate's memory

A non-prompt renders only on CHANGE against the previous note's state for its
IDENTITY. "The same true thing, unchanged" needs something that remembers what
was said and what it was about; `daily_notes` records that a day existed, not
what it contained.

⚠️ NOT NULL FROM THE START, and that is not a contradiction of r176's
expand/contract note. r176 had to widen-then-tighten because a live writer was
serving traffic against the old schema during the deploy. This is a NEW table
with no writer at all, so there is no old code to break and no window to protect.
The rule was about deploy choreography, not about NOT NULL being unsafe.

Revision ID: r178_note_fragment_renders
Revises: r177_anomaly_supersede_constraints
"""

import sqlalchemy as sa
from alembic import op

revision = "r178_note_fragment_renders"
down_revision = "r177_anomaly_supersede_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "note_fragment_renders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("daily_note_id", sa.String(36),
                  sa.ForeignKey("daily_notes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.String(36),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("note_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fragment_id", sa.String(100), nullable=False),
        # 255, not 36: subjects are composites after the anomaly-subject arc.
        sa.Column("instance_key", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("change_digest", sa.String(64), nullable=False),
        sa.Column("change_inputs", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_note_fragment_renders_daily_note_id",
                    "note_fragment_renders", ["daily_note_id"])
    # One record per identity per note: a second render of the same identity on
    # the same note is a bug, not a second occurrence.
    op.create_unique_constraint(
        "uq_note_fragment_renders_identity", "note_fragment_renders",
        ["daily_note_id", "fragment_id", "instance_key"],
    )
    # The gate's read path.
    op.create_index(
        "ix_note_fragment_renders_lookup", "note_fragment_renders",
        ["user_id", "fragment_id", "instance_key", "note_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_note_fragment_renders_lookup", table_name="note_fragment_renders")
    op.drop_constraint("uq_note_fragment_renders_identity",
                       "note_fragment_renders", type_="unique")
    op.drop_index("ix_note_fragment_renders_daily_note_id", table_name="note_fragment_renders")
    op.drop_table("note_fragment_renders")
