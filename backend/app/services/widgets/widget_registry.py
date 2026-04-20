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
        # V-1c: extended to vault_overview so the CRM service can
        # claim this widget in its overview. Same component renders
        # in both contexts; position controlled per-context by the
        # widget framework's default_position value (shared).
        "page_contexts": ["home", "ops_board", "vault_overview"],
        "default_size": "1x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1"],
        "category": "crm",
        "icon": "AlertTriangle",
        "default_enabled": True,
        "default_position": 7,
        "required_permission": "customers.view",
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
    # ───────────────────────────────────────────────────────────────
    # V-1b — Bridgeable Vault Overview widgets
    #
    # Five widgets that populate the /vault landing page. Each wraps
    # an existing tenant API (no new aggregation endpoints). Widget
    # framework filters by permission/extension via the standard seed
    # columns. Default positions 1-5; position 6 intentionally empty
    # so the empty "Add widget" tile suggests customization.
    # ───────────────────────────────────────────────────────────────
    {
        "widget_id": "vault_recent_documents",
        "title": "Recent documents",
        "description": "Latest documents generated across your tenant",
        "page_contexts": ["vault_overview"],
        "default_size": "2x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1", "2x2"],
        "category": "documents",
        "icon": "FileText",
        "default_enabled": True,
        "default_position": 1,
    },
    {
        "widget_id": "vault_pending_signatures",
        "title": "Pending signatures",
        "description": "Signing envelopes awaiting signer action",
        "page_contexts": ["vault_overview"],
        "default_size": "2x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1", "2x2"],
        "category": "documents",
        "icon": "FileCheck",
        "default_enabled": True,
        "default_position": 2,
    },
    {
        "widget_id": "vault_unread_inbox",
        "title": "Inbox",
        "description": "Cross-tenant documents shared with this tenant that you haven't read",
        "page_contexts": ["vault_overview"],
        "default_size": "2x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1", "2x2"],
        "category": "documents",
        "icon": "Megaphone",
        "default_enabled": True,
        "default_position": 3,
    },
    {
        "widget_id": "vault_notifications",
        "title": "Notifications",
        "description": "Unread platform notifications across all sources",
        "page_contexts": ["vault_overview"],
        "default_size": "2x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1", "2x2"],
        "category": "notifications",
        "icon": "Bell",
        "default_enabled": True,
        "default_position": 4,
    },
    {
        "widget_id": "vault_recent_deliveries",
        "title": "Recent deliveries",
        "description": "Emails / SMS / documents routed through DeliveryService — toggle to filter failures",
        "page_contexts": ["vault_overview"],
        "default_size": "2x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1", "2x2"],
        "category": "documents",
        "icon": "Truck",
        "default_enabled": True,
        "default_position": 5,
    },
    # ───────────────────────────────────────────────────────────────
    # V-1c — CRM Overview widget
    #
    # Surfaces the tenant-wide ActivityLog tail (new
    # /api/v1/vault/activity/recent endpoint). Sits at position 6,
    # paired with `at_risk_accounts` at position 7 — both owned by
    # the `crm` Vault service and gated on `customers.view`.
    # ───────────────────────────────────────────────────────────────
    {
        "widget_id": "vault_crm_recent_activity",
        "title": "Recent CRM activity",
        "description": "Latest customer / vendor interactions across your tenant",
        "page_contexts": ["vault_overview"],
        "default_size": "2x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1", "2x2"],
        "category": "crm",
        "icon": "Activity",
        "default_enabled": True,
        "default_position": 6,
        "required_permission": "customers.view",
    },
    # ───────────────────────────────────────────────────────────────────
    # V-1e: Accounting admin widgets. All gated on `admin` so only
    # platform-admin users see them. Appended at positions 8, 9, 10
    # (default_position 7 is at_risk_accounts from V-1c).
    # ───────────────────────────────────────────────────────────────────
    {
        "widget_id": "vault_pending_period_close",
        "title": "Pending period close",
        "description": "Months the month-end-close agent flagged as ready to close",
        "page_contexts": ["vault_overview"],
        "default_size": "2x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1", "2x2"],
        "category": "accounting",
        "icon": "Calendar",
        "default_enabled": True,
        "default_position": 8,
        "required_permission": "admin",
    },
    {
        "widget_id": "vault_gl_classification_review",
        "title": "GL classifications awaiting review",
        "description": "Pending AI-classified GL accounts waiting for admin confirmation",
        "page_contexts": ["vault_overview"],
        "default_size": "2x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1", "2x2"],
        "category": "accounting",
        "icon": "ClipboardList",
        "default_enabled": True,
        "default_position": 9,
        "required_permission": "admin",
    },
    {
        "widget_id": "vault_agent_recent_activity",
        "title": "Recent agent activity",
        "description": "Most recent accounting-agent job runs across all 12 agents",
        "page_contexts": ["vault_overview"],
        "default_size": "2x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1", "2x2"],
        "category": "accounting",
        "icon": "Bot",
        "default_enabled": True,
        "default_position": 10,
        "required_permission": "admin",
    },
]


def seed_widget_definitions(db: Session) -> int:
    """Insert or update widget definitions.

    Behavior:
      - Rows with a new `widget_id` are inserted.
      - Existing rows are UPDATED on the **system-owned** columns only:
        title, description, page_contexts, default_size, supported_sizes,
        min_size, max_size, category, icon, default_enabled,
        default_position, required_extension, required_permission,
        required_preset.

      Per-user layouts live in `user_widget_layouts` and are untouched;
      only the definition metadata is refreshed. This lets V-1c+ extend
      an existing widget's `page_contexts` (e.g. making
      `at_risk_accounts` also appear in `vault_overview`) just by
      shipping new code — no migration required.

    Returns the count of rows inserted OR meaningfully updated.
    """
    changed = 0
    for defn in WIDGET_DEFINITIONS:
        row = {**defn, "id": str(uuid.uuid4()), "is_system": True}
        row.setdefault("required_extension", None)
        row.setdefault("required_permission", None)
        row.setdefault("required_preset", None)
        row.setdefault("min_size", row.get("default_size", "1x1"))
        row.setdefault("max_size", "4x4")

        updatable_columns = {
            "title": row["title"],
            "description": row.get("description"),
            "page_contexts": row["page_contexts"],
            "default_size": row["default_size"],
            "supported_sizes": row.get("supported_sizes"),
            "min_size": row["min_size"],
            "max_size": row["max_size"],
            "category": row.get("category"),
            "icon": row.get("icon"),
            "default_enabled": row.get("default_enabled", True),
            "default_position": row.get("default_position", 0),
            "required_extension": row["required_extension"],
            "required_permission": row["required_permission"],
            "required_preset": row["required_preset"],
        }
        stmt = (
            pg_insert(WidgetDefinition)
            .values(**row)
            .on_conflict_do_update(
                index_elements=["widget_id"],
                set_=updatable_columns,
            )
        )
        result = db.execute(stmt)
        # rowcount is 1 both for INSERT and UPDATE via ON CONFLICT DO
        # UPDATE, so we can't distinguish cheaply. Report as "touched".
        if result.rowcount:
            changed += 1

    db.commit()
    if changed:
        logger.info(
            "Widget definitions seeded/updated: %d touched (%d total in registry)",
            changed,
            len(WIDGET_DEFINITIONS),
        )
    return changed
