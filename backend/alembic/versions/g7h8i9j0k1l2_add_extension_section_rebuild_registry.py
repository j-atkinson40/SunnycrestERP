"""Add section column to extension_definitions and rebuild manufacturing registry.

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2026-03-20 14:00:00.000000+00:00
"""

from typing import Sequence, Union

import json
import sqlalchemy as sa
from alembic import op

revision: str = "g7h8i9j0k1l2"
down_revision: Union[str, None] = "f6g7h8i9j0k1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.scalar() > 0


def upgrade() -> None:
    # 1. Add section column if not present
    if not _column_exists("extension_definitions", "section"):
        op.add_column(
            "extension_definitions",
            sa.Column("section", sa.String(50), nullable=False, server_default="core"),
        )

    bind = op.get_bind()

    # 2. Safety check — verify no tenant_extensions reference entries being removed
    KEEPING_KEYS = [
        "funeral_kanban_scheduler",
        "funeral_home_coordination",
        "osha_inspection_prep",
        "npca_audit_prep",
        "legacy_print_generator",
        "ai_obituary_builder",
        "wastewater_treatment",
        "redi_rock",
        "rosetta_hardscapes",
        "work_orders",
        "pour_events_cure_tracking",
        "qc_module_full",
        "bill_of_materials",
        "equipment_maintenance",
        "capacity_planning",
        "mold_inventory",
        "purchasing_vendors",
        "hr_time_tracking",
        "point_of_sale",
        "scheduling_calendar",
    ]

    # Check for active tenant_extensions that would be orphaned
    placeholders = ", ".join(f":k{i}" for i in range(len(KEEPING_KEYS)))
    params = {f"k{i}": k for i, k in enumerate(KEEPING_KEYS)}
    result = bind.execute(
        sa.text(
            f"SELECT COUNT(*) FROM tenant_extensions te "
            f"JOIN extension_definitions er ON te.extension_id = er.id "
            f"WHERE er.extension_key NOT IN ({placeholders})"
        ),
        params,
    )
    orphan_count = result.scalar()

    if orphan_count > 0:
        # Report which ones and stop
        detail = bind.execute(
            sa.text(
                f"SELECT er.extension_key, COUNT(*) as cnt FROM tenant_extensions te "
                f"JOIN extension_definitions er ON te.extension_id = er.id "
                f"WHERE er.extension_key NOT IN ({placeholders}) "
                f"GROUP BY er.extension_key"
            ),
            params,
        )
        rows = detail.fetchall()
        msg = "; ".join(f"{r[0]}={r[1]}" for r in rows)
        raise RuntimeError(
            f"ABORT: {orphan_count} tenant_extensions reference entries being removed: {msg}. "
            f"Resolve these before proceeding."
        )

    # 3. Capture existing tenant_extensions by extension_key (for re-linking)
    existing_te = bind.execute(
        sa.text("SELECT id, extension_key, extension_id FROM tenant_extensions")
    ).fetchall()

    # 4. Delete all extension_definitions
    bind.execute(sa.text("DELETE FROM extension_definitions"))

    # 5. Seed the new registry
    NEW_REGISTRY = [
        # ── CORE ──
        {
            "extension_key": "funeral_kanban_scheduler",
            "module_key": "driver_delivery",
            "display_name": "Funeral Kanban Scheduler",
            "tagline": "Drag-and-drop funeral scheduling board organized by date and driver",
            "description": "Date-based swimlane kanban board for scheduling funeral vault deliveries. Unassigned queue with drag to driver lanes. Saturday bookings auto-shift to Monday.",
            "section": "core",
            "category": "scheduling",
            "applicable_verticals": ["manufacturing"],
            "default_enabled_for": ["manufacturing"],
            "cannot_disable": False,
            "access_model": "included",
            "status": "active",
            "version": "1.0.0",
            "feature_bullets": [
                "Date-based swimlane kanban board",
                "Unassigned queue with drag to driver lanes",
                "Saturday bookings auto-shift to Monday",
                "Color coding by service type",
                "Real-time across all dispatch staff",
            ],
            "setup_required": False,
            "sort_order": 1,
        },
        {
            "extension_key": "funeral_home_coordination",
            "module_key": "driver_delivery",
            "display_name": "Funeral Home Coordination",
            "tagline": "Automatic notifications to funeral homes and cemeteries at each delivery milestone",
            "description": "Notifies funeral homes and cemeteries automatically when deliveries are scheduled, departed, and completed. Configurable per customer.",
            "section": "core",
            "category": "workflow",
            "applicable_verticals": ["manufacturing"],
            "default_enabled_for": ["manufacturing"],
            "cannot_disable": False,
            "access_model": "included",
            "status": "active",
            "version": "1.0.0",
            "feature_bullets": [
                "Notifies funeral home at scheduling confirmation",
                "Departure and arrival alerts",
                "Setup complete confirmation",
                "Configurable notification recipients per customer",
                "SMS and email delivery",
            ],
            "setup_required": True,
            "sort_order": 2,
        },
        {
            "extension_key": "npca_audit_prep",
            "module_key": "safety_management",
            "display_name": "NPCA Audit Prep",
            "tagline": "One-button NPCA inspection package — complete audit-ready documentation in seconds",
            "description": "Maintains a continuous audit readiness score across all NPCA requirements. Generates complete audit package on demand — every required document organized by audit section, formatted the way an NPCA plant certification auditor expects to see it.",
            "section": "core",
            "category": "compliance",
            "applicable_verticals": ["manufacturing"],
            "default_enabled_for": [],
            "cannot_disable": False,
            "access_model": "included",
            "status": "active",
            "version": "1.0.0",
            "feature_bullets": [
                "Real-time compliance score across all NPCA requirements",
                "Gap analysis with specific actionable items",
                "One-button audit package generation",
                "Annual safety calendar auto-generated",
                "ZIP export organized by NPCA standard",
            ],
            "setup_required": True,
            "sort_order": 3,
        },
        {
            "extension_key": "legacy_print_generator",
            "module_key": "core",
            "display_name": "Legacy Print Generator",
            "tagline": "Design personalized vault legacy prints live with families — TIF production files generated automatically",
            "description": "An interactive design tool that lets funeral directors build legacy print previews with families during arrangement conferences. Families approve via the portal. Production TIF files are automatically generated and sent to the vault manufacturer for Wilbert submission.",
            "section": "core",
            "category": "workflow",
            "applicable_verticals": ["manufacturing", "funeral_home"],
            "default_enabled_for": ["manufacturing"],
            "cannot_disable": False,
            "access_model": "included",
            "status": "active",
            "version": "1.0.0",
            "feature_bullets": [
                "Live canvas designer — drag, drop, and preview in real time",
                "Family approves via portal — no in-person meeting required",
                "Production TIF generated automatically at print resolution",
                "File delivered directly to your vault manufacturer",
                "Supports photos, veteran emblems, religious symbols, and custom verses",
            ],
            "setup_required": True,
            "sort_order": 4,
        },

        # ── PRODUCT LINES ──
        {
            "extension_key": "wastewater_treatment",
            "module_key": "products",
            "display_name": "Wastewater Treatment Products",
            "tagline": "Septic tanks, pump chambers, and treatment products with permit-aware quoting",
            "description": "Adds wastewater product catalog templates, permit and engineering reference fields on quotes, and AI quoting intelligence for tank sizing conversations. Designed for operations selling to septic installers, general contractors, civil engineers, and municipalities.",
            "section": "product_lines",
            "category": "workflow",
            "applicable_verticals": ["manufacturing"],
            "default_enabled_for": [],
            "cannot_disable": False,
            "access_model": "included",
            "status": "coming_soon",
            "version": "1.0.0",
            "feature_bullets": [
                "Wastewater product catalog with standard tank configurations",
                "Permit number and engineering spec fields on every quote",
                "AI understands tank sizing shorthand — 1500 two-comp maps to the right product",
                "Buyer-appropriate quote templates for installers vs engineers",
                "Delivery notes for heavy equipment requirements",
            ],
            "setup_required": True,
            "sort_order": 1,
        },
        {
            "extension_key": "redi_rock",
            "module_key": "products",
            "display_name": "Redi-Rock Retaining Walls",
            "tagline": "Wall design assistance, block quantity calculation, and contractor-ready quoting",
            "description": "Adds Redi-Rock product catalog templates, AI-assisted wall quantity estimation, SketchUp CSV import for design-software-generated block lists, and quote templates appropriate for landscape contractors, civil engineers, and homeowners.",
            "section": "product_lines",
            "category": "workflow",
            "applicable_verticals": ["manufacturing"],
            "default_enabled_for": [],
            "cannot_disable": False,
            "access_model": "included",
            "status": "coming_soon",
            "version": "1.0.0",
            "feature_bullets": [
                "Three quoting paths: CSV import, manual entry, or AI-assisted estimation",
                "SketchUp CSV import auto-populates block quantities from Redi-Rock design software",
                "AI understands wall dimensions and calculates approximate block counts",
                "Contractor and homeowner quote templates with optional product photos",
                "Supports all Redi-Rock block sizes and texture variants",
            ],
            "setup_required": True,
            "sort_order": 2,
        },
        {
            "extension_key": "rosetta_hardscapes",
            "module_key": "products",
            "display_name": "Rosetta Hardscapes",
            "tagline": "Decorative concrete product catalog and visual quoting for landscape and hardscape projects",
            "description": "Adds Rosetta Hardscapes product catalog templates, visual quote presentations with product photos, and AI quoting intelligence for decorative concrete conversations. Designed for operations selling to landscape contractors and homeowners.",
            "section": "product_lines",
            "category": "workflow",
            "applicable_verticals": ["manufacturing"],
            "default_enabled_for": [],
            "cannot_disable": False,
            "access_model": "included",
            "status": "coming_soon",
            "version": "1.0.0",
            "feature_bullets": [
                "Rosetta product catalog with decorative concrete product line",
                "Visual quotes with product photos — homeowners see what they are buying",
                "AI understands Rosetta product names and application descriptions",
                "Separate templates for contractors and homeowners",
                "Square footage based quantity estimation for paver and wall products",
            ],
            "setup_required": True,
            "sort_order": 3,
        },

        # ── BASIC OPERATIONS ──
        {
            "extension_key": "purchasing_vendors",
            "module_key": "purchasing",
            "display_name": "Purchasing & Vendors",
            "tagline": "Vendor management, purchase orders, and bill tracking — lean and straightforward",
            "description": "A focused purchasing workflow designed for small manufacturing operations. Manage your vendors, create and send purchase orders, receive against POs, and track what you owe. Syncs to QuickBooks. No complex approval workflows — just the purchasing flow a 15-person operation actually needs.",
            "section": "basic_operations",
            "category": "operations",
            "applicable_verticals": ["manufacturing"],
            "default_enabled_for": [],
            "cannot_disable": False,
            "access_model": "included",
            "status": "coming_soon",
            "version": "1.0.0",
            "feature_bullets": [
                "Vendor list with contact info and payment terms",
                "Create and send purchase orders",
                "Receive against POs — partial and full receipt",
                "Bill tracking and payment recording",
                "QuickBooks sync for AP transactions",
            ],
            "setup_required": True,
            "sort_order": 1,
        },
        {
            "extension_key": "hr_time_tracking",
            "module_key": "core",
            "display_name": "HR & Time Tracking",
            "tagline": "Employee hours, PTO balances, and payroll export — lean and mobile-friendly",
            "description": "Simple time tracking designed for manufacturing operations. Employees clock in and out from their phone. Managers approve timesheets. PTO balances tracked automatically. Payroll summary exports to CSV for your payroll provider. No complex HR workflows.",
            "section": "basic_operations",
            "category": "operations",
            "applicable_verticals": ["manufacturing"],
            "default_enabled_for": [],
            "cannot_disable": False,
            "access_model": "included",
            "status": "coming_soon",
            "version": "1.0.0",
            "feature_bullets": [
                "Mobile clock in and out — works on any phone browser",
                "Manager timesheet approval",
                "PTO balance tracking and requests",
                "Payroll summary CSV export",
                "Overtime calculation and alerts",
            ],
            "setup_required": True,
            "sort_order": 2,
        },
        {
            "extension_key": "point_of_sale",
            "module_key": "sales",
            "display_name": "Point of Sale",
            "tagline": "Walk-in counter sales with cash and card payments — built for the vault yard",
            "description": "A lean POS for manufacturers who sell direct at the counter or yard. Process walk-in sales, accept cash or card, print receipts. Inventory updates automatically. Syncs to QuickBooks. Designed for vault yards and precast operations, not retail stores.",
            "section": "basic_operations",
            "category": "operations",
            "applicable_verticals": ["manufacturing"],
            "default_enabled_for": [],
            "cannot_disable": False,
            "access_model": "included",
            "status": "coming_soon",
            "version": "1.0.0",
            "feature_bullets": [
                "Counter sales from any tablet or computer",
                "Cash and card payment processing",
                "Receipt printing and email",
                "Automatic inventory update on sale",
                "QuickBooks sync for sales transactions",
            ],
            "setup_required": True,
            "sort_order": 3,
        },
        {
            "extension_key": "scheduling_calendar",
            "module_key": "core",
            "display_name": "Staff Scheduling & Calendar",
            "tagline": "Shift scheduling, staff availability, and team calendar — separate from delivery scheduling",
            "description": "Staff scheduling for your manufacturing operation. Plan shifts, track who is available, and manage time-off requests. Separate from the delivery scheduling board — this is for managing your team, not your trucks.",
            "section": "basic_operations",
            "category": "scheduling",
            "applicable_verticals": ["manufacturing"],
            "default_enabled_for": [],
            "cannot_disable": False,
            "access_model": "included",
            "status": "coming_soon",
            "version": "1.0.0",
            "feature_bullets": [
                "Shift planning with drag-and-drop schedule builder",
                "Staff availability and time-off management",
                "Team calendar view",
                "Shift notifications to employees",
                "Integrates with HR and Time Tracking extension",
            ],
            "setup_required": True,
            "sort_order": 4,
        },

        # ── ADVANCED MANUFACTURING ──
        {
            "extension_key": "work_orders",
            "module_key": "work_orders",
            "display_name": "Work Orders & Production Scheduling",
            "tagline": "Formal work order tracking from sales order through production completion",
            "description": "For operations that want detailed production planning. Create work orders from sales orders, track production status through a formal kanban board, and manage the complete order-to-inventory lifecycle. Recommended for plants producing 50+ units per week or managing multiple product lines simultaneously.",
            "section": "advanced_manufacturing",
            "category": "workflow",
            "applicable_verticals": ["manufacturing"],
            "default_enabled_for": [],
            "cannot_disable": False,
            "access_model": "included",
            "status": "active",
            "version": "1.0.0",
            "feature_bullets": [
                "Work orders auto-created from confirmed sales orders",
                "Production board with kanban status tracking",
                "Connects to pour events and cure tracking when both extensions are enabled",
                "Inventory automatically updated on completion",
                "On-time production reporting",
            ],
            "setup_required": True,
            "sort_order": 1,
        },
        {
            "extension_key": "pour_events_cure_tracking",
            "module_key": "work_orders",
            "display_name": "Pour Events & Cure Tracking",
            "tagline": "Batch-level production traceability from pour through cure release",
            "description": "Track individual pour events, record batch ticket data, and manage cure schedules for each production run. Provides full traceability from finished product back to the batch it was poured in. Recommended for NPCA certified plants and operations that want batch-level quality documentation.",
            "section": "advanced_manufacturing",
            "category": "workflow",
            "applicable_verticals": ["manufacturing"],
            "default_enabled_for": [],
            "cannot_disable": False,
            "access_model": "included",
            "status": "active",
            "version": "1.0.0",
            "feature_bullets": [
                "Pour events link multiple work orders to a single production run",
                "Batch ticket records mix design, slump, temperatures, yield",
                "Cure schedule tracking with automatic release notifications",
                "Full traceability: finished unit to QC to batch to raw materials",
                "Feeds NPCA audit documentation automatically",
            ],
            "setup_required": True,
            "sort_order": 2,
        },
        {
            "extension_key": "qc_module_full",
            "module_key": "safety_management",
            "display_name": "Full QC Module",
            "tagline": "Detailed quality inspection workflows with pressure testing and mobile capture",
            "description": "Complete quality control system with product inspection checklists, pressure test cylinder tracking, photo documentation, defect classification, and disposition workflow. Builds on the basic QC capture in NPCA Audit Prep with full inspection depth. Recommended for NPCA certified plants.",
            "section": "advanced_manufacturing",
            "category": "compliance",
            "applicable_verticals": ["manufacturing"],
            "default_enabled_for": [],
            "cannot_disable": False,
            "access_model": "included",
            "status": "active",
            "version": "1.0.0",
            "feature_bullets": [
                "Mobile inspection interface for yard and shop floor",
                "Pressure test cylinder tracking linked to pour batches",
                "Photo documentation with defect annotation",
                "Pass/fail disposition with scrap tracking",
                "QC certificates generated automatically on pass",
            ],
            "setup_required": True,
            "sort_order": 3,
        },
        {
            "extension_key": "bill_of_materials",
            "module_key": "inventory",
            "display_name": "Bill of Materials",
            "tagline": "Mix designs, raw material requirements, and cost rollups per product",
            "description": "Define the raw material composition of every product you make. Calculate material requirements from open work orders. Track raw material costs and roll them up to product cost. Connects to purchasing for automatic reorder suggestions when materials run low.",
            "section": "advanced_manufacturing",
            "category": "operations",
            "applicable_verticals": ["manufacturing"],
            "default_enabled_for": [],
            "cannot_disable": False,
            "access_model": "included",
            "status": "active",
            "version": "1.0.0",
            "feature_bullets": [
                "Multi-level bill of materials per product",
                "Material requirements planning from open work orders",
                "Cost rollup to product cost",
                "Low material alerts and purchase order suggestions",
                "Connects to Pour Events for batch-level material consumption",
            ],
            "setup_required": True,
            "sort_order": 4,
        },
        {
            "extension_key": "equipment_maintenance",
            "module_key": "safety_management",
            "display_name": "Equipment Maintenance",
            "tagline": "Preventive maintenance schedules, work requests, and equipment lifecycle tracking",
            "description": "Track scheduled maintenance for your plant equipment — batch plant, mixer, forklifts, and other production assets. Log maintenance performed, track equipment downtime, and get alerts when PM is due. Separate from safety inspections — this is for keeping your equipment running.",
            "section": "advanced_manufacturing",
            "category": "operations",
            "applicable_verticals": ["manufacturing"],
            "default_enabled_for": [],
            "cannot_disable": False,
            "access_model": "included",
            "status": "active",
            "version": "1.0.0",
            "feature_bullets": [
                "Equipment asset registry with maintenance schedules",
                "PM alerts based on calendar or usage hours",
                "Maintenance work order logging",
                "Equipment downtime tracking",
                "Maintenance cost tracking per asset",
            ],
            "setup_required": True,
            "sort_order": 5,
        },
        {
            "extension_key": "capacity_planning",
            "module_key": "sales",
            "display_name": "Capacity Planning",
            "tagline": "Production capacity vs demand visibility — know before you are overcommitted",
            "description": "See your production capacity against committed order demand over the next 4-6 weeks. Know before you are in trouble — identify when demand exceeds capacity so you can accelerate production, set realistic customer expectations, or identify subcontract opportunities.",
            "section": "advanced_manufacturing",
            "category": "reporting",
            "applicable_verticals": ["manufacturing"],
            "default_enabled_for": [],
            "cannot_disable": False,
            "access_model": "included",
            "status": "active",
            "version": "1.0.0",
            "feature_bullets": [
                "Forward-looking capacity vs demand view",
                "Mold utilization tracking",
                "Cure schedule impact on available capacity",
                "Early warning when demand exceeds capacity",
                "Connects to work orders and production scheduling",
            ],
            "setup_required": True,
            "sort_order": 6,
        },
        {
            "extension_key": "mold_inventory",
            "module_key": "inventory",
            "display_name": "Mold Inventory",
            "tagline": "Track your molds, their condition, cycle counts, and maintenance history",
            "description": "Your molds are capital assets that directly constrain production capacity. Track which molds you own, what product they produce, their current condition, cycle count against rated life, maintenance history, and current status. Surfaces mold constraints on the production board.",
            "section": "advanced_manufacturing",
            "category": "operations",
            "applicable_verticals": ["manufacturing"],
            "default_enabled_for": [],
            "cannot_disable": False,
            "access_model": "included",
            "status": "active",
            "version": "1.0.0",
            "feature_bullets": [
                "Mold asset registry with product mapping",
                "Cycle count tracking against rated mold life",
                "Maintenance history per mold",
                "Current status tracking: available, in use, in cure, under repair",
                "Mold constraint visibility on production board",
            ],
            "setup_required": True,
            "sort_order": 7,
        },
    ]

    import uuid

    for ext in NEW_REGISTRY:
        ext_id = str(uuid.uuid4())
        verticals = json.dumps(ext.get("applicable_verticals", []))
        enabled_for = json.dumps(ext.get("default_enabled_for", []))
        bullets = json.dumps(ext.get("feature_bullets", []))

        bind.execute(
            sa.text(
                "INSERT INTO extension_definitions "
                "(id, extension_key, module_key, display_name, tagline, description, "
                "section, category, applicable_verticals, default_enabled_for, "
                "cannot_disable, access_model, status, version, feature_bullets, "
                "setup_required, sort_order, is_active) "
                "VALUES (:id, :key, :mod, :name, :tag, :desc, :sec, :cat, "
                ":vert, :enabled, :nodis, :access, :status, :ver, :bullets, "
                ":setup, :sort, true)"
            ),
            {
                "id": ext_id,
                "key": ext["extension_key"],
                "mod": ext["module_key"],
                "name": ext["display_name"],
                "tag": ext["tagline"],
                "desc": ext["description"],
                "sec": ext["section"],
                "cat": ext["category"],
                "vert": verticals,
                "enabled": enabled_for,
                "nodis": ext.get("cannot_disable", False),
                "access": ext["access_model"],
                "status": ext["status"],
                "ver": ext["version"],
                "bullets": bullets,
                "setup": ext.get("setup_required", False),
                "sort": ext["sort_order"],
            },
        )

    # 6. Re-link tenant_extensions to new IDs by extension_key
    if existing_te:
        bind.execute(
            sa.text(
                "UPDATE tenant_extensions te "
                "SET extension_id = er.id "
                "FROM extension_definitions er "
                "WHERE te.extension_key = er.extension_key"
            )
        )


def downgrade() -> None:
    # Cannot meaningfully restore the old catalog — just remove the section column
    op.drop_column("extension_definitions", "section")
