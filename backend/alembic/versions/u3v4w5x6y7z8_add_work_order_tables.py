"""Add work order, pour event, batch ticket, mix design, cure schedule,
work order product, and stock replenishment rule tables.

Revision ID: u3v4w5x6y7z8
Revises: t2u3v4w5x6y7
Create Date: 2026-03-17

"""
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "u3v4w5x6y7z8"
down_revision = "t2u3v4w5x6y7"
branch_labels = None
depends_on = None

DEFAULT_COMPANY_ID = "65ef982b-5bee-4fc8-a8bb-19096b58ff3d"


def upgrade() -> None:
    # -- 1. cure_schedules
    op.create_table(
        "cure_schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_hours", sa.Integer(), nullable=False),
        sa.Column(
            "minimum_strength_release_percent",
            sa.Integer(),
            nullable=False,
            server_default="70",
        ),
        sa.Column(
            "temperature_adjusted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 2. mix_designs
    op.create_table(
        "mix_designs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("mix_design_code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("design_strength_psi", sa.Integer(), nullable=False),
        sa.Column("cement_type", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "npca_approved",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "cure_schedule_id",
            sa.String(36),
            sa.ForeignKey("cure_schedules.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 3. work_orders
    op.create_table(
        "work_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("work_order_number", sa.String(50), nullable=False),
        sa.Column("trigger_type", sa.String(30), nullable=False),
        sa.Column("source_order_id", sa.String(36), nullable=True),
        sa.Column("source_order_line_id", sa.String(36), nullable=True),
        sa.Column(
            "product_id",
            sa.String(36),
            sa.ForeignKey("products.id"),
            nullable=False,
        ),
        sa.Column("product_variant_id", sa.String(36), nullable=True),
        sa.Column("quantity_ordered", sa.Integer(), nullable=False),
        sa.Column(
            "quantity_produced",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "quantity_passed_qc",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("needed_by_date", sa.Date(), nullable=True),
        sa.Column(
            "priority",
            sa.String(20),
            nullable=False,
            server_default="standard",
        ),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", sa.String(36), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("company_id", "work_order_number", name="uq_work_order_number_per_company"),
    )

    # -- 4. pour_events
    op.create_table(
        "pour_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("pour_event_number", sa.String(50), nullable=False),
        sa.Column("pour_date", sa.Date(), nullable=False),
        sa.Column("pour_time", sa.String(20), nullable=True),
        sa.Column("crew_notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="planned",
        ),
        sa.Column("batch_ticket_id", sa.String(36), nullable=True),
        sa.Column(
            "cure_schedule_id",
            sa.String(36),
            sa.ForeignKey("cure_schedules.id"),
            nullable=True,
        ),
        sa.Column("cure_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cure_complete_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_release_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 5. pour_event_work_orders (junction table)
    op.create_table(
        "pour_event_work_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "pour_event_id",
            sa.String(36),
            sa.ForeignKey("pour_events.id"),
            nullable=False,
        ),
        sa.Column(
            "work_order_id",
            sa.String(36),
            sa.ForeignKey("work_orders.id"),
            nullable=False,
        ),
        sa.Column("quantity_in_this_pour", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # -- 6. batch_tickets
    op.create_table(
        "batch_tickets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "pour_event_id",
            sa.String(36),
            sa.ForeignKey("pour_events.id"),
            nullable=False,
        ),
        sa.Column(
            "mix_design_id",
            sa.String(36),
            sa.ForeignKey("mix_designs.id"),
            nullable=True,
        ),
        sa.Column("design_strength_psi", sa.Integer(), nullable=True),
        sa.Column("water_cement_ratio", sa.Numeric(5, 3), nullable=True),
        sa.Column("slump_inches", sa.Numeric(5, 2), nullable=True),
        sa.Column("air_content_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("ambient_temp_f", sa.Integer(), nullable=True),
        sa.Column("concrete_temp_f", sa.Integer(), nullable=True),
        sa.Column("yield_cubic_yards", sa.Numeric(8, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 7. work_order_products
    op.create_table(
        "work_order_products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "work_order_id",
            sa.String(36),
            sa.ForeignKey("work_orders.id"),
            nullable=False,
        ),
        sa.Column(
            "pour_event_id",
            sa.String(36),
            sa.ForeignKey("pour_events.id"),
            nullable=True,
        ),
        sa.Column("serial_number", sa.String(50), nullable=False),
        sa.Column(
            "product_id",
            sa.String(36),
            sa.ForeignKey("products.id"),
            nullable=False,
        ),
        sa.Column("product_variant_id", sa.String(36), nullable=True),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="produced",
        ),
        sa.Column("qc_inspection_id", sa.String(36), nullable=True),
        sa.Column("received_to_inventory_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_by", sa.String(36), nullable=True),
        sa.Column("inventory_location", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 8. stock_replenishment_rules
    op.create_table(
        "stock_replenishment_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "product_id",
            sa.String(36),
            sa.ForeignKey("products.id"),
            nullable=False,
        ),
        sa.Column("product_variant_id", sa.String(36), nullable=True),
        sa.Column("minimum_stock_quantity", sa.Integer(), nullable=False),
        sa.Column("target_stock_quantity", sa.Integer(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- Add is_manufactured to products
    op.add_column(
        "products",
        sa.Column(
            "is_manufactured",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # -- Add delivery_readiness_status to deliveries
    op.add_column(
        "deliveries",
        sa.Column("delivery_readiness_status", sa.String(30), nullable=True),
    )

    # ------------------------------------------------------------------ #
    #  SEED DATA — only if the default company exists                     #
    # ------------------------------------------------------------------ #
    conn = op.get_bind()
    company_exists = conn.execute(
        sa.text("SELECT 1 FROM companies WHERE id = :cid"),
        {"cid": DEFAULT_COMPANY_ID},
    ).fetchone()

    if not company_exists:
        return  # Skip seed data — company not present (e.g. fresh production DB)

    now = datetime.now(timezone.utc)

    # -- Seed cure_schedules --------------------------------------------------
    cure_table = sa.table(
        "cure_schedules",
        sa.column("id", sa.String),
        sa.column("company_id", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("duration_hours", sa.Integer),
        sa.column("minimum_strength_release_percent", sa.Integer),
        sa.column("temperature_adjusted", sa.Boolean),
        sa.column("is_default", sa.Boolean),
        sa.column("created_at", sa.DateTime),
    )

    std_28_id = str(uuid.uuid4())
    accel_7_id = str(uuid.uuid4())
    winter_35_id = str(uuid.uuid4())

    op.bulk_insert(
        cure_table,
        [
            {
                "id": std_28_id,
                "company_id": DEFAULT_COMPANY_ID,
                "name": "Standard 28-Day",
                "description": "Standard 28-day cure cycle for normal conditions.",
                "duration_hours": 672,
                "minimum_strength_release_percent": 70,
                "temperature_adjusted": False,
                "is_default": True,
                "created_at": now,
            },
            {
                "id": accel_7_id,
                "company_id": DEFAULT_COMPANY_ID,
                "name": "Accelerated 7-Day",
                "description": "Accelerated 7-day cure for time-sensitive production.",
                "duration_hours": 168,
                "minimum_strength_release_percent": 70,
                "temperature_adjusted": False,
                "is_default": False,
                "created_at": now,
            },
            {
                "id": winter_35_id,
                "company_id": DEFAULT_COMPANY_ID,
                "name": "Winter Extended 35-Day",
                "description": "Extended 35-day cure for cold weather conditions.",
                "duration_hours": 840,
                "minimum_strength_release_percent": 70,
                "temperature_adjusted": True,
                "is_default": False,
                "created_at": now,
            },
        ],
    )

    # -- Seed mix_designs -----------------------------------------------------
    mix_table = sa.table(
        "mix_designs",
        sa.column("id", sa.String),
        sa.column("company_id", sa.String),
        sa.column("mix_design_code", sa.String),
        sa.column("name", sa.String),
        sa.column("design_strength_psi", sa.Integer),
        sa.column("cement_type", sa.String),
        sa.column("description", sa.Text),
        sa.column("is_active", sa.Boolean),
        sa.column("npca_approved", sa.Boolean),
        sa.column("cure_schedule_id", sa.String),
        sa.column("created_at", sa.DateTime),
    )

    op.bulk_insert(
        mix_table,
        [
            {
                "id": str(uuid.uuid4()),
                "company_id": DEFAULT_COMPANY_ID,
                "mix_design_code": "4000-STD",
                "name": "4000 PSI Standard",
                "design_strength_psi": 4000,
                "cement_type": "Type I/II",
                "description": "Standard 4000 PSI mix for general precast production.",
                "is_active": True,
                "npca_approved": False,
                "cure_schedule_id": std_28_id,
                "created_at": now,
            },
            {
                "id": str(uuid.uuid4()),
                "company_id": DEFAULT_COMPANY_ID,
                "mix_design_code": "5000-HS",
                "name": "5000 PSI High Strength",
                "design_strength_psi": 5000,
                "cement_type": "Type III",
                "description": "High strength 5000 PSI mix for structural precast elements.",
                "is_active": True,
                "npca_approved": True,
                "cure_schedule_id": std_28_id,
                "created_at": now,
            },
            {
                "id": str(uuid.uuid4()),
                "company_id": DEFAULT_COMPANY_ID,
                "mix_design_code": "5000-AE",
                "name": "5000 PSI Air Entrained",
                "design_strength_psi": 5000,
                "cement_type": "Type I/II",
                "description": "5000 PSI air-entrained mix for freeze-thaw exposure applications.",
                "is_active": True,
                "npca_approved": True,
                "cure_schedule_id": std_28_id,
                "created_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.drop_column("deliveries", "delivery_readiness_status")
    op.drop_column("products", "is_manufactured")
    op.drop_table("stock_replenishment_rules")
    op.drop_table("work_order_products")
    op.drop_table("batch_tickets")
    op.drop_table("pour_event_work_orders")
    op.drop_table("pour_events")
    op.drop_table("work_orders")
    op.drop_table("mix_designs")
    op.drop_table("cure_schedules")
