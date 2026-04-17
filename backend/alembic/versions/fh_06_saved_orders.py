"""Saved Orders — named compose templates that pre-fill NaturalLanguageOverlay.

Templates match trigger keywords on the user's typed input BEFORE Claude
extraction runs, so repeat patterns don't burn API calls.
"""

from alembic import op
import sqlalchemy as sa


revision = "fh_06_saved_orders"
down_revision = "fh_05_command_bar_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "workflow_id",
            sa.String(36),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trigger_keywords", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("product_type", sa.String(100), nullable=True),
        sa.Column("entry_intent", sa.String(20), nullable=False, server_default="order"),
        sa.Column("saved_fields", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("scope", sa.String(20), nullable=False, server_default="user"),
        sa.Column("use_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_used_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_saved_orders_company",
        "saved_orders",
        ["company_id", "is_active"],
    )
    op.create_index(
        "ix_saved_orders_user",
        "saved_orders",
        ["created_by_user_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_saved_orders_user", table_name="saved_orders")
    op.drop_index("ix_saved_orders_company", table_name="saved_orders")
    op.drop_table("saved_orders")
