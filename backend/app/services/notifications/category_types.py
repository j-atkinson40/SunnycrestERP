"""Notification category registry (R-8.1).

Single source of truth for canonical Notification `category` values.
Backend was previously permissive — any string flowed to the DB —
which created drift risk across the ~18 categories spread across
callers (V-1d notification sources, calendar consent state machine,
personalization studio consent flow, employee/pricing/inventory
domain notifications). R-8 audit Section 2 item 4 flagged this;
R-6.1 independently flagged "category vocabulary central-registry"
as DEBT.

Scope: this registry governs `app.models.notification.Notification`
ONLY. The separate `Notification.type` column (info/success/warning
/error tone) is a closed enum at the model layer and out of scope.

Closed-vocabulary discipline: notification categories are a
platform-owned catalog. Tenants don't add categories. If signal
emerges later that tenants need custom categories, the frozen-
constant pattern can evolve to extensible — YAGNI now.

Pattern: closed vocabulary as a frozen module constant. Categories
are NOT plugin extensions; they're a fixed catalog. New categories
added by editing this file. Frontend (`notification-dropdown.tsx`,
`NotificationsWidget.tsx`, `notifications.tsx`) dispatches on
`type` not `category`, so no frontend-backend symmetry test is
required at September scope. If a future surface adds category-
driven dispatch, mirror the R-8.2 frontend-backend symmetry test
pattern at that time.

R-8.x sequence: 4 of 4 sub-arcs complete (R-8.4 + R-8.3 + R-8.2 +
R-8.1). See R-8 audit `/tmp/r8_configuration_over_plugins_audit.md`
Section 2 item 4 for the original phrasing.
"""

from __future__ import annotations

