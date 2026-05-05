"""Cross-tenant calendar event pairing — Phase W-4b Layer 1 Step 4.

Per §3.26.16.14 + §3.26.16.20 canonical specifications. The
``cross_tenant_event_pairing`` junction table shipped at Step 1; Step 4
ships the runtime lifecycle (propose / finalize / revoke) + bilateral
state propagation hooks + per-tenant participant routing.

**Per Q2 confirmed pre-build**: ``paired_at`` semantics —
  - ``paired_at IS NULL`` = pending bilateral acceptance
  - ``paired_at IS NOT NULL AND revoked_at IS NULL`` = finalized (paired)
  - ``revoked_at IS NOT NULL`` = revoked (terminal)

**Bilateral acceptance flow** (per §3.26.16.14 verbatim):
  1. Initiating tenant proposes cross-tenant event
  2. Initiating tenant's calendar gets event row with
     ``is_cross_tenant=True`` + ``cross_tenant_event_pairing`` pending
     acceptance (paired_at=NULL)
  3. Partner tenant receives proposal via Communications layer +
     email-mediated calendar invitation + cross-tenant Pulse widget
     (Step 5)
  4. Partner accepts → their calendar gets paired event row; bilateral
     state propagates per §3.26.16.20
  5. Partner declines OR proposes counter-time: state machine handles
     per §3.26.16.17

**Per-tenant copy semantics** (per §3.26.16.20 verbatim):
  - Each tenant carries its own ``CalendarEvent`` row + own attendees
    + own commentary
  - ``cross_tenant_event_pairing`` junction connects the two row-pairs
    via ``event_a_id`` + ``event_b_id`` + ``tenant_a_id`` + ``tenant_b_id``
  - On finalize (commit accept), pairing transitions from pending to
    finalized
  - Either tenant can revoke at any time

**Per-tenant participant routing** (per §3.26.11.7): each tenant's
attendee notifications follow that tenant's role-based routing rules.
Per-side audit logs per §3.26.11.10.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.calendar_primitive import (
    CalendarEvent,
    CalendarEventAttendee,
    CrossTenantEventPairing,
)
from app.models.platform_tenant_relationship import PlatformTenantRelationship
from app.services.calendar.account_service import (
    CalendarAccountError,
    CalendarAccountNotFound,
    CalendarAccountValidation,
    _audit,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────


class CrossTenantPairingError(CalendarAccountError):
    http_status = 400


class CrossTenantPairingNotFound(CalendarAccountError):
    http_status = 404


class CrossTenantPairingPermissionDenied(CalendarAccountError):
    http_status = 403


class CrossTenantPairingConflict(CalendarAccountError):
    http_status = 409


# ─────────────────────────────────────────────────────────────────────
# Lifecycle: propose / finalize / revoke
# ─────────────────────────────────────────────────────────────────────


def propose_pairing(
    db: Session,
    *,
    initiating_event: CalendarEvent,
    partner_tenant_id: str,
    actor_user_id: str | None = None,
    relationship_id: str | None = None,
    partner_event_id: str | None = None,
) -> CrossTenantEventPairing:
    """Create a pending cross-tenant event pairing.

    Per §3.26.16.14 step 2: initiating tenant's event gains a pending
    pairing row. partner_event_id may be NULL at proposal time —
    partner's CalendarEvent row gets created at accept-time.

    Args:
        initiating_event: The proposing tenant's CalendarEvent row.
            Must already have ``is_cross_tenant=True``.
        partner_tenant_id: Target tenant id; must differ from
            initiating event's tenant.
        actor_user_id: User initiating the pairing (audit attribution).
        relationship_id: Optional FK to platform_tenant_relationships.
            When set, the pairing is scoped to the named relationship.
            When NULL, the pairing is ad-hoc (no PTR row required).
        partner_event_id: Optional pre-resolved partner CalendarEvent
            id. Typically NULL at proposal; populated when partner
            accepts via the bilateral propagation flow.

    Returns the persisted CrossTenantEventPairing row in pending state
    (``paired_at IS NULL``).

    Raises:
        CrossTenantPairingError (400): self-pairing OR
            initiating_event.is_cross_tenant=False.
        CrossTenantPairingConflict (409): an active (non-revoked)
            pairing already exists for the (event_a, partner_tenant)
            pair.
    """
    if initiating_event.tenant_id == partner_tenant_id:
        raise CrossTenantPairingError(
            "Self-pairing rejected: partner_tenant_id must differ from "
            "initiating event's tenant_id."
        )

    if not initiating_event.is_cross_tenant:
        raise CrossTenantPairingError(
            "Initiating event must have is_cross_tenant=True before a "
            "pairing can be proposed."
        )

    # Defensive: prevent duplicate active pairings (same initiating
    # event paired to same partner tenant). Caller can revoke + re-propose.
    existing = (
        db.query(CrossTenantEventPairing)
        .filter(
            CrossTenantEventPairing.event_a_id == initiating_event.id,
            CrossTenantEventPairing.tenant_b_id == partner_tenant_id,
            CrossTenantEventPairing.revoked_at.is_(None),
        )
        .first()
    )
    if existing is not None:
        raise CrossTenantPairingConflict(
            f"An active pairing already exists for event "
            f"{initiating_event.id!r} ↔ tenant {partner_tenant_id!r}."
        )

    pairing = CrossTenantEventPairing(
        id=str(uuid.uuid4()),
        event_a_id=initiating_event.id,
        event_b_id=partner_event_id,  # may be NULL at proposal time
        tenant_a_id=initiating_event.tenant_id,
        tenant_b_id=partner_tenant_id,
        relationship_id=relationship_id,
        paired_at=None,  # pending semantics per Q2
        revoked_at=None,
    )
    db.add(pairing)
    db.flush()

    _audit(
        db,
        tenant_id=initiating_event.tenant_id,
        actor_user_id=actor_user_id,
        action="cross_tenant_pairing_proposed",
        entity_type="cross_tenant_event_pairing",
        entity_id=pairing.id,
        changes={
            "event_a_id": initiating_event.id,
            "tenant_b_id": partner_tenant_id,
            "relationship_id": relationship_id,
            "partner_event_id": partner_event_id,
        },
    )
    db.flush()

    return pairing


def finalize_pairing(
    db: Session,
    *,
    pairing: CrossTenantEventPairing,
    partner_event_id: str | None = None,
    actor_user_id: str | None = None,
) -> CrossTenantEventPairing:
    """Finalize a pending pairing on bilateral acceptance.

    Sets ``paired_at = now()``. If ``partner_event_id`` is supplied
    and the pairing's ``event_b_id`` was previously NULL (deferred
    until accept-time), populate it now.

    Per §3.26.16.14 step 4 + §3.26.16.20 bilateral state propagation:
    on partner-side accept, the pairing transitions from pending to
    finalized; both tenants' events become "confirmed".

    Idempotent — finalizing an already-finalized pairing is a no-op.
    Raises if pairing already revoked.
    """
    if pairing.revoked_at is not None:
        raise CrossTenantPairingError(
            f"Pairing {pairing.id!r} is revoked; cannot finalize."
        )

    if pairing.paired_at is not None:
        # Already finalized — idempotent no-op.
        if (
            partner_event_id is not None
            and pairing.event_b_id is None
        ):
            # Edge case: pairing finalized before partner_event_id was
            # known. Backfill is allowed.
            pairing.event_b_id = partner_event_id
            db.flush()
        return pairing

    pairing.paired_at = datetime.now(timezone.utc)
    if partner_event_id is not None:
        pairing.event_b_id = partner_event_id

    db.flush()

    _audit(
        db,
        tenant_id=pairing.tenant_a_id,
        actor_user_id=actor_user_id,
        action="cross_tenant_pairing_finalized",
        entity_type="cross_tenant_event_pairing",
        entity_id=pairing.id,
        changes={
            "event_a_id": pairing.event_a_id,
            "event_b_id": pairing.event_b_id,
            "tenant_b_id": pairing.tenant_b_id,
        },
    )
    # Per-side audit log: also write to tenant_b's audit channel.
    _audit(
        db,
        tenant_id=pairing.tenant_b_id,
        actor_user_id=actor_user_id,
        action="cross_tenant_pairing_finalized",
        entity_type="cross_tenant_event_pairing",
        entity_id=pairing.id,
        changes={
            "event_a_id": pairing.event_a_id,
            "event_b_id": pairing.event_b_id,
            "tenant_a_id": pairing.tenant_a_id,
        },
    )
    db.flush()

    return pairing


def revoke_pairing(
    db: Session,
    *,
    pairing: CrossTenantEventPairing,
    revoking_tenant_id: str,
    actor_user_id: str | None = None,
    reason: str | None = None,
) -> CrossTenantEventPairing:
    """Revoke a cross-tenant pairing per §3.26.16.14 revocation discipline.

    Either tenant can revoke participation. Revoking tenant's event is
    marked via ``cross_tenant_event_pairing.revoked_at``; the other
    tenant retains their event row + audit log + can elect to keep as
    internal-only OR cancel.

    Raises:
        CrossTenantPairingPermissionDenied (403): revoking_tenant_id is
            not one of the pairing's tenants.
        CrossTenantPairingError (400): already revoked.
    """
    if revoking_tenant_id not in (pairing.tenant_a_id, pairing.tenant_b_id):
        raise CrossTenantPairingPermissionDenied(
            f"Tenant {revoking_tenant_id!r} is not a participant in "
            f"pairing {pairing.id!r}; cannot revoke."
        )
    if pairing.revoked_at is not None:
        raise CrossTenantPairingError(
            f"Pairing {pairing.id!r} already revoked."
        )

    pairing.revoked_at = datetime.now(timezone.utc)
    db.flush()

    # Per-side audit logs per §3.26.11.10.
    audit_changes = {
        "event_a_id": pairing.event_a_id,
        "event_b_id": pairing.event_b_id,
        "revoking_tenant_id": revoking_tenant_id,
        "reason": (reason or "")[:200] or None,
    }
    _audit(
        db,
        tenant_id=pairing.tenant_a_id,
        actor_user_id=actor_user_id,
        action="cross_tenant_pairing_revoked",
        entity_type="cross_tenant_event_pairing",
        entity_id=pairing.id,
        changes=audit_changes,
    )
    if pairing.tenant_a_id != pairing.tenant_b_id:
        _audit(
            db,
            tenant_id=pairing.tenant_b_id,
            actor_user_id=actor_user_id,
            action="cross_tenant_pairing_revoked",
            entity_type="cross_tenant_event_pairing",
            entity_id=pairing.id,
            changes=audit_changes,
        )
    db.flush()

    return pairing


# ─────────────────────────────────────────────────────────────────────
# Lookups
# ─────────────────────────────────────────────────────────────────────


def get_pairing(
    db: Session, *, pairing_id: str
) -> CrossTenantEventPairing:
    """Fetch a pairing by id. Raises CrossTenantPairingNotFound."""
    pairing = (
        db.query(CrossTenantEventPairing)
        .filter(CrossTenantEventPairing.id == pairing_id)
        .first()
    )
    if pairing is None:
        raise CrossTenantPairingNotFound(
            f"CrossTenantEventPairing {pairing_id!r} not found."
        )
    return pairing


def list_pairings_for_tenant(
    db: Session,
    *,
    tenant_id: str,
    status: str | None = None,
    limit: int = 100,
) -> list[CrossTenantEventPairing]:
    """List pairings touching a tenant.

    Args:
        tenant_id: filter — pairing must have tenant_a_id OR
            tenant_b_id matching.
        status: optional filter — 'pending' (paired_at=NULL +
            revoked_at=NULL), 'paired' (paired_at!=NULL +
            revoked_at=NULL), 'revoked' (revoked_at!=NULL), or None
            for all.
        limit: max rows.
    """
    q = db.query(CrossTenantEventPairing).filter(
        (CrossTenantEventPairing.tenant_a_id == tenant_id)
        | (CrossTenantEventPairing.tenant_b_id == tenant_id)
    )
    if status == "pending":
        q = q.filter(
            CrossTenantEventPairing.paired_at.is_(None),
            CrossTenantEventPairing.revoked_at.is_(None),
        )
    elif status == "paired":
        q = q.filter(
            CrossTenantEventPairing.paired_at.isnot(None),
            CrossTenantEventPairing.revoked_at.is_(None),
        )
    elif status == "revoked":
        q = q.filter(CrossTenantEventPairing.revoked_at.isnot(None))
    return q.limit(max(1, min(limit, 500))).all()


def get_pairing_status(pairing: CrossTenantEventPairing) -> str:
    """Resolve a pairing's lifecycle status from paired_at + revoked_at."""
    if pairing.revoked_at is not None:
        return "revoked"
    if pairing.paired_at is not None:
        return "paired"
    return "pending"


