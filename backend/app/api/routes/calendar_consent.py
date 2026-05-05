"""Calendar PTR consent upgrade UI write-side — Phase W-4b Layer 1 Step 4.1.

Per §3.26.16.6 + §3.26.16.14 + §3.26.11.10 cross-tenant Focus consent
canonical precedent: bilateral consent state machine for
``platform_tenant_relationships.calendar_freebusy_consent``. Read-side
shipped at Step 3 (``freebusy_service.query_cross_tenant_freebusy``);
Step 4.1 ships write-side UI + state machine + audit + notifications.

Four endpoints:
  - ``GET /api/v1/calendar/consent`` — list partner tenants + per-relationship
    consent state for the current tenant.
  - ``POST /api/v1/calendar/consent/{relationship_id}/request`` —
    flip caller's PTR row to ``full_details`` (request bilateral upgrade).
    State transition: default → pending_outbound (or pending_inbound → active
    if partner already at full_details).
  - ``POST /api/v1/calendar/consent/{relationship_id}/accept`` —
    flip caller's PTR row to ``full_details`` to accept partner's pending
    request. State transition: pending_inbound → active.
  - ``POST /api/v1/calendar/consent/{relationship_id}/revoke`` —
    flip caller's PTR row back to ``free_busy_only``. State transition:
    pending_outbound | active → default | pending_inbound.

Authorization: caller must be authenticated tenant member; relationship
ownership enforced at service layer (existence-hiding 404 if relationship
not owned by caller's tenant). Calendar consent management is admin-
relevant by canon (§3.26.16.6 bilateral consent prevents asymmetric
disclosure power dynamics) — endpoint requires authenticated user; the
settings page UI gates by admin role at the route layer.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.calendar import ptr_consent_service
from app.services.calendar.account_service import CalendarAccountError
from app.services.calendar.ptr_consent_service import (
    PtrConsentError,
    PtrConsentInvalidTransition,
    PtrConsentNotFound,
    PtrConsentPermissionDenied,
)

logger = logging.getLogger(__name__)


router = APIRouter()


# ─────────────────────────────────────────────────────────────────────
# Pydantic shapes
# ─────────────────────────────────────────────────────────────────────


class PartnerConsentRow(BaseModel):
    relationship_id: str
    relationship_type: str
    partner_tenant_id: str
    partner_tenant_name: str | None
    this_side_consent: Literal["free_busy_only", "full_details"]
    partner_side_consent: Literal["free_busy_only", "full_details"] | None
    state: Literal[
        "default",
        "pending_outbound",
        "pending_inbound",
        "active",
    ]
    updated_at: str | None = Field(
        default=None,
        description=(
            "ISO datetime of last consent state mutation, or null when "
            "consent has never been changed (default-state row from "
            "pre-Step-4.1 era)."
        ),
    )
    updated_by_user_id: str | None


class ConsentListResponse(BaseModel):
    partners: list[PartnerConsentRow]


class ConsentTransitionResponse(BaseModel):
    relationship_id: str
    partner_tenant_id: str
    prior_state: Literal[
        "default",
        "pending_outbound",
        "pending_inbound",
        "active",
    ]
    new_state: Literal[
        "default",
        "pending_outbound",
        "pending_inbound",
        "active",
    ]


# ─────────────────────────────────────────────────────────────────────
# Error translation
# ─────────────────────────────────────────────────────────────────────


def _translate(exc: CalendarAccountError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=exc.message)


# ─────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────


@router.get("/consent", response_model=ConsentListResponse)
def list_consent_states(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConsentListResponse:
    """List partner tenants + per-relationship consent state.

    Returns one row per PTR row owned by the caller's tenant. Consent
    state resolved via ``resolve_consent_state(forward, reverse)``.
    """
    rows = ptr_consent_service.list_partner_consent_states(
        db, tenant_id=current_user.company_id
    )
    return ConsentListResponse(
        partners=[PartnerConsentRow(**r) for r in rows]
    )


@router.post(
    "/consent/{relationship_id}/request",
    response_model=ConsentTransitionResponse,
    status_code=200,
)
def post_request_upgrade(
    relationship_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConsentTransitionResponse:
    """Request bilateral consent upgrade.

    Flips caller's PTR row to ``full_details`` + writes audit log +
    fires V-1d notification to partner tenant's admins.

    Per §3.26.16.6 + §3.26.11.10: partner tenant must explicitly accept
    via ``/accept`` for bilateral consent to activate.
    """
    try:
        result = ptr_consent_service.request_upgrade(
            db,
            requesting_tenant_id=current_user.company_id,
            relationship_id=relationship_id,
            requested_by_user_id=current_user.id,
        )
        db.commit()
        return ConsentTransitionResponse(**result)
    except CalendarAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


@router.post(
    "/consent/{relationship_id}/accept",
    response_model=ConsentTransitionResponse,
    status_code=200,
)
def post_accept_upgrade(
    relationship_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConsentTransitionResponse:
    """Accept partner's pending consent upgrade request.

    Flips caller's PTR row to ``full_details`` + writes per-side audit
    logs to BOTH tenants' scopes (joint event per §3.26.11.10) + fires
    notification to requesting tenant's admins.

    Valid only when partner has already requested upgrade (state=
    pending_inbound). Use ``/request`` to initiate the bilateral flow
    from this side.
    """
    try:
        result = ptr_consent_service.accept_upgrade(
            db,
            accepting_tenant_id=current_user.company_id,
            relationship_id=relationship_id,
            accepted_by_user_id=current_user.id,
        )
        db.commit()
        return ConsentTransitionResponse(**result)
    except CalendarAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


@router.post(
    "/consent/{relationship_id}/revoke",
    response_model=ConsentTransitionResponse,
    status_code=200,
)
def post_revoke_upgrade(
    relationship_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConsentTransitionResponse:
    """Revoke this side's consent (drops bilateral if active, cancels if pending).

    Per §3.26.16.6 + §3.26.11.10: "either tenant can unilaterally
    revoke". Flips caller's PTR row back to ``free_busy_only`` + writes
    per-side audit logs + fires notification to partner tenant's admins.
    """
    try:
        result = ptr_consent_service.revoke_upgrade(
            db,
            revoking_tenant_id=current_user.company_id,
            relationship_id=relationship_id,
            revoked_by_user_id=current_user.id,
        )
        db.commit()
        return ConsentTransitionResponse(**result)
    except CalendarAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc
