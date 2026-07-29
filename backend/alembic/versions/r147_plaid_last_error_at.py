"""S-1b — PlaidItem.last_error_at + 'internal_error' status.

The scheduled Plaid sweep (loud-failure hardening) records WHEN a
connection last failed (`last_error_at`, alongside the existing
`last_error_code` "what" and `last_synced_at` "last success"), and marks
UNEXPECTED (our-code) failures under a DISTINCT `internal_error` status so
a bug is never indistinguishable from a bank problem (their remedies are
opposite). Extends the `ck_plaid_items_status` CHECK to admit it.
"""

from alembic import op
import sqlalchemy as sa

revision = "r147_plaid_last_error_at"
down_revision = "r146_focus_session_draft_state"
branch_labels = None
depends_on = None

_OLD = (
    "status IN ('active', 'login_required', 'pending_expiration', "
    "'error', 'disconnected')"
)
_NEW = (
    "status IN ('active', 'login_required', 'pending_expiration', "
    "'error', 'disconnected', 'internal_error')"
)


def upgrade() -> None:
    op.add_column(
        "plaid_items",
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Drop-if-exists then re-add keeps this re-run-safe (mirrors the repo's
    # idempotent-migration discipline).
    op.execute("ALTER TABLE plaid_items DROP CONSTRAINT IF EXISTS ck_plaid_items_status")
    op.create_check_constraint("ck_plaid_items_status", "plaid_items", _NEW)


def downgrade() -> None:
    op.execute("ALTER TABLE plaid_items DROP CONSTRAINT IF EXISTS ck_plaid_items_status")
    op.create_check_constraint("ck_plaid_items_status", "plaid_items", _OLD)
    op.drop_column("plaid_items", "last_error_at")