# ─────────────────────────────────────────────────────────────────────
# Per-tenant participant routing (§3.26.11.7)
# ─────────────────────────────────────────────────────────────────────


def list_participants_for_tenant_side(
    db: Session,
    *,
    pairing: CrossTenantEventPairing,
    tenant_id: str,
) -> list[CalendarEventAttendee]:
    """List attendees on the pairing's tenant-specific event row.

    Per §3.26.11.7 per-tenant participant routing canonical: each
    tenant's attendee notifications follow that tenant's role-based
    routing rules. This helper resolves the appropriate event_id
    (event_a or event_b) for the requested tenant_id.

    Returns the attendees of the matching event row only — never
    cross-tenant. Raises CrossTenantPairingError if tenant_id isn't
    a participant in the pairing.
    """
    if tenant_id == pairing.tenant_a_id:
        target_event_id = pairing.event_a_id
    elif tenant_id == pairing.tenant_b_id:
        target_event_id = pairing.event_b_id
    else:
        raise CrossTenantPairingError(
            f"Tenant {tenant_id!r} is not a participant in pairing "
            f"{pairing.id!r}."
        )

    if target_event_id is None:
        # Partner-side event row may not exist yet (pre-accept state).
        return []

    return (
        db.query(CalendarEventAttendee)
        .filter(
            CalendarEventAttendee.event_id == target_event_id,
            CalendarEventAttendee.tenant_id == tenant_id,
        )
        .order_by(CalendarEventAttendee.first_seen_at)
        .all()
    )
