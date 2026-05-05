"""Calendar primitive action-token facade — Phase W-4b Layer 1 Step 4.

Per §3.26.16.17 + §3.26.16.18 + §3.26.16.20 canonical specifications:
five action_types ship at September scope, each with bespoke commit
handler that propagates state to the canonical operational entity.

**Pattern parallels Email Step 4c facade verbatim** post-Path-B
substrate consolidation:
  - Module registers 5 ActionTypeDescriptors against the central
    ``app.services.platform.action_registry`` via side-effect imports
    triggered by Calendar package init
  - Each commit_handler conforms to the substrate's canonical signature
    (db, *, action, outcome, descriptor, ...) and returns the updated
    action dict with stamped completion fields
  - Per-action_type ``build_*_action()`` shape helpers parallel
    Email's ``build_quote_approval_action``
  - Token CRUD inherits from substrate; magic-link tokens carry
    ``linked_entity_type='calendar_event'`` per Path B substrate
    consolidation

**5 canonical action_types** (per §3.26.16.17):

| action_type | action_target_type | use case |
|---|---|---|
| service_date_acceptance | fh_case | FH director accepts service date proposed by manufacturer |
| delivery_date_acceptance | sales_order | FH or cemetery accepts delivery time |
| joint_event_acceptance | cross_tenant_event | Bilateral cross-tenant event acceptance per §3.26.16.14 |
| recurring_meeting_proposal | cross_tenant_event | Recurring meeting proposal with bilateral acceptance |
| event_reschedule_proposal | calendar_event | Post-confirmation event time modification + downstream cascade |

**Status flow** (per §3.26.16.17):
  pending → accepted | rejected | counter_proposed (terminal)

**Outcomes vocabulary**: ``accept`` / ``reject`` / ``counter_propose``.
``counter_propose`` requires completion_note (carries proposed counter
time + optional explanation).

**State propagation table** (per §3.26.16.17 verbatim):

| outcome | Calendar event update | Operational state update |
|---|---|---|
| accept | event status="confirmed"; attendee response_status="accepted" | FHCase.service_date set; SalesOrder.scheduled_date set; cross-tenant pairing finalized |
| reject | event status="cancelled" OR attendee response_status="declined" | operational state retained; operator follows up |
| counter_propose | new action created with proposed counter-time; original action terminal | operator reviews counter-time; iteration continues |

**Counter-proposal chaining canonical** (per §3.26.16.20 iterative-
negotiation pattern): counter_propose marks original action terminal +
appends new action at next ``action_idx`` in
``calendar_events.action_payload['actions']`` + caller (route handler)
issues new platform_action_token + outbound iTIP REPLY embeds new
magic-link URL.

**Reschedule cascade discipline** (per §14.10.5 reschedule flow):
``compute_reschedule_cascade(db, event)`` walks
calendar_event_linkages + cross_tenant_event_pairing for cascade
impact disclosure ("Rescheduling this event will affect: 2 linked
entities, 1 paired cross-tenant event").
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.calendar_primitive import (
    CalendarEvent,
    CalendarEventAttendee,
    CalendarEventLinkage,
    CrossTenantEventPairing,
)
from app.services.calendar.account_service import _audit
from app.services.platform.action_registry import (
    ActionTypeDescriptor,
    register_action_type,
)
from app.services.platform.action_service import (
    ActionAlreadyCompleted,
    ActionError,
    ActionNotFound,
    ActionTokenAlreadyConsumed,
    ActionTokenExpired,
    ActionTokenInvalid,
    CrossPrimitiveTokenMismatch,
    PlatformActionError,
    TOKEN_TTL_DAYS,
    build_magic_link_url,
    consume_action_token,
    generate_action_token,
    lookup_action_token,
    lookup_token_row_raw,
)
from app.services.platform.action_service import (
    issue_action_token as _platform_issue_action_token,
)
from app.services.platform.action_service import (
    commit_action as _platform_commit_action,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Calendar-specific canonical vocabulary
# ─────────────────────────────────────────────────────────────────────


# Per §3.26.16.17 verbatim — 5 canonical action_types at September scope.
ACTION_TYPES = (
    "service_date_acceptance",
    "delivery_date_acceptance",
    "joint_event_acceptance",
    "recurring_meeting_proposal",
    "event_reschedule_proposal",
)


# Canonical outcomes vocabulary per §3.26.16.17 (parallel
# ACTION_OUTCOMES_QUOTE_APPROVAL but Calendar-domain semantics).
ACTION_OUTCOMES_CALENDAR = (
    "accept",
    "reject",
    "counter_propose",
)


# action_status values stored on the action object inside
# calendar_events.action_payload.actions[]
ACTION_STATUSES = (
    "pending",
    "accepted",
    "rejected",
    "counter_proposed",
)


# Outcome → terminal action_status mapping for canonical commit logic.
_OUTCOME_TO_STATUS = {
    "accept": "accepted",
    "reject": "rejected",
    "counter_propose": "counter_proposed",
}


# ─────────────────────────────────────────────────────────────────────
# Action shape helpers
# ─────────────────────────────────────────────────────────────────────


def _new_action_envelope(
    *,
    action_type: str,
    action_target_type: str,
    action_target_id: str,
    action_metadata: dict[str, Any],
) -> dict[str, Any]:
    """Build a canonical action envelope per §3.26.16.17 shape.

    Returns:
        dict with action_type / action_target_type / action_target_id /
        action_metadata / action_status="pending" / completion fields
        nulled out (stamped at commit).
    """
    return {
        "action_type": action_type,
        "action_target_type": action_target_type,
        "action_target_id": action_target_id,
        "action_metadata": action_metadata,
        "action_status": "pending",
        "action_completed_at": None,
        "action_completed_by": None,
        "action_completion_metadata": None,
    }


def build_service_date_acceptance_action(
    *,
    fh_case_id: str,
    proposed_start_at: datetime,
    proposed_end_at: datetime,
    proposed_location: str | None,
    proposing_tenant_name: str,
    deceased_name: str | None = None,
) -> dict[str, Any]:
    """Build a canonical service_date_acceptance action.

    action_target_type='fh_case' per §3.26.16.17.
    """
    metadata: dict[str, Any] = {
        "proposed_start_at": proposed_start_at.isoformat(),
        "proposed_end_at": proposed_end_at.isoformat(),
        "proposing_tenant_name": proposing_tenant_name,
    }
    if proposed_location:
        metadata["proposed_location"] = proposed_location
    if deceased_name:
        metadata["deceased_name"] = deceased_name

    return _new_action_envelope(
        action_type="service_date_acceptance",
        action_target_type="fh_case",
        action_target_id=fh_case_id,
        action_metadata=metadata,
    )


def build_delivery_date_acceptance_action(
    *,
    sales_order_id: str,
    proposed_start_at: datetime,
    proposed_end_at: datetime,
    proposed_location: str | None,
    proposing_tenant_name: str,
    sales_order_number: str | None = None,
) -> dict[str, Any]:
    """Build a canonical delivery_date_acceptance action.

    action_target_type='sales_order' per §3.26.16.17.
    """
    metadata: dict[str, Any] = {
        "proposed_start_at": proposed_start_at.isoformat(),
        "proposed_end_at": proposed_end_at.isoformat(),
        "proposing_tenant_name": proposing_tenant_name,
    }
    if proposed_location:
        metadata["proposed_location"] = proposed_location
    if sales_order_number:
        metadata["sales_order_number"] = sales_order_number

    return _new_action_envelope(
        action_type="delivery_date_acceptance",
        action_target_type="sales_order",
        action_target_id=sales_order_id,
        action_metadata=metadata,
    )


def build_joint_event_acceptance_action(
    *,
    pairing_id: str,
    proposed_start_at: datetime,
    proposed_end_at: datetime,
    proposed_location: str | None,
    proposing_tenant_name: str,
    event_subject: str | None = None,
) -> dict[str, Any]:
    """Build a canonical joint_event_acceptance action.

    action_target_type='cross_tenant_event' per §3.26.16.17. Target id
    references CrossTenantEventPairing.id (the bilateral pairing row).
    """
    metadata: dict[str, Any] = {
        "proposed_start_at": proposed_start_at.isoformat(),
        "proposed_end_at": proposed_end_at.isoformat(),
        "proposing_tenant_name": proposing_tenant_name,
    }
    if proposed_location:
        metadata["proposed_location"] = proposed_location
    if event_subject:
        metadata["event_subject"] = event_subject

    return _new_action_envelope(
        action_type="joint_event_acceptance",
        action_target_type="cross_tenant_event",
        action_target_id=pairing_id,
        action_metadata=metadata,
    )


def build_recurring_meeting_proposal_action(
    *,
    pairing_id: str,
    proposed_start_at: datetime,
    proposed_end_at: datetime,
    proposed_location: str | None,
    proposing_tenant_name: str,
    recurrence_rule: str,
    event_subject: str | None = None,
) -> dict[str, Any]:
    """Build a canonical recurring_meeting_proposal action.

    Per Q4 (en bloc semantics): single acceptance creates the recurring
    pairing; per-instance overrides via existing
    calendar_event_instance_overrides substrate.

    action_metadata carries the RFC 5545 RRULE so the magic-link surface
    can render "Every Tuesday at 9:30 AM" type readable display.
    """
    metadata: dict[str, Any] = {
        "proposed_start_at": proposed_start_at.isoformat(),
        "proposed_end_at": proposed_end_at.isoformat(),
        "proposing_tenant_name": proposing_tenant_name,
        "recurrence_rule": recurrence_rule,
    }
    if proposed_location:
        metadata["proposed_location"] = proposed_location
    if event_subject:
        metadata["event_subject"] = event_subject

    return _new_action_envelope(
        action_type="recurring_meeting_proposal",
        action_target_type="cross_tenant_event",
        action_target_id=pairing_id,
        action_metadata=metadata,
    )


def build_event_reschedule_proposal_action(
    *,
    event_id: str,
    proposed_start_at: datetime,
    proposed_end_at: datetime,
    proposed_location: str | None,
    proposing_tenant_name: str,
    cascade_impact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a canonical event_reschedule_proposal action.

    action_target_type='calendar_event' per §3.26.16.17. Includes
    cascade_impact metadata per §14.10.5 reschedule flow visual canon
    so the magic-link surface can render "Rescheduling this event will
    affect: 2 linked entities, 1 paired cross-tenant event".
    """
    metadata: dict[str, Any] = {
        "proposed_start_at": proposed_start_at.isoformat(),
        "proposed_end_at": proposed_end_at.isoformat(),
        "proposing_tenant_name": proposing_tenant_name,
    }
    if proposed_location:
        metadata["proposed_location"] = proposed_location
    if cascade_impact:
        metadata["cascade_impact"] = cascade_impact

    return _new_action_envelope(
        action_type="event_reschedule_proposal",
        action_target_type="calendar_event",
        action_target_id=event_id,
        action_metadata=metadata,
    )


