"""Portal API — Workflow Arc Phase 8e.2.

Public + portal-authed endpoints under `/api/v1/portal/*`.

Route tree:
  Public (no auth):
    GET  /portal/{slug}/branding                 — tenant branding for login UI
    POST /portal/{slug}/login                    — credentials → JWT pair
    POST /portal/{slug}/refresh                  — refresh token → new access
    POST /portal/{slug}/password/recover/request — start recovery flow (email)
    POST /portal/{slug}/password/recover/confirm — set password via token

  Portal-authed:
    GET  /portal/me                              — current portal user
    GET  /portal/drivers/me/summary              — driver's at-a-glance data
                                                   (thin router over
                                                    delivery services)

Identity + realm boundary enforced by `get_current_portal_user` and
`get_current_portal_user_for_tenant`. See SPACES_ARCHITECTURE.md §10.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_portal_user,
    get_current_portal_user_for_tenant,
    get_portal_company_from_slug,
)
from app.database import get_db
from app.models.company import Company
from app.models.portal_user import PortalUser
from app.services.portal import (
    PortalAuthError,
    PortalLoginInvalid,
    PortalLoginLocked,
    authenticate_portal_user,
    create_portal_tokens,
    get_portal_branding,
    resolve_driver_for_portal_user,
    verify_portal_refresh_token,
)
from app.services.portal.auth import (
    PortalRateLimited,
    consume_recovery_token,
    issue_recovery_token,
)

router = APIRouter()


# ── Request / response schemas ───────────────────────────────────────


class _BrandingResponse(BaseModel):
    slug: str
    display_name: str
    logo_url: str | None
    brand_color: str
    footer_text: str | None


class _LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class _TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    # Portal space context for the UI (so it can pick the right
    # template / landing route without an extra round trip).
    space_id: str


class _RefreshRequest(BaseModel):
    refresh_token: str


class _RecoveryRequest(BaseModel):
    email: EmailStr


class _RecoveryConfirmRequest(BaseModel):
    token: str = Field(..., min_length=16)
    new_password: str = Field(..., min_length=8)


class _MeResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    company_id: str
    assigned_space_id: str | None


class _DriverSummaryResponse(BaseModel):
    """Minimal driver summary for the portal driver home page.
    Phase 8e.2 ships the reconnaissance: driver identity + today's
    stops count (derived from existing deliveries). Full driver data
    mirror endpoints land in 8e.2.1 when the remaining pages mount.
    """

    portal_user_id: str
    driver_id: str | None
    driver_name: str
    today_stops_count: int
    tenant_display_name: str


# ── Public endpoints ────────────────────────────────────────────────


@router.get(
    "/{tenant_slug}/branding",
    response_model=_BrandingResponse,
)
def read_branding(
    tenant_slug: str,
    db: Session = Depends(get_db),
) -> _BrandingResponse:
    """Public — load tenant branding for the portal login page
    before authentication. No data leaks beyond existing public
    fields (logo already appears on emails + public-ish surfaces).
    """
    branding = get_portal_branding(db, slug=tenant_slug)
    if branding is None:
        raise HTTPException(status_code=404, detail="Portal not found")
    return _BrandingResponse(
        slug=branding.slug,
        display_name=branding.display_name,
        logo_url=branding.logo_url,
        brand_color=branding.brand_color,
        footer_text=branding.footer_text,
    )


@router.post("/{tenant_slug}/login", response_model=_TokenPair)
def portal_login(
    tenant_slug: str,
    body: _LoginRequest,
    request: Request,
    company: Company = Depends(get_portal_company_from_slug),
    db: Session = Depends(get_db),
) -> _TokenPair:
    """Authenticate a portal user against a tenant. Returns a portal-
    realm JWT pair on success.

    Security posture (per SPACES_ARCHITECTURE.md §10):
      - Generic "Invalid email or password" on any failure except
        lockout + rate-limit (which need distinct copy so the user
        knows to wait).
      - Account locks after 10 failed attempts for 30 minutes.
      - IP+email rate limit: 10 attempts / 30 min per worker.
    """
    client_ip = request.client.host if request.client else "unknown"
    try:
        portal_user = authenticate_portal_user(
            db,
            company=company,
            email=body.email,
            password=body.password,
            client_ip=client_ip,
        )
    except PortalRateLimited as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except PortalLoginLocked as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except PortalLoginInvalid as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    # Resolve per-space TTL override if the user has an assigned
    # space with session_timeout_minutes set.
    access_ttl_minutes = _resolve_access_ttl_for_portal_user(
        db, portal_user=portal_user, company=company
    )

    tokens = create_portal_tokens(
        portal_user, access_ttl_minutes=access_ttl_minutes
    )
    return _TokenPair(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        space_id=portal_user.assigned_space_id or "",
    )


@router.post("/{tenant_slug}/refresh", response_model=_TokenPair)
def portal_refresh(
    tenant_slug: str,
    body: _RefreshRequest,
    company: Company = Depends(get_portal_company_from_slug),
    db: Session = Depends(get_db),
) -> _TokenPair:
    """Exchange a valid portal refresh token for a new access +
    refresh pair. Tenant scope enforced from the URL path."""
    try:
        payload = verify_portal_refresh_token(body.refresh_token)
    except PortalAuthError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc

    if payload.get("company_id") != company.id:
        raise HTTPException(
            status_code=401, detail="Token does not match this portal"
        )

    user_id = payload.get("sub")
    portal_user = (
        db.query(PortalUser)
        .filter(
            PortalUser.id == user_id,
            PortalUser.company_id == company.id,
        )
        .first()
    )
    if portal_user is None or not portal_user.is_active:
        raise HTTPException(status_code=401, detail="Portal user not found or inactive")

    access_ttl = _resolve_access_ttl_for_portal_user(
        db, portal_user=portal_user, company=company
    )
    tokens = create_portal_tokens(portal_user, access_ttl_minutes=access_ttl)
    return _TokenPair(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        space_id=portal_user.assigned_space_id or "",
    )


@router.post(
    "/{tenant_slug}/password/recover/request",
    response_class=Response,
)
def request_password_recovery(
    tenant_slug: str,
    body: _RecoveryRequest,
    company: Company = Depends(get_portal_company_from_slug),
    db: Session = Depends(get_db),
) -> Response:
    """Start the password-recovery flow — issue a 1-hour token and
    email it via the D-7 delivery layer. Returns 204 regardless of
    whether the email exists (prevents email-enumeration).

    Phase 8e.2 ships the backend; the email template key
    `email.portal_password_recovery` is seeded via the seed script
    for dev + staging (prod tenants get it on next migration run).
    """
    email_clean = body.email.lower().strip()
    portal_user = (
        db.query(PortalUser)
        .filter(
            PortalUser.company_id == company.id,
            PortalUser.email == email_clean,
        )
        .first()
    )
    if portal_user is None or not portal_user.is_active:
        # Silent — same response as success, no email sent.
        return Response(status_code=204)

    token = issue_recovery_token(db, user=portal_user)

    # Best-effort send via D-7 delivery layer.
    try:
        from app.services.delivery_service import send_email_with_template

        send_email_with_template(
            db,
            template_key="email.portal_password_recovery",
            company_id=company.id,
            recipient={
                "name": f"{portal_user.first_name} {portal_user.last_name}",
                "value": portal_user.email,
                "type": "email",
            },
            subject=f"{company.name} — Reset your portal password",
            template_context={
                "first_name": portal_user.first_name,
                "tenant_name": company.name,
                "reset_url": (
                    f"/portal/{company.slug}/reset-password"
                    f"?token={token}"
                ),
                "expires_in": "1 hour",
            },
            caller_module="portal.password_recovery",
        )
    except Exception:
        # Don't leak failure to the client. Log server-side.
        import logging

        logging.getLogger(__name__).exception(
            "Portal password recovery email send failed for "
            "portal_user=%s tenant=%s",
            portal_user.id,
            company.slug,
        )
    return Response(status_code=204)


@router.post(
    "/{tenant_slug}/password/recover/confirm",
    response_class=Response,
)
def confirm_password_recovery(
    tenant_slug: str,
    body: _RecoveryConfirmRequest,
    company: Company = Depends(get_portal_company_from_slug),
    db: Session = Depends(get_db),
) -> Response:
    """Exchange a valid recovery token + new password for a set
    password. Token is single-use; cleared on success."""
    try:
        consume_recovery_token(
            db,
            company=company,
            token=body.token,
            new_password=body.new_password,
        )
    except PortalAuthError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=204)


# ── Portal-authed endpoints ─────────────────────────────────────────


@router.get("/me", response_model=_MeResponse)
def read_me(
    portal_user: PortalUser = Depends(get_current_portal_user),
) -> _MeResponse:
    return _MeResponse(
        id=portal_user.id,
        email=portal_user.email,
        first_name=portal_user.first_name,
        last_name=portal_user.last_name,
        company_id=portal_user.company_id,
        assigned_space_id=portal_user.assigned_space_id,
    )


@router.get(
    "/drivers/me/summary",
    response_model=_DriverSummaryResponse,
)
def read_driver_summary(
    portal_user: PortalUser = Depends(get_current_portal_user),
    db: Session = Depends(get_db),
) -> _DriverSummaryResponse:
    """Phase 8e.2 minimal driver summary — identity + today's stop
    count. Proves the portal → driver resolution → service-layer
    pattern documented in SPACES_ARCHITECTURE.md §10.7 (thin router
    over existing service). Phase 8e.2.1 ships the full driver
    data mirror endpoints.
    """
    driver = resolve_driver_for_portal_user(db, portal_user=portal_user)

    tenant = db.query(Company).filter(Company.id == portal_user.company_id).first()
    tenant_name = tenant.name if tenant else ""

    if driver is None:
        # Portal user exists but admin hasn't linked them to a Driver
        # row yet. Phase 8e.2.1 admin UI fixes this; for now return
        # a graceful zero-summary.
        return _DriverSummaryResponse(
            portal_user_id=portal_user.id,
            driver_id=None,
            driver_name=f"{portal_user.first_name} {portal_user.last_name}",
            today_stops_count=0,
            tenant_display_name=tenant_name,
        )

    # Count today's delivery stops assigned to this driver.
    from app.models.delivery_stop import DeliveryStop
    from app.models.delivery_route import DeliveryRoute

    today = date.today()
    count = (
        db.query(DeliveryStop)
        .join(DeliveryRoute, DeliveryStop.route_id == DeliveryRoute.id)
        .filter(
            DeliveryRoute.driver_id == driver.id,
            DeliveryRoute.company_id == portal_user.company_id,
            DeliveryRoute.route_date == today,
        )
        .count()
    )

    return _DriverSummaryResponse(
        portal_user_id=portal_user.id,
        driver_id=driver.id,
        driver_name=f"{portal_user.first_name} {portal_user.last_name}",
        today_stops_count=count,
        tenant_display_name=tenant_name,
    )


# ── Phase 8e.2.1 — portal driver-data mirror endpoints ──────────────
#
# Thin routers over the existing `driver_mobile_service`. Portal
# token → portal_user → Driver → same business logic as the tenant-
# authed /driver/* endpoints. Canonical thin-router-over-service
# pattern (SPACES_ARCHITECTURE.md §10.7).
#
# Endpoint shape mirrors `routes/driver_mobile.py` under the
# `/portal/drivers/me/*` namespace. Adjacent to the Phase 8e.2
# `/portal/drivers/me/summary` that proved the pattern.


class _PortalRouteStopShape(BaseModel):
    """Lean per-stop response for portal driver UI. Matches the
    DeliveryStop fields the mobile driver pages actually display."""

    id: str
    sequence_number: int | None = None
    status: str
    status_label: str | None = None
    address: str | None = None
    customer_name: str | None = None
    notes: str | None = None
    cemetery_contact: str | None = None
    funeral_home_contact: str | None = None


class _PortalRouteResponse(BaseModel):
    id: str
    driver_id: str
    route_date: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_mileage: float | None = None
    total_stops: int
    vehicle_name: str | None = None
    driver_name: str | None = None
    stops: list[_PortalRouteStopShape] = Field(default_factory=list)


class _StopExceptionRequest(BaseModel):
    reason_code: str = Field(..., min_length=1, max_length=50)
    note: str | None = None


class _StopStatusRequest(BaseModel):
    status: str = Field(..., min_length=1, max_length=30)
    note: str | None = None


class _MileageSubmitRequest(BaseModel):
    start_mileage: float = Field(..., ge=0)
    end_mileage: float = Field(..., ge=0)
    notes: str | None = None


def _require_driver_for_portal(
    db: Session, *, portal_user: PortalUser
) -> Any:
    """Resolve the portal user's Driver row or 404. Reused by every
    driver-data mirror endpoint."""
    driver = resolve_driver_for_portal_user(db, portal_user=portal_user)
    if driver is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No driver record is linked to your account yet. "
                "Ask your dispatcher to finish provisioning."
            ),
        )
    return driver


def _portal_stop_to_response(stop: Any) -> _PortalRouteStopShape:
    """Extract the portal-relevant subset from a DeliveryStop row.
    Portal UI doesn't need the full DeliveryStop shape — just what
    the mobile driver displays."""
    address_parts = [
        stop.address_line1 if getattr(stop, "address_line1", None) else None,
        stop.address_city if getattr(stop, "address_city", None) else None,
        stop.address_state if getattr(stop, "address_state", None) else None,
    ]
    address = ", ".join(p for p in address_parts if p) or None
    return _PortalRouteStopShape(
        id=stop.id,
        sequence_number=getattr(stop, "sequence_number", None),
        status=getattr(stop, "status", "pending"),
        status_label=getattr(stop, "status", None),
        address=address,
        customer_name=getattr(stop, "customer_name", None),
        notes=getattr(stop, "notes", None),
        cemetery_contact=getattr(stop, "cemetery_contact", None),
        funeral_home_contact=getattr(stop, "funeral_home_contact", None),
    )


@router.get("/drivers/me/route", response_model=_PortalRouteResponse)
def portal_get_today_route(
    portal_user: PortalUser = Depends(get_current_portal_user),
    db: Session = Depends(get_db),
) -> _PortalRouteResponse:
    """Today's route + stops for the portal-authed driver. Thin
    router — resolves Driver, delegates to driver_mobile_service."""
    from app.services import driver_mobile_service
    from app.models.delivery_route import DeliveryRoute

    driver = _require_driver_for_portal(db, portal_user=portal_user)
    route = driver_mobile_service.get_today_route(
        db, driver.id, portal_user.company_id
    )
    if route is None:
        # No route today — return a minimal shell so the UI can
        # render "no route scheduled" cleanly.
        return _PortalRouteResponse(
            id="",
            driver_id=driver.id,
            route_date=date.today().isoformat(),
            status="none",
            total_stops=0,
        )
    resp = _PortalRouteResponse(
        id=route.id,
        driver_id=driver.id,
        route_date=route.route_date.isoformat(),
        status=route.status,
        started_at=route.started_at,
        completed_at=route.completed_at,
        total_mileage=float(route.total_mileage) if route.total_mileage else None,
        total_stops=route.total_stops or 0,
        vehicle_name=route.vehicle.name if route.vehicle else None,
        driver_name=f"{portal_user.first_name} {portal_user.last_name}",
        stops=[_portal_stop_to_response(s) for s in (route.stops or [])],
    )
    return resp


@router.get(
    "/drivers/me/stops/{stop_id}", response_model=_PortalRouteStopShape
)
def portal_get_stop(
    stop_id: str,
    portal_user: PortalUser = Depends(get_current_portal_user),
    db: Session = Depends(get_db),
) -> _PortalRouteStopShape:
    """Get a single stop by id. Scoped to the portal user's driver
    — a stop from another driver's route 404s."""
    from app.models.delivery_route import DeliveryRoute
    from app.models.delivery_stop import DeliveryStop

    driver = _require_driver_for_portal(db, portal_user=portal_user)
    stop = (
        db.query(DeliveryStop)
        .join(DeliveryRoute, DeliveryStop.route_id == DeliveryRoute.id)
        .filter(
            DeliveryStop.id == stop_id,
            DeliveryRoute.driver_id == driver.id,
            DeliveryRoute.company_id == portal_user.company_id,
        )
        .first()
    )
    if stop is None:
        raise HTTPException(status_code=404, detail="Stop not found")
    return _portal_stop_to_response(stop)


