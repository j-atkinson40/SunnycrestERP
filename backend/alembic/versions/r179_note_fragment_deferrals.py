"""note_fragment_deferrals — a prompt's only exit besides resolution

A prompt has no dismiss. It leaves the note by its declared end transition
occurring, or by the reader naming a date to see it again. This table is the
record of the second.

⚠️ APPEND-ONLY, AND DELIBERATELY WITHOUT A UNIQUE CONSTRAINT ON THE IDENTITY.
That is the opposite of r178's `note_fragment_renders`, which refuses a second
render of the same identity on the same note because a second row there is a
bug. Here a second row is the second deferral, and "deferred three times" is the
only signal that would reveal a badly designed prompt. The count is a
`count(*)` over the acts rather than a maintained number, because a maintained
number can drift from the acts it claims to summarise.

⚠️ `deferred_until` IS A DATE, NOT A TIMESTAMP. "Presets plus a date picker, no
finer granularity" is enforced by the column type rather than by validation —
an unexpressible 3:15pm deferral needs no guard. Removal over recognition.

⚠️ `user_id` IS NOT NULL. The note surface is this row's writer and the acting
user is on the request, so a deferral record can always say who deferred. That
is not true of every event on this platform — `agent_anomalies.resolved_by` is
correctly NULL for machine resolutions — which is why this one is required
rather than nullable: there is no machine path to deferral.

NOT NULL from the start throughout: new table, no existing writer, so r176's
expand/contract sequencing does not apply — there is no old code to break.

Revision ID: r179_note_fragment_deferrals
Revises: r178_note_fragment_renders
"""

import sqlalchemy as sa
from alembic import op

revision = "r179_note_fragment_deferrals"
down_revision = "r178_note_fragment_renders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "note_fragment_deferrals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fragment_id", sa.String(100), nullable=False),
        sa.Column("instance_key", sa.String(255), nullable=False),
        sa.Column("daily_note_id", sa.String(36),
                  sa.ForeignKey("daily_notes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deferred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deferred_until", sa.Date(), nullable=False),
        sa.Column("preset", sa.String(20), nullable=False),
        sa.Column("condition_digest", sa.String(64), nullable=False),
        sa.Column("condition_inputs", sa.Text(), nullable=True),
        sa.Column("woken_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_note_fragment_deferrals_lookup",
        "note_fragment_deferrals",
        ["user_id", "fragment_id", "instance_key", "deferred_at"],
    )
    op.create_index(
        "ix_note_fragment_deferrals_daily_note_id",
        "note_fragment_deferrals",
        ["daily_note_id"],
    )


def downgrade() -> None:
    """Drops the deferral record.

    ⚠️ THIS DESTROYS THE RECORD OF WHAT PEOPLE CHOSE NOT TO DO, which is the
    half of the history that is not reconstructible from anything else. A
    resolved prompt leaves traces elsewhere; a deferred one leaves only these
    rows. Downgrade only where the table has never been written.
    """
    op.drop_index(
        "ix_note_fragment_deferrals_daily_note_id",
        table_name="note_fragment_deferrals",
    )
    op.drop_index(
        "ix_note_fragment_deferrals_lookup",
        table_name="note_fragment_deferrals",
    )
    op.drop_table("note_fragment_deferrals")