# ─────────────────────────────────────────────────────────────────────
# action_payload accessors
# ─────────────────────────────────────────────────────────────────────


def get_event_actions(event: CalendarEvent) -> list[dict[str, Any]]:
    """Return the actions list from action_payload, defaulting to []."""
    payload = event.action_payload or {}
    actions = payload.get("actions")
    if not isinstance(actions, list):
        return []
    return actions


def get_action_at_index(
    event: CalendarEvent, action_idx: int
) -> dict[str, Any]:
    """Return a specific action by index. Raises ActionNotFound if missing."""
    actions = get_event_actions(event)
    if action_idx < 0 or action_idx >= len(actions):
        raise ActionNotFound(
            f"Action index {action_idx} not found on calendar event "
            f"{event.id}"
        )
    return actions[action_idx]


def append_action_to_event(
    event: CalendarEvent, action: dict[str, Any]
) -> int:
    """Append a new action to event.action_payload['actions'] + return its index.

    JSONB columns require explicit dict replacement to trigger SQLAlchemy
    dirty tracking — this helper rebuilds the payload safely.
    """
    payload = dict(event.action_payload or {})
    actions = list(payload.get("actions") or [])
    actions.append(action)
    payload["actions"] = actions
    event.action_payload = payload
    return len(actions) - 1


