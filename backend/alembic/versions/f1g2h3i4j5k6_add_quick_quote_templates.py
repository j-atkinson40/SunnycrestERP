"""Add quick_quote_templates table and order station fields on quotes.

Revision ID: a1b2c3d4e5f6
Revises: z3a4b5c6d7e8
Create Date: 2026-03-19
"""

import json
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "f1g2h3i4j5k6"
down_revision = "z3a4b5c6d7e8"
branch_labels = None
depends_on = None


def _get_columns(conn, table_name: str) -> list[str]:
    inspector = sa_inspect(conn)
    return [c["name"] for c in inspector.get_columns(table_name)]


def _get_tables(conn) -> list[str]:
    inspector = sa_inspect(conn)
    return inspector.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()
    tables = _get_tables(conn)

    # ── quick_quote_templates table ──────────────────────────────────────
    if "quick_quote_templates" in tables:
        # Ensure tenant_id is nullable for system templates
        op.alter_column(
            "quick_quote_templates",
            "tenant_id",
            existing_type=sa.String(36),
            nullable=True,
        )
    else:
        op.create_table(
            "quick_quote_templates",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.String(36),
                sa.ForeignKey("companies.id"),
                nullable=True,
                index=True,
            ),
            sa.Column("template_name", sa.String(255), nullable=False),
            sa.Column("display_label", sa.String(100), nullable=False),
            sa.Column("display_description", sa.Text, nullable=True),
            sa.Column("icon", sa.String(50), nullable=True),
            sa.Column("product_line", sa.String(50), nullable=False),
            sa.Column("sort_order", sa.Integer, server_default="0"),
            sa.Column(
                "is_active",
                sa.Boolean,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "is_system_template",
                sa.Boolean,
                server_default=sa.text("false"),
            ),
            sa.Column("line_items", sa.Text, nullable=True),
            sa.Column("variable_fields", sa.Text, nullable=True),
            sa.Column("slide_over_width", sa.Integer, server_default="640"),
            sa.Column(
                "primary_action", sa.String(20), server_default="split"
            ),
            sa.Column("quote_template_key", sa.String(100), nullable=True),
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

    # ── Add order-station-specific columns to quotes ─────────────────────
    quote_cols = _get_columns(conn, "quotes")

    if "product_line" not in quote_cols:
        op.add_column(
            "quotes", sa.Column("product_line", sa.String(50), nullable=True)
        )

    if "permit_number" not in quote_cols:
        op.add_column(
            "quotes", sa.Column("permit_number", sa.String(100), nullable=True)
        )

    if "permit_jurisdiction" not in quote_cols:
        op.add_column(
            "quotes",
            sa.Column("permit_jurisdiction", sa.String(100), nullable=True),
        )

    if "installation_address" not in quote_cols:
        op.add_column(
            "quotes",
            sa.Column("installation_address", sa.String(500), nullable=True),
        )

    if "installation_city" not in quote_cols:
        op.add_column(
            "quotes",
            sa.Column("installation_city", sa.String(100), nullable=True),
        )

    if "installation_state" not in quote_cols:
        op.add_column(
            "quotes",
            sa.Column("installation_state", sa.String(50), nullable=True),
        )

    if "contact_name" not in quote_cols:
        op.add_column(
            "quotes",
            sa.Column("contact_name", sa.String(200), nullable=True),
        )

    if "contact_phone" not in quote_cols:
        op.add_column(
            "quotes",
            sa.Column("contact_phone", sa.String(50), nullable=True),
        )

    if "delivery_charge" not in quote_cols:
        op.add_column(
            "quotes",
            sa.Column("delivery_charge", sa.Numeric(12, 2), nullable=True),
        )

    if "template_id" not in quote_cols:
        op.add_column(
            "quotes",
            sa.Column("template_id", sa.String(36), nullable=True),
        )

    # Make customer_id nullable for walk-in / quick quotes
    # (existing constraint is NOT NULL; we relax it)
    if "customer_id" in quote_cols:
        op.alter_column(
            "quotes",
            "customer_id",
            existing_type=sa.String(36),
            nullable=True,
        )

    if "customer_name" not in quote_cols:
        op.add_column(
            "quotes",
            sa.Column("customer_name", sa.String(255), nullable=True),
        )

    # ── Seed system wastewater templates ─────────────────────────────────
    _seed_wastewater_templates(conn)


