"""Widget definitions seed data.

Called on application startup. Uses INSERT ... ON CONFLICT DO NOTHING
so re-running never overwrites user customizations or existing rows.
"""

import uuid
import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.widget_definition import WidgetDefinition

logger = logging.getLogger(__name__)

WIDGET_DEFINITIONS: list[dict] = [
    # ── Operations Board widgets ──────────────────────────────
    {
        "widget_id": "todays_services",
        "title": "Today's Services",
        "description": "All vault orders scheduled for today with status and cemetery info",
        "page_contexts": ["ops_board"],
        "default_size": "2x1",
        "min_size": "2x1",
        "supported_sizes": ["2x1", "2x2", "4x1"],
        "category": "operations",
        "icon": "Calendar",
        "default_enabled": True,
        "default_position": 1,
    },
    {
        "widget_id": "legacy_queue",
        "title": "Legacy Proof Queue",
        "description": "Proofs awaiting review or approval",
        "page_contexts": ["ops_board", "home"],
        "default_size": "1x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1"],
        "category": "operations",
        "icon": "Image",
        "default_enabled": True,
        "default_position": 2,
    },
    {
        "widget_id": "driver_status",
        "title": "Driver Status",
        "description": "Active drivers and their current stops",
        "page_contexts": ["ops_board"],
        "default_size": "2x1",
        "min_size": "2x1",
        "supported_sizes": ["2x1", "2x2"],
        "category": "operations",
        "icon": "Truck",
        "default_enabled": True,
        "default_position": 3,
    },
    {
        "widget_id": "production_status",
        "title": "Production Status",
        "description": "Vault production progress for today",
        "page_contexts": ["ops_board", "home"],
        "default_size": "1x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1"],
        "category": "production",
        "icon": "Factory",
        "default_enabled": True,
        "default_position": 4,
    },
    {
        "widget_id": "open_orders",
        "title": "Open Orders",
        "description": "Orders pending scheduling or fulfillment",
        "page_contexts": ["ops_board", "home"],
        "default_size": "1x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1"],
        "category": "operations",
        "icon": "ClipboardList",
        "default_enabled": True,
        "default_position": 5,
    },
    {
        "widget_id": "inventory_levels",
        "title": "Key Inventory",
        "description": "Stock levels for important vault products",
        "page_contexts": ["ops_board", "home"],
        "default_size": "1x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1"],
        "category": "production",
        "icon": "Package",
        "default_enabled": True,
        "default_position": 6,
    },
    {
        "widget_id": "briefing_summary",
        "title": "Morning Briefing",
        "description": "Today's briefing items and action items",
        "page_contexts": ["ops_board", "home"],
        "default_size": "2x1",
        "min_size": "2x1",
        "supported_sizes": ["2x1", "4x1"],
        "category": "intelligence",
        "icon": "Sunrise",
        "default_enabled": True,
        "default_position": 7,
    },
    {
        "widget_id": "activity_feed",
        "title": "Recent Activity",
        "description": "Latest actions across the platform",
        "page_contexts": ["ops_board", "home", "company_detail"],
        "default_size": "1x2",
        "min_size": "1x2",
        "supported_sizes": ["1x2", "2x2"],
        "category": "crm",
        "icon": "Activity",
        "default_enabled": False,
        "default_position": 8,
    },
    # ── Extension widgets (ops board) ─────────────────────────
    {
        "widget_id": "qc_status",
        "title": "QC Inspection Status",
        "description": "Today's quality control checks and results",
        "page_contexts": ["ops_board"],
        "default_size": "1x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1"],
        "required_extension": "npca_audit_prep",
        "category": "production",
        "icon": "CheckSquare",
        "default_enabled": True,
        "default_position": 9,
    },
    {
        "widget_id": "time_clock",
        "title": "Time Clock",
        "description": "Clocked in staff, hours, time-off requests",
        "page_contexts": ["ops_board", "home"],
        "default_size": "2x1",
        "min_size": "2x1",
        "supported_sizes": ["2x1", "2x2"],
        "required_extension": "time_clock",
        "category": "operations",
        "icon": "Clock",
        "default_enabled": True,
        "default_position": 10,
    },
    {
        "widget_id": "safety_status",
        "title": "Safety Dashboard",
        "description": "Open incidents, training due, equipment inspections",
        "page_contexts": ["ops_board", "home"],
        "default_size": "1x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1"],
        "required_extension": "safety",
        "category": "safety",
        "icon": "ShieldCheck",
        "default_enabled": True,
        "default_position": 11,
    },
    # ── Home Dashboard widgets (future, seeded now) ───────────
    {
        "widget_id": "revenue_summary",
        "title": "Revenue",
        "description": "Monthly revenue vs prior month",
        "page_contexts": ["home"],
        "default_size": "1x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1"],
        "category": "financial",
        "icon": "DollarSign",
        "required_permission": "ar.view",
        "default_enabled": True,
        "default_position": 1,
    },
    {
        "widget_id": "ar_summary",
        "title": "Accounts Receivable",
        "description": "Outstanding AR and overdue summary",
        "page_contexts": ["home"],
        "default_size": "1x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1"],
        "category": "financial",
        "icon": "Receipt",
        "required_permission": "ar.view",
        "default_enabled": True,
        "default_position": 2,
    },
    {
        "widget_id": "at_risk_accounts",
        "title": "At-Risk Accounts",
        "description": "Funeral homes that need attention",
        "page_contexts": ["home", "ops_board"],
        "default_size": "1x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1"],
        "category": "crm",
        "icon": "AlertTriangle",
        "default_enabled": True,
        "default_position": 3,
    },
    # ───────────────────────────────────────────────────────────────
    # Platform Polish additions — compliance, training, knowledge base surfaces
    # ───────────────────────────────────────────────────────────────
    {
        "widget_id": "compliance_upcoming",
        "title": "Compliance — Upcoming",
        "description": "Compliance items due in the next 30 days (overdue / this week / soon)",
        "page_contexts": ["home", "ops_board"],
        "default_size": "2x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1", "2x2"],
        "category": "compliance",
        "icon": "ShieldCheck",
        "default_enabled": True,
        "default_position": 20,
        "required_permission": "compliance.view",
    },
    {
        "widget_id": "team_certifications",
        "title": "Team Certifications Expiring",
        "description": "Team members with certifications expiring soon (CDL, forklift, OSHA)",
        "page_contexts": ["home", "ops_board"],
        "default_size": "2x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1", "2x2"],
        "category": "safety",
        "icon": "Users",
        "default_enabled": True,
        "default_position": 21,
        "required_permission": "employees.view",
    },
    {
        "widget_id": "my_certifications",
        "title": "My Certifications",
        "description": "Your certification status and expiration dates",
        "page_contexts": ["home"],
        "default_size": "2x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1"],
        "category": "safety",
        "icon": "Award",
        "default_enabled": True,
        "default_position": 22,
    },
    {
        "widget_id": "my_training",
        "title": "My Training",
        "description": "Your assigned training items and due dates",
        "page_contexts": ["home"],
        "default_size": "2x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1"],
        "category": "safety",
        "icon": "GraduationCap",
        "default_enabled": True,
        "default_position": 23,
    },
    {
        "widget_id": "kb_recent",
        "title": "Knowledge Base — Recent",
        "description": "Most recent knowledge base additions and updates",
        "page_contexts": ["home"],
        "default_size": "1x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1"],
        "category": "operations",
        "icon": "BookOpen",
        "default_enabled": True,
        "default_position": 24,
    },
]


def seed_widget_definitions(db: Session) -> int:
    """Insert widget definitions, skipping any that already exist.

    Returns the number of newly inserted rows.
    """
    inserted = 0
    for defn in WIDGET_DEFINITIONS:
        row = {**defn, "id": str(uuid.uuid4()), "is_system": True}
        row.setdefault("required_extension", None)
        row.setdefault("required_permission", None)
        row.setdefault("required_preset", None)
        row.setdefault("min_size", row.get("default_size", "1x1"))
        row.setdefault("max_size", "4x4")

        stmt = (
            pg_insert(WidgetDefinition)
            .values(**row)
            .on_conflict_do_nothing(index_elements=["widget_id"])
        )
        result = db.execute(stmt)
        if result.rowcount:
            inserted += 1

    db.commit()
    if inserted:
        logger.info("Seeded %d new widget definitions (%d total in registry)", inserted, len(WIDGET_DEFINITIONS))
    return inserted