def replace_action_at_index(
    event: CalendarEvent, action_idx: int, updated_action: dict[str, Any]
) -> None:
    """Replace the action at action_idx with updated_action.

    Same JSONB dirty-tracking discipline as append_action_to_event.
    """
    payload = dict(event.action_payload or {})
    actions = list(payload.get("actions") or [])
    if action_idx < 0 or action_idx >= len(actions):
        raise ActionNotFound(
            f"Action index {action_idx} not found on calendar event "
            f"{event.id}"
        )
    actions[action_idx] = updated_action
    payload["actions"] = actions
    event.action_payload = payload


# ─────────────────────────────────────────────────────────────────────
# Calendar-specific token issuance facade
# ─────────────────────────────────────────────────────────────────────


def issue_action_token(
    db: Session,
    *,
    tenant_id: str,
    event_id: str,
    action_idx: int,
    action_type: str,
    recipient_email: str,
    ttl_days: int = TOKEN_TTL_DAYS,
) -> str:
    """Issue an action token for a calendar event.

    Calendar-specific facade — keeps ``event_id`` kwarg for caller
    ergonomics. Internally maps to ``linked_entity_type='calendar_event'``
    + ``linked_entity_id=event_id`` against the platform substrate.

    Validates ``action_type`` is one of the 5 canonical Calendar
    action_types per §3.26.16.17.
    """
    if action_type not in ACTION_TYPES:
        raise ActionError(
            f"Unknown Calendar action_type {action_type!r}. Expected "
            f"one of {ACTION_TYPES}."
        )
    return _platform_issue_action_token(
        db,
        tenant_id=tenant_id,
        linked_entity_type="calendar_event",
        linked_entity_id=event_id,
        action_idx=action_idx,
        action_type=action_type,
        recipient_email=recipient_email,
        ttl_days=ttl_days,
    )


# ─────────────────────────────────────────────────────────────────────
# Calendar-specific commit facade
# ─────────────────────────────────────────────────────────────────────


@dataclass
class CommitResult:
    """Returned from commit_action — caller uses to render UI feedback +
    issue follow-on tokens for counter-proposal chaining."""

    updated_action: dict[str, Any]
    """The action dict with stamped completion fields."""

    target_status: str | None
    """Updated status of the action_target entity (e.g. CalendarEvent.status,
    FHCase.service_date as ISO string, SalesOrder.scheduled_date)."""

    counter_action_idx: int | None = None
    """If outcome=counter_propose, the action_idx of the new chained
    action appended to event.action_payload. Caller (route handler)
    uses this to issue a new token + embed magic-link URL in iTIP REPLY."""

    pairing_id: str | None = None
    """If commit affected a cross_tenant_event_pairing, the pairing id
    for caller to reference (e.g. for outbound iTIP propagation to
    partner tenant)."""


def commit_action(
    db: Session,
    *,
    event: CalendarEvent,
    action_idx: int,
    outcome: str,
    actor_user_id: str | None,
    actor_email: str | None,
    completion_note: str | None = None,
    auth_method: str = "bridgeable",
    ip_address: str | None = None,
    user_agent: str | None = None,
    counter_proposed_start_at: datetime | None = None,
    counter_proposed_end_at: datetime | None = None,
) -> CommitResult:
    """Commit a Calendar primitive action — atomic.

    Both the inline-action endpoint (Bridgeable user) AND the magic-
    link surface (token-authenticated non-Bridgeable user) call this.

    Args:
      event: CalendarEvent carrying the action in action_payload.
      action_idx: Index into action_payload['actions'].
      outcome: One of ACTION_OUTCOMES_CALENDAR.
      actor_user_id: Bridgeable user id when auth_method="bridgeable".
      actor_email: Recipient email when auth_method="magic_link".
      completion_note: Optional note (required for counter_propose to
        carry the rationale; optional for accept/reject).
      auth_method: "bridgeable" | "magic_link".
      counter_proposed_start_at + counter_proposed_end_at: required
        when outcome="counter_propose"; the proposed counter-time.

    Raises:
      ActionAlreadyCompleted (409) if action already terminal.
      ActionError (400) on outcome/note validation issues.
    """
    action = get_action_at_index(event, action_idx)
    return _platform_commit_action(
        db,
        action=action,
        outcome=outcome,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        auth_method=auth_method,
        completion_note=completion_note,
        ip_address=ip_address,
        user_agent=user_agent,
        # Calendar-specific kwargs forwarded to the registered handler:
        event=event,
        action_idx=action_idx,
        counter_proposed_start_at=counter_proposed_start_at,
        counter_proposed_end_at=counter_proposed_end_at,
    )