@router.post(
    "/drivers/me/stops/{stop_id}/exception",
    response_class=Response,
)
def portal_mark_stop_exception(
    stop_id: str,
    body: _StopExceptionRequest,
    portal_user: PortalUser = Depends(get_current_portal_user),
    db: Session = Depends(get_db),
) -> Response:
    """Mark a stop with an exception status + reason. Portal
    driver-authored action. Writes directly to the DeliveryStop;
    audit layer stamps `actor_type="portal_user"` via the
    audit_logs discriminator added in r42."""
    from app.models.delivery_route import DeliveryRoute
    from app.models.delivery_stop import DeliveryStop

    driver = _require_driver_for_portal(db, portal_user=portal_user)
    stop = (
        db.query(DeliveryStop)
        .join(DeliveryRoute, DeliveryStop.route_id == DeliveryRoute.id)
        .filter(
            DeliveryStop.id == stop_id,
            DeliveryRoute.driver_id == driver.id,
            DeliveryRoute.company_id == portal_user.company_id,
        )
        .first()
    )
    if stop is None:
        raise HTTPException(status_code=404, detail="Stop not found")
    # Minimal status + note write. Full exception workflow (photo
    # evidence, dispatcher notification) is covered by the bespoke
    # `/driver/stops/{id}/exception` endpoint; portal path mirrors
    # the simple status/note update.
    stop.status = "exception"
    if hasattr(stop, "notes"):
        note_parts = []
        if stop.notes:
            note_parts.append(stop.notes)
        note_parts.append(f"[exception: {body.reason_code}]")
        if body.note:
            note_parts.append(body.note)
        stop.notes = "\n".join(note_parts)
    db.commit()
    return Response(status_code=204)


