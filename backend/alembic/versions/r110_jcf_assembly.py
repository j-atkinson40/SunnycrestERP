"""JCF-1 — Job Coordination Focus assembly substrate.

Four tables (per the JCF Phase 0 verdict + settled decisions in
DECISIONS.md 2026-06-10):

- coordination_focus_instances — the order-launched, job-scoped Focus
  instance (the thing FocusShares + the thread attach to). One per
  sales_order (unique). task_id mirrors r108's focus_sessions.task_id
  (vault_items FK, ON DELETE SET NULL) so the focus_closer event family
  can drive decision-bounded closure.
- focus_shares — the cross-tenant grant, cloned from the DocumentShare
  shape (owner/target company + optional person scope + permission +
  granted/revoked lifecycle).
- focus_share_events — append-only audit, cloned from DocumentShareEvent
  (granted | revoked | accessed).
- jcf_thread_messages — the in-platform Focus-scoped thread (settled
  decision 2): tenant-attributed messages, authorized through the SAME
  read-guard as the Focus itself.

Revision ID: r110_jcf_assembly
Revises: r109_task_routing_rules
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r110_jcf_assembly"
down_revision = "r109_task_routing_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coordination_focus_instances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "sales_order_id",
            sa.String(36),
            sa.ForeignKey("sales_orders.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("source_fh_company_id", sa.String(36), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="active"
        ),
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("vault_items.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_cfi_status",
        "coordination_focus_instances",
        "status IN ('active', 'closed')",
    )

    op.create_table(
        "focus_shares",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "instance_id",
            sa.String(36),
            sa.ForeignKey("coordination_focus_instances.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "owner_company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column(
            "target_company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("target_user_id", sa.String(36), nullable=True),
        sa.Column(
            "permission", sa.String(16), nullable=False, server_default="read"
        ),
        sa.Column("granted_by_user_id", sa.String(36), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_by_user_id", sa.String(36), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("source_module", sa.String(64), nullable=True),
    )

    op.create_table(
        "focus_share_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "share_id",
            sa.String(36),
            sa.ForeignKey("focus_shares.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("actor_user_id", sa.String(36), nullable=True),
        sa.Column("actor_company_id", sa.String(36), nullable=True),
        sa.Column("detail", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "jcf_thread_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "instance_id",
            sa.String(36),
            sa.ForeignKey("coordination_focus_instances.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "author_company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column("author_user_id", sa.String(36), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("jcf_thread_messages")
    op.drop_table("focus_share_events")
    op.drop_table("focus_shares")
    op.drop_constraint(
        "ck_cfi_status", "coordination_focus_instances", type_="check"
    )
    op.drop_table("coordination_focus_instances")