# ─────────────────────────────────────────────────────────────────────
# Reschedule cascade impact computation per §14.10.5
# ─────────────────────────────────────────────────────────────────────


def compute_reschedule_cascade(
    db: Session, event: CalendarEvent
) -> dict[str, Any]:
    """Compute cascade impact disclosure for event_reschedule_proposal.

    Per §14.10.5 reschedule flow visual canon: "Rescheduling this event
    will affect: N linked entities, M paired cross-tenant events".

    Walks:
      - calendar_event_linkages WHERE event_id = event.id (operational
        entities linked to this event — sales_order, fh_case, quote,
        etc.)
      - cross_tenant_event_pairing WHERE event_a_id = event.id OR
        event_b_id = event.id (paired bilateral events with partner
        tenants)

    Returns dict shape:
      {
        "linked_entity_count": int,
        "paired_cross_tenant_count": int,
        "linked_entities": [{linked_entity_type, linked_entity_id}, ...],
        "paired_tenants": [partner_tenant_id, ...],  # masked per
            §3.25.x; only IDs surfaced
      }
    """
    linkages = (
        db.query(CalendarEventLinkage)
        .filter(
            CalendarEventLinkage.event_id == event.id,
            CalendarEventLinkage.dismissed_at.is_(None),
        )
        .all()
    )
    pairings = (
        db.query(CrossTenantEventPairing)
        .filter(
            (CrossTenantEventPairing.event_a_id == event.id)
            | (CrossTenantEventPairing.event_b_id == event.id),
            CrossTenantEventPairing.revoked_at.is_(None),
        )
        .all()
    )

    paired_tenants: list[str] = []
    for p in pairings:
        # Surface the partner tenant_id (not this event's tenant).
        if p.event_a_id == event.id:
            paired_tenants.append(p.tenant_b_id)
        else:
            paired_tenants.append(p.tenant_a_id)

    return {
        "linked_entity_count": len(linkages),
        "paired_cross_tenant_count": len(pairings),
        "linked_entities": [
            {
                "linked_entity_type": l.linked_entity_type,
                "linked_entity_id": l.linked_entity_id,
            }
            for l in linkages
        ],
        "paired_tenants": paired_tenants,
    }


# ─────────────────────────────────────────────────────────────────────
# Counter-proposal chaining helper
# ─────────────────────────────────────────────────────────────────────


def chain_counter_proposal(
    *,
    event: CalendarEvent,
    original_action: dict[str, Any],
    counter_start_at: datetime,
    counter_end_at: datetime,
    counter_note: str | None,
    proposing_tenant_name: str,
) -> tuple[dict[str, Any], int]:
    """Append a new chained action with counter-proposed time.

    Per §3.26.16.20 iterative-negotiation pattern: original action
    transitions to terminal counter_proposed; new action appended at
    next index with caller-supplied counter-time. Returns
    (new_action, new_action_idx).

    Caller (route handler) is responsible for:
      - Issuing a fresh platform_action_token for the new action_idx
      - Embedding magic-link URL in outbound iTIP REPLY back to the
        original proposing party
    """
    action_type = original_action["action_type"]
    target_type = original_action["action_target_type"]
    target_id = original_action["action_target_id"]

    metadata: dict[str, Any] = {
        "proposed_start_at": counter_start_at.isoformat(),
        "proposed_end_at": counter_end_at.isoformat(),
        "proposing_tenant_name": proposing_tenant_name,
        "is_counter_proposal": True,
    }
    if counter_note:
        metadata["counter_proposal_note"] = counter_note

    # Preserve original metadata fields (location, recurrence_rule,
    # cascade_impact, etc.) by carrying forward non-time fields.
    original_metadata = original_action.get("action_metadata") or {}
    for key in (
        "proposed_location",
        "deceased_name",
        "sales_order_number",
        "event_subject",
        "recurrence_rule",
        "cascade_impact",
    ):
        if key in original_metadata and key not in metadata:
            metadata[key] = original_metadata[key]

    new_action = _new_action_envelope(
        action_type=action_type,
        action_target_type=target_type,
        action_target_id=target_id,
        action_metadata=metadata,
    )
    new_idx = append_action_to_event(event, new_action)
    return new_action, new_idx


# ─────────────────────────────────────────────────────────────────────
# Commit handlers — registered against the central registry
# ─────────────────────────────────────────────────────────────────────


