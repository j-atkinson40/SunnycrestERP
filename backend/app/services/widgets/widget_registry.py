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
        # Phase W-1 — NPCA audit prep is funeral-home compliance per
        # CLAUDE.md §1; flagged in Phase W-1 audit + Section 12.4
        # 4-axis filter (vertical axis).
        "required_vertical": ["funeral_home"],
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
    # ── Phase W-3a cross-vertical foundation widgets ──────────
    # Cross-vertical (required_vertical: "*") + cross-line
    # (required_product_line: "*"). Visible to every tenant
    # regardless of vertical or product-line activation. Per
    # DESIGN_LANGUAGE.md §12.10 reference implementations expanded
    # for the W-3a foundation set.
    {
        "widget_id": "saved_view",
        "title": "Saved View",
        "description": (
            "Generic widget rendering any tenant saved view. "
            "Config-driven: each instance carries `config: {view_id: ...}` "
            "selecting which saved view to render. Per-instance "
            "configuration mechanism makes 'any saved view becomes a "
            "widget instance' a first-class platform pattern — the "
            "user-authored widget catalog without widget code. "
            "Variants Brief + Detail + Deep — NO Glance because saved "
            "views need at minimum a list to be informative; surface "
            "compatibility excludes `spaces_pin` for the same reason "
            "(sidebar requires Glance variant per §12.2 compatibility "
            "matrix). Reuses the V-1c SavedView API + the existing "
            "SavedViewRenderer per-mode dispatch (list / table / kanban "
            "/ calendar / cards / chart / stat — 7 presentation modes). "
            "View-only with click-through to entity per §12.6a — full "
            "saved view editing happens at /saved-views/{view_id}."
        ),
        "page_contexts": ["pulse", "home", "ops_board"],
        "default_size": "2x2",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1", "2x2", "4x2", "4x4"],
        "category": "operations",
        "icon": "Layers",
        "default_enabled": True,
        "default_position": 6,
        # Section 12.5 surface declaration. Excludes `spaces_pin`
        # because saved_view declares no Glance variant, and §12.2
        # compatibility matrix requires Glance variants for sidebar
        # rendering. Excludes `peek_inline` because the widget's
        # variants are too dense for peek-panel content composition;
        # peek panels can render saved views directly via
        # SavedViewRenderer if needed.
        "supported_surfaces": [
            "pulse_grid",
            "dashboard_grid",
            "focus_canvas",
        ],
        "default_surfaces": ["dashboard_grid"],
        "intelligence_keywords": [
            "saved_view",
            "view",
            "list",
            "table",
            "kanban",
            "calendar",
            "report",
        ],
        "variants": [
            {
                "variant_id": "brief",
                "density": "focused",
                "grid_size": {"cols": 1, "rows": 1},
                "canvas_size": {
                    "width": 320,
                    "height": "auto",
                    "maxHeight": 400,
                },
                "supported_surfaces": [
                    "pulse_grid",
                    "dashboard_grid",
                    "focus_canvas",
                ],
            },
            {
                "variant_id": "detail",
                "density": "rich",
                "grid_size": {"cols": 2, "rows": 2},
                "canvas_size": {
                    "width": 480,
                    "height": "auto",
                    "maxHeight": 600,
                },
                "supported_surfaces": [
                    "pulse_grid",
                    "dashboard_grid",
                    "focus_canvas",
                ],
            },
            {
                "variant_id": "deep",
                "density": "deep",
                "grid_size": {"cols": 4, "rows": 4},
                "canvas_size": {
                    "width": 640,
                    "height": "auto",
                    "maxHeight": 800,
                },
                "supported_surfaces": [
                    "pulse_grid",
                    "dashboard_grid",
                    "focus_canvas",
                ],
            },
        ],
        "default_variant_id": "detail",
    },
    {
        "widget_id": "anomalies",
        "title": "Anomalies",
        "description": (
            "Tenant-scoped unresolved anomaly feed — cross-vertical "
            "foundation widget. Surfaces real production anomaly data "
            "from the existing agent_anomalies table (accounting agent "
            "infrastructure). Phase W-3a: real data over stub — "
            "Wilbert licensee tenants running accounting agents have "
            "production-emitted anomalies this widget surfaces "
            "directly. Phase W-5 (Intelligence-detected anomalies) "
            "extends the data source rather than replacing the widget. "
            "Brief: 2-4 most recent/critical anomalies with "
            "Acknowledge action. Detail: full scrollable list with "
            "severity filter chips. NO Glance variant per §12.10 — "
            "anomalies need at least Brief context. Per §12.6a: "
            "Acknowledge is a bounded state flip (single anomaly, "
            "single field, audit-logged) — widget-appropriate."
        ),
        "page_contexts": ["pulse", "home", "ops_board"],
        "default_size": "1x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1", "2x2"],
        "category": "operations",
        "icon": "AlertTriangle",
        "default_enabled": True,
        "default_position": 5,
        "supported_surfaces": [
            "pulse_grid",
            "spaces_pin",
            "dashboard_grid",
            "focus_canvas",
        ],
        "default_surfaces": ["pulse_grid", "dashboard_grid"],
        "intelligence_keywords": [
            "anomaly",
            "anomalies",
            "alert",
            "exception",
            "issue",
            "warning",
        ],
        "variants": [
            {
                "variant_id": "brief",
                "density": "focused",
                "grid_size": {"cols": 1, "rows": 1},
                "canvas_size": {
                    "width": 320,
                    "height": "auto",
                    "maxHeight": 320,
                },
                "supported_surfaces": [
                    "pulse_grid",
                    "dashboard_grid",
                    "focus_canvas",
                    "spaces_pin",
                ],
            },
            {
                "variant_id": "detail",
                "density": "rich",
                "grid_size": {"cols": 2, "rows": 2},
                "canvas_size": {
                    "width": 480,
                    "height": "auto",
                    "maxHeight": 600,
                },
                "supported_surfaces": [
                    "pulse_grid",
                    "dashboard_grid",
                    "focus_canvas",
                ],
            },
        ],
        "default_variant_id": "brief",
    },
    {
        "widget_id": "recent_activity",
        "title": "Recent Activity",
        "description": (
            "Tenant-wide activity feed — cross-vertical foundation "
            "widget. Backed by the V-1c `/vault/activity/recent` "
            "endpoint extended Phase W-3a with `actor_name` shim. "
            "Glance: count of recent events. Brief: 3-5 most recent "
            "events with actor + action + entity + timestamp. Detail: "
            "full scrollable list with event-type filter chips. "
            "View-only widget per §12.6a — no state-flip interactions; "
            "click-through navigates to the related entity. Used "
            "inside peek panels at Brief variant for cross-surface "
            "composition."
        ),
        "page_contexts": ["pulse", "home", "ops_board"],
        "default_size": "1x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1", "2x2"],
        "category": "operations",
        "icon": "Activity",
        "default_enabled": True,
        "default_position": 4,
        "supported_surfaces": [
            "pulse_grid",
            "spaces_pin",
            "dashboard_grid",
            "focus_canvas",
            "peek_inline",
        ],
        "default_surfaces": ["pulse_grid", "dashboard_grid"],
        "intelligence_keywords": [
            "activity",
            "recent",
            "feed",
            "events",
            "log",
        ],
        "variants": [
            {
                "variant_id": "glance",
                "density": "minimal",
                "grid_size": {"cols": 1, "rows": 1},
                "canvas_size": {"width": 240, "height": 60},
                "supported_surfaces": ["spaces_pin", "pulse_grid"],
            },
            {
                "variant_id": "brief",
                "density": "focused",
                "grid_size": {"cols": 1, "rows": 1},
                "canvas_size": {
                    "width": 320,
                    "height": "auto",
                    "maxHeight": 320,
                },
                "supported_surfaces": [
                    "pulse_grid",
                    "dashboard_grid",
                    "focus_canvas",
                    "peek_inline",
                ],
            },
            {
                "variant_id": "detail",
                "density": "rich",
                "grid_size": {"cols": 2, "rows": 2},
                "canvas_size": {
                    "width": 480,
                    "height": "auto",
                    "maxHeight": 600,
                },
                "supported_surfaces": [
                    "pulse_grid",
                    "dashboard_grid",
                    "focus_canvas",
                ],
            },
        ],
        "default_variant_id": "brief",
    },
    {
        "widget_id": "operator_profile",
        "title": "Operator Profile",
        "description": (
            "Current user's identity + role + active space — cross-"
            "vertical foundation widget. Reads entirely from auth "
            "context + spaces context (no backend call). Glance: "
            "avatar + name + role. Brief: full identity + role + "
            "active space + access summary (permissions / modules / "
            "extensions counts). Click → /settings/profile for deep "
            "edit."
        ),
        "page_contexts": ["pulse", "home"],
        "default_size": "1x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1"],
        "category": "operations",
        "icon": "User",
        "default_enabled": True,
        "default_position": 2,
        "supported_surfaces": [
            "pulse_grid",
            "spaces_pin",
            "dashboard_grid",
        ],
        "default_surfaces": ["pulse_grid"],
        "intelligence_keywords": [
            "profile",
            "operator",
            "identity",
            "role",
            "permissions",
        ],
        "variants": [
            {
                "variant_id": "glance",
                "density": "minimal",
                "grid_size": {"cols": 1, "rows": 1},
                "canvas_size": {"width": 240, "height": 60},
                "supported_surfaces": ["spaces_pin", "pulse_grid"],
            },
            {
                "variant_id": "brief",
                "density": "focused",
                "grid_size": {"cols": 1, "rows": 1},
                "canvas_size": {
                    "width": 280,
                    "height": "auto",
                    "maxHeight": 240,
                },
                "supported_surfaces": [
                    "pulse_grid",
                    "dashboard_grid",
                ],
            },
        ],
        "default_variant_id": "brief",
    },
    {
        "widget_id": "today",
        "title": "Today",
        "description": (
            "Today's work summary — cross-vertical foundation widget. "
            "Shows the count + breakdown of relevant work items for the "
            "user's tenant. Manufacturing+vault tenants see vault "
            "deliveries, ancillary pool items waiting, and unscheduled "
            "deliveries. Other verticals get a thoughtful empty state "
            "with a CTA to their primary work surface (vertical-aware). "
            "Per Section 12.10 W-3a reference implementation: Glance + "
            "Brief variants only — `today` is a reference widget, not "
            "a workspace surface."
        ),
        "page_contexts": ["pulse", "home", "ops_board"],
        "default_size": "1x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1"],
        "category": "operations",
        "icon": "Calendar",
        "default_enabled": True,
        "default_position": 1,
        # Cross-vertical + cross-line per W-3a foundation contract.
        # Interactions per §12.6a are bounded to navigation only
        # (no acknowledge / edit). View-only with click-through.
        "supported_surfaces": [
            "pulse_grid",
            "spaces_pin",
            "dashboard_grid",
            "focus_canvas",
        ],
        "default_surfaces": ["pulse_grid", "dashboard_grid"],
        "intelligence_keywords": [
            "today",
            "schedule",
            "summary",
            "overview",
        ],
        "variants": [
            {
                "variant_id": "glance",
                "density": "minimal",
                "grid_size": {"cols": 1, "rows": 1},
                "canvas_size": {"width": 180, "height": 60},
                "supported_surfaces": ["spaces_pin", "pulse_grid"],
            },
            {
                "variant_id": "brief",
                "density": "focused",
                "grid_size": {"cols": 1, "rows": 1},
                "canvas_size": {
                    "width": 280,
                    "height": "auto",
                    "maxHeight": 240,
                },
                "supported_surfaces": [
                    "pulse_grid",
                    "dashboard_grid",
                    "focus_canvas",
                ],
            },
        ],
        "default_variant_id": "brief",
    },
    {
        "widget_id": "briefing",
        "title": "Briefing",
        "description": (
            "Per-user AI briefing widget — Phase W-3b promotion of the "
            "Phase 6 BriefingCard to widget contract. Per-user scoped: "
            "every user sees their own latest morning OR evening "
            "briefing (the existing Phase 6 `/briefings/v2/latest` "
            "endpoint enforces the user-scoping). Glance: unread badge "
            "+ briefing-type icon (sunrise/sunset). Brief: condensed "
            "narrative excerpt + active space pill + 'Read full → ' "
            "deep link to /briefing. Detail: full narrative + "
            "structured-section preview cards (queue summaries, flags, "
            "pending decisions) + Read full link. View-only per §12.6a "
            "— Mark-read + Regenerate live on the dedicated /briefing "
            "page, not the widget. Briefing-type selectable per "
            "instance via `config.briefing_type` (default: 'morning'). "
            "Cross-vertical + cross-line — every tenant + every user "
            "with at least one Phase 6 briefing seen. Empty state when "
            "the user has no briefing today routes to /briefing."
        ),
        "page_contexts": ["pulse", "home", "ops_board"],
        "default_size": "1x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1", "2x2"],
        "category": "intelligence",
        "icon": "Sunrise",
        "default_enabled": True,
        "default_position": 7,
        # Briefing surfaces: pulse_grid + spaces_pin (Glance) +
        # dashboard_grid + focus_canvas (Brief / Detail). NOT
        # peek_inline — briefing is per-user content, not
        # entity-scoped, so peek panels (which compose around an
        # entity) don't have a meaningful briefing rendering.
        "supported_surfaces": [
            "pulse_grid",
            "spaces_pin",
            "dashboard_grid",
            "focus_canvas",
        ],
        "default_surfaces": ["pulse_grid", "dashboard_grid"],
        "intelligence_keywords": [
            "briefing",
            "morning",
            "evening",
            "summary",
            "today",
            "agenda",
        ],
        "variants": [
            {
                "variant_id": "glance",
                "density": "minimal",
                "grid_size": {"cols": 1, "rows": 1},
                "canvas_size": {"width": 200, "height": 60},
                "supported_surfaces": ["spaces_pin", "pulse_grid"],
            },
            {
                "variant_id": "brief",
                "density": "focused",
                "grid_size": {"cols": 1, "rows": 1},
                "canvas_size": {
                    "width": 320,
                    "height": "auto",
                    "maxHeight": 320,
                },
                "supported_surfaces": [
                    "pulse_grid",
                    "dashboard_grid",
                    "focus_canvas",
                ],
            },
            {
                "variant_id": "detail",
                "density": "rich",
                "grid_size": {"cols": 2, "rows": 2},
                "canvas_size": {
                    "width": 480,
                    "height": "auto",
                    "maxHeight": 600,
                },
                "supported_surfaces": [
                    "pulse_grid",
                    "dashboard_grid",
                    "focus_canvas",
                ],
            },
        ],
        "default_variant_id": "brief",
    },
    # ── Phase W-3d manufacturing per-line widgets ─────────────
    # Vertical-scoped + product-line-scoped. First widgets to exercise
    # the 5-axis filter at full activation: vault_schedule + line_status
    # use `required_product_line: ["vault"]` (or "*" for line_status
    # cross-line aggregator); urn_catalog_status uses
    # `required_extension: ["urn_sales"]` — first widget testing the
    # extension axis end-to-end.
    {
        "widget_id": "vault_schedule",
        "title": "Vault Schedule",
        "description": (
            "Mode-aware vault production schedule — Phase W-3d "
            "workspace-core widget per §12.6. Reads "
            "`TenantProductLine(line_key='vault').config['operating_mode']` "
            "and dispatches: production mode reads Delivery rows "
            "(kanban shape — same data scheduling Focus consumes); "
            "purchase mode reads incoming LicenseeTransfer rows; "
            "hybrid composes both. **Workspace-core canonical "
            "reference**: bounded interactive surface per §12.6a "
            "(mark hole-dug, drag delivery between drivers, attach/"
            "detach ancillary, update single ETA); finalize / "
            "day-switch / bulk reassignment remain Focus-only — "
            "click-through 'Open in Focus' affordance always present. "
            "Glance + Brief + Detail + Deep variants per §12.10 "
            "reference. Per the SalesOrder vs Delivery investigation "
            "(2026-04-27): widget consumes Delivery rows because "
            "ancillary items are independent SalesOrders; driver "
            "lives on Delivery (logistics concept). Cards enrich "
            "with SalesOrder context (deceased, customer, line "
            "items) at render time."
        ),
        "page_contexts": ["pulse", "home", "ops_board"],
        "default_size": "2x2",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1", "2x2", "4x2", "4x4"],
        "category": "operations",
        "icon": "Truck",
        "default_enabled": True,
        "default_position": 8,
        "required_vertical": ["manufacturing"],
        "required_product_line": ["vault"],
        # Section 12.5 surface declaration. Includes `spaces_pin` via
        # Glance variant (sidebar-pinnable per §12.2 compatibility
        # matrix). Excludes `peek_inline` because schedule is per-
        # tenant operational data, not entity-scoped.
        "supported_surfaces": [
            "pulse_grid",
            "spaces_pin",
            "dashboard_grid",
            "focus_canvas",
        ],
        "default_surfaces": ["pulse_grid", "dashboard_grid"],
        "intelligence_keywords": [
            "vault",
            "schedule",
            "pour",
            "delivery",
            "kanban",
            "production",
            "purchase",
            "incoming",
        ],
        "variants": [
            {
                "variant_id": "glance",
                "density": "minimal",
                "grid_size": {"cols": 1, "rows": 1},
                "canvas_size": {"width": 240, "height": 60},
                "supported_surfaces": ["spaces_pin", "pulse_grid"],
            },
            {
                "variant_id": "brief",
                "density": "focused",
                "grid_size": {"cols": 1, "rows": 1},
                "canvas_size": {
                    "width": 320,
                    "height": "auto",
                    "maxHeight": 360,
                },
                "supported_surfaces": [
                    "pulse_grid",
                    "dashboard_grid",
                    "focus_canvas",
                ],
            },
            {
                "variant_id": "detail",
                "density": "rich",
                "grid_size": {"cols": 2, "rows": 2},
                "canvas_size": {
                    "width": 480,
                    "height": "auto",
                    "maxHeight": 600,
                },
                "supported_surfaces": [
                    "pulse_grid",
                    "dashboard_grid",
                    "focus_canvas",
                ],
            },
            {
                "variant_id": "deep",
                "density": "deep",
                "grid_size": {"cols": 4, "rows": 4},
                "canvas_size": {
                    "width": 720,
                    "height": "auto",
                    "maxHeight": 900,
                },
                "supported_surfaces": [
                    "pulse_grid",
                    "dashboard_grid",
                    "focus_canvas",
                ],
            },
        ],
        "default_variant_id": "brief",
    },
    {
        "widget_id": "line_status",
        "title": "Line Status",
        "description": (
            "Cross-line operational health aggregator — Phase W-3d "
            "manufacturing per-line widget. Surfaces per-line status "
            "for whichever product lines the tenant has activated. "
            "Replaces the implicit pre-canon `production_status` "
            "widget (which assumed all lines are production-mode) "
            "with a mode-agnostic, per-line health view. Production-"
            "mode lines show pour load + driver assignment; purchase-"
            "mode lines show supplier delivery status; hybrid lines "
            "compose both. Brief + Detail variants per §12.10 — NO "
            "Glance because line status is operational-health "
            "information that doesn't compress to count-only. "
            "Cross-line scope (`required_product_line=['*']`) — "
            "renders for whichever lines are active per tenant. "
            "Multi-line builder pattern (mirrors today widget): "
            "vault metrics real, redi_rock/wastewater/urn_sales "
            "placeholders activate as their per-line aggregators "
            "ship."
        ),
        "page_contexts": ["pulse", "home", "ops_board"],
        "default_size": "1x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1", "2x2"],
        "category": "operations",
        "icon": "Activity",
        "default_enabled": True,
        "default_position": 9,
        "required_vertical": ["manufacturing"],
        "required_product_line": ["*"],
        "supported_surfaces": [
            "pulse_grid",
            "dashboard_grid",
            "focus_canvas",
        ],
        "default_surfaces": ["pulse_grid", "dashboard_grid"],
        "intelligence_keywords": [
            "line",
            "status",
            "health",
            "operations",
            "production",
            "capacity",
        ],
        "variants": [
            {
                "variant_id": "brief",
                "density": "focused",
                "grid_size": {"cols": 1, "rows": 1},
                "canvas_size": {
                    "width": 320,
                    "height": "auto",
                    "maxHeight": 280,
                },
                "supported_surfaces": [
                    "pulse_grid",
                    "dashboard_grid",
                    "focus_canvas",
                ],
            },
            {
                "variant_id": "detail",
                "density": "rich",
                "grid_size": {"cols": 2, "rows": 2},
                "canvas_size": {
                    "width": 480,
                    "height": "auto",
                    "maxHeight": 600,
                },
                "supported_surfaces": [
                    "pulse_grid",
                    "dashboard_grid",
                    "focus_canvas",
                ],
            },
        ],
        "default_variant_id": "brief",
    },
    {
        "widget_id": "urn_catalog_status",
        "title": "Urn Catalog Status",
        "description": (
            "Urn catalog health — Phase W-3d extension-gated widget. "
            "**First widget in the catalog exercising the "
            "`required_extension` axis end-to-end** — visible only "
            "to tenants with the `urn_sales` extension activated. "
            "Surfaces total active SKUs, stocked vs drop-ship "
            "split, low-stock count + identification, recent order "
            "volume. Glance + Brief variants per §12.10 — operator "
            "wants 'how is my catalog' in one glance, not deep "
            "navigation. Click-through to /urns/catalog for full "
            "catalog management. View-only per §12.6a — adjusting "
            "stock levels, reorder points, SKU activation happens "
            "on the catalog page."
        ),
        "page_contexts": ["pulse", "home", "ops_board"],
        "default_size": "1x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x1"],
        "category": "operations",
        "icon": "Package",
        "default_enabled": True,
        "default_position": 10,
        "required_vertical": ["manufacturing"],
        # Product line + extension gating: must have urn_sales line
        # AND extension activated.
        "required_product_line": ["urn_sales"],
        "required_extension": "urn_sales",
        "supported_surfaces": [
            "pulse_grid",
            "spaces_pin",
            "dashboard_grid",
            "focus_canvas",
        ],
        "default_surfaces": ["pulse_grid", "dashboard_grid"],
        "intelligence_keywords": [
            "urn",
            "catalog",
            "sku",
            "inventory",
            "stock",
        ],
        "variants": [
            {
                "variant_id": "glance",
                "density": "minimal",
                "grid_size": {"cols": 1, "rows": 1},
                "canvas_size": {"width": 240, "height": 60},
                "supported_surfaces": ["spaces_pin", "pulse_grid"],
            },
            {
                "variant_id": "brief",
                "density": "focused",
                "grid_size": {"cols": 1, "rows": 1},
                "canvas_size": {
                    "width": 320,
                    "height": "auto",
                    "maxHeight": 320,
                },
                "supported_surfaces": [
                    "pulse_grid",
                    "dashboard_grid",
                    "focus_canvas",
                ],
            },
        ],
        "default_variant_id": "brief",
    },
    # ── Canvas widgets (Widget Library Phase W-1) ─────────────
    # Per Decision 1 unified contract, canvas widgets enter the
    # backend catalog with the same WidgetDefinition shape as
    # dashboard widgets. Section 12.5 composition rules: canvas
    # widgets render on focus_canvas / focus_stack / pulse_grid /
    # spaces_pin via the variants[].supported_surfaces declaration.
    # MockSavedViewWidget stays frontend-only as a placeholder
    # fallback (not catalog-citizen).
    {
        "widget_id": "scheduling.ancillary-pool",
        "title": "Ancillary Pool",
        "description": (
            "Pool of date-less, unassigned ancillary deliveries waiting "
            "to be paired with a primary vault delivery. Drag from pool "
            "to driver lane (standalone) or onto a parent delivery card "
            "(attached). Reference implementation for Section 12 "
            "Pattern 1 tablet treatment. Tracks vault-line-related "
            "ancillaries (urns, cremation trays) riding along with "
            "vault deliveries — hence vault product line scoping."
        ),
        "page_contexts": ["funeral_scheduling_focus", "pulse"],
        "default_size": "1x1",
        "min_size": "1x1",
        "supported_sizes": ["1x1", "2x2"],
        "category": "operations",
        "icon": "Inbox",
        "default_enabled": True,
        "default_position": 1,
        "required_permission": "delivery.view",
        # Phase W-3a tagging correction (April 2026, post Product Line +
        # Operating Mode canon): scheduling Focus is Sunnycrest
        # manufacturing operations (outbound vault deliveries to FH
        # customers); ancillary pool tracks vault-line ancillaries.
        # Pre-canon was tagged ["funeral_home"] — that was the bug the
        # canon investigation surfaced. Correct tagging per 5-axis
        # filter: manufacturing vertical + vault product line.
        "required_vertical": ["manufacturing"],
        "required_product_line": ["vault"],
        "supported_surfaces": [
            "focus_canvas",
            "focus_stack",
            "pulse_grid",
            "spaces_pin",
            "dashboard_grid",
        ],
        "default_surfaces": ["focus_canvas"],
        "intelligence_keywords": [
            "ancillary",
            "pool",
            "pairing",
            "scheduling",
            "delivery",
        ],
        # Per Section 12.10 reference implementation: Glance + Brief +
        # Detail variants. Glance for sidebar (count chip);
        # Brief for compact list (top 5 items); Detail for full
        # scrollable list with drag-source affordance in Focus.
        "variants": [
            {
                "variant_id": "glance",
                "density": "minimal",
                "grid_size": {"cols": 1, "rows": 1},
                "canvas_size": {"width": 180, "height": 60},
                "supported_surfaces": ["spaces_pin", "pulse_grid"],
            },
            {
                "variant_id": "brief",
                "density": "focused",
                "grid_size": {"cols": 1, "rows": 1},
                "canvas_size": {
                    "width": 180,
                    "height": "auto",
                    "maxHeight": 280,
                },
                "supported_surfaces": [
                    "pulse_grid",
                    "focus_stack",
                    "dashboard_grid",
                ],
            },
            {
                "variant_id": "detail",
                "density": "rich",
                "grid_size": {"cols": 2, "rows": 2},
                "canvas_size": {
                    "width": 180,
                    "height": "auto",
                    "maxHeight": 480,
                },
                "supported_surfaces": [
                    "focus_canvas",
                    "pulse_grid",
                    "dashboard_grid",
                ],
            },
        ],
        "default_variant_id": "detail",
    },
]