@router.patch(
    "/drivers/me/stops/{stop_id}/status",
    response_model=_PortalRouteStopShape,
)
def portal_update_stop_status(
    stop_id: str,
    body: _StopStatusRequest,
    portal_user: PortalUser = Depends(get_current_portal_user),
    db: Session = Depends(get_db),
) -> _PortalRouteStopShape:
    """Update a stop's status (arrived, delivered, etc.). Portal
    driver-authored. Restricted write_mode=limited — can update
    status + note, cannot edit upstream order/invoice data."""
    from app.models.delivery_route import DeliveryRoute
    from app.models.delivery_stop import DeliveryStop

    driver = _require_driver_for_portal(db, portal_user=portal_user)
    stop = (
        db.query(DeliveryStop)
        .join(DeliveryRoute, DeliveryStop.route_id == DeliveryRoute.id)
        .filter(
            DeliveryStop.id == stop_id,
            DeliveryRoute.driver_id == driver.id,
            DeliveryRoute.company_id == portal_user.company_id,
        )
        .first()
    )
    if stop is None:
        raise HTTPException(status_code=404, detail="Stop not found")
    stop.status = body.status
    if body.note and hasattr(stop, "notes"):
        if stop.notes:
            stop.notes = f"{stop.notes}\n{body.note}"
        else:
            stop.notes = body.note
    db.commit()
    db.refresh(stop)
    return _portal_stop_to_response(stop)


