"""Phase R-6.0a — workflow_review_items table.

R-6 introduces headless Generation Focus invocation + a canonical
workflow review-pause primitive. When a workflow step of type
``invoke_review_focus`` runs, the engine creates a ``WorkflowReviewItem``
row, transitions the run to ``status="awaiting_approval"``, and exposes
the item via the canonical ``workflow_review_triage`` queue. On reviewer
decision (approve / reject / edit_and_approve), the item's decision
fields are stamped + ``workflow_engine.advance_run`` resumes the run
with the decision payload as the next step's input.

Schema:

  - ``id``                       : UUID PK.
  - ``run_id``                   : FK → workflow_runs (CASCADE).
  - ``run_step_id``              : FK → workflow_run_steps (SET NULL on
                                   delete — pre-decision audit-trail
                                   preservation matches D-1 review
                                   substrate semantics).
  - ``company_id``               : FK → companies (tenant scoping; NOT
                                   NULL for audit + cross-tenant
                                   isolation parity with workflow_runs).
  - ``review_focus_id``          : VARCHAR(64) — discriminator naming
                                   the review focus (e.g. "decedent_info_review",
                                   "draft_email_review"); future review focuses
                                   register dispatch entries off this slug.
  - ``input_data``               : JSONB — payload presented to the
                                   reviewer (e.g. extracted fields from
                                   the prior generation step).
  - ``decision``                 : VARCHAR(32) NULLABLE — set by reviewer
                                   action; one of approve / reject /
                                   edit_and_approve.
  - ``edited_data``              : JSONB NULLABLE — operator-supplied
                                   edits when decision="edit_and_approve".
  - ``decision_notes``           : TEXT NULLABLE — freeform reviewer
                                   note (e.g. rejection reason).
  - ``decided_by_user_id``       : FK → users (NULLABLE; SET NULL on
                                   delete to preserve the audit trail
                                   even after user deactivation).
  - ``decided_at``               : timestamptz NULLABLE.
  - ``created_at`` / ``updated_at``.

Indexes:

  - Partial ``ix_workflow_review_items_pending`` on (company_id, created_at DESC)
    WHERE decision IS NULL — hot-path for the triage direct-query
    builder (only pending items surface to reviewers; decided items
    stay in the audit trail but drop out of the queue).

  - Composite ``ix_workflow_review_items_by_run`` on (run_id) — used
    by the workflow engine when checking whether a run has
    outstanding review items + by audit drill-down from the run
    detail page.

Down: drops both indexes + table cleanly. Reversible.

Revision ID: r92_workflow_review_items
Revises: r91_compositions_kind_and_pages
Create Date: 2026-05-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "r92_workflow_review_items"
down_revision: Union[str, Sequence[str], None] = (
    "r91_compositions_kind_and_pages"
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLE = "workflow_review_items"
_IX_PENDING = "ix_workflow_review_items_pending"
_IX_BY_RUN = "ix_workflow_review_items_by_run"


def _conn():
    return op.get_bind()


def _table_exists(name: str) -> bool:
    insp = sa.inspect(_conn())
    return name in insp.get_table_names()


def _index_exists(table: str, index_name: str) -> bool:
    insp = sa.inspect(_conn())
    if not _table_exists(table):
        return False
    indexes = insp.get_indexes(table)
    return any(idx["name"] == index_name for idx in indexes)


def upgrade() -> None:
    if _table_exists(_TABLE):
        # Idempotent guard mirroring r91 + env.py monkey-patches.
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_step_id",
            sa.String(36),
            sa.ForeignKey("workflow_run_steps.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column("review_focus_id", sa.String(64), nullable=False),
        sa.Column("input_data", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("decision", sa.String(32), nullable=True),
        sa.Column("edited_data", JSONB, nullable=True),
        sa.Column("decision_notes", sa.Text, nullable=True),
        sa.Column(
            "decided_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "decision IS NULL OR decision IN ('approve', 'reject', 'edit_and_approve')",
            name="ck_workflow_review_items_decision",
        ),
    )

    op.create_index(
        _IX_PENDING,
        _TABLE,
        ["company_id", "created_at"],
        postgresql_where=sa.text("decision IS NULL"),
    )

    op.create_index(
        _IX_BY_RUN,
        _TABLE,
        ["run_id"],
    )


def downgrade() -> None:
    if _index_exists(_TABLE, _IX_PENDING):
        op.drop_index(_IX_PENDING, table_name=_TABLE)
    if _index_exists(_TABLE, _IX_BY_RUN):
        op.drop_index(_IX_BY_RUN, table_name=_TABLE)
    if _table_exists(_TABLE):
        op.drop_table(_TABLE)