# Canonical notification category vocabulary.
# Each entry carries description (operator-facing purpose),
# default_icon (Lucide name — informational; frontend dispatches on
# `type` today, but icon metadata reserves the seam for a future
# category-aware icon mapper), and default_color_token (DESIGN_LANGUAGE
# token name — same reservation).
NOTIFICATION_CATEGORY_REGISTRY: dict[str, dict[str, str]] = {
    # ── Domain-level categories (employee + business operations) ──
    "employee": {
        "description": "Employee profile / HR-related notification (profile updated by admin, role change, etc.).",
        "default_icon": "User",
        "default_color_token": "status-info",
    },
    "user": {
        "description": "User-account-scoped notification (invitation accepted, account settings changed).",
        "default_icon": "UserCircle",
        "default_color_token": "status-info",
    },
    "pricing": {
        "description": "Price list / pricing notification (price increase scheduled, list activated).",
        "default_icon": "DollarSign",
        "default_color_token": "status-info",
    },
    "inventory": {
        "description": "Inventory event notification (low stock, reorder threshold, count adjustment).",
        "default_icon": "Package",
        "default_color_token": "status-warning",
    },
    # ── V-1d Phase notification sources ──
    "share_granted": {
        "description": "Cross-tenant Document share granted to this tenant (D-6 fabric).",
        "default_icon": "Share2",
        "default_color_token": "status-info",
    },
    "delivery_failed": {
        "description": "Outbound delivery (email/SMS) failed after retry exhaustion (D-7).",
        "default_icon": "AlertTriangle",
        "default_color_token": "status-error",
    },
    "signature_requested": {
        "description": "Native e-signature envelope requires this user's signature (D-4).",
        "default_icon": "Signature",
        "default_color_token": "status-info",
    },
    "compliance_expiry": {
        "description": "Compliance item expiring soon (equipment inspection, training cert, regulatory deadline).",
        "default_icon": "ShieldAlert",
        "default_color_token": "status-warning",
    },
    "account_at_risk": {
        "description": "Customer account transitioned into at-risk health score (CRM intelligence).",
        "default_icon": "TrendingDown",
        "default_color_token": "status-warning",
    },
    "safety_alert": {
        "description": "Safety-related alert (merged from former SafetyAlert model in V-1d). Read-only legacy category — surfaced by safety_service but no longer written by new code paths.",
        "default_icon": "HardHat",
        "default_color_token": "status-warning",
    },
    # ── Calendar primitive consent + response notifications (Phase W-4b Calendar Step 4.1 + 5) ──
    "calendar_consent_upgrade_request": {
        "description": "Partner tenant requested a calendar free/busy consent upgrade (PTR consent state machine).",
        "default_icon": "CalendarCheck",
        "default_color_token": "status-info",
    },
    "calendar_consent_upgrade_accepted": {
        "description": "Partner tenant accepted a calendar consent upgrade request — bilateral full-details now active.",
        "default_icon": "CalendarCheck",
        "default_color_token": "status-success",
    },
    "calendar_consent_upgrade_revoked": {
        "description": "Partner tenant revoked a calendar consent upgrade — bilateral consent dropped back to free/busy-only.",
        "default_icon": "CalendarX",
        "default_color_token": "status-warning",
    },
    "calendar_attendee_responded": {
        "description": "Event organizer notified that an attendee responded to a calendar invite (iTIP REPLY).",
        "default_icon": "Calendar",
        "default_color_token": "status-info",
    },
    # ── Personalization Studio consent + workflow notifications ──
    "personalization_studio_consent_upgrade_request": {
        "description": "Family / FH requested Personalization Studio consent upgrade.",
        "default_icon": "ImagePlus",
        "default_color_token": "status-info",
    },
    "personalization_studio_consent_upgrade_accepted": {
        "description": "Personalization Studio consent upgrade accepted by partner.",
        "default_icon": "ImagePlus",
        "default_color_token": "status-success",
    },
    "personalization_studio_consent_revoked": {
        "description": "Personalization Studio consent revoked by either side.",
        "default_icon": "ImageOff",
        "default_color_token": "status-warning",
    },
    "personalization_studio_mfg_reviewed": {
        "description": "Manufacturer reviewed a Personalization Studio submission (canvas state committed for production).",
        "default_icon": "BadgeCheck",
        "default_color_token": "status-success",
    },
    "personalization_studio_share_failed": {
        "description": "Cross-tenant Personalization Studio DocumentShare failed to register (best-effort path).",
        "default_icon": "AlertTriangle",
        "default_color_token": "status-error",
    },
}

# Frozen set of valid notification category keys.
NOTIFICATION_CATEGORIES: frozenset[str] = frozenset(
    NOTIFICATION_CATEGORY_REGISTRY.keys()
)


class UnknownNotificationCategoryError(ValueError):
    """Raised when a notification category is not registered.

    Inherits from ValueError so existing exception handlers continue
    to work; carries a typed class name for callers that want to
    distinguish registry-validation errors from other ValueErrors.
    """


def validate_notification_category(category: str | None) -> bool:
    """Return True if category is registered, False otherwise.

    Non-raising form for callers that want to branch on validity.
    `None` is accepted as valid (categories are nullable per the
    Notification model — many notifications have no category) and
    returns True. Empty string returns False.
    """
    if category is None:
        return True
    return category in NOTIFICATION_CATEGORIES


def assert_valid_notification_category(category: str | None) -> None:
    """Raise UnknownNotificationCategoryError if category is not registered.

    Canonical write-side validation entry point. Called by
    `create_notification` and `notify_tenant_admins` to enforce
    vocabulary discipline at the boundary.

    `None` is permitted — many notifications carry no category.
    Empty-string + any other unknown string raises.
    """
    if category is None:
        return
    if category not in NOTIFICATION_CATEGORIES:
        raise UnknownNotificationCategoryError(
            f"Unknown notification category '{category}'. "
            f"Valid categories: {sorted(NOTIFICATION_CATEGORIES)}. "
            f"Register new categories in app.services.notifications.category_types."
        )