@router.post("/drivers/me/mileage", response_class=Response)
def portal_submit_mileage(
    body: _MileageSubmitRequest,
    portal_user: PortalUser = Depends(get_current_portal_user),
    db: Session = Depends(get_db),
) -> Response:
    """Submit today's start + end mileage for the portal-authed
    driver's route. Validates end >= start."""
    from app.models.delivery_route import DeliveryRoute

    if body.end_mileage < body.start_mileage:
        raise HTTPException(
            status_code=400,
            detail="End mileage must be greater than or equal to start mileage.",
        )

    driver = _require_driver_for_portal(db, portal_user=portal_user)
    today = date.today()
    route = (
        db.query(DeliveryRoute)
        .filter(
            DeliveryRoute.driver_id == driver.id,
            DeliveryRoute.company_id == portal_user.company_id,
            DeliveryRoute.route_date == today,
        )
        .first()
    )
    if route is None:
        raise HTTPException(
            status_code=404, detail="No route scheduled for today"
        )
    route.total_mileage = body.end_mileage - body.start_mileage
    if body.notes:
        existing_notes = route.notes or ""
        route.notes = (
            f"{existing_notes}\n[mileage note] {body.notes}".strip()
        )
    db.commit()
    return Response(status_code=204)


# ── Helpers ─────────────────────────────────────────────────────────


