"""note_settled_records — the past-tense record on a settled note

⚠️ UNIQUENESS INCLUDES THE OUTCOME. A prompt can end more than one way on the
same day: three tasks due today, two done and one cancelled, is TWO records —
"you completed 2 tasks due today" and "you cancelled 1 task due today" — not one
row that has to pick which happened.

Keyed on the SUBJECT and the outcome, never on the run. Settling fires from a
*/15 sweep and will evaluate the same tenant-local day many times; the
constraint is what makes the second evaluation a no-op rather than a duplicate.
That is the anomaly arc's rule, where a run-scoped key turned one finding into
1,825 rows.

⚠️ `text` AND `spans` ARE STORED, NOT RECOMPUTED. A settled note that re-words
itself is worse than one that says nothing — it is what "what did I decide
Tuesday" reads. And a span re-serialised next week would resolve against next
week's world, which is a link quietly showing today's data under yesterday's
sentence.

Revision ID: r181_note_settled_records
Revises: r180_anomaly_resolution_outcome
"""

import sqlalchemy as sa
from alembic import op

revision = "r181_note_settled_records"
down_revision = "r180_anomaly_resolution_outcome"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "note_settled_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("daily_note_id", sa.String(36),
                  sa.ForeignKey("daily_notes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.String(36),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("note_date", sa.Date(), nullable=False),
        sa.Column("fragment_id", sa.String(100), nullable=False),
        sa.Column("instance_key", sa.String(255), nullable=False),
        sa.Column("outcome_key", sa.String(40), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("spans", sa.Text(), nullable=True),
        sa.Column("occurred_through", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_note_settled_records_identity",
        "note_settled_records",
        ["daily_note_id", "fragment_id", "instance_key", "outcome_key"],
    )
    op.create_index(
        "ix_note_settled_records_lookup",
        "note_settled_records", ["user_id", "note_date"],
    )
    op.create_index(
        "ix_note_settled_records_daily_note_id",
        "note_settled_records", ["daily_note_id"],
    )


def downgrade() -> None:
    """Drops the settled record.

    ⚠️ This is the record of what people DID, frozen at the day it happened. It
    is not reconstructible afterwards — the wording was generated once against
    that day's events, and the spans resolve against that day's world.
    """
    op.drop_index("ix_note_settled_records_daily_note_id",
                  table_name="note_settled_records")
    op.drop_index("ix_note_settled_records_lookup",
                  table_name="note_settled_records")
    op.drop_constraint("uq_note_settled_records_identity",
                       "note_settled_records", type_="unique")
    op.drop_table("note_settled_records")
