"""Portal admin API — Workflow Arc Phase 8e.2.1.

Tenant-admin endpoints for managing portal users + branding +
logo upload. Mounted at `/api/v1/portal/admin/*`. All endpoints
use the TENANT realm (`get_current_user` + `require_admin`) — NOT
the portal realm. Separate from `/api/v1/portal/*` (the portal-
user-facing endpoints).

The realm separation matters: only tenant admins provision portal
users. Portal users themselves never reach these endpoints.

Endpoints:
  Portal users CRUD:
    GET    /portal/admin/users                    — list w/ filters
    POST   /portal/admin/users                    — invite
    PATCH  /portal/admin/users/{id}               — edit
    POST   /portal/admin/users/{id}/deactivate    — soft-disable
    POST   /portal/admin/users/{id}/reactivate    — re-enable
    POST   /portal/admin/users/{id}/unlock        — clear lockout
    POST   /portal/admin/users/{id}/reset-password
    POST   /portal/admin/users/{id}/resend-invite

  Branding:
    GET    /portal/admin/branding                 — read
    PATCH  /portal/admin/branding                 — update color / footer
    POST   /portal/admin/branding/logo            — multipart upload
"""

from __future__ import annotations

import io
import logging
import mimetypes
from datetime import datetime
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
)
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.company_resolver import get_current_company
from app.database import get_db
from app.models.company import Company
from app.models.user import User
from app.services.portal import (
    PortalUserSummary,
    deactivate_portal_user,
    invite_portal_user,
    issue_admin_reset_password,
    list_portal_users_for_tenant,
    reactivate_portal_user,
    resend_invite,
    set_portal_branding,
    unlock_portal_user,
    update_portal_user_profile,
)
from app.services.portal.branding import get_portal_branding

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request / response shapes ────────────────────────────────────────


PortalUserStatus = Literal["active", "pending", "locked", "inactive"]


class _PortalUserSummaryResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    assigned_space_id: str | None
    assigned_space_name: str | None
    status: PortalUserStatus
    last_login_at: datetime | None
    driver_id: str | None
    created_at: datetime


class _PortalUsersListResponse(BaseModel):
    users: list[_PortalUserSummaryResponse]


class _InviteRequest(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    assigned_space_id: str = Field(..., min_length=1, max_length=36)


class _InviteResponse(BaseModel):
    user: _PortalUserSummaryResponse
    # Invite token deliberately NOT returned in the response body —
    # it's sent via email only. Admin gets success confirmation.


class _EditRequest(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    assigned_space_id: str | None = Field(default=None, min_length=1, max_length=36)


class _BrandingPatchRequest(BaseModel):
    brand_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    footer_text: str | None = Field(default=None, max_length=500)


class _BrandingResponse(BaseModel):
    slug: str
    display_name: str
    logo_url: str | None
    brand_color: str
    footer_text: str | None


class _LogoUploadResponse(BaseModel):
    logo_url: str


# ── Helpers ──────────────────────────────────────────────────────────


def _to_summary_response(s: PortalUserSummary) -> _PortalUserSummaryResponse:
    return _PortalUserSummaryResponse(
        id=s.id,
        email=s.email,
        first_name=s.first_name,
        last_name=s.last_name,
        assigned_space_id=s.assigned_space_id,
        assigned_space_name=s.assigned_space_name,
        status=s.status,
        last_login_at=s.last_login_at,
        driver_id=s.driver_id,
        created_at=s.created_at,
    )


def _send_invite_email(
    db: Session,
    *,
    company: Company,
    portal_user,
    invite_token: str,
) -> None:
    """Fire the portal_invite email via D-7 delivery."""
    try:
        from app.services.delivery_service import send_email_with_template

        send_email_with_template(
            db,
            template_key="email.portal_invite",
            company_id=company.id,
            recipient={
                "name": f"{portal_user.first_name} {portal_user.last_name}",
                "value": portal_user.email,
                "type": "email",
            },
            subject=f"Welcome to the {company.name} driver portal",
            template_context={
                "first_name": portal_user.first_name,
                "tenant_name": company.name,
                "invite_url": (
                    f"/portal/{company.slug}/reset-password?token={invite_token}"
                ),
                "expires_in": "3 days",
            },
            caller_module="portal_admin.invite",
        )
    except Exception:
        logger.exception(
            "Portal invite email send failed for portal_user=%s tenant=%s",
            portal_user.id,
            company.slug,
        )


def _send_reset_email(
    db: Session,
    *,
    company: Company,
    portal_user,
    token: str,
) -> None:
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
                    f"/portal/{company.slug}/reset-password?token={token}"
                ),
                "expires_in": "1 hour",
            },
            caller_module="portal_admin.reset_password",
        )
    except Exception:
        logger.exception(
            "Portal reset email send failed for portal_user=%s tenant=%s",
            portal_user.id,
            company.slug,
        )