def _shared_commit(
    db: Session,
    *,
    event: CalendarEvent,
    action_idx: int,
    action: dict[str, Any],
    outcome: str,
    actor_user_id: str | None,
    actor_email: str | None,
    auth_method: str,
    completion_metadata: dict[str, Any],
    completion_note: str | None,
    ip_address: str | None,
    user_agent: str | None,
    counter_proposed_start_at: datetime | None,
    counter_proposed_end_at: datetime | None,
    proposing_tenant_name: str = "Bridgeable tenant",
) -> tuple[dict[str, Any], int | None]:
    """Shared commit-pipeline logic across the 5 Calendar action_types.

    Per §3.26.16.17 status flow + counter-proposal chaining per
    §3.26.16.20 iterative-negotiation pattern.

    Returns (updated_original_action, counter_action_idx) — the latter
    is None unless outcome=counter_propose.
    """
    new_action_status = _OUTCOME_TO_STATUS[outcome]

    # Counter-propose validation: requires counter_proposed_start_at +
    # counter_proposed_end_at per §3.26.16.20 iterative-negotiation.
    if outcome == "counter_propose":
        if not counter_proposed_start_at or not counter_proposed_end_at:
            raise ActionError(
                "counter_propose outcome requires counter_proposed_start_at "
                "+ counter_proposed_end_at."
            )

    now = datetime.now(timezone.utc)

    # Update the original action with terminal state.
    updated_action = dict(action)
    updated_action["action_status"] = new_action_status
    updated_action["action_completed_at"] = now.isoformat()
    updated_action["action_completed_by"] = actor_user_id or actor_email
    updated_action["action_completion_metadata"] = completion_metadata
    replace_action_at_index(event, action_idx, updated_action)

    counter_idx: int | None = None
    if outcome == "counter_propose":
        # Append new chained action at next idx per §3.26.16.20.
        _, counter_idx = chain_counter_proposal(
            event=event,
            original_action=action,
            counter_start_at=counter_proposed_start_at,
            counter_end_at=counter_proposed_end_at,
            counter_note=completion_note,
            proposing_tenant_name=proposing_tenant_name,
        )

    return updated_action, counter_idx


def _propagate_event_state_for_outcome(
    event: CalendarEvent, outcome: str
) -> None:
    """Update CalendarEvent.status per §3.26.16.17 state propagation table.

      accept → status="confirmed"
      reject → status retained (operator follows up); attendee response
        already updated by handler; we don't auto-cancel the event row
        unless the canonical row says so. Per canon: "event status=
        cancelled OR attendee declined" — we do attendee declined here,
        leaving cancellation as an operator decision.
      counter_propose → no change (event remains tentative; iteration
        continues).
    """
    if outcome == "accept" and event.status == "tentative":
        event.status = "confirmed"