def _seed_wastewater_templates(conn) -> None:
    """Insert system wastewater templates (idempotent — skips if any exist)."""
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM quick_quote_templates "
            "WHERE is_system_template = true AND product_line = 'wastewater'"
        )
    )
    if result.scalar() > 0:
        return

    now = datetime.now(timezone.utc).isoformat()

    templates = [
        {
            "id": str(uuid.uuid4()),
            "tenant_id": None,  # system-wide; will be copied per tenant
            "template_name": "ww_1000_2comp",
            "display_label": "1000 Gallon 2-Compartment",
            "display_description": "Standard 1000-gallon two-compartment septic tank",
            "icon": "tank",
            "product_line": "wastewater",
            "sort_order": 1,
            "is_active": True,
            "is_system_template": True,
            "line_items": json.dumps([
                {
                    "description": "1000 Gal 2-Compartment Septic Tank",
                    "quantity": 1,
                    "unit_price": 0,
                    "product_key": "ww-1000-2c",
                },
                {
                    "description": "Delivery",
                    "quantity": 1,
                    "unit_price": 0,
                    "product_key": "delivery",
                    "is_delivery": True,
                },
            ]),
            "variable_fields": json.dumps([
                {"key": "permit_number", "label": "Permit #", "type": "text", "required": False},
                {"key": "permit_jurisdiction", "label": "Jurisdiction", "type": "text", "required": False},
                {"key": "installation_address", "label": "Installation Address", "type": "text", "required": False},
                {"key": "installation_city", "label": "City", "type": "text", "required": False},
                {"key": "installation_state", "label": "State", "type": "text", "required": False},
                {"key": "contact_name", "label": "Site Contact", "type": "text", "required": False},
                {"key": "contact_phone", "label": "Contact Phone", "type": "phone", "required": False},
            ]),
            "slide_over_width": 640,
            "primary_action": "split",
            "quote_template_key": "ww_1000_2comp",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": str(uuid.uuid4()),
            "tenant_id": None,
            "template_name": "ww_1500_2comp",
            "display_label": "1500 Gallon 2-Compartment",
            "display_description": "Large 1500-gallon two-compartment septic tank",
            "icon": "tank",
            "product_line": "wastewater",
            "sort_order": 2,
            "is_active": True,
            "is_system_template": True,
            "line_items": json.dumps([
                {
                    "description": "1500 Gal 2-Compartment Septic Tank",
                    "quantity": 1,
                    "unit_price": 0,
                    "product_key": "ww-1500-2c",
                },
                {
                    "description": "Delivery",
                    "quantity": 1,
                    "unit_price": 0,
                    "product_key": "delivery",
                    "is_delivery": True,
                },
            ]),
            "variable_fields": json.dumps([
                {"key": "permit_number", "label": "Permit #", "type": "text", "required": False},
                {"key": "permit_jurisdiction", "label": "Jurisdiction", "type": "text", "required": False},
                {"key": "installation_address", "label": "Installation Address", "type": "text", "required": False},
                {"key": "installation_city", "label": "City", "type": "text", "required": False},
                {"key": "installation_state", "label": "State", "type": "text", "required": False},
                {"key": "contact_name", "label": "Site Contact", "type": "text", "required": False},
                {"key": "contact_phone", "label": "Contact Phone", "type": "phone", "required": False},
            ]),
            "slide_over_width": 640,
            "primary_action": "split",
            "quote_template_key": "ww_1500_2comp",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": str(uuid.uuid4()),
            "tenant_id": None,
            "template_name": "ww_1000_single",
            "display_label": "1000 Gallon Single Compartment",
            "display_description": "Standard 1000-gallon single-compartment septic tank",
            "icon": "tank",
            "product_line": "wastewater",
            "sort_order": 3,
            "is_active": True,
            "is_system_template": True,
            "line_items": json.dumps([
                {
                    "description": "1000 Gal Single Compartment Septic Tank",
                    "quantity": 1,
                    "unit_price": 0,
                    "product_key": "ww-1000-1c",
                },
                {
                    "description": "Delivery",
                    "quantity": 1,
                    "unit_price": 0,
                    "product_key": "delivery",
                    "is_delivery": True,
                },
            ]),
            "variable_fields": json.dumps([
                {"key": "permit_number", "label": "Permit #", "type": "text", "required": False},
                {"key": "permit_jurisdiction", "label": "Jurisdiction", "type": "text", "required": False},
                {"key": "installation_address", "label": "Installation Address", "type": "text", "required": False},
                {"key": "installation_city", "label": "City", "type": "text", "required": False},
                {"key": "installation_state", "label": "State", "type": "text", "required": False},
                {"key": "contact_name", "label": "Site Contact", "type": "text", "required": False},
                {"key": "contact_phone", "label": "Contact Phone", "type": "phone", "required": False},
            ]),
            "slide_over_width": 640,
            "primary_action": "split",
            "quote_template_key": "ww_1000_single",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": str(uuid.uuid4()),
            "tenant_id": None,
            "template_name": "ww_distribution_box",
            "display_label": "Distribution Box",
            "display_description": "Wastewater distribution box for septic systems",
            "icon": "box",
            "product_line": "wastewater",
            "sort_order": 4,
            "is_active": True,
            "is_system_template": True,
            "line_items": json.dumps([
                {
                    "description": "Distribution Box",
                    "quantity": 1,
                    "unit_price": 0,
                    "product_key": "ww-dist-box",
                },
                {
                    "description": "Delivery",
                    "quantity": 1,
                    "unit_price": 0,
                    "product_key": "delivery",
                    "is_delivery": True,
                },
            ]),
            "variable_fields": json.dumps([
                {"key": "permit_number", "label": "Permit #", "type": "text", "required": False},
                {"key": "permit_jurisdiction", "label": "Jurisdiction", "type": "text", "required": False},
                {"key": "installation_address", "label": "Installation Address", "type": "text", "required": False},
                {"key": "installation_city", "label": "City", "type": "text", "required": False},
                {"key": "installation_state", "label": "State", "type": "text", "required": False},
                {"key": "contact_name", "label": "Site Contact", "type": "text", "required": False},
                {"key": "contact_phone", "label": "Contact Phone", "type": "phone", "required": False},
            ]),
            "slide_over_width": 640,
            "primary_action": "split",
            "quote_template_key": "ww_distribution_box",
            "created_at": now,
            "updated_at": now,
        },
    ]

    table = sa.table(
        "quick_quote_templates",
        sa.column("id", sa.String),
        sa.column("tenant_id", sa.String),
        sa.column("template_name", sa.String),
        sa.column("display_label", sa.String),
        sa.column("display_description", sa.Text),
        sa.column("icon", sa.String),
        sa.column("product_line", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("is_system_template", sa.Boolean),
        sa.column("line_items", sa.Text),
        sa.column("variable_fields", sa.Text),
        sa.column("slide_over_width", sa.Integer),
        sa.column("primary_action", sa.String),
        sa.column("quote_template_key", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )

    op.bulk_insert(table, templates)


def downgrade() -> None:
    op.drop_table("quick_quote_templates")

    # Remove order-station columns from quotes
    for col in [
        "product_line",
        "permit_number",
        "permit_jurisdiction",
        "installation_address",
        "installation_city",
        "installation_state",
        "contact_name",
        "contact_phone",
        "delivery_charge",
        "template_id",
        "customer_name",
    ]:
        op.drop_column("quotes", col)
