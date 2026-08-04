"""Books Review Arc B B-4 — the flag/park table + the real flag_id FK.

`reconciliation_flags` is the workspace park record. The RETURN TRIGGER is a
DISCRIMINATED SHAPE, legible from the schema — `return_trigger_kind` names which
of three mechanisms a park is waiting on, NOT a single nullable timestamp with
the discrimination hidden in application code:
  * task_completed   — "Ask someone": a Task was created (task_id); the return
                       fires from the task-completion subscriber.
  * document_attached — "Hold for documentation": the return fires synchronously
                       when a document is attached to the exception.
  * terminal          — "Accept as a reconciling item": no evaluator; the amount
                       flows to the run's reconciling difference. returned_at is
                       stamped at creation.

`returned_at IS NULL` = an ACTIVE park (the item is out of the queue). On return
the subscriber/hook stamps returned_at and clears `reconciliation_exceptions.
flag_id` — the SAME exception reopens, with the park row kept as queryable
history (who was asked, what came back).

Also lands the `reconciliation_exceptions.flag_id` FK, deliberately FK-less since
A-1b pending this table (ondelete SET NULL — clearing a park frees the exception).
"""

from alembic import op
import sqlalchemy as sa

revision = "r151_reconciliation_flags"
down_revision = "r150_bank_transaction_counterparty"
branch_labels = None
depends_on = None

_DESTINATIONS = "'ask_someone', 'hold_for_documentation', 'accept_reconciling'"
_TRIGGER_KINDS = "'task_completed', 'document_attached', 'terminal'"


def upgrade() -> None:
    op.create_table(
        "reconciliation_flags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("reconciliation_exception_id", sa.String(36),
                  sa.ForeignKey("reconciliation_exceptions.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("destination", sa.String(30), nullable=False),
        # THE discriminated return trigger — which mechanism the park waits on.
        sa.Column("return_trigger_kind", sa.String(30), nullable=False),
        # Owner of the return: the recipient (ask), the parker (hold), NULL (terminal).
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        # task_completed only — the Task's vault_item_id the subscriber matches on.
        sa.Column("task_id", sa.String(36),
                  sa.ForeignKey("vault_items.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("note", sa.Text, nullable=True),  # why parked / what was asked
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        # NULL = active park (item out of queue); stamped on return.
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("return_note", sa.Text, nullable=True),  # what came back
        sa.CheckConstraint(f"destination IN ({_DESTINATIONS})", name="ck_recon_flag_destination"),
        sa.CheckConstraint(f"return_trigger_kind IN ({_TRIGGER_KINDS})", name="ck_recon_flag_trigger_kind"),
    )

    # The flag_id FK — deliberately FK-less since A-1b, pending this table.
    # Idempotent (drop-if-exists + add), matching r149's CHECK pattern.
    op.execute(
        "ALTER TABLE reconciliation_exceptions "
        "DROP CONSTRAINT IF EXISTS fk_recon_exception_flag_id"
    )
    op.execute(
        "ALTER TABLE reconciliation_exceptions "
        "ADD CONSTRAINT fk_recon_exception_flag_id "
        "FOREIGN KEY (flag_id) REFERENCES reconciliation_flags(id) ON DELETE SET NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE reconciliation_exceptions "
        "DROP CONSTRAINT IF EXISTS fk_recon_exception_flag_id"
    )
    op.drop_table("reconciliation_flags")
