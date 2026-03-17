"""Add onboarding tables.

Revision ID: x1y2z3a4b5c6
Revises: w5x6y7z8a9b0
Create Date: 2026-03-17
"""

import uuid

from alembic import op
import sqlalchemy as sa

revision = "x1y2z3a4b5c6"
down_revision = "w5x6y7z8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_onboarding_checklists",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("preset", sa.String(30), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="not_started"
        ),
        sa.Column("must_complete_percent", sa.Integer, server_default="0"),
        sa.Column("overall_percent", sa.Integer, server_default="0"),
        sa.Column("check_in_call_offered_at", sa.DateTime(timezone=True)),
        sa.Column(
            "check_in_call_scheduled", sa.Boolean, server_default=sa.text("false")
        ),
        sa.Column("check_in_call_completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "white_glove_import_requested", sa.Boolean, server_default=sa.text("false")
        ),
        sa.Column("white_glove_import_completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "onboarding_checklist_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "checklist_id",
            sa.String(36),
            sa.ForeignKey("tenant_onboarding_checklists.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("item_key", sa.String(100), nullable=False),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("estimated_minutes", sa.Integer, server_default="0"),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="not_started"
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "completed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("action_type", sa.String(20), nullable=False),
        sa.Column("action_target", sa.String(500)),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("depends_on", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("tenant_id", "item_key", name="uq_onboarding_item_key"),
    )

    op.create_table(
        "onboarding_scenarios",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("scenario_key", sa.String(100), nullable=False),
        sa.Column("preset", sa.String(30), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("estimated_minutes", sa.Integer, server_default="0"),
        sa.Column("step_count", sa.Integer, server_default="0"),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="not_started"
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("current_step", sa.Integer, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "tenant_id", "scenario_key", name="uq_onboarding_scenario_key"
        ),
    )

    op.create_table(
        "onboarding_scenario_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "scenario_id",
            sa.String(36),
            sa.ForeignKey("onboarding_scenarios.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column("step_number", sa.Integer, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("instruction", sa.Text, nullable=False),
        sa.Column("target_route", sa.String(500)),
        sa.Column("target_element", sa.String(255)),
        sa.Column("completion_trigger", sa.String(100)),
        sa.Column("completion_trigger_metadata", sa.Text),
        sa.Column("hint_text", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "onboarding_data_imports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("import_type", sa.String(30), nullable=False),
        sa.Column("source_format", sa.String(30), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="not_started"
        ),
        sa.Column("total_records", sa.Integer, server_default="0"),
        sa.Column("imported_records", sa.Integer, server_default="0"),
        sa.Column("failed_records", sa.Integer, server_default="0"),
        sa.Column("field_mapping", sa.Text),
        sa.Column("preview_data", sa.Text),
        sa.Column("error_log", sa.Text),
        sa.Column("file_url", sa.String(500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "onboarding_integration_setups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("integration_type", sa.String(30), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="not_started"
        ),
        sa.Column("briefing_acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("sandbox_test_run_at", sa.DateTime(timezone=True)),
        sa.Column("sandbox_test_approved_at", sa.DateTime(timezone=True)),
        sa.Column("went_live_at", sa.DateTime(timezone=True)),
        sa.Column("connection_metadata", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "onboarding_help_dismissals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "employee_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("help_key", sa.String(100), nullable=False),
        sa.Column(
            "dismissed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "employee_id",
            "help_key",
            name="uq_onboarding_help_dismissal",
        ),
    )

    product_catalog_templates = op.create_table(
        "product_catalog_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("preset", sa.String(30), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("product_description", sa.Text),
        sa.Column("sku_prefix", sa.String(50)),
        sa.Column("default_unit", sa.String(20)),
        sa.Column("is_manufactured", sa.Boolean, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    # Seed product catalog templates
    seed_data = []
    sort = 0

    # Burial Vaults
    burial_vaults = [
        ("Standard Concrete Burial Vault", "BV-STD"),
        ("Monticello Burial Vault", "BV-MON"),
        ("Venetian Burial Vault", "BV-VEN"),
        ("Mahogany Select Vault", "BV-MAH"),
        ("Wilbert Triune Burial Vault", "BV-TRI"),
        ("Infant Burial Vault", "BV-INF"),
        ("Standard Concrete Grave Box", "GB-STD"),
        ("Concrete Urn Vault", "UV-STD"),
    ]
    for name, sku in burial_vaults:
        seed_data.append(
            {
                "id": str(uuid.uuid4()),
                "preset": "manufacturing",
                "category": "Burial Vaults",
                "product_name": name,
                "sku_prefix": sku,
                "default_unit": "each",
                "is_manufactured": True,
                "sort_order": sort,
            }
        )
        sort += 1

    # Wastewater
    wastewater = [
        ("500 Gallon Septic Tank (1 compartment)", "ST-500-1"),
        ("1000 Gallon Septic Tank (1 compartment)", "ST-1000-1"),
        ("1500 Gallon Septic Tank (2 compartment)", "ST-1500-2"),
        ("1000 Gallon Pump Chamber", "PC-1000"),
        ("Distribution Box", "DB-STD"),
        ("Concrete Leach Chamber", "LC-STD"),
        ("Grease Trap — 500 Gallon", "GT-500"),
    ]
    for name, sku in wastewater:
        seed_data.append(
            {
                "id": str(uuid.uuid4()),
                "preset": "manufacturing",
                "category": "Wastewater",
                "product_name": name,
                "sku_prefix": sku,
                "default_unit": "each",
                "is_manufactured": True,
                "sort_order": sort,
            }
        )
        sort += 1

    # Redi-Rock
    redirock = [
        ("Redi-Rock Freestanding Block 41\"", "RR-FS41"),
        ("Redi-Rock Freestanding Block 28\"", "RR-FS28"),
        ("Redi-Rock Cobblestone Texture", "RR-COB"),
        ("Redi-Rock Ledgestone Texture", "RR-LED"),
        ("Redi-Rock Corner Block", "RR-CRN"),
        ("Redi-Rock Cap Block", "RR-CAP"),
    ]
    for name, sku in redirock:
        seed_data.append(
            {
                "id": str(uuid.uuid4()),
                "preset": "manufacturing",
                "category": "Redi-Rock",
                "product_name": name,
                "sku_prefix": sku,
                "default_unit": "each",
                "is_manufactured": False,
                "sort_order": sort,
            }
        )
        sort += 1

    # Rosetta Hardscapes
    rosetta = [
        ("Rosetta Dimensional Wall Block", "RH-DIM", "each"),
        ("Rosetta Belvedere Wall Block", "RH-BEL", "each"),
        ("Rosetta Outcropping", "RH-OUT", "each"),
        ("Rosetta Pavers", "RH-PAV", "sqft"),
    ]
    for item in rosetta:
        name, sku, unit = item
        seed_data.append(
            {
                "id": str(uuid.uuid4()),
                "preset": "manufacturing",
                "category": "Rosetta Hardscapes",
                "product_name": name,
                "sku_prefix": sku,
                "default_unit": unit,
                "is_manufactured": False,
                "sort_order": sort,
            }
        )
        sort += 1

    op.bulk_insert(product_catalog_templates, seed_data)


def downgrade() -> None:
    op.drop_table("product_catalog_templates")
    op.drop_table("onboarding_help_dismissals")
    op.drop_table("onboarding_integration_setups")
    op.drop_table("onboarding_data_imports")
    op.drop_table("onboarding_scenario_steps")
    op.drop_table("onboarding_scenarios")
    op.drop_table("onboarding_checklist_items")
    op.drop_table("tenant_onboarding_checklists")
