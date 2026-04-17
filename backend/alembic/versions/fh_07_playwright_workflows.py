"""Playwright Workflow Steps — external account credentials + execution log.

Adds:
  tenant_external_accounts — encrypted credentials for external sites
  playwright_execution_log — per-step Playwright execution history
  purchase_orders.*         — external_order_id, external_order_total,
                              external_service_key for automated PO placement
"""

from alembic import op
import sqlalchemy as sa


revision = "fh_07_playwright_workflows"
down_revision = "fh_06_saved_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Encrypted external account credentials ────────────────────
    op.create_table(
        "tenant_external_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("service_name", sa.String(100), nullable=False),
        sa.Column("service_key", sa.String(100), nullable=False),
        sa.Column("encrypted_credentials", sa.Text, nullable=False),
        sa.Column("credential_fields", sa.JSON, nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_unique_constraint(
        "uq_tenant_external_accounts",
        "tenant_external_accounts",
        ["company_id", "service_key"],
    )
    op.create_index(
        "ix_external_accounts_company",
        "tenant_external_accounts",
        ["company_id", "is_active"],
    )

    # ── 2. Playwright execution log ──────────────────────────────────
    op.create_table(
        "playwright_execution_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "workflow_run_id",
            sa.String(36),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("script_name", sa.String(100), nullable=False),
        sa.Column("service_key", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("input_data", sa.JSON, nullable=True),
        sa.Column("output_data", sa.JSON, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("screenshot_path", sa.Text, nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_playwright_log_run",
        "playwright_execution_log",
        ["workflow_run_id"],
    )
    op.create_index(
        "ix_playwright_log_company",
        "playwright_execution_log",
        ["company_id"],
    )

    # ── 3. Purchase order — automated placement fields ───────────────
    op.add_column(
        "purchase_orders",
        sa.Column("external_order_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "purchase_orders",
        sa.Column("external_order_total", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "purchase_orders",
        sa.Column("external_service_key", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("purchase_orders", "external_service_key")
    op.drop_column("purchase_orders", "external_order_total")
    op.drop_column("purchase_orders", "external_order_id")
    op.drop_index("ix_playwright_log_company", table_name="playwright_execution_log")
    op.drop_index("ix_playwright_log_run", table_name="playwright_execution_log")
    op.drop_table("playwright_execution_log")
    op.drop_index("ix_external_accounts_company", table_name="tenant_external_accounts")
    op.drop_constraint("uq_tenant_external_accounts", "tenant_external_accounts")
    op.drop_table("tenant_external_accounts")
