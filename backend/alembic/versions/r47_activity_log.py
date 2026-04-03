"""Create activity_log table for CRM activity tracking.

Revision ID: r47_activity_log
Revises: r46_legacy_fh_contact_ids
"""

from alembic import op
import sqlalchemy as sa

revision = "r47_activity_log"
down_revision = "r46_legacy_fh_contact_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("master_company_id", sa.String(36), sa.ForeignKey("company_entities.id"), nullable=False),
        sa.Column("contact_id", sa.String(36), sa.ForeignKey("contacts.id"), nullable=True),
        sa.Column("logged_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),

        sa.Column("activity_type", sa.String(30), nullable=False),
        sa.Column("is_system_generated", sa.Boolean, server_default="false"),

        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("outcome", sa.Text, nullable=True),

        sa.Column("follow_up_date", sa.Date, nullable=True),
        sa.Column("follow_up_assigned_to", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("follow_up_completed", sa.Boolean, server_default="false"),
        sa.Column("follow_up_completed_at", sa.DateTime(timezone=True), nullable=True),

        sa.Column("related_order_id", sa.String(36), nullable=True),
        sa.Column("related_invoice_id", sa.String(36), nullable=True),
        sa.Column("related_legacy_proof_id", sa.String(36), nullable=True),

        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_index("idx_activity_company", "activity_log", ["master_company_id", sa.text("created_at DESC")])
    op.create_index("idx_activity_tenant", "activity_log", ["tenant_id"])
    op.create_index(
        "idx_activity_followup", "activity_log",
        ["follow_up_assigned_to", "follow_up_date"],
        postgresql_where=sa.text("follow_up_completed = false AND follow_up_date IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("activity_log")
