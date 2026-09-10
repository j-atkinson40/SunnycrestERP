"""Per-customer composition sources — email threads and calendar events.

⚠️ THESE TWO ENDPOINTS SURVIVED THE PULSE REMOVAL AND ALMOST DID NOT.

They lived in `api/routes/pulse.py` and were mounted under the `/pulse`
prefix, so a removal scoped by filename and route prefix took them with it.
Neither is Pulse. They are per-customer composition SOURCES — "give me this
customer's recent email threads / calendar events" — and they were only ever
adjacent to Pulse because Pulse was the first surface expected to consume them.

Caught 2026-09-10 by three failing tests in `test_email_primitive_step5.py`,
not by the consumer enumeration that preceded the removal, because that
enumeration looked for importers of pulse MODULES and these are neither
importers nor modules. Filename-shaped scope, third instance in this arc.

⚠️ THE URL IS DELIBERATELY UNCHANGED — `/api/v1/pulse/...` — AND IS NOW A
MISNOMER. Preserving behaviour exactly was the conservative move while Pulse
came out; renaming the prefix is a separate decision with no consumer pressure
behind it (no frontend calls either endpoint; the only caller is a test).
Ruling owed. Do not treat the prefix as evidence that Pulse still exists.

Consumers, enumerated 2026-09-10: zero frontend callers; one backend test
suite. Both endpoints are documented as resources for scoped-surface
consumption that has not shipped — i.e. correct machinery behind an entrance
nothing has walked through yet.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User

router = APIRouter()


# ── Phase W-4b Layer 1 Step 5 — customer email threads composition source ──


@router.get("/email-threads-for-customer/{customer_entity_id}")
def get_customer_email_threads(
    customer_entity_id: str,
    limit: int = Query(
        default=5,
        ge=1,
        le=50,
        description=(
            "Max threads to return. Default 5 matches Customer Pulse "
            "template default slot capacity per §3.26.12.4 Layer A. "
            "Hard ceiling 50."
        ),
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Recent email threads scoped to a customer (CompanyEntity).

    Per §3.26.12.3 composition sources canon: Customer Pulse template
    composes recent threads filtered to the orchestration entity.

    **Step 5 ships data-layer-only**: this endpoint establishes the
    canonical query pattern. Customer Pulse template extension (slot
    mapping declaration) deferred until scoped Pulse infrastructure
    ships per §3.26.12.4.

    **This is the canonical resource for future scoped Pulse Customer
    Pulse consumption** — when scoped Pulse summoning + per-template
    slot mapping infrastructure lands, the Customer Pulse template's
    email_threads slot consumes this endpoint rather than building
    parallel query patterns.

    **Two-source resolution**: matches threads via (1) explicit
    EmailThreadLinkage with linked_entity_type="customer", (2)
    EmailParticipant resolved to this CompanyEntity. Union, deduped,
    sorted by last_message_at DESC, capped at `limit`.

    **Tenant isolation**: customer_entity_id must belong to caller's
    tenant; cross-tenant probes return existence-hiding empty payload
    (404-shaped — `{customer_entity_id, customer_name: null,
    threads: [], total_count: 0}`).

    **Access enforcement**: only threads on accounts the caller has
    read access on (per EmailAccountAccess) surface.

    **Performance**: p50 < 300ms per Step 5 spec (matches scoped Pulse
    composition resolution budget per §3.26.12.4 Layer B).
    """
    from app.services.email.customer_email_threads_service import (
        get_threads_for_customer,
    )

    return get_threads_for_customer(
        db,
        customer_entity_id=customer_entity_id,
        user=current_user,
        limit=limit,
    )


# ── Phase W-4b Layer 1 Calendar Step 5 — customer calendar events composition source ──


@router.get("/calendar-events-for-customer/{customer_entity_id}")
def get_customer_calendar_events(
    customer_entity_id: str,
    limit: int = Query(
        default=5,
        ge=1,
        le=50,
        description=(
            "Max events per bucket (recent + upcoming). Default 5 "
            "matches Customer Pulse template default slot capacity per "
            "§3.26.12.4 Layer A. Hard ceiling 50."
        ),
    ),
    upcoming_window_days: int = Query(default=60, ge=1, le=365),
    recent_window_days: int = Query(default=60, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Recent + upcoming calendar events scoped to a customer (CompanyEntity).

    Per §3.26.12.3 composition sources canon + §3.26.16.10 row 4
    Customer Pulse events surface. Customer Pulse template composes
    recent + upcoming events filtered to the orchestration entity.

    **Step 5 ships data-layer-only** per Email Step 5 precedent: this
    endpoint establishes the canonical query pattern. Customer Pulse
    template extension (slot mapping declaration) deferred until
    scoped Pulse infrastructure ships per §3.26.12.4.

    **Multi-source resolution**: matches events via (1) explicit
    CalendarEventLinkage(linked_entity_type='customer'), (2) indirect
    via fh_case → Customer.master_company_id, (3) indirect via
    sales_order → Customer.master_company_id, (4) attendee
    resolved_company_entity_id.

    **Tenant isolation**: customer_entity_id must belong to caller's
    tenant; cross-tenant probes return existence-hiding empty payload.

    **Access enforcement**: only events on accounts the caller has
    read access on (per CalendarAccountAccess) surface.

    **Performance**: p50 < 300ms per Step 5 spec.
    """
    from app.services.calendar.customer_calendar_events_service import (
        get_calendar_events_for_customer,
    )

    return get_calendar_events_for_customer(
        db,
        customer_entity_id=customer_entity_id,
        caller_tenant_id=current_user.company_id,
        caller_user_id=current_user.id,
        limit=limit,
        upcoming_window_days=upcoming_window_days,
        recent_window_days=recent_window_days,
    )
