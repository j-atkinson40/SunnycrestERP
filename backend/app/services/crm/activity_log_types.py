"""Activity log type registry (R-8.2).

Single source of truth for canonical CRM ActivityLog `activity_type`
values. Mirrors the frontend's de-facto vocabulary at
`frontend/src/components/widgets/foundation/RecentActivityWidget.tsx`
(`activityVerb` map). Backend was previously permissive — any string
flowed to the DB — which created drift risk against the frontend's
hardcoded verb mapping (R-8 audit Section 2 item 5).

Scope: this registry governs `app.models.activity_log.ActivityLog`
ONLY. The separate `FHCaseActivity` table (case timeline) has its own
vocabulary and is intentionally out of scope.

Frontend-backend symmetry contract: every key in `ACTIVITY_TYPES` MUST
have a corresponding entry in the frontend `activityVerb` map. Future
additions register on both sides. Lint-or-test enforcement of the
symmetry is deferred unless drift surfaces.

Pattern: closed vocabulary as a frozen module constant. Activity types
are NOT plugin extensions; they're a fixed catalog. New types added by
editing this file + the frontend map in lockstep.
"""

from __future__ import annotations

# Canonical activity type vocabulary.
# Keys MUST stay in sync with frontend RecentActivityWidget.activityVerb.
ACTIVITY_TYPE_REGISTRY: dict[str, dict[str, str]] = {
    "note": {
        "display_label": "added a note",
        "description": "Manual note logged against a company entity.",
    },
    "call": {
        "display_label": "logged a call",
        "description": "Manual phone-call activity entry.",
    },
    "email": {
        "display_label": "logged an email",
        "description": "System event from Email primitive — inbound/outbound message logged against a CRM company.",
    },
    "calendar": {
        "display_label": "updated a calendar event",
        "description": "System event from Calendar primitive — event scheduled/modified/cancelled/responded.",
    },
    "meeting": {
        "display_label": "logged a meeting",
        "description": "Manual meeting activity entry.",
    },
    "document": {
        "display_label": "uploaded a document",
        "description": "System event — a document was uploaded against the CRM company.",
    },
    "follow_up": {
        "display_label": "scheduled a follow-up",
        "description": "Manual follow-up entry with optional due date and assignee.",
    },
    "status_change": {
        "display_label": "changed status",
        "description": "System event — entity status transition.",
    },
    "delivery": {
        "display_label": "updated a delivery",
        "description": "System event — delivery state change against the CRM company.",
    },
    "invoice": {
        "display_label": "updated an invoice",
        "description": "System event from invoicing — draft, send, payment recorded against the CRM company.",
    },
    "order": {
        "display_label": "updated an order",
        "description": "System event — sales order state change against the CRM company.",
    },
    "payment": {
        "display_label": "logged a payment",
        "description": "System event — customer payment recorded against the CRM company.",
    },
    "proof": {
        "display_label": "updated a proof",
        "description": "System event — legacy proof / engraving proof status update.",
    },
    "case": {
        "display_label": "updated a case",
        "description": "System event — FH case state change surfaced to the CRM company feed.",
    },
    # Backend-only synonym for proof events surfaced from legacy_email_service.
    # Frontend renders this via the fallback path (replaces _ with space).
    # Future cleanup: migrate legacy_email_service to use "proof" and remove
    # this entry. Until then, registered so the canonical write path validates.
    "legacy_proof": {
        "display_label": "logged a legacy proof event",
        "description": "Legacy-pipeline proof event from legacy_email_service. Synonym for 'proof' pending caller migration.",
    },
}

# Frozen set of valid activity_type keys.
ACTIVITY_TYPES: frozenset[str] = frozenset(ACTIVITY_TYPE_REGISTRY.keys())


class UnknownActivityTypeError(ValueError):
    """Raised when an activity_type is not registered in ACTIVITY_TYPES.

    Inherits from ValueError so existing exception handlers continue
    to work; carries a typed class name for callers that want to
    distinguish registry-validation errors from other ValueErrors.
    """


def validate_activity_type(activity_type: str) -> bool:
    """Return True if activity_type is registered, False otherwise.

    Non-raising form for callers that want to branch on validity.
    """
    return activity_type in ACTIVITY_TYPES


def assert_valid_activity_type(activity_type: str) -> None:
    """Raise UnknownActivityTypeError if activity_type is not registered.

    Canonical write-side validation entry point. Called by
    `log_system_event` and `log_manual_activity` to enforce vocabulary
    discipline at the boundary.
    """
    if activity_type not in ACTIVITY_TYPES:
        raise UnknownActivityTypeError(
            f"Unknown activity_type '{activity_type}'. "
            f"Valid types: {sorted(ACTIVITY_TYPES)}. "
            f"Register new types in app.services.crm.activity_log_types."
        )