# ── Portal user admin routes ────────────────────────────────────────


@router.get("/users", response_model=_PortalUsersListResponse)
def admin_list_portal_users(
    status: PortalUserStatus | None = None,
    space: str | None = None,
    admin: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> _PortalUsersListResponse:
    summaries = list_portal_users_for_tenant(
        db,
        company=company,
        status_filter=status,
        space_filter=space,
    )
    return _PortalUsersListResponse(
        users=[_to_summary_response(s) for s in summaries]
    )


@router.post("/users", response_model=_InviteResponse, status_code=201)
def admin_invite_portal_user(
    body: _InviteRequest,
    admin: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> _InviteResponse:
    try:
        portal_user, invite_token = invite_portal_user(
            db,
            company=company,
            inviter=admin,
            email=body.email,
            first_name=body.first_name,
            last_name=body.last_name,
            assigned_space_id=body.assigned_space_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _send_invite_email(
        db, company=company, portal_user=portal_user, invite_token=invite_token
    )

    # Re-fetch summary shape (handles status derivation + space name + driver_id).
    summaries = list_portal_users_for_tenant(db, company=company)
    match = next((s for s in summaries if s.id == portal_user.id), None)
    if match is None:
        # Shouldn't happen — just created. Defensive.
        raise HTTPException(status_code=500, detail="Invited user not visible")
    return _InviteResponse(user=_to_summary_response(match))


@router.patch("/users/{portal_user_id}", response_model=_PortalUserSummaryResponse)
def admin_edit_portal_user(
    portal_user_id: str,
    body: _EditRequest,
    admin: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> _PortalUserSummaryResponse:
    try:
        update_portal_user_profile(
            db,
            company=company,
            portal_user_id=portal_user_id,
            first_name=body.first_name,
            last_name=body.last_name,
            email=body.email,
            assigned_space_id=body.assigned_space_id,
        )
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(
            status_code=404 if "not found" in detail else 409,
            detail=detail,
        ) from exc

    summaries = list_portal_users_for_tenant(db, company=company)
    match = next((s for s in summaries if s.id == portal_user_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Portal user not found")
    return _to_summary_response(match)


@router.post("/users/{portal_user_id}/deactivate", response_model=_PortalUserSummaryResponse)
def admin_deactivate(
    portal_user_id: str,
    admin: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> _PortalUserSummaryResponse:
    try:
        deactivate_portal_user(
            db, company=company, portal_user_id=portal_user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _find_summary_or_404(db, company=company, portal_user_id=portal_user_id)


@router.post("/users/{portal_user_id}/reactivate", response_model=_PortalUserSummaryResponse)
def admin_reactivate(
    portal_user_id: str,
    admin: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> _PortalUserSummaryResponse:
    try:
        reactivate_portal_user(
            db, company=company, portal_user_id=portal_user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _find_summary_or_404(db, company=company, portal_user_id=portal_user_id)


@router.post("/users/{portal_user_id}/unlock", response_model=_PortalUserSummaryResponse)
def admin_unlock(
    portal_user_id: str,
    admin: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> _PortalUserSummaryResponse:
    try:
        unlock_portal_user(
            db, company=company, portal_user_id=portal_user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _find_summary_or_404(db, company=company, portal_user_id=portal_user_id)


@router.post("/users/{portal_user_id}/reset-password", response_class=Response)
def admin_reset_password(
    portal_user_id: str,
    admin: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> Response:
    try:
        portal_user, token = issue_admin_reset_password(
            db, company=company, portal_user_id=portal_user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _send_reset_email(
        db, company=company, portal_user=portal_user, token=token
    )
    return Response(status_code=204)


@router.post("/users/{portal_user_id}/resend-invite", response_class=Response)
def admin_resend_invite(
    portal_user_id: str,
    admin: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> Response:
    try:
        portal_user, token = resend_invite(
            db, company=company, portal_user_id=portal_user_id
        )
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(
            status_code=404 if "not found" in detail else 409,
            detail=detail,
        ) from exc
    _send_invite_email(
        db, company=company, portal_user=portal_user, invite_token=token
    )
    return Response(status_code=204)


def _find_summary_or_404(
    db: Session, *, company: Company, portal_user_id: str
) -> _PortalUserSummaryResponse:
    summaries = list_portal_users_for_tenant(db, company=company)
    match = next((s for s in summaries if s.id == portal_user_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Portal user not found")
    return _to_summary_response(match)


# ── Branding admin routes ────────────────────────────────────────────


@router.get("/branding", response_model=_BrandingResponse)
def admin_read_branding(
    admin: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> _BrandingResponse:
    b = get_portal_branding(db, slug=company.slug)
    if b is None:
        raise HTTPException(status_code=404, detail="Portal not found")
    return _BrandingResponse(
        slug=b.slug,
        display_name=b.display_name,
        logo_url=b.logo_url,
        brand_color=b.brand_color,
        footer_text=b.footer_text,
    )


@router.patch("/branding", response_model=_BrandingResponse)
def admin_update_branding(
    body: _BrandingPatchRequest,
    admin: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> _BrandingResponse:
    b = set_portal_branding(
        db,
        company=company,
        brand_color=body.brand_color,
        footer_text=body.footer_text,
    )
    return _BrandingResponse(
        slug=b.slug,
        display_name=b.display_name,
        logo_url=b.logo_url,
        brand_color=b.brand_color,
        footer_text=b.footer_text,
    )


# ── Logo upload ─────────────────────────────────────────────────────


_MAX_LOGO_BYTES: int = 2 * 1024 * 1024  # 2 MB
_ALLOWED_MIME: set[str] = {"image/png", "image/jpeg"}
# Phase 8e.2.1 rejects SVG — potential embedded-script vector. Future
# polish can add SVG with `bleach`-style sanitization.
_MIN_DIMENSION: int = 50
_MAX_DIMENSION: int = 1024


@router.post("/branding/logo", response_model=_LogoUploadResponse)
async def admin_upload_logo(
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> _LogoUploadResponse:
    """Upload a tenant portal logo. PNG/JPG only, ≤2MB, dimensions
    50–1024px. Stores at `tenants/{company_id}/portal/logo.{ext}` in
    R2 and updates `Company.logo_url`."""
    if file.content_type not in _ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail=(
                "Logo must be PNG or JPG. SVG is not currently supported."
            ),
        )

    data = await file.read()
    if len(data) > _MAX_LOGO_BYTES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Logo exceeds {_MAX_LOGO_BYTES // (1024 * 1024)}MB limit."
            ),
        )
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file upload.")

    # Image validation via Pillow — verifies it actually decodes.
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(data))
        img.verify()
        # After verify(), reopen for size check — verify() consumed
        # the parser state.
        img = Image.open(io.BytesIO(data))
        w, h = img.size
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail="Couldn't decode image."
        ) from exc

    if w < _MIN_DIMENSION or h < _MIN_DIMENSION:
        raise HTTPException(
            status_code=400,
            detail=f"Logo too small (min {_MIN_DIMENSION}×{_MIN_DIMENSION}).",
        )
    if w > _MAX_DIMENSION or h > _MAX_DIMENSION:
        raise HTTPException(
            status_code=400,
            detail=f"Logo too large (max {_MAX_DIMENSION}×{_MAX_DIMENSION}).",
        )

    # Upload to R2 at a stable key so repeated uploads overwrite.
    from app.services.legacy_r2_client import upload_bytes, get_public_url

    ext = "png" if file.content_type == "image/png" else "jpg"
    r2_key = f"tenants/{company.id}/portal/logo.{ext}"
    try:
        url = upload_bytes(data, r2_key, content_type=file.content_type)
    except RuntimeError as exc:
        logger.exception("R2 upload failed for portal logo")
        raise HTTPException(
            status_code=500, detail="Logo upload failed. Check R2 configuration."
        ) from exc

    company.logo_url = url
    db.commit()
    db.refresh(company)
    return _LogoUploadResponse(logo_url=url)
