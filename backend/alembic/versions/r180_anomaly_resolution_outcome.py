"""agent_anomalies.resolution_outcome — which ACT resolved the row, as a key

A settled note says what happened: "you emailed 2 customers about an outstanding
balance", not "you worked 2 outstanding balances" when one was emailed and one
was skipped. Selecting that wording needs to know WHICH ACT occurred.

`resolution_note` already said so — in a sentence. "Sent via triage — standard
tier collection email to a@b.com" / "Skipped via triage — customer disputed".
That is enough for a human reading one row and NOT enough to select a settled
record's wording, because doing so means prefix-matching prose a person typed.
The note surface already rejected substring marking for spans; a settled record
is the same failure one layer up, on the copy someone reads a week later as
evidence of what they did.

⚠️ NULLABLE, AND THE NULLS ARE HONEST. Every existing row was resolved by an act
that did not declare an outcome — including the 205 machine resolutions from
`clear_agent_backlog`, which correctly carry no actor either. Backfilling them by
parsing `resolution_note` is exactly the prose-matching this column exists to
avoid, so they stay NULL and are reported as unsettleable rather than guessed at.

Five other adapters resolve anomalies without declaring an outcome
(`agents.py`, `cash_receipts_adapter`, `expense_categorization_adapter`,
`aftercare_adapter`, `anomalies_widget_service`). None of them backs a settled
fragment today. Each becomes settleable when it declares its outcome, and not
before.

Revision ID: r180_anomaly_resolution_outcome
Revises: r179_note_fragment_deferrals
"""

import sqlalchemy as sa
from alembic import op

revision = "r180_anomaly_resolution_outcome"
down_revision = "r179_note_fragment_deferrals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_anomalies",
        sa.Column("resolution_outcome", sa.String(40), nullable=True),
    )


def downgrade() -> None:
    """Drops the outcome key.

    ⚠️ The information is not recoverable from `resolution_note` without the
    prose-matching this column exists to avoid. Downgrade loses the distinction
    between an emailed balance and a skipped one.
    """
    op.drop_column("agent_anomalies", "resolution_outcome")