def _brief_variant_for_size(default_size: str) -> dict:
    """Build a single 'brief' variant matching a legacy `default_size`.

    Used by `seed_widget_definitions` to backfill variants on widgets
    that don't declare them explicitly. Phase W-3 widget builds add
    additional variants (Glance / Detail / Deep) per Section 12.10.
    """
    try:
        cols, rows = (int(x) for x in (default_size or "1x1").split("x"))
    except (AttributeError, ValueError):
        cols, rows = 1, 1

    canvas_width = 280 * cols
    canvas_height = 200 * rows
    return {
        "variant_id": "brief",
        "density": "focused",
        "grid_size": {"cols": cols, "rows": rows},
        "canvas_size": {
            "width": canvas_width,
            "height": canvas_height,
            "maxHeight": canvas_height + 200,
        },
        "supported_surfaces": ["dashboard_grid"],
    }


def seed_widget_definitions(db: Session) -> int:
    """Insert or update widget definitions.

    Behavior:
      - Rows with a new `widget_id` are inserted.
      - Existing rows are UPDATED on the **system-owned** columns:
        title, description, page_contexts, default_size, supported_sizes,
        min_size, max_size, category, icon, default_enabled,
        default_position, required_extension, required_permission,
        required_preset, variants, default_variant_id, required_vertical,
        supported_surfaces, default_surfaces, intelligence_keywords.

      Per-user layouts live in `user_widget_layouts` and are untouched;
      only the definition metadata is refreshed. This lets V-1c+ extend
      an existing widget's `page_contexts` (e.g. making
      `at_risk_accounts` also appear in `vault_overview`) just by
      shipping new code — no migration required.

    Per Widget Library Phase W-1 + W-3a (Section 12), every widget
    must declare `variants` + `default_variant_id` + `required_vertical`
    + `required_product_line` + `supported_surfaces` + `default_surfaces`
    + `intelligence_keywords`. Widgets that don't declare them get
    sensible defaults backfilled:
      • variants → single 'brief' variant matching legacy default_size
      • default_variant_id → 'brief'
      • required_vertical → ["*"] (cross-vertical, per Decision 9)
      • required_product_line → ["*"] (cross-line, Phase W-3a default —
        most platform-foundation widgets are line-agnostic; per-line
        widgets like vault_schedule explicitly declare ["vault"])
      • supported_surfaces → ["dashboard_grid"] (current rendering target)
      • default_surfaces → same as supported_surfaces
      • intelligence_keywords → []

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

        # Phase W-1 + W-3a unified contract defaults (Section 12).
        row.setdefault("variants", [_brief_variant_for_size(row.get("default_size", "1x1"))])
        row.setdefault("default_variant_id", "brief")
        row.setdefault("required_vertical", ["*"])
        # Phase W-3a — 5th axis default. Cross-line is the canonical
        # default per §12.4 Decision 9 carry-through.
        row.setdefault("required_product_line", ["*"])
        row.setdefault("supported_surfaces", ["dashboard_grid"])
        row.setdefault("default_surfaces", row["supported_surfaces"])
        row.setdefault("intelligence_keywords", [])

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
            # Phase W-1 + W-3a unified contract.
            "variants": row["variants"],
            "default_variant_id": row["default_variant_id"],
            "required_vertical": row["required_vertical"],
            "required_product_line": row["required_product_line"],
            "supported_surfaces": row["supported_surfaces"],
            "default_surfaces": row["default_surfaces"],
            "intelligence_keywords": row["intelligence_keywords"],
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
