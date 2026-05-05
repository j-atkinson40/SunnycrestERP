"""Calendar Free/Busy API — Phase W-4b Layer 1 Calendar Step 3.

Two endpoints per §3.26.16.14 + Step 3 build prompt:

  - ``GET /api/v1/calendar/free-busy?account_id=...&start=...&end=...``
    Per-account internal freebusy. Tenant-scoped via current_user;
    requires ``read`` access on the account.

  - ``GET /api/v1/calendar/free-busy/cross-tenant?partner_tenant_id=...``
    Cross-tenant freebusy with consent enforcement per §3.26.16.14 +
    §3.26.16.6 three-tier anonymization granularity.

Both endpoints query canonical recurrence engine (Step 2 substrate)
per §3.26.16.4 RRULE-as-source-of-truth. Last-sync staleness disclosure
per §3.26.16.8 transparency discipline.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.calendar import account_service, freebusy_service
from app.services.calendar.account_service import (
    CalendarAccountError,
)
from app.services.calendar.freebusy_service import (
    CrossTenantConsentDenied,
    FreebusyError,
    FreebusyWindow,
    FreebusyResult,
)


router = APIRouter()


# ─────────────────────────────────────────────────────────────────────
# Pydantic response shapes
# ─────────────────────────────────────────────────────────────────────


class FreebusyWindowResponse(BaseModel):
    start: str
    end: str
    status: Literal["busy", "tentative", "out_of_office"]
    # Full-details fields per §3.26.16.6 — only populated when consent
    # allows + matching internal/full_details query path.
    subject: str | None = None
    location: str | None = None
    attendee_count_bucket: str | None = None

    @classmethod
    def from_window(cls, w: FreebusyWindow) -> FreebusyWindowResponse:
        return cls(
            start=w.start_at.isoformat(),
            end=w.end_at.isoformat(),
            status=w.status,
            subject=w.subject,
            location=w.location,
            attendee_count_bucket=w.attendee_count_bucket,
        )


class FreebusyResponse(BaseModel):
    """Per-account freebusy response (internal scope)."""

    windows: list[FreebusyWindowResponse]
    last_sync_at: str | None
    stale: bool
    account_id: str


class CrossTenantFreebusyResponse(BaseModel):
    """Cross-tenant freebusy response per §3.26.16.14 canonical shape."""

    partner_tenant_id: str
    windows: list[FreebusyWindowResponse]
    consent_level: Literal["free_busy_only", "full_details"]
    last_sync_at: str | None
    stale: bool


# ─────────────────────────────────────────────────────────────────────
# Error translation
# ─────────────────────────────────────────────────────────────────────


def _translate(exc: CalendarAccountError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=exc.message)


# ─────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────


@router.get("/free-busy", response_model=FreebusyResponse)
def get_per_account_freebusy(
    account_id: str = Query(min_length=1),
    start: datetime = Query(...),
    end: datetime = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FreebusyResponse:
    """Query internal per-account freebusy.

    Tenant-scoped via current_user.company_id; requires ``read`` access
    on the calendar account. Returns event-precision windows with full
    subject + location detail (consent_level="internal").
    """
    try:
        if not account_service.user_has_access(
            db,
            account_id=account_id,
            user_id=current_user.id,
            minimum_level="read",
        ):
            raise HTTPException(
                status_code=403,
                detail=(
                    f"User does not have read access on calendar account "
                    f"{account_id!r}."
                ),
            )
        result = freebusy_service.query_per_account_freebusy(
            db,
            tenant_id=current_user.company_id,
            account_id=account_id,
            range_start=start,
            range_end=end,
        )
        return FreebusyResponse(
            windows=[FreebusyWindowResponse.from_window(w) for w in result.windows],
            last_sync_at=(
                result.last_sync_at.isoformat() if result.last_sync_at else None
            ),
            stale=result.stale,
            account_id=account_id,
        )
    except CalendarAccountError as exc:
        raise _translate(exc) from exc


@router.get(
    "/free-busy/cross-tenant",
    response_model=CrossTenantFreebusyResponse,
)
def get_cross_tenant_freebusy(
    partner_tenant_id: str = Query(min_length=1),
    start: datetime = Query(...),
    end: datetime = Query(...),
    granularity: Literal["hour", "day"] = Query(default="hour"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CrossTenantFreebusyResponse:
    """Query cross-tenant freebusy per §3.26.16.14 canonical endpoint.

    Privacy-preserving by default (consent_level="free_busy_only";
    busy/free + status only). Bilateral consent unlocks full_details
    (subject + location + attendee_count_bucket per §3.26.16.6
    three-tier anonymization granularity).

    Raises 403 (CrossTenantConsentDenied) when no active
    platform_tenant_relationships row connects the requesting tenant
    to the partner.
    """
    try:
        result = freebusy_service.query_cross_tenant_freebusy(
            db,
            requesting_tenant_id=current_user.company_id,
            partner_tenant_id=partner_tenant_id,
            range_start=start,
            range_end=end,
            granularity=granularity,
        )
        return CrossTenantFreebusyResponse(
            partner_tenant_id=partner_tenant_id,
            windows=[FreebusyWindowResponse.from_window(w) for w in result.windows],
            consent_level=result.consent_level,  # type: ignore[arg-type]
            last_sync_at=(
                result.last_sync_at.isoformat() if result.last_sync_at else None
            ),
            stale=result.stale,
        )
    except CalendarAccountError as exc:
        raise _translate(exc) from exc