def _resolve_access_ttl_for_portal_user(
    db: Session,
    *,
    portal_user: PortalUser,
    company: Company,
) -> int | None:
    """Look up the per-space session_timeout_minutes override on
    the portal user's assigned space. Returns None to use the portal
    default (12 hours).

    Spaces live on the tenant admin's `User.preferences.spaces`
    JSONB. For reconnaissance portal setup, the assigned space may
    belong to the tenant admin who provisioned the portal user; for
    future flexibility, we also scan any tenant user's preferences
    for the space_id — expensive on large tenants, but bounded by
    MAX_SPACES_PER_USER and typically just the provisioning admin.
    """
    if not portal_user.assigned_space_id:
        return None
    # Query tenant users whose preferences mention this space.
    # The MFG driver template's session_timeout_minutes (12 * 60) is
    # already the default — but future portal types (family 1h,
    # supplier 4h) need this lookup to work.
    from app.models.user import User
    from sqlalchemy import cast
    from sqlalchemy.dialects.postgresql import JSONB

    users = (
        db.query(User)
        .filter(
            User.company_id == company.id,
            cast(User.preferences, JSONB)["spaces"].astext.contains(
                portal_user.assigned_space_id
            ),
        )
        .all()
    )
    for u in users:
        for space in (u.preferences or {}).get("spaces", []):
            if space.get("space_id") == portal_user.assigned_space_id:
                return space.get("session_timeout_minutes")
    return None
