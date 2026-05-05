"""PTR consent state machines — Phase W-4b Layer 1 Step 4.1 (Calendar) +
Personalization Studio implementation arc Step 1 Step 0 Migration r75
(Personalization Studio Cross-Tenant Sharing).

**Module canonical scope post-r75 (Q4 column-per-capability discipline)**:
this module hosts the canonical PTR consent state machine across multiple
capabilities. Calendar Step 4.1 was the canonical-pattern-establisher;
Personalization Studio (Step 1 Step 0 Migration r75) is the second
canonical instance. Each capability gets:

- One canonical column on ``platform_tenant_relationships`` row
  (e.g. ``calendar_freebusy_consent`` for Calendar; ``personalization_studio_cross_tenant_sharing_consent``
  for Personalization Studio).
- Parallel public API: ``request_*``, ``accept_*``, ``revoke_*``,
  ``list_partner_*_consent_states``.
- Capability-specific audit destination + notification categories.
- Shared helper infrastructure (``_get_relationship``,
  ``_resolve_pair_for_caller``, ``_notify_partner_admins``,
  ``resolve_consent_state``).

Per Q4 canonical resolution: column-per-capability storage shape preserves
canonical-quality discipline at substrate boundary; the alternative
(single polymorphic ``capability_consents`` JSONB column) was canonically
rejected. Module historically lives in ``app/services/calendar/`` because
Calendar Step 4.1 was the canonical-pattern-establisher; future capabilities
add their parallel APIs here rather than fragmenting the shared helper
infrastructure.

Per §3.26.16.6 + §3.26.16.14 + §3.26.11.10 cross-tenant Focus consent
canonical precedent: bilateral consent state machine for
``platform_tenant_relationships.calendar_freebusy_consent`` writes
(read-side enforcement shipped at Step 3 in
``freebusy_service.query_cross_tenant_freebusy``).

**Storage shape canonical (Q1 confirmed pre-build)**: existing
single-column-per-PTR-row schema is canonically complete. PTR's
existing per-direction-row architecture (one row for tenant_a→tenant_b,
one row for tenant_b→tenant_a) already encodes per-side intent. Each
row's ``calendar_freebusy_consent`` value reflects that side's stated
consent. Step 4.1 ships the service-layer state machine + audit trail
+ in-app notifications + settings page UI; **zero schema rework of the
consent column itself**.

**Three-state machine** (resolved from `(forward.consent, reverse.consent)` tuple):
  - ``default``: both sides ``free_busy_only`` → privacy-preserving baseline
  - ``pending_outbound``: this side ``full_details``, partner side ``free_busy_only``
    → "I requested upgrade; awaiting partner"
  - ``pending_inbound``: this side ``free_busy_only``, partner side ``full_details``
    → "Partner requested upgrade from me"
  - ``active``: both sides ``full_details`` → bilateral consent in force; full
    detail unlocked per §3.26.16.6 anonymization granularity canonical

**Either-side revocation** (per §3.26.16.6 + §3.26.11.10): "either tenant can
unilaterally revoke" — flipping back to ``free_busy_only`` from any non-default
state immediately drops bilateral consent regardless of partner's value.

**Per-side audit logs** (per §3.26.11.10): canonical pattern matches Calendar
Step 4 ``cross_tenant_pairing_service`` precedent — joint state transitions
write to BOTH tenants' ``calendar_audit_log`` scopes; tenant-side-only events
(e.g. cancellation of pending-outbound by initiator) write only to that side.

**In-app notifications via ``notify_tenant_admins`` V-1d substrate** (per Q4
confirmed pre-build): three categories — ``calendar_consent_upgrade_request``
(notify partner admins on outbound request) + ``calendar_consent_upgrade_accepted``
(notify requester admins on bilateral activation) + ``calendar_consent_upgrade_revoked``
(notify partner admins on revoke). Email-mediated requests + cross-tenant Pulse
widget deferred to Step 5.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models.platform_tenant_relationship import PlatformTenantRelationship
from app.services import notification_service
from app.services.calendar.account_service import (
    CalendarAccountError,
    CalendarAccountNotFound,
    CalendarAccountPermissionDenied,
    _audit,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────


class PtrConsentError(CalendarAccountError):
    http_status = 400


class PtrConsentNotFound(CalendarAccountError):
    http_status = 404


class PtrConsentPermissionDenied(CalendarAccountError):
    http_status = 403


class PtrConsentInvalidTransition(CalendarAccountError):
    http_status = 409


# ─────────────────────────────────────────────────────────────────────
# Canonical vocabulary
# ─────────────────────────────────────────────────────────────────────


# Three-state machine values per §3.26.16.6 + §3.26.16.14 + §3.26.11.10.
ConsentState = Literal[
    "default",
    "pending_outbound",
    "pending_inbound",
    "active",
]


CONSENT_STATES: tuple[ConsentState, ...] = (
    "default",
    "pending_outbound",
    "pending_inbound",
    "active",
)


CONSENT_VALUES = ("free_busy_only", "full_details")


# ─────────────────────────────────────────────────────────────────────
# State resolver
# ─────────────────────────────────────────────────────────────────────


def resolve_consent_state(
    forward_row: PlatformTenantRelationship | None,
    reverse_row: PlatformTenantRelationship | None,
) -> ConsentState:
    """Resolve the bilateral consent state from a (forward, reverse) PTR row pair.

    Args:
        forward_row: PTR row from the perspective of "this tenant" —
            this side's consent encoded in ``forward_row.calendar_freebusy_consent``.
        reverse_row: PTR row from the perspective of the partner tenant —
            partner side's consent encoded in
            ``reverse_row.calendar_freebusy_consent``.

    Returns one of ``default`` | ``pending_outbound`` | ``pending_inbound``
    | ``active``.

    Treats missing rows as ``free_busy_only`` (privacy default per
    §3.26.16.6) — consistent with Q2 latent-bug-fix discipline at the
    read-side.
    """
    this_consent = (
        forward_row.calendar_freebusy_consent if forward_row else "free_busy_only"
    )
    partner_consent = (
        reverse_row.calendar_freebusy_consent if reverse_row else "free_busy_only"
    )

    if this_consent == "full_details" and partner_consent == "full_details":
        return "active"
    if this_consent == "full_details" and partner_consent == "free_busy_only":
        return "pending_outbound"
    if this_consent == "free_busy_only" and partner_consent == "full_details":
        return "pending_inbound"
    return "default"


# ─────────────────────────────────────────────────────────────────────
# Lookup helpers
# ─────────────────────────────────────────────────────────────────────


def _get_relationship(
    db: Session, *, relationship_id: str
) -> PlatformTenantRelationship:
    rel = (
        db.query(PlatformTenantRelationship)
        .filter(PlatformTenantRelationship.id == relationship_id)
        .first()
    )
    if rel is None:
        raise PtrConsentNotFound(
            f"PlatformTenantRelationship {relationship_id!r} not found."
        )
    return rel


def _resolve_pair_for_caller(
    db: Session,
    *,
    relationship_id: str,
    caller_tenant_id: str,
) -> tuple[
    PlatformTenantRelationship,
    PlatformTenantRelationship | None,
]:
    """Resolve (forward, reverse) PTR row pair from the caller's perspective.

    The caller-supplied ``relationship_id`` MUST be the row owned by
    ``caller_tenant_id`` (i.e. caller's `tenant_id == relationship.tenant_id`).
    Cross-tenant existence-hiding 404 if the row is owned by a different
    tenant or doesn't exist.

    Returns:
        (forward_row, reverse_row | None)

        forward_row: caller's perspective row (always present).
        reverse_row: partner-side row if it exists; None when the
            partner tenant has no PTR row in this relationship_type.

    Raises:
        PtrConsentNotFound: relationship not found or not owned by caller.
    """
    forward_row = _get_relationship(db, relationship_id=relationship_id)

    if forward_row.tenant_id != caller_tenant_id:
        # Existence-hiding 404 — caller's tenant doesn't own this row.
        raise PtrConsentNotFound(
            f"PlatformTenantRelationship {relationship_id!r} not found."
        )

    # Find the reverse-direction row (partner_tenant_id → caller_tenant_id)
    # for the same relationship_type.
    reverse_row = (
        db.query(PlatformTenantRelationship)
        .filter(
            PlatformTenantRelationship.tenant_id == forward_row.supplier_tenant_id,
            PlatformTenantRelationship.supplier_tenant_id == caller_tenant_id,
            PlatformTenantRelationship.relationship_type
            == forward_row.relationship_type,
        )
        .first()
    )

    return forward_row, reverse_row


# ─────────────────────────────────────────────────────────────────────
# State machine: request_upgrade / accept_upgrade / revoke_upgrade
# ─────────────────────────────────────────────────────────────────────


def request_upgrade(
    db: Session,
    *,
    requesting_tenant_id: str,
    relationship_id: str,
    requested_by_user_id: str,
    send_email: bool = False,
) -> dict[str, Any]:
    """Flip the requesting tenant's PTR row to ``full_details``.

    Per §3.26.11.10 + §3.26.16.6: initiator opts in; target tenant
    receives consent request via Communications-layer notification
    (V-1d notify_tenant_admins at Step 4.1; email-mediated requests
    via Email primitive Step 4c outbound substrate at Step 5.1, opt-in
    per ``send_email`` kwarg per Q1 confirmed pre-build).

    The ``send_email`` kwarg is opt-in (default ``False``) per Step 5.1
    Q1 confirmation. When True, dispatches a per-recipient email per
    partner tenant admin via ``delivery_service.send_email_with_template``
    using the managed ``email.calendar_consent_upgrade_request``
    template. In-app notify continues unconditionally regardless of
    ``send_email`` per Step 4.1 contract (Communications-Layer in-app
    surface is canonical; email is opt-in escalation).

    Email send failures NEVER block consent state mutation OR in-app
    notify per best-effort discipline. Per-recipient ``DocumentDelivery``
    rows preserve per-admin audit + bounce attribution per Q2 confirmed.

    Valid prior states (caller's perspective):
      - ``default`` → ``pending_outbound`` (canonical request flow)
      - ``pending_inbound`` → ``active`` (caller flips to full_details
        while partner already at full_details — equivalent to accept
        from the receiving side; canon allows but route layer prefers
        accept_upgrade for this case)

    Raises:
        PtrConsentInvalidTransition (409): caller's row already at
            full_details (already requested or already active).
        PtrConsentNotFound (404): relationship not found or not owned
            by caller.
    """
    forward_row, reverse_row = _resolve_pair_for_caller(
        db,
        relationship_id=relationship_id,
        caller_tenant_id=requesting_tenant_id,
    )
    prior_state = resolve_consent_state(forward_row, reverse_row)

    if forward_row.calendar_freebusy_consent == "full_details":
        raise PtrConsentInvalidTransition(
            f"Caller's PTR row already at full_details (state="
            f"{prior_state!r}); use accept_upgrade or revoke_upgrade."
        )

    forward_row.calendar_freebusy_consent = "full_details"
    forward_row.calendar_freebusy_consent_updated_at = datetime.now(timezone.utc)
    forward_row.calendar_freebusy_consent_updated_by = requested_by_user_id
    db.flush()

    new_state = resolve_consent_state(forward_row, reverse_row)
    partner_tenant_id = forward_row.supplier_tenant_id

    # Per-side audit log: caller side only at request time per §3.26.11.10
    # ("Tenant-side-only events appear only in the originating side's log").
    _audit(
        db,
        tenant_id=requesting_tenant_id,
        actor_user_id=requested_by_user_id,
        action="consent_upgrade_requested",
        entity_type="platform_tenant_relationship",
        entity_id=forward_row.id,
        changes={
            "relationship_id": forward_row.id,
            "partner_tenant_id": partner_tenant_id,
            "requesting_tenant_id": requesting_tenant_id,
            "prior_state": prior_state,
            "new_state": new_state,
        },
    )
    db.flush()

    # In-app notification to partner tenant admins per Q4 confirmed.
    _notify_partner_admins(
        db,
        partner_tenant_id=partner_tenant_id,
        category="calendar_consent_upgrade_request",
        title="Calendar consent upgrade request",
        message=(
            "A connected tenant has requested calendar full-details "
            "consent. Review pending requests in calendar consent "
            "settings."
        ),
        type="info",
        link="/settings/calendar/freebusy-consent",
        relationship_id=forward_row.id,
        actor_user_id=requested_by_user_id,
    )

    # Step 5.1 email-mediated extension per Q1 (opt-in default off).
    # Best-effort: failure NEVER blocks consent state mutation OR in-app
    # notify per Step 4.1 contract. Per-recipient DocumentDelivery rows
    # preserve per-admin audit per Q2.
    if send_email:
        _email_partner_admins_for_consent_request(
            db,
            requesting_tenant_id=requesting_tenant_id,
            partner_tenant_id=partner_tenant_id,
            relationship_id=forward_row.id,
            relationship_type=forward_row.relationship_type,
        )

    return {
        "relationship_id": forward_row.id,
        "partner_tenant_id": partner_tenant_id,
        "prior_state": prior_state,
        "new_state": new_state,
    }


def accept_upgrade(
    db: Session,
    *,
    accepting_tenant_id: str,
    relationship_id: str,
    accepted_by_user_id: str,
) -> dict[str, Any]:
    """Flip the accepting tenant's PTR row to ``full_details``; activate bilateral.

    Per §3.26.11.10 canonical pattern: target tenant accepts → bilateral
    consent active. State transition typically: ``pending_inbound`` →
    ``active``.

    Per-side audit logs per §3.26.11.10: when bilateral state activates,
    write to BOTH tenants' calendar_audit_log scopes (joint event).

    Raises:
        PtrConsentInvalidTransition (409): caller's row already at
            full_details OR partner side hasn't requested upgrade
            (would result in ``pending_outbound`` rather than ``active``
            — canon directs caller to ``request_upgrade`` for that).
        PtrConsentNotFound (404): relationship not found or not owned
            by caller.
    """
    forward_row, reverse_row = _resolve_pair_for_caller(
        db,
        relationship_id=relationship_id,
        caller_tenant_id=accepting_tenant_id,
    )
    prior_state = resolve_consent_state(forward_row, reverse_row)

    if forward_row.calendar_freebusy_consent == "full_details":
        raise PtrConsentInvalidTransition(
            "Caller's PTR row already at full_details; nothing to accept."
        )

    if reverse_row is None or (
        reverse_row.calendar_freebusy_consent != "full_details"
    ):
        # Partner hasn't requested upgrade — caller should use
        # request_upgrade (transitions to pending_outbound) instead.
        raise PtrConsentInvalidTransition(
            "Partner has not requested upgrade. Use request_upgrade "
            "to initiate the bilateral flow from this side."
        )

    forward_row.calendar_freebusy_consent = "full_details"
    forward_row.calendar_freebusy_consent_updated_at = datetime.now(timezone.utc)
    forward_row.calendar_freebusy_consent_updated_by = accepted_by_user_id
    db.flush()

    new_state = resolve_consent_state(forward_row, reverse_row)
    partner_tenant_id = forward_row.supplier_tenant_id

    audit_changes = {
        "relationship_id": forward_row.id,
        "partner_tenant_id": partner_tenant_id,
        "requesting_tenant_id": partner_tenant_id,  # partner was the requester
        "prior_state": prior_state,
        "new_state": new_state,
    }

    # Per-side audit logs per §3.26.11.10 (joint event = both sides).
    _audit(
        db,
        tenant_id=accepting_tenant_id,
        actor_user_id=accepted_by_user_id,
        action="consent_upgrade_accepted",
        entity_type="platform_tenant_relationship",
        entity_id=forward_row.id,
        changes=audit_changes,
    )
    _audit(
        db,
        tenant_id=partner_tenant_id,
        actor_user_id=accepted_by_user_id,
        action="consent_upgrade_accepted",
        entity_type="platform_tenant_relationship",
        entity_id=reverse_row.id if reverse_row else forward_row.id,
        changes=audit_changes,
    )
    db.flush()

    # Notify the requesting (partner) tenant's admins.
    _notify_partner_admins(
        db,
        partner_tenant_id=partner_tenant_id,
        category="calendar_consent_upgrade_accepted",
        title="Calendar consent upgrade accepted",
        message=(
            "A connected tenant accepted your calendar consent upgrade "
            "request. Bilateral full-details consent is now active."
        ),
        type="success",
        link="/settings/calendar/freebusy-consent",
        relationship_id=forward_row.id,
        actor_user_id=accepted_by_user_id,
    )

    return {
        "relationship_id": forward_row.id,
        "partner_tenant_id": partner_tenant_id,
        "prior_state": prior_state,
        "new_state": new_state,
    }


def revoke_upgrade(
    db: Session,
    *,
    revoking_tenant_id: str,
    relationship_id: str,
    revoked_by_user_id: str,
) -> dict[str, Any]:
    """Flip the revoking tenant's PTR row back to ``free_busy_only``.

    Per §3.26.16.6 + §3.26.11.10: "either tenant can unilaterally
    revoke". Valid from any non-default state on the caller's side
    (caller's row currently at ``full_details``).

    Per-side audit logs (joint event): writes to BOTH tenants' scopes
    when bilateral state was previously ``active`` (or ``pending_outbound``
    where partner had no consent yet but the caller is cancelling
    their own request — still a joint event for audit transparency).

    Raises:
        PtrConsentInvalidTransition (409): caller's row already at
            free_busy_only (nothing to revoke).
        PtrConsentNotFound (404): relationship not found or not owned
            by caller.
    """
    forward_row, reverse_row = _resolve_pair_for_caller(
        db,
        relationship_id=relationship_id,
        caller_tenant_id=revoking_tenant_id,
    )
    prior_state = resolve_consent_state(forward_row, reverse_row)

    if forward_row.calendar_freebusy_consent == "free_busy_only":
        raise PtrConsentInvalidTransition(
            "Caller's PTR row already at free_busy_only; nothing to revoke."
        )

    forward_row.calendar_freebusy_consent = "free_busy_only"
    forward_row.calendar_freebusy_consent_updated_at = datetime.now(timezone.utc)
    forward_row.calendar_freebusy_consent_updated_by = revoked_by_user_id
    db.flush()

    new_state = resolve_consent_state(forward_row, reverse_row)
    partner_tenant_id = forward_row.supplier_tenant_id

    audit_changes = {
        "relationship_id": forward_row.id,
        "partner_tenant_id": partner_tenant_id,
        "revoking_tenant_id": revoking_tenant_id,
        "prior_state": prior_state,
        "new_state": new_state,
    }

    # Per-side audit logs (joint event per §3.26.11.10).
    _audit(
        db,
        tenant_id=revoking_tenant_id,
        actor_user_id=revoked_by_user_id,
        action="consent_revoked",
        entity_type="platform_tenant_relationship",
        entity_id=forward_row.id,
        changes=audit_changes,
    )
    if partner_tenant_id != revoking_tenant_id:
        _audit(
            db,
            tenant_id=partner_tenant_id,
            actor_user_id=revoked_by_user_id,
            action="consent_revoked",
            entity_type="platform_tenant_relationship",
            entity_id=reverse_row.id if reverse_row else forward_row.id,
            changes=audit_changes,
        )
    db.flush()

    # Notify partner tenant's admins (whether previously active or just
    # cancelling pending-outbound, partner deserves to know).
    _notify_partner_admins(
        db,
        partner_tenant_id=partner_tenant_id,
        category="calendar_consent_upgrade_revoked",
        title="Calendar consent upgrade revoked",
        message=(
            "A connected tenant revoked their calendar consent. "
            "Cross-tenant free/busy queries return privacy-preserving "
            "windows only."
        ),
        type="warning",
        link="/settings/calendar/freebusy-consent",
        relationship_id=forward_row.id,
        actor_user_id=revoked_by_user_id,
    )

    return {
        "relationship_id": forward_row.id,
        "partner_tenant_id": partner_tenant_id,
        "prior_state": prior_state,
        "new_state": new_state,
    }


# ─────────────────────────────────────────────────────────────────────
# List partner consent states (settings page surface)
# ─────────────────────────────────────────────────────────────────────


def list_partner_consent_states(
    db: Session, *, tenant_id: str
) -> list[dict[str, Any]]:
    """List partner tenants + per-relationship consent state.

    Returns one dict per PTR row owned by ``tenant_id``. Each dict
    carries:
      - relationship_id
      - relationship_type
      - partner_tenant_id
      - partner_tenant_name (resolved via Company lookup; best-effort)
      - this_side_consent: 'free_busy_only' | 'full_details'
      - partner_side_consent: 'free_busy_only' | 'full_details' (or None
        if reverse row doesn't exist)
      - state: ConsentState
      - updated_at: ISO datetime or None
      - updated_by_user_id: user id or None

    Filters to active relationships (status='active') + only those
    where calendar consent is operationally meaningful (any
    ``relationship_type`` — Step 4.1 doesn't gate by relationship_type;
    settings page surfaces all PTR rows for tenant transparency).
    """
    from app.models.company import Company

    forward_rows = (
        db.query(PlatformTenantRelationship)
        .filter(
            PlatformTenantRelationship.tenant_id == tenant_id,
            PlatformTenantRelationship.status == "active",
        )
        .order_by(PlatformTenantRelationship.connected_at.desc())
        .all()
    )

    results: list[dict[str, Any]] = []
    for forward in forward_rows:
        # Resolve partner-side row.
        reverse = (
            db.query(PlatformTenantRelationship)
            .filter(
                PlatformTenantRelationship.tenant_id == forward.supplier_tenant_id,
                PlatformTenantRelationship.supplier_tenant_id == tenant_id,
                PlatformTenantRelationship.relationship_type
                == forward.relationship_type,
            )
            .first()
        )

        # Resolve partner tenant name (best-effort).
        partner_company = (
            db.query(Company)
            .filter(Company.id == forward.supplier_tenant_id)
            .first()
        )

        results.append(
            {
                "relationship_id": forward.id,
                "relationship_type": forward.relationship_type,
                "partner_tenant_id": forward.supplier_tenant_id,
                "partner_tenant_name": (
                    partner_company.name if partner_company else None
                ),
                "this_side_consent": forward.calendar_freebusy_consent,
                "partner_side_consent": (
                    reverse.calendar_freebusy_consent if reverse else None
                ),
                "state": resolve_consent_state(forward, reverse),
                "updated_at": (
                    forward.calendar_freebusy_consent_updated_at.isoformat()
                    if forward.calendar_freebusy_consent_updated_at
                    else None
                ),
                "updated_by_user_id": (
                    forward.calendar_freebusy_consent_updated_by
                ),
            }
        )

    return results


# ─────────────────────────────────────────────────────────────────────
# Notification helper
# ─────────────────────────────────────────────────────────────────────


def _notify_partner_admins(
    db: Session,
    *,
    partner_tenant_id: str,
    category: str,
    title: str,
    message: str,
    type: str,
    link: str,
    relationship_id: str,
    actor_user_id: str | None,
) -> None:
    """Best-effort fan-out to partner tenant admins per V-1d substrate.

    Per Q4 confirmed pre-build: in-app notifications via
    ``notify_tenant_admins``. Wraps in try/except so a notification
    failure never blocks the consent state mutation.
    """
    try:
        notification_service.notify_tenant_admins(
            db,
            company_id=partner_tenant_id,
            title=title,
            message=message,
            type=type,
            category=category,
            link=link,
            actor_id=actor_user_id,
            source_reference_type="platform_tenant_relationship",
            source_reference_id=relationship_id,
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "ptr_consent_service: notify_tenant_admins failed for "
            "partner_tenant_id=%s category=%s relationship_id=%s",
            partner_tenant_id,
            category,
            relationship_id,
        )


# ─────────────────────────────────────────────────────────────────────
# Step 5.1 — email-mediated consent upgrade request (opt-in)
# ─────────────────────────────────────────────────────────────────────


def _email_partner_admins_for_consent_request(
    db: Session,
    *,
    requesting_tenant_id: str,
    partner_tenant_id: str,
    relationship_id: str,
    relationship_type: str,
) -> None:
    """Best-effort fan-out email to partner tenant admins.

    Phase W-4b Calendar Step 5.1 per Q1 confirmed pre-build (opt-in
    email extension; default-off via ``request_upgrade(send_email=...)``).

    Resolves partner tenant admins via the canonical V-1d cohort
    (``User.is_active=True AND Role.slug='admin'``); mirrors
    ``notify_tenant_admins`` recipient resolution exactly.

    Per-recipient ``DocumentDelivery`` rows per Q2 — separate
    ``delivery_service.send_email_with_template`` call per admin
    preserves per-admin audit + bounce attribution. NOT a BCC blast.

    Cross-primitive audit linkage per Q7: ``DocumentDelivery.metadata_json``
    JSONB carries ``relationship_id`` + ``caller_module`` for
    traceability ("what emails were sent for relationship X?" via
    metadata search). No new FK column on ``document_deliveries``.

    Best-effort discipline preservation: every send wrapped in
    try/except. Failure NEVER blocks consent state mutation OR in-app
    notify per Step 4.1 contract. Per-recipient failures are isolated
    — one admin's bounce doesn't block emails to other admins.

    ``company_id=partner_tenant_id`` per Phase D-9 mandatory threading
    (the receiving tenant — DocumentDelivery row attributes to whose
    audit log the send appears in).
    """
    # Defer model imports to avoid circular cycles between calendar
    # service + delivery service + V-1d substrate.
    from app.models import Company, Role, User
    from app.services.delivery import delivery_service

    try:
        admins = (
            db.query(User)
            .join(Role, Role.id == User.role_id)
            .filter(
                User.company_id == partner_tenant_id,
                User.is_active.is_(True),
                Role.slug == "admin",
            )
            .all()
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "ptr_consent_service: admin resolution failed for "
            "partner_tenant_id=%s relationship_id=%s",
            partner_tenant_id,
            relationship_id,
        )
        return

    if not admins:
        logger.info(
            "ptr_consent_service: no active admins for partner_tenant_id=%s "
            "relationship_id=%s — email send skipped",
            partner_tenant_id,
            relationship_id,
        )
        return

    # Best-effort tenant-name resolution for both sides; fall back to
    # opaque labels if lookups fail.
    try:
        requesting_company = (
            db.query(Company).filter(Company.id == requesting_tenant_id).first()
        )
        partner_company = (
            db.query(Company).filter(Company.id == partner_tenant_id).first()
        )
    except Exception:  # noqa: BLE001
        requesting_company = None
        partner_company = None

    requesting_tenant_name = (
        requesting_company.name if requesting_company else "A connected tenant"
    )
    partner_tenant_name = (
        partner_company.name if partner_company else "your tenant"
    )

    # Per-recipient send. Failure on one admin doesn't cascade.
    for admin in admins:
        if not admin.email:
            continue
        try:
            delivery_service.send_email_with_template(
                db,
                # Phase D-9 mandatory threading: company_id=partner
                # tenant id (the receiving tenant — admin's tenant).
                company_id=partner_tenant_id,
                to_email=admin.email,
                to_name=(
                    f"{admin.first_name or ''} {admin.last_name or ''}".strip()
                    or None
                ),
                template_key="email.calendar_consent_upgrade_request",
                template_context={
                    "requesting_tenant_name": requesting_tenant_name,
                    "partner_tenant_name": partner_tenant_name,
                    "recipient_first_name": admin.first_name or "there",
                    "consent_upgrade_url": (
                        "/settings/calendar/freebusy-consent"
                    ),
                    "relationship_type": relationship_type,
                },
                caller_module="ptr_consent_service.request_upgrade_email",
                metadata={
                    "relationship_id": relationship_id,
                    "requesting_tenant_id": requesting_tenant_id,
                    "partner_tenant_id": partner_tenant_id,
                    "step_5_1_category": "calendar_consent_upgrade_request",
                },
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "ptr_consent_service: email send failed for "
                "partner_tenant_id=%s admin_id=%s relationship_id=%s "
                "— continuing fan-out per best-effort discipline",
                partner_tenant_id,
                admin.id,
                relationship_id,
            )


# ─────────────────────────────────────────────────────────────────────
# Personalization Studio Cross-Tenant Sharing Consent — Step 1 Step 0
# Migration r75 canonical parallel API per Q4 column-per-capability
# discipline.
#
# **Canonical-substrate-shape distinction from Calendar Step 4.1**:
# Calendar Step 4.1 stores per-side intent (free_busy_only | full_details)
# and resolves the bilateral 4-state machine at service-layer state
# resolver from the (forward, reverse) tuple. Q4 canonical direction for
# personalization_studio capability stores the canonical 4-state machine
# DIRECTLY at column substrate per-tenant-perspective: each PTR row's
# column reflects the bilateral state from THAT tenant's canonical
# perspective. State transitions update BOTH PTR rows synchronously per
# dual-row canonical pattern. Service layer reads state directly from
# caller's row (no resolver needed at service substrate).
#
# **Canonical state machine values stored directly at column substrate**:
#   - ``default`` — canonical privacy-preserving baseline
#   - ``pending_outbound`` — caller has requested upgrade; partner has
#     not yet accepted (caller's perspective)
#   - ``pending_inbound`` — partner has requested upgrade; caller has
#     not yet accepted (caller's perspective)
#   - ``active`` — bilateral consent in force; canonical cross-tenant
#     DocumentShare grant authorized
#
# **Canonical state machine transitions** (dual-row update pattern):
#   - ``request_*``: forward (caller) ``default → pending_outbound``;
#     reverse (partner) ``default → pending_inbound``
#   - ``accept_*``: forward (acceptor) ``pending_inbound → active``;
#     reverse (requester) ``pending_outbound → active``
#   - ``revoke_*``: forward (revoker) ``* → default``;
#     reverse (partner) ``* → default``
#
# **Audit destination**: platform-wide ``audit_logs`` via
# ``audit_service.log_action`` (NOT ``calendar_audit_log``) per
# canonical-domain-boundary discipline — per-capability audit destinations
# preserve canonical separation while sharing the column-per-capability
# storage substrate on PTR row.
#
# **Notification categories**:
#   - ``personalization_studio_consent_upgrade_request``
#   - ``personalization_studio_consent_upgrade_accepted``
#   - ``personalization_studio_consent_revoked``
#
# **Settings-page link**: ``/settings/personalization-studio/cross-tenant-sharing-consent``
#
# **Email-mediated upgrade requests deferred to Step 1 Phase 1E** (parallel
# to Calendar Step 5.1 email-mediated extension; ships as opt-in
# ``send_email`` kwarg per Q1 Calendar precedent when Phase 1E lands).
# ─────────────────────────────────────────────────────────────────────


# Canonical column name on PlatformTenantRelationship row for
# personalization_studio capability per r75. Q4 column-per-capability
# canonical: each capability gets its own canonical column.
PERSONALIZATION_STUDIO_CONSENT_COLUMN = (
    "personalization_studio_cross_tenant_sharing_consent"
)


# Canonical 4-state machine values stored directly at column substrate
# per Q4 canonical direction. Keep in sync with migration r75 +
# PlatformTenantRelationship model.
CANONICAL_PERSONALIZATION_STUDIO_STATES: tuple[ConsentState, ...] = (
    "default",
    "pending_outbound",
    "pending_inbound",
    "active",
)


def _audit_personalization_consent(
    db: Session,
    *,
    company_id: str,
    actor_user_id: str | None,
    action: str,
    relationship_id: str,
    changes: dict[str, Any],
) -> None:
    """Write personalization_studio consent audit row to platform-wide audit_logs.

    Per canonical-domain-boundary discipline: personalization_studio
    consent transitions write to platform ``audit_logs`` (NOT
    ``calendar_audit_log``). Each capability's audit destination
    preserves canonical separation while sharing the column-per-capability
    storage substrate on PTR row.
    """
    # Defer import to avoid module-load circularity.
    from app.services import audit_service

    audit_service.log_action(
        db,
        company_id=company_id,
        action=action,
        entity_type="platform_tenant_relationship",
        entity_id=relationship_id,
        user_id=actor_user_id,
        changes=changes,
    )


def _stamp_consent_metadata(
    row: PlatformTenantRelationship,
    *,
    new_state: ConsentState,
    actor_user_id: str | None,
) -> None:
    """Stamp canonical consent state + Q3 metadata columns on a PTR row.

    Per canonical dual-row update pattern: state + metadata are stamped
    canonically on every PTR row updated as part of a state transition
    (forward + reverse). Q3 metadata columns reflect the most-recent
    actor + timestamp on each row independently, preserving per-row
    audit-trail clarity.
    """
    setattr(row, PERSONALIZATION_STUDIO_CONSENT_COLUMN, new_state)
    row.personalization_studio_cross_tenant_sharing_consent_updated_at = (
        datetime.now(timezone.utc)
    )
    row.personalization_studio_cross_tenant_sharing_consent_updated_by = (
        actor_user_id
    )


def request_personalization_studio_consent(
    db: Session,
    *,
    requesting_tenant_id: str,
    relationship_id: str,
    requested_by_user_id: str,
) -> dict[str, Any]:
    """Initiate canonical personalization_studio consent upgrade — dual-row update.

    **Canonical state transitions** per Q4 dual-row update pattern:
      - forward row (caller side): ``default → pending_outbound``
      - reverse row (partner side): ``default → pending_inbound``

    Per-side audit logs per §3.26.11.10: tenant-side-only event at request
    time (caller's audit_logs scope only — reverse-row update is a
    canonical state-machine sync, not a partner-initiated event).

    Notification fan-out: V-1d notify_tenant_admins to partner admins
    (canonical pattern matches Calendar Step 4.1 precedent).

    Raises:
        PtrConsentInvalidTransition (409): caller's row not at
            ``default`` (already requested or already in non-default state).
        PtrConsentNotFound (404): relationship not found, not owned by
            caller, OR canonical reverse row missing (canonical bilateral
            state-machine requires both PTR rows to exist for dual-row
            update pattern).
    """
    forward_row, reverse_row = _resolve_pair_for_caller(
        db,
        relationship_id=relationship_id,
        caller_tenant_id=requesting_tenant_id,
    )

    if reverse_row is None:
        # Canonical dual-row update pattern requires both PTR rows to
        # exist. Missing reverse blocks canonical state-machine sync —
        # caller must establish bidirectional PTR pair first.
        raise PtrConsentNotFound(
            f"Canonical reverse PTR row missing for relationship "
            f"{relationship_id!r}; bidirectional PTR pair required "
            f"for personalization_studio canonical bilateral consent."
        )

    prior_state = getattr(forward_row, PERSONALIZATION_STUDIO_CONSENT_COLUMN)

    if prior_state != "default":
        raise PtrConsentInvalidTransition(
            f"Caller's PTR row at {prior_state!r}; canonical "
            f"request_personalization_studio_consent requires "
            f"'default' prior state. Use accept_* / revoke_* per "
            f"canonical state machine."
        )

    # Dual-row canonical update: forward → pending_outbound; reverse → pending_inbound
    _stamp_consent_metadata(
        forward_row,
        new_state="pending_outbound",
        actor_user_id=requested_by_user_id,
    )
    _stamp_consent_metadata(
        reverse_row,
        new_state="pending_inbound",
        actor_user_id=requested_by_user_id,
    )
    db.flush()

    partner_tenant_id = forward_row.supplier_tenant_id

    # Per-side audit log: caller side only at request time per §3.26.11.10
    # ("Tenant-side-only events appear only in the originating side's log").
    _audit_personalization_consent(
        db,
        company_id=requesting_tenant_id,
        actor_user_id=requested_by_user_id,
        action="personalization_studio_consent_upgrade_requested",
        relationship_id=forward_row.id,
        changes={
            "relationship_id": forward_row.id,
            "partner_tenant_id": partner_tenant_id,
            "requesting_tenant_id": requesting_tenant_id,
            "prior_state": prior_state,
            "new_state": "pending_outbound",
            "reverse_row_new_state": "pending_inbound",
        },
    )

    # In-app notification to partner tenant admins.
    _notify_partner_admins(
        db,
        partner_tenant_id=partner_tenant_id,
        category="personalization_studio_consent_upgrade_request",
        title="Personalization Studio cross-tenant sharing consent request",
        message=(
            "A connected tenant has requested consent upgrade for "
            "Personalization Studio cross-tenant sharing. Review pending "
            "requests in personalization studio consent settings."
        ),
        type="info",
        link="/settings/personalization-studio/cross-tenant-sharing-consent",
        relationship_id=forward_row.id,
        actor_user_id=requested_by_user_id,
    )

    return {
        "relationship_id": forward_row.id,
        "partner_tenant_id": partner_tenant_id,
        "prior_state": prior_state,
        "new_state": "pending_outbound",
    }


def accept_personalization_studio_consent(
    db: Session,
    *,
    accepting_tenant_id: str,
    relationship_id: str,
    accepted_by_user_id: str,
) -> dict[str, Any]:
    """Accept canonical personalization_studio consent upgrade — dual-row update.

    **Canonical state transitions** per Q4 dual-row update pattern:
      - forward row (acceptor side): ``pending_inbound → active``
      - reverse row (requester side): ``pending_outbound → active``

    Per-side audit logs per §3.26.11.10: bilateral activation = joint
    event; writes audit row to BOTH tenants' audit_logs scopes.

    Raises:
        PtrConsentInvalidTransition (409): caller's row not at
            ``pending_inbound`` (canon directs to ``request_*`` for
            ``default`` prior state; nothing to accept from ``active``
            or ``pending_outbound`` perspective).
        PtrConsentNotFound (404): relationship not found, not owned by
            caller, OR canonical reverse row missing.
    """
    forward_row, reverse_row = _resolve_pair_for_caller(
        db,
        relationship_id=relationship_id,
        caller_tenant_id=accepting_tenant_id,
    )

    if reverse_row is None:
        raise PtrConsentNotFound(
            f"Canonical reverse PTR row missing for relationship "
            f"{relationship_id!r}; bidirectional PTR pair required "
            f"for personalization_studio canonical bilateral consent."
        )

    prior_state = getattr(forward_row, PERSONALIZATION_STUDIO_CONSENT_COLUMN)

    if prior_state != "pending_inbound":
        raise PtrConsentInvalidTransition(
            f"Caller's PTR row at {prior_state!r}; canonical "
            f"accept_personalization_studio_consent requires "
            f"'pending_inbound' prior state. Partner has not requested "
            f"upgrade — use request_personalization_studio_consent to "
            f"initiate the bilateral flow from this side."
        )

    # Dual-row canonical update: forward → active; reverse → active
    _stamp_consent_metadata(
        forward_row,
        new_state="active",
        actor_user_id=accepted_by_user_id,
    )
    _stamp_consent_metadata(
        reverse_row,
        new_state="active",
        actor_user_id=accepted_by_user_id,
    )
    db.flush()

    partner_tenant_id = forward_row.supplier_tenant_id

    audit_changes = {
        "relationship_id": forward_row.id,
        "partner_tenant_id": partner_tenant_id,
        "requesting_tenant_id": partner_tenant_id,  # partner was the requester
        "prior_state": prior_state,
        "new_state": "active",
    }

    # Per-side audit logs per §3.26.11.10 (joint event = both sides).
    _audit_personalization_consent(
        db,
        company_id=accepting_tenant_id,
        actor_user_id=accepted_by_user_id,
        action="personalization_studio_consent_upgrade_accepted",
        relationship_id=forward_row.id,
        changes=audit_changes,
    )
    _audit_personalization_consent(
        db,
        company_id=partner_tenant_id,
        actor_user_id=accepted_by_user_id,
        action="personalization_studio_consent_upgrade_accepted",
        relationship_id=reverse_row.id,
        changes=audit_changes,
    )

    # Notify the requesting (partner) tenant's admins.
    _notify_partner_admins(
        db,
        partner_tenant_id=partner_tenant_id,
        category="personalization_studio_consent_upgrade_accepted",
        title="Personalization Studio cross-tenant sharing consent accepted",
        message=(
            "A connected tenant accepted your Personalization Studio "
            "cross-tenant sharing consent upgrade request. Bilateral "
            "consent is now active."
        ),
        type="success",
        link="/settings/personalization-studio/cross-tenant-sharing-consent",
        relationship_id=forward_row.id,
        actor_user_id=accepted_by_user_id,
    )

    return {
        "relationship_id": forward_row.id,
        "partner_tenant_id": partner_tenant_id,
        "prior_state": prior_state,
        "new_state": "active",
    }


def revoke_personalization_studio_consent(
    db: Session,
    *,
    revoking_tenant_id: str,
    relationship_id: str,
    revoked_by_user_id: str,
) -> dict[str, Any]:
    """Revoke canonical personalization_studio consent — dual-row update.

    **Canonical state transitions** per Q4 dual-row update pattern:
      - forward row (revoker side): ``* → default``
      - reverse row (partner side): ``* → default``

    Per §3.26.16.6 + §3.26.11.10 either-side-revocation canonical:
    "either tenant can unilaterally revoke" from any non-default state.

    Per-side audit logs (joint event): writes to BOTH tenants' audit_logs
    scopes per §3.26.11.10.

    Raises:
        PtrConsentInvalidTransition (409): caller's row already at
            ``default`` (nothing to revoke).
        PtrConsentNotFound (404): relationship not found, not owned by
            caller, OR canonical reverse row missing.
    """
    forward_row, reverse_row = _resolve_pair_for_caller(
        db,
        relationship_id=relationship_id,
        caller_tenant_id=revoking_tenant_id,
    )

    if reverse_row is None:
        raise PtrConsentNotFound(
            f"Canonical reverse PTR row missing for relationship "
            f"{relationship_id!r}; bidirectional PTR pair required "
            f"for personalization_studio canonical bilateral consent."
        )

    prior_state = getattr(forward_row, PERSONALIZATION_STUDIO_CONSENT_COLUMN)

    if prior_state == "default":
        raise PtrConsentInvalidTransition(
            "Caller's PTR row already at 'default' for "
            "personalization_studio capability; nothing to revoke."
        )

    # Dual-row canonical update: forward → default; reverse → default
    _stamp_consent_metadata(
        forward_row,
        new_state="default",
        actor_user_id=revoked_by_user_id,
    )
    _stamp_consent_metadata(
        reverse_row,
        new_state="default",
        actor_user_id=revoked_by_user_id,
    )
    db.flush()

    partner_tenant_id = forward_row.supplier_tenant_id

    audit_changes = {
        "relationship_id": forward_row.id,
        "partner_tenant_id": partner_tenant_id,
        "revoking_tenant_id": revoking_tenant_id,
        "prior_state": prior_state,
        "new_state": "default",
    }

    # Per-side audit logs (joint event per §3.26.11.10).
    _audit_personalization_consent(
        db,
        company_id=revoking_tenant_id,
        actor_user_id=revoked_by_user_id,
        action="personalization_studio_consent_revoked",
        relationship_id=forward_row.id,
        changes=audit_changes,
    )
    if partner_tenant_id != revoking_tenant_id:
        _audit_personalization_consent(
            db,
            company_id=partner_tenant_id,
            actor_user_id=revoked_by_user_id,
            action="personalization_studio_consent_revoked",
            relationship_id=reverse_row.id,
            changes=audit_changes,
        )

    # Notify partner tenant's admins.
    _notify_partner_admins(
        db,
        partner_tenant_id=partner_tenant_id,
        category="personalization_studio_consent_revoked",
        title="Personalization Studio cross-tenant sharing consent revoked",
        message=(
            "A connected tenant revoked their Personalization Studio "
            "cross-tenant sharing consent. Cross-tenant DocumentShare "
            "grants of personalization Generation Focus Document substrate "
            "are no longer canonically authorized."
        ),
        type="warning",
        link="/settings/personalization-studio/cross-tenant-sharing-consent",
        relationship_id=forward_row.id,
        actor_user_id=revoked_by_user_id,
    )

    return {
        "relationship_id": forward_row.id,
        "partner_tenant_id": partner_tenant_id,
        "prior_state": prior_state,
        "new_state": "default",
    }


def check_personalization_studio_consent(
    db: Session,
    *,
    tenant_id: str,
    partner_tenant_id: str,
    relationship_type: str,
) -> ConsentState:
    """Read canonical personalization_studio consent state from caller's perspective.

    Reads state directly from caller's PTR row (forward row) per Q4
    canonical direction — state stored DIRECTLY at column substrate;
    no resolver needed at service substrate.

    Read-side canonical helper for cross-tenant DocumentShare grant
    authorization at Step 1 Phase 1F. Returns ``active`` only when
    bilateral consent is in force; returns ``default`` / ``pending_*``
    for all other states. The grant flow at Phase 1F authorizes only
    when state == ``active``.

    Returns the canonical 4-value ConsentState. Treats missing forward
    row as ``default`` (canonical privacy default).
    """
    forward_row = (
        db.query(PlatformTenantRelationship)
        .filter(
            PlatformTenantRelationship.tenant_id == tenant_id,
            PlatformTenantRelationship.supplier_tenant_id == partner_tenant_id,
            PlatformTenantRelationship.relationship_type == relationship_type,
        )
        .first()
    )
    if forward_row is None:
        return "default"
    return getattr(forward_row, PERSONALIZATION_STUDIO_CONSENT_COLUMN)


def list_partner_personalization_studio_consent_states(
    db: Session, *, tenant_id: str
) -> list[dict[str, Any]]:
    """List partner tenants + per-relationship personalization_studio consent state.

    Settings-page surface for the personalization_studio consent admin UI
    (ships at Step 1 Phase 1E). Reads state directly from each forward
    PTR row's column per Q4 canonical direction (no resolver).

    Returns one dict per PTR row owned by ``tenant_id``. Each dict carries:
      - relationship_id
      - relationship_type
      - partner_tenant_id
      - partner_tenant_name (best-effort Company lookup)
      - state: canonical 4-state ConsentState read directly from caller's row
      - partner_side_state: canonical 4-state ConsentState read directly
        from reverse row (None if reverse missing)
      - updated_at: ISO datetime or None
      - updated_by_user_id: user id or None
    """
    from app.models.company import Company

    forward_rows = (
        db.query(PlatformTenantRelationship)
        .filter(
            PlatformTenantRelationship.tenant_id == tenant_id,
            PlatformTenantRelationship.status == "active",
        )
        .order_by(PlatformTenantRelationship.connected_at.desc())
        .all()
    )

    results: list[dict[str, Any]] = []
    for forward in forward_rows:
        reverse = (
            db.query(PlatformTenantRelationship)
            .filter(
                PlatformTenantRelationship.tenant_id == forward.supplier_tenant_id,
                PlatformTenantRelationship.supplier_tenant_id == tenant_id,
                PlatformTenantRelationship.relationship_type
                == forward.relationship_type,
            )
            .first()
        )

        partner_company = (
            db.query(Company)
            .filter(Company.id == forward.supplier_tenant_id)
            .first()
        )

        results.append(
            {
                "relationship_id": forward.id,
                "relationship_type": forward.relationship_type,
                "partner_tenant_id": forward.supplier_tenant_id,
                "partner_tenant_name": (
                    partner_company.name if partner_company else None
                ),
                "state": getattr(
                    forward, PERSONALIZATION_STUDIO_CONSENT_COLUMN
                ),
                "partner_side_state": (
                    getattr(reverse, PERSONALIZATION_STUDIO_CONSENT_COLUMN)
                    if reverse
                    else None
                ),
                "updated_at": (
                    forward.personalization_studio_cross_tenant_sharing_consent_updated_at.isoformat()
                    if forward.personalization_studio_cross_tenant_sharing_consent_updated_at
                    else None
                ),
                "updated_by_user_id": (
                    forward.personalization_studio_cross_tenant_sharing_consent_updated_by
                ),
            }
        )

    return results
