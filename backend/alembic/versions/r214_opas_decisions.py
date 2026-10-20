"""The Opas decision log — one row per bar interpretation.

James's dispatch of 2026-10-20, step 4, with his go for this one migration: "Decision log
(migration, James's go): one row per bar interpretation (input text, rules or model, the
request proposed, what the person then did, actor, timestamps). Expand-only, reversible.
No 'why?' line yet, and no rulebook."

⚠️ WHY THIS COMES BEFORE THE RULEBOOK, in James's own ordering: "the log is the evidence
the rules come from". A rulebook built first is a table of rules nobody has evidence for.
It is also where the test set comes from — the 59 phrasings scored on 2026-10-20 were
drafted from the repo's own tests and alias tables, which is the half the rules were
written for. `input_text` is what a director actually typed.

⚠️ EXPAND-ONLY. One new table. No column on any existing table is added, altered or
dropped, so a rollback to the previous image runs against this schema unchanged.

⚠️ AND REVERSIBLE IN FULL. `downgrade` drops the table and its indexes and nothing else.
There is no data to preserve on the way down because nothing else reads this table —
which will stop being true the moment the rulebook arrives, and the rulebook's own
migration will have to say so.

Revision ID: r214_opas_decisions
Revises: r213_sunnycrest_timezone
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "r214_opas_decisions"
down_revision = "r213_sunnycrest_timezone"
branch_labels = None
depends_on = None

TABLE = "opas_decisions"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        # ⚠️ NOT NULL AND FK'd. A decision with no tenant cannot be read back safely —
        # every query over this table is one tenant's evidence.
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # ⚠️ NULLABLE, DELIBERATELY, AND `ondelete="SET NULL"`. The bar is reachable by a
        # signed-in tenant user today, but `/order-list/ask` is also exercised by a
        # background caller with no user, and a deleted user must not take the evidence
        # of what was typed with them.
        sa.Column(
            "actor_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # ⚠️ VERBATIM, UNTRIMMED, UNNORMALISED. This column is the whole point: a
        # normalised copy would be the rules' view of the phrase rather than the
        # person's, and the rules' view is what we are trying to improve.
        sa.Column("input_text", sa.Text(), nullable=False),
        # ⚠️ WHERE THE SURFACE WAS. "orders" in a cold bar and "only hopkins" with a list
        # open are different requests, and a log that could not tell them apart would
        # make an unanswerable test set.
        sa.Column("surface", sa.String(24), nullable=False),
        # 'rules' | 'model' | 'rulebook' — who produced the request. CHECKed below.
        sa.Column("proposed_by", sa.String(16), nullable=False),
        # ⚠️ JSONB, NOT TEXT. The request will be queried by shape — "every row where the
        # model proposed a cemetery filter" — and that is a `->>` away in JSONB and a
        # parse away in text.
        sa.Column("proposed_request", postgresql.JSONB(), nullable=True),
        # 'executed' | 'asked' | 'refused'
        sa.Column("outcome", sa.String(16), nullable=False),
        # For an `asked` row: what became of the question.
        # 'answered' | 'replaced' | 'cancelled', or NULL while it is still open.
        sa.Column("resolution", sa.String(16), nullable=True),
        sa.Column("resolved_option", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        # ⚠️ THE MODEL'S OWN NUMBERS LIVE HERE AND NOT IN `intelligence_executions`, AND
        # THAT IS NOT A CHOICE — `order_list/proposal.py` calls Intelligence with
        # `persist=False`, because asking is a read and an audit row would commit the
        # caller's session. So no execution row exists for a door call and there is
        # nothing to point a foreign key at.
        #
        # ⚠️ WHICH MEANS TOKENS AND COST ARE NOT RECORDED ANYWHERE for this path. Latency
        # and the accept/refuse verdict are what a `persist=False` caller can observe.
        # Flagged for James: either the door persists, or this is the ceiling of what the
        # log can say about cost.
        sa.Column("model_latency_ms", sa.Integer(), nullable=True),
        sa.Column("model_accepted", sa.Boolean(), nullable=True),
        sa.Column("model_refused_reason", sa.String(64), nullable=True),
        sa.CheckConstraint(
            "proposed_by IN ('rules', 'model', 'rulebook')",
            name="ck_opas_decisions_proposed_by",
        ),
        sa.CheckConstraint(
            "outcome IN ('executed', 'asked', 'refused')",
            name="ck_opas_decisions_outcome",
        ),
        sa.CheckConstraint(
            "resolution IS NULL OR resolution IN ('answered', 'replaced', 'cancelled')",
            name="ck_opas_decisions_resolution",
        ),
        # ⚠️ A MODEL ROW MUST CARRY A VERDICT. `proposed_by = 'model'` with
        # `model_accepted` NULL would be a row that cannot say whether the door worked,
        # which is the one question this table exists to answer about the model.
        sa.CheckConstraint(
            "proposed_by <> 'model' OR model_accepted IS NOT NULL",
            name="ck_opas_decisions_model_has_verdict",
        ),
    )
    # The read this table is for: one tenant's phrasings, newest first.
    op.create_index(
        "ix_opas_decisions_company_created", TABLE, ["company_id", "created_at"],
    )
    # ⚠️ AND THE READ THAT MATTERS MOST: what the bar did NOT understand. A partial index
    # so the scan over "show me every miss" does not widen as the log fills with hits.
    op.create_index(
        "ix_opas_decisions_misses",
        TABLE,
        ["company_id", "created_at"],
        postgresql_where=sa.text("outcome = 'refused'"),
    )


def downgrade() -> None:
    op.drop_index("ix_opas_decisions_misses", table_name=TABLE)
    op.drop_index("ix_opas_decisions_company_created", table_name=TABLE)
    op.drop_table(TABLE)
