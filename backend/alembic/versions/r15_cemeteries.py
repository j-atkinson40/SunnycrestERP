"""Add cemeteries and funeral_home_cemetery_history tables.

Revision ID: r15_cemeteries
Revises: r14_customer_type
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa

revision = "r15_cemeteries"
down_revision = "r14_customer_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cemeteries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        # Identity
        sa.Column("name", sa.String(200), nullable=False),
        # Location
        sa.Column("address", sa.String(300), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column("county", sa.String(100), nullable=True),
        sa.Column("zip_code", sa.String(10), nullable=True),
        # Contact
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("contact_name", sa.String(100), nullable=True),
        # Equipment — what the cemetery provides themselves
        sa.Column(
            "cemetery_provides_lowering_device",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "cemetery_provides_grass",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "cemetery_provides_tent",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "cemetery_provides_chairs",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        # Notes
        sa.Column("equipment_note", sa.Text(), nullable=True),
        sa.Column("access_notes", sa.Text(), nullable=True),
        # Status / metadata
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("company_id", "name", name="uq_cemetery_company_name"),
    )

    op.create_index(
        "idx_cemeteries_company",
        "cemeteries",
        ["company_id"],
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "idx_cemeteries_county",
        "cemeteries",
        ["company_id", "state", "county"],
    )

    op.create_table(
        "funeral_home_cemetery_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.String(36),
            sa.ForeignKey("customers.id"),
            nullable=False,
        ),
        sa.Column(
            "cemetery_id",
            sa.String(36),
            sa.ForeignKey("cemeteries.id"),
            nullable=False,
        ),
        sa.Column("order_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_order_date", sa.Date(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "company_id",
            "customer_id",
            "cemetery_id",
            name="uq_fh_cemetery_history",
        ),
    )

    op.create_index(
        "idx_fh_cemetery_history",
        "funeral_home_cemetery_history",
        ["company_id", "customer_id", "order_count"],
        postgresql_ops={"order_count": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("idx_fh_cemetery_history", table_name="funeral_home_cemetery_history")
    op.drop_table("funeral_home_cemetery_history")
    op.drop_index("idx_cemeteries_county", table_name="cemeteries")
    op.drop_index("idx_cemeteries_company", table_name="cemeteries")
    op.drop_table("cemeteries")