def _commit_handler_service_date_acceptance(
    db: Session,
    *,
    action: dict[str, Any],
    outcome: str,
    descriptor: ActionTypeDescriptor,
    actor_user_id: str | None,
    actor_email: str | None,
    auth_method: str,
    completion_metadata: dict[str, Any],
    completion_note: str | None,
    ip_address: str | None,
    user_agent: str | None,
    event: CalendarEvent,
    action_idx: int,
    counter_proposed_start_at: datetime | None = None,
    counter_proposed_end_at: datetime | None = None,
    **_: Any,
) -> CommitResult:
    """service_date_acceptance commit handler — propagates FHCase.service_date.

    Per §3.26.16.18 state propagation: on accept, FHCase.service_date
    is set to the proposed_start_at; on reject, FHCase.service_date
    cleared OR retained (operator follows up — we retain by default).
    """
    target_id = action.get("action_target_id")
    if not target_id:
        raise ActionError("Action is missing action_target_id (fh_case).")

    proposing_name = (
        action.get("action_metadata") or {}
    ).get("proposing_tenant_name", "Bridgeable tenant")

    updated_action, counter_idx = _shared_commit(
        db,
        event=event,
        action_idx=action_idx,
        action=action,
        outcome=outcome,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        auth_method=auth_method,
        completion_metadata=completion_metadata,
        completion_note=completion_note,
        ip_address=ip_address,
        user_agent=user_agent,
        counter_proposed_start_at=counter_proposed_start_at,
        counter_proposed_end_at=counter_proposed_end_at,
        proposing_tenant_name=proposing_name,
    )

    target_status: str | None = None
    if outcome == "accept":
        # Propagate to FHCase.service_date if FH model importable.
        # FHCase uses ``company_id`` column for tenancy (canonical pre-
        # vault-phase naming) — distinct from CalendarEvent's tenant_id.
        try:
            from app.models.fh_case import FHCase

            fh_case = (
                db.query(FHCase)
                .filter(
                    FHCase.id == target_id,
                    FHCase.company_id == event.tenant_id,
                )
                .first()
            )
            if fh_case is not None:
                fh_case.service_date = event.start_at
                target_status = event.start_at.isoformat()
        except ImportError:
            # FH model not present in this build — log + continue.
            logger.warning(
                "service_date_acceptance: FHCase model not available; "
                "skipping operational propagation"
            )

        _propagate_event_state_for_outcome(event, outcome)

    db.flush()
    _audit_calendar_action(
        db,
        event=event,
        action_idx=action_idx,
        action_type="service_date_acceptance",
        outcome=outcome,
        auth_method=auth_method,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        target_type="fh_case",
        target_id=str(target_id),
        target_status=target_status,
        completion_note=completion_note,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return CommitResult(
        updated_action=updated_action,
        target_status=target_status,
        counter_action_idx=counter_idx,
    )


def _commit_handler_delivery_date_acceptance(
    db: Session,
    *,
    action: dict[str, Any],
    outcome: str,
    descriptor: ActionTypeDescriptor,
    actor_user_id: str | None,
    actor_email: str | None,
    auth_method: str,
    completion_metadata: dict[str, Any],
    completion_note: str | None,
    ip_address: str | None,
    user_agent: str | None,
    event: CalendarEvent,
    action_idx: int,
    counter_proposed_start_at: datetime | None = None,
    counter_proposed_end_at: datetime | None = None,
    **_: Any,
) -> CommitResult:
    """delivery_date_acceptance commit handler — propagates SalesOrder.scheduled_date."""
    target_id = action.get("action_target_id")
    if not target_id:
        raise ActionError("Action is missing action_target_id (sales_order).")

    proposing_name = (
        action.get("action_metadata") or {}
    ).get("proposing_tenant_name", "Bridgeable tenant")

    updated_action, counter_idx = _shared_commit(
        db,
        event=event,
        action_idx=action_idx,
        action=action,
        outcome=outcome,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        auth_method=auth_method,
        completion_metadata=completion_metadata,
        completion_note=completion_note,
        ip_address=ip_address,
        user_agent=user_agent,
        counter_proposed_start_at=counter_proposed_start_at,
        counter_proposed_end_at=counter_proposed_end_at,
        proposing_tenant_name=proposing_name,
    )

    target_status: str | None = None
    if outcome == "accept":
        try:
            from app.models.sales_order import SalesOrder

            order = (
                db.query(SalesOrder)
                .filter(
                    SalesOrder.id == target_id,
                    SalesOrder.company_id == event.tenant_id,
                )
                .first()
            )
            if order is not None:
                order.scheduled_date = event.start_at
                target_status = event.start_at.isoformat()
        except ImportError:
            logger.warning(
                "delivery_date_acceptance: SalesOrder model not available; "
                "skipping operational propagation"
            )

        _propagate_event_state_for_outcome(event, outcome)

    db.flush()
    _audit_calendar_action(
        db,
        event=event,
        action_idx=action_idx,
        action_type="delivery_date_acceptance",
        outcome=outcome,
        auth_method=auth_method,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        target_type="sales_order",
        target_id=str(target_id),
        target_status=target_status,
        completion_note=completion_note,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return CommitResult(
        updated_action=updated_action,
        target_status=target_status,
        counter_action_idx=counter_idx,
    )


def _commit_handler_joint_event_acceptance(
    db: Session,
    *,
    action: dict[str, Any],
    outcome: str,
    descriptor: ActionTypeDescriptor,
    actor_user_id: str | None,
    actor_email: str | None,
    auth_method: str,
    completion_metadata: dict[str, Any],
    completion_note: str | None,
    ip_address: str | None,
    user_agent: str | None,
    event: CalendarEvent,
    action_idx: int,
    counter_proposed_start_at: datetime | None = None,
    counter_proposed_end_at: datetime | None = None,
    **_: Any,
) -> CommitResult:
    """joint_event_acceptance commit handler — finalizes cross_tenant_event_pairing.

    Per §3.26.16.14 + §3.26.16.20: on accept, the partner tenant's
    pairing row transitions from pending (paired_at=NULL) to finalized
    (paired_at=now()). Both tenants' events become "confirmed".
    """
    pairing_id = action.get("action_target_id")
    if not pairing_id:
        raise ActionError(
            "joint_event_acceptance action is missing action_target_id "
            "(cross_tenant_event pairing id)."
        )

    proposing_name = (
        action.get("action_metadata") or {}
    ).get("proposing_tenant_name", "Bridgeable tenant")

    updated_action, counter_idx = _shared_commit(
        db,
        event=event,
        action_idx=action_idx,
        action=action,
        outcome=outcome,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        auth_method=auth_method,
        completion_metadata=completion_metadata,
        completion_note=completion_note,
        ip_address=ip_address,
        user_agent=user_agent,
        counter_proposed_start_at=counter_proposed_start_at,
        counter_proposed_end_at=counter_proposed_end_at,
        proposing_tenant_name=proposing_name,
    )

    pairing = (
        db.query(CrossTenantEventPairing)
        .filter(CrossTenantEventPairing.id == pairing_id)
        .first()
    )
    if pairing is None:
        raise ActionNotFound(
            f"CrossTenantEventPairing {pairing_id!r} not found."
        )

    if outcome == "accept":
        # Finalize bilateral pairing per §3.26.16.14.
        if pairing.paired_at is None:
            pairing.paired_at = datetime.now(timezone.utc)
        # Per-tenant copy semantics: confirm THIS tenant's event row.
        # Partner's event row update propagates via cross_tenant_pairing_service
        # via outbound iTIP REPLY (Step 3 substrate handles propagation).
        _propagate_event_state_for_outcome(event, outcome)
    elif outcome == "reject":
        # Per §3.26.16.14 revocation discipline: rejecting tenant marks
        # pairing.revoked_at. Partner tenant retains audit log per canon.
        pairing.revoked_at = datetime.now(timezone.utc)

    db.flush()
    _audit_calendar_action(
        db,
        event=event,
        action_idx=action_idx,
        action_type="joint_event_acceptance",
        outcome=outcome,
        auth_method=auth_method,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        target_type="cross_tenant_event",
        target_id=str(pairing_id),
        target_status=("paired" if pairing.paired_at and not pairing.revoked_at else
                       ("revoked" if pairing.revoked_at else "pending")),
        completion_note=completion_note,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return CommitResult(
        updated_action=updated_action,
        target_status=(
            "paired" if pairing.paired_at and not pairing.revoked_at else
            ("revoked" if pairing.revoked_at else "pending")
        ),
        counter_action_idx=counter_idx,
        pairing_id=str(pairing_id),
    )


def _commit_handler_recurring_meeting_proposal(
    db: Session,
    *,
    action: dict[str, Any],
    outcome: str,
    descriptor: ActionTypeDescriptor,
    actor_user_id: str | None,
    actor_email: str | None,
    auth_method: str,
    completion_metadata: dict[str, Any],
    completion_note: str | None,
    ip_address: str | None,
    user_agent: str | None,
    event: CalendarEvent,
    action_idx: int,
    counter_proposed_start_at: datetime | None = None,
    counter_proposed_end_at: datetime | None = None,
    **_: Any,
) -> CommitResult:
    """recurring_meeting_proposal commit handler — finalizes recurring pairing.

    Per Q4 confirmed (en bloc semantics): single acceptance creates the
    recurring pairing; per-instance overrides via existing
    calendar_event_instance_overrides substrate (Step 2 RRULE engine).
    """
    pairing_id = action.get("action_target_id")
    if not pairing_id:
        raise ActionError(
            "recurring_meeting_proposal action is missing action_target_id."
        )

    proposing_name = (
        action.get("action_metadata") or {}
    ).get("proposing_tenant_name", "Bridgeable tenant")

    updated_action, counter_idx = _shared_commit(
        db,
        event=event,
        action_idx=action_idx,
        action=action,
        outcome=outcome,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        auth_method=auth_method,
        completion_metadata=completion_metadata,
        completion_note=completion_note,
        ip_address=ip_address,
        user_agent=user_agent,
        counter_proposed_start_at=counter_proposed_start_at,
        counter_proposed_end_at=counter_proposed_end_at,
        proposing_tenant_name=proposing_name,
    )

    pairing = (
        db.query(CrossTenantEventPairing)
        .filter(CrossTenantEventPairing.id == pairing_id)
        .first()
    )
    if pairing is None:
        raise ActionNotFound(
            f"CrossTenantEventPairing {pairing_id!r} not found."
        )

    target_status: str | None = None
    if outcome == "accept":
        # En bloc per Q4: single acceptance finalizes the recurring
        # pairing. Recurrence rule already lives on event.recurrence_rule
        # from event creation; per-instance overrides via existing
        # calendar_event_instance_overrides substrate.
        if pairing.paired_at is None:
            pairing.paired_at = datetime.now(timezone.utc)
        _propagate_event_state_for_outcome(event, outcome)
        target_status = "paired_recurring"
    elif outcome == "reject":
        pairing.revoked_at = datetime.now(timezone.utc)
        target_status = "revoked"

    db.flush()
    _audit_calendar_action(
        db,
        event=event,
        action_idx=action_idx,
        action_type="recurring_meeting_proposal",
        outcome=outcome,
        auth_method=auth_method,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        target_type="cross_tenant_event",
        target_id=str(pairing_id),
        target_status=target_status,
        completion_note=completion_note,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return CommitResult(
        updated_action=updated_action,
        target_status=target_status,
        counter_action_idx=counter_idx,
        pairing_id=str(pairing_id),
    )


def _commit_handler_event_reschedule_proposal(
    db: Session,
    *,
    action: dict[str, Any],
    outcome: str,
    descriptor: ActionTypeDescriptor,
    actor_user_id: str | None,
    actor_email: str | None,
    auth_method: str,
    completion_metadata: dict[str, Any],
    completion_note: str | None,
    ip_address: str | None,
    user_agent: str | None,
    event: CalendarEvent,
    action_idx: int,
    counter_proposed_start_at: datetime | None = None,
    counter_proposed_end_at: datetime | None = None,
    **_: Any,
) -> CommitResult:
    """event_reschedule_proposal commit handler — propagates reschedule + cascade.

    Per §3.26.16.17 + §14.10.5 reschedule flow: on accept, event time
    updates to proposed_start_at / proposed_end_at; cascade impact
    (linked entities + paired cross-tenant events) recorded in audit
    metadata so downstream handlers can apply propagation.
    """
    target_id = action.get("action_target_id")
    if not target_id or target_id != event.id:
        raise ActionError(
            "event_reschedule_proposal action_target_id must match event.id."
        )

    proposing_name = (
        action.get("action_metadata") or {}
    ).get("proposing_tenant_name", "Bridgeable tenant")

    updated_action, counter_idx = _shared_commit(
        db,
        event=event,
        action_idx=action_idx,
        action=action,
        outcome=outcome,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        auth_method=auth_method,
        completion_metadata=completion_metadata,
        completion_note=completion_note,
        ip_address=ip_address,
        user_agent=user_agent,
        counter_proposed_start_at=counter_proposed_start_at,
        counter_proposed_end_at=counter_proposed_end_at,
        proposing_tenant_name=proposing_name,
    )

    target_status: str | None = None
    if outcome == "accept":
        # Apply reschedule per action_metadata.proposed_start_at /
        # proposed_end_at. Parse from ISO string back to datetime.
        metadata = action.get("action_metadata") or {}
        try:
            new_start = datetime.fromisoformat(metadata["proposed_start_at"])
            new_end = datetime.fromisoformat(metadata["proposed_end_at"])
        except (KeyError, ValueError) as exc:
            raise ActionError(
                f"event_reschedule_proposal action_metadata invalid: {exc}"
            ) from exc

        event.start_at = new_start
        event.end_at = new_end
        # Status stays "confirmed" (reschedule is a confirmed-event mutation).
        target_status = f"rescheduled_to_{new_start.isoformat()}"

    db.flush()
    _audit_calendar_action(
        db,
        event=event,
        action_idx=action_idx,
        action_type="event_reschedule_proposal",
        outcome=outcome,
        auth_method=auth_method,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        target_type="calendar_event",
        target_id=str(target_id),
        target_status=target_status,
        completion_note=completion_note,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return CommitResult(
        updated_action=updated_action,
        target_status=target_status,
        counter_action_idx=counter_idx,
    )


# ─────────────────────────────────────────────────────────────────────
# Audit log helper
# ─────────────────────────────────────────────────────────────────────


def _audit_calendar_action(
    db: Session,
    *,
    event: CalendarEvent,
    action_idx: int,
    action_type: str,
    outcome: str,
    auth_method: str,
    actor_user_id: str | None,
    actor_email: str | None,
    target_type: str,
    target_id: str,
    target_status: str | None,
    completion_note: str | None,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    """Write canonical Calendar action audit row per §3.26.15.8 transparency."""
    _audit(
        db,
        tenant_id=event.tenant_id,
        actor_user_id=actor_user_id,
        action="calendar_action_committed",
        entity_type="calendar_event",
        entity_id=event.id,
        changes={
            "action_idx": action_idx,
            "action_type": action_type,
            "outcome": outcome,
            "auth_method": auth_method,
            "target_type": target_type,
            "target_id": target_id,
            "target_status": target_status,
            "actor_email": (actor_email or "").lower().strip() or None,
            "has_completion_note": bool(completion_note),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


# ─────────────────────────────────────────────────────────────────────
# Side-effect registration — runs at module import time so the central
# registry is populated when Calendar package imports this module via
# its __init__. Idempotent per registry semantics.
# ─────────────────────────────────────────────────────────────────────


_CANONICAL_DESCRIPTORS = (
    ActionTypeDescriptor(
        action_type="service_date_acceptance",
        primitive="calendar",
        target_entity_type="fh_case",
        outcomes=ACTION_OUTCOMES_CALENDAR,
        terminal_outcomes=ACTION_OUTCOMES_CALENDAR,
        requires_completion_note=("counter_propose",),
        commit_handler=_commit_handler_service_date_acceptance,
    ),
    ActionTypeDescriptor(
        action_type="delivery_date_acceptance",
        primitive="calendar",
        target_entity_type="sales_order",
        outcomes=ACTION_OUTCOMES_CALENDAR,
        terminal_outcomes=ACTION_OUTCOMES_CALENDAR,
        requires_completion_note=("counter_propose",),
        commit_handler=_commit_handler_delivery_date_acceptance,
    ),
    ActionTypeDescriptor(
        action_type="joint_event_acceptance",
        primitive="calendar",
        target_entity_type="cross_tenant_event",
        outcomes=ACTION_OUTCOMES_CALENDAR,
        terminal_outcomes=ACTION_OUTCOMES_CALENDAR,
        requires_completion_note=("counter_propose",),
        commit_handler=_commit_handler_joint_event_acceptance,
    ),
    ActionTypeDescriptor(
        action_type="recurring_meeting_proposal",
        primitive="calendar",
        target_entity_type="cross_tenant_event",
        outcomes=ACTION_OUTCOMES_CALENDAR,
        terminal_outcomes=ACTION_OUTCOMES_CALENDAR,
        requires_completion_note=("counter_propose",),
        commit_handler=_commit_handler_recurring_meeting_proposal,
    ),
    ActionTypeDescriptor(
        action_type="event_reschedule_proposal",
        primitive="calendar",
        target_entity_type="calendar_event",
        outcomes=ACTION_OUTCOMES_CALENDAR,
        terminal_outcomes=ACTION_OUTCOMES_CALENDAR,
        requires_completion_note=("counter_propose",),
        commit_handler=_commit_handler_event_reschedule_proposal,
    ),
)


for _d in _CANONICAL_DESCRIPTORS:
    register_action_type(_d)


# ─────────────────────────────────────────────────────────────────────
# Public exports
# ─────────────────────────────────────────────────────────────────────


__all__ = [
    # Canonical vocabulary
    "ACTION_TYPES",
    "ACTION_OUTCOMES_CALENDAR",
    "ACTION_STATUSES",
    "TOKEN_TTL_DAYS",
    # Action-shape helpers
    "build_service_date_acceptance_action",
    "build_delivery_date_acceptance_action",
    "build_joint_event_acceptance_action",
    "build_recurring_meeting_proposal_action",
    "build_event_reschedule_proposal_action",
    # action_payload accessors
    "get_event_actions",
    "get_action_at_index",
    "append_action_to_event",
    "replace_action_at_index",
    # Token CRUD facade
    "issue_action_token",
    "lookup_action_token",
    "consume_action_token",
    "lookup_token_row_raw",
    "generate_action_token",
    # Commit facade
    "CommitResult",
    "commit_action",
    # Reschedule cascade computation
    "compute_reschedule_cascade",
    # Counter-proposal chaining
    "chain_counter_proposal",
    # Magic-link URL helper
    "build_magic_link_url",
    # Errors (re-exported from substrate)
    "PlatformActionError",
    "ActionError",
    "ActionNotFound",
    "ActionAlreadyCompleted",
    "ActionTokenInvalid",
    "ActionTokenExpired",
    "ActionTokenAlreadyConsumed",
    "CrossPrimitiveTokenMismatch",
]
