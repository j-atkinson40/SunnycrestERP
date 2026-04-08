"""Disinterment case management & union rotation tables

Revision ID: z9o3p4q5r6s7
Revises: z9n1o2p3q4r5
Create Date: 2026-04-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "z9o3p4q5r6s7"
down_revision = "z9n1o2p3q4r5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Add fulfilling_location_id to company_entities (cemetery location mapping)
    # -----------------------------------------------------------------------
    op.add_column(
        "company_entities",
        sa.Column(
            "fulfilling_location_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_company_entities_fulfilling_location",
        "company_entities",
        ["fulfilling_location_id"],
        postgresql_where=sa.text("is_cemetery = true"),
    )

    # -----------------------------------------------------------------------
    # 2. Disinterment charge types
    # -----------------------------------------------------------------------
    op.create_table(
        "disinterment_charge_types",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column(
            "calculation_type",
            sa.String(20),
            nullable=False,
        ),  # flat, per_mile, per_unit, hourly
        sa.Column(
            "default_rate",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "requires_input",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column("input_label", sa.String(120), nullable=True),
        sa.Column(
            "is_hazard_pay",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "sort_order", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column(
            "active", sa.Boolean, nullable=False, server_default="true"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -----------------------------------------------------------------------
    # 3. Union rotation lists
    # -----------------------------------------------------------------------
    op.create_table(
        "union_rotation_lists",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "location_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "trigger_type",
            sa.String(30),
            nullable=False,
        ),  # hazard_pay, day_of_week, manual
        sa.Column(
            "trigger_config",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "assignment_mode",
            sa.String(20),
            nullable=False,
        ),  # sole_driver, longest_day
        sa.Column(
            "active", sa.Boolean, nullable=False, server_default="true"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "union_rotation_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "list_id",
            sa.String(36),
            sa.ForeignKey("union_rotation_lists.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("rotation_position", sa.Integer, nullable=False),
        sa.Column(
            "last_assigned_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("last_assignment_id", sa.String(36), nullable=True),
        sa.Column("last_assignment_type", sa.String(50), nullable=True),
        sa.Column(
            "active", sa.Boolean, nullable=False, server_default="true"
        ),
        sa.UniqueConstraint("list_id", "rotation_position", name="uq_rotation_member_position"),
    )

    op.create_table(
        "union_rotation_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "list_id",
            sa.String(36),
            sa.ForeignKey("union_rotation_lists.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "member_id",
            sa.String(36),
            sa.ForeignKey("union_rotation_members.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("assignment_type", sa.String(50), nullable=False),
        sa.Column("assignment_id", sa.String(36), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "assigned_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text, nullable=True),
    )

    # -----------------------------------------------------------------------
    # 4. Disinterment cases
    # -----------------------------------------------------------------------
    op.create_table(
        "disinterment_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("case_number", sa.String(30), nullable=False, unique=True),
        # Pipeline stage
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="intake",
        ),
        # Decedent
        sa.Column("decedent_name", sa.String(200), nullable=False),
        sa.Column("date_of_death", sa.Date, nullable=True),
        sa.Column("date_of_burial", sa.Date, nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("destination", sa.String(500), nullable=True),
        sa.Column("vault_description", sa.String(300), nullable=True),
        # Cemetery & location
        sa.Column(
            "cemetery_id",
            sa.String(36),
            sa.ForeignKey("company_entities.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("cemetery_lot_section", sa.String(100), nullable=True),
        sa.Column("cemetery_lot_space", sa.String(100), nullable=True),
        sa.Column(
            "fulfilling_location_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Relationships
        sa.Column(
            "funeral_home_id",
            sa.String(36),
            sa.ForeignKey("company_entities.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "funeral_director_contact_id",
            sa.String(36),
            sa.ForeignKey("contacts.id"),
            nullable=True,
        ),
        sa.Column(
            "next_of_kin",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        # Intake form
        sa.Column("intake_token", sa.String(64), unique=True, nullable=True),
        sa.Column(
            "intake_submitted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("intake_submitted_data", JSONB, nullable=True),
        # Quote
        sa.Column(
            "quote_id",
            sa.String(36),
            sa.ForeignKey("quotes.id"),
            nullable=True,
        ),
        sa.Column(
            "accepted_quote_amount", sa.Numeric(10, 2), nullable=True
        ),
        sa.Column(
            "has_hazard_pay",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        # DocuSign
        sa.Column("docusign_envelope_id", sa.String(100), nullable=True),
        sa.Column(
            "sig_funeral_home",
            sa.String(20),
            server_default="not_sent",
        ),
        sa.Column(
            "sig_funeral_home_signed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "sig_cemetery", sa.String(20), server_default="not_sent"
        ),
        sa.Column(
            "sig_cemetery_signed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "sig_next_of_kin", sa.String(20), server_default="not_sent"
        ),
        sa.Column(
            "sig_next_of_kin_signed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "sig_manufacturer", sa.String(20), server_default="not_sent"
        ),
        sa.Column(
            "sig_manufacturer_signed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        # Scheduling & assignment
        sa.Column("scheduled_date", sa.Date, nullable=True),
        sa.Column(
            "assigned_driver_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("assigned_crew", JSONB, server_default=sa.text("'[]'")),
        sa.Column(
            "rotation_assignment_id",
            sa.String(36),
            sa.ForeignKey("union_rotation_assignments.id"),
            nullable=True,
        ),
        # Completion
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "invoice_id",
            sa.String(36),
            sa.ForeignKey("invoices.id"),
            nullable=True,
        ),
        # Audit
        sa.Column(
            "created_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("disinterment_cases")
    op.drop_table("union_rotation_assignments")
    op.drop_table("union_rotation_members")
    op.drop_table("union_rotation_lists")
    op.drop_table("disinterment_charge_types")
    op.drop_index("idx_company_entities_fulfilling_location", "company_entities")
    op.drop_column("company_entities", "fulfilling_location_id")
