"""Calendar consent-pending widget data service — Phase W-4b Layer 1
Calendar Step 5.1.

Surfaces cross-tenant calendar consent upgrade requests pending this
tenant's response per §3.26.16.10 Pulse Communications Layer canon.
Pattern parallels ``calendar_glance_service`` Step 5 widget verbatim.

**Signals computed**:
  - ``has_pending`` — bool driving empty-state vs populated rendering
  - ``pending_consent_count`` — count of ``state='pending_inbound'``
    PTR consent rows (partner has opted into ``full_details``; this
    side hasn't accepted yet)
  - ``top_requester_name`` — most-recent pending requester's tenant
    label (per §3.26.9.4 anonymization-at-layer canonical — tenant-
    level, not user-level)
  - ``top_requester_tenant_label`` — same as ``top_requester_name``
    today; kept as separate field for forward-compat with mixed
    requester labeling (e.g., relationship-aware naming)
  - ``target_relationship_id`` — set ONLY when single pending request
    surfaces (drives direct ``?relationship_id={id}`` deep-link to
    settings page; multi-request surface lands on plain
    ``/settings/calendar/freebusy-consent``)

**Communications Layer scope discipline** per §3.26.16.10 hybrid
contribution: this widget surfaces interpersonal-coordination signals
only ("partner needs my response on consent"). Operational schedule
signals route separately via ``calendar_summary`` + ``today_widget``.

**Tenant isolation discipline** (mirrors ``calendar_glance``):
``ptr_consent_service.list_partner_consent_states`` already
tenant-scopes via ``PlatformTenantRelationship.tenant_id ==
caller_tenant_id``; this service relies on that contract and adds no
new isolation surface.

**View-only widget per §12.6a**: count + click-through to settings
page. Accept / decline / revoke happens on the settings page
(``/settings/calendar/freebusy-consent``), NOT inline on the widget.

**Performance budget** (per Step 5 spec): p50 < 200ms — matches
``calendar_glance`` budget. Reuses ``list_partner_consent_states``;
zero new DB query needed beyond the partner-state walk that surface
already performs.

**Empty/disabled states**:
  - User's tenant has no PTR relationships at all → ``has_pending=False``,
    ``pending_consent_count=0`` (canonical empty state "No pending
    consent requests")
  - User's tenant has PTR relationships but none in ``pending_inbound``
    → same shape as above
  - User has at least one ``pending_inbound`` row → populated with
    count + top_requester
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.calendar.ptr_consent_service import (
    list_partner_consent_states,
)

logger = logging.getLogger(__name__)


def get_calendar_consent_pending(
    db: Session, *, user: User
) -> dict[str, Any]:
    """Return the calendar_consent_pending widget data payload.

    Returns a JSON-serializable dict with:
      - has_pending: bool — True iff at least one pending_inbound
        consent request exists for the caller's tenant
      - pending_consent_count: int
      - top_requester_name: str | None — most-recent pending
        requester's tenant name (best-effort)
      - top_requester_tenant_label: str | None — alias for
        forward-compat with mixed labeling
      - target_relationship_id: str | None — single-request direct
        link target

    Tenant isolation is enforced inside
    ``list_partner_consent_states`` (filters by ``tenant_id ==
    caller_tenant_id``); empty payload when caller has no tenant.
    """
    if not user.company_id:
        return _empty_payload()

    try:
        all_states = list_partner_consent_states(db, tenant_id=user.company_id)
    except Exception:  # noqa: BLE001
        # Per Step 4.1 best-effort discipline: widget data should never
        # crash the home Pulse render. Log + return empty payload so
        # the widget falls back to its empty-state chrome.
        logger.exception(
            "calendar_consent_pending: list_partner_consent_states "
            "failed for tenant_id=%s — returning empty payload",
            user.company_id,
        )
        return _empty_payload()

    # Filter to pending_inbound subset — partner has opted into
    # full_details + this side hasn't accepted yet. Per Step 4.1
    # ConsentState canon: pending_inbound = (this_side='free_busy_only',
    # partner_side='full_details').
    pending = [s for s in all_states if s.get("state") == "pending_inbound"]

    if not pending:
        return _empty_payload()

    # Order by updated_at DESC for top_requester resolution. The list
    # already comes ordered by connected_at DESC (PTR canonical order
    # at line 561); we re-sort by consent updated_at since that's the
    # canonical "most-recent request" signal for this widget.
    def _sort_key(row: dict[str, Any]) -> str:
        # ISO-8601 strings sort lexicographically as datetimes.
        # None values sort last via empty string fallback.
        return row.get("updated_at") or ""

    pending.sort(key=_sort_key, reverse=True)

    top = pending[0]
    top_requester_name = top.get("partner_tenant_name")

    # Single-request surface → direct deep-link target. Multi-request →
    # None so widget click resolves to plain settings page list view.
    target_relationship_id = (
        top.get("relationship_id") if len(pending) == 1 else None
    )

    return {
        "has_pending": True,
        "pending_consent_count": len(pending),
        "top_requester_name": top_requester_name,
        "top_requester_tenant_label": top_requester_name,
        "target_relationship_id": target_relationship_id,
    }


def _empty_payload() -> dict[str, Any]:
    """Return the canonical empty-state shape."""
    return {
        "has_pending": False,
        "pending_consent_count": 0,
        "top_requester_name": None,
        "top_requester_tenant_label": None,
        "target_relationship_id": None,
    }
