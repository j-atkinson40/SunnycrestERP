"""Create vaults and vault_items tables.

Revision ID: vault_01_core_tables
Revises: r15_safety_program_generation
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "vault_01_core_tables"
down_revision = "r15_safety_program_generation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vaults",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("vault_type", sa.String(30), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "vault_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("vault_id", sa.String(36), sa.ForeignKey("vaults.id"), nullable=False),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("item_type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("r2_key", sa.String(500), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("document_type", sa.String(50), nullable=True),
        sa.Column("event_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_location", sa.String(500), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=True),
        sa.Column("event_type_sub", sa.String(50), nullable=True),
        sa.Column("all_day", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("recurrence_rule", sa.String(500), nullable=True),
        sa.Column("notify_recipients", postgresql.JSONB(), nullable=True),
        sa.Column("notify_before_minutes", postgresql.JSONB(), nullable=True),
        sa.Column("visibility", sa.String(20), nullable=False, server_default=sa.text("'internal'")),
        sa.Column("shared_with_company_ids", postgresql.JSONB(), nullable=True),
        sa.Column("parent_item_id", sa.String(36), sa.ForeignKey("vault_items.id"), nullable=True),
        sa.Column("related_entity_type", sa.String(50), nullable=True),
        sa.Column("related_entity_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'active'")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(30), nullable=False, server_default=sa.text("'system_generated'")),
        sa.Column("source_entity_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
    )

    # Indexes on vaults
    op.create_index("ix_vaults_company", "vaults", ["company_id"])

    # Indexes on vault_items
    op.create_index(
        "ix_vault_items_company_type_start",
        "vault_items",
        ["company_id", "item_type", "event_start"],
    )
    op.create_index(
        "ix_vault_items_vault_status",
        "vault_items",
        ["vault_id", "status", "is_active"],
    )
    op.create_index(
        "ix_vault_items_related",
        "vault_items",
        ["related_entity_type", "related_entity_id"],
    )
    op.create_index(
        "ix_vault_items_metadata_json",
        "vault_items",
        ["metadata_json"],
        postgresql_using="gin",
    )

    # Add calendar_token to users for iCal feed auth
    op.add_column("users", sa.Column("calendar_token", sa.String(100), nullable=True))
    op.create_index("ix_users_calendar_token", "users", ["calendar_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_vault_items_metadata_json", table_name="vault_items")
    op.drop_index("ix_vault_items_related", table_name="vault_items")
    op.drop_index("ix_vault_items_vault_status", table_name="vault_items")
    op.drop_index("ix_vault_items_company_type_start", table_name="vault_items")
    op.drop_index("ix_vaults_company", table_name="vaults")
    op.drop_table("vault_items")
    op.drop_table("vaults")
