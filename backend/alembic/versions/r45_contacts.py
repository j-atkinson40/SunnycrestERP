"""Create contacts table for CRM contact management.

Revision ID: r45_contacts
Revises: r44_master_company_entities
"""

from alembic import op
import sqlalchemy as sa

revision = "r45_contacts"
down_revision = "r44_master_company_entities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("master_company_id", sa.String(36), sa.ForeignKey("company_entities.id", ondelete="CASCADE"), nullable=False),

        # Identity
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),

        # Contact info
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("phone_ext", sa.String(20), nullable=True),
        sa.Column("mobile", sa.String(50), nullable=True),
        sa.Column("email", sa.String(500), nullable=True),

        # Role
        sa.Column("role", sa.String(50), nullable=True),

        # Flags
        sa.Column("is_primary", sa.Boolean, server_default="false"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("receives_invoices", sa.Boolean, server_default="false"),
        sa.Column("receives_legacy_proofs", sa.Boolean, server_default="false"),

        # Platform link
        sa.Column("linked_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("linked_auto", sa.Boolean, server_default="false"),

        sa.Column("notes", sa.Text, nullable=True),

        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_index("idx_contacts_company", "contacts", ["master_company_id"])
    op.create_index("idx_contacts_tenant", "contacts", ["company_id"])
    op.create_index("idx_contacts_email", "contacts", ["email"], postgresql_where=sa.text("email IS NOT NULL"))
    op.create_index("idx_contacts_user", "contacts", ["linked_user_id"], postgresql_where=sa.text("linked_user_id IS NOT NULL"))
    op.create_index(
        "idx_contacts_one_primary", "contacts", ["master_company_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true AND is_active = true"),
    )


def downgrade() -> None:
    op.drop_table("contacts")
