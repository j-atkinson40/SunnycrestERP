"""Calendar Accounts API — Phase W-4b Layer 1 Calendar Step 1.

Tenant-admin endpoints for managing ``CalendarAccount`` +
``CalendarAccountAccess`` records. Subsequent Steps 2-N add the
sync/event/freebusy endpoints on top of these foundations.

All endpoints require ``require_admin`` for create/update/delete +
access management. List endpoints (mine + tenant) follow the Email
account precedent: tenant-wide list is admin-only; per-user 'mine'
list is any authenticated tenant user filtered by access grants.

Per ``CLAUDE.md`` §12 conventions:
  - All queries filter by ``tenant_id`` via ``current_user.company_id``
  - Service-layer errors (``CalendarAccountError`` subclasses) are
    translated to HTTP via the ``http_status`` attribute
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.calendar_primitive import (
    ACCESS_LEVELS,
    ACCOUNT_TYPES,
    PROVIDER_TYPES,
    CalendarAccount,
    CalendarAccountAccess,
)
from app.models.user import User
from app.services.calendar import account_service, oauth_service
from app.services.calendar.account_service import CalendarAccountError
from app.services.calendar.crypto import decrypt_credentials
from app.services.calendar.providers import PROVIDER_REGISTRY
from app.services.calendar.sync_engine import (
    SyncEngineError,
    ensure_sync_state,
    run_initial_backfill,
)


router = APIRouter()


# ─────────────────────────────────────────────────────────────────────
# Pydantic response shapes
# ─────────────────────────────────────────────────────────────────────


class CalendarAccountResponse(BaseModel):
    id: str
    tenant_id: str
    account_type: Literal["shared", "personal"]
    display_name: str
    primary_email_address: str
    provider_type: Literal["google_calendar", "msgraph", "local"]
    provider_config_keys: list[str] = Field(
        default_factory=list,
        description="Keys present in provider_config (NOT values — credentials hidden)",
    )
    outbound_enabled: bool
    default_event_timezone: str
    is_active: bool
    is_default: bool
    # Step 2: sync_status from CalendarAccountSyncState. Pending if no
    # sync state row exists yet (account hasn't been backfilled).
    sync_status: str | None = None
    # Step 2: credential lifecycle surfaced for the CalendarAccountsPage
    # status sub-row. None when account hasn't completed OAuth yet.
    last_credential_op: str | None = None
    last_credential_op_at: str | None = None
    backfill_status: str = "not_started"
    backfill_progress_pct: int = 0
    created_by_user_id: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, account: CalendarAccount) -> CalendarAccountResponse:
        # sync_status from sync_state relationship (lazy-loaded); None
        # if no sync state row yet (account never synced).
        sync_status = (
            account.sync_state.sync_status if account.sync_state else None
        )
        return cls(
            id=account.id,
            tenant_id=account.tenant_id,
            account_type=account.account_type,  # type: ignore[arg-type]
            display_name=account.display_name,
            primary_email_address=account.primary_email_address,
            provider_type=account.provider_type,  # type: ignore[arg-type]
            provider_config_keys=sorted((account.provider_config or {}).keys()),
            outbound_enabled=account.outbound_enabled,
            default_event_timezone=account.default_event_timezone,
            is_active=account.is_active,
            is_default=account.is_default,
            sync_status=sync_status,
            last_credential_op=account.last_credential_op,
            last_credential_op_at=(
                account.last_credential_op_at.isoformat()
                if account.last_credential_op_at
                else None
            ),
            backfill_status=account.backfill_status,
            backfill_progress_pct=account.backfill_progress_pct,
            created_by_user_id=account.created_by_user_id,
            created_at=account.created_at.isoformat(),
            updated_at=account.updated_at.isoformat(),
        )


class CalendarAccountAccessResponse(BaseModel):
    id: str
    account_id: str
    user_id: str
    user_email: str | None
    user_name: str | None
    access_level: Literal["read", "read_write", "admin"]
    granted_by_user_id: str | None
    granted_at: str
    revoked_at: str | None

    @classmethod
    def from_model(
        cls, grant: CalendarAccountAccess
    ) -> CalendarAccountAccessResponse:
        # The ``user`` relationship is lazy; touching ``.email`` /
        # ``.full_name`` may issue a separate query. Acceptable for
        # admin endpoints that already iterate per-grant.
        user = grant.user
        return cls(
            id=grant.id,
            account_id=grant.account_id,
            user_id=grant.user_id,
            user_email=getattr(user, "email", None) if user else None,
            user_name=getattr(user, "full_name", None) if user else None,
            access_level=grant.access_level,  # type: ignore[arg-type]
            granted_by_user_id=grant.granted_by_user_id,
            granted_at=grant.granted_at.isoformat(),
            revoked_at=(
                grant.revoked_at.isoformat() if grant.revoked_at else None
            ),
        )


class ProviderInfo(BaseModel):
    provider_type: str
    display_label: str
    supports_inbound: bool
    supports_realtime: bool
    supports_freebusy: bool


# ─────────────────────────────────────────────────────────────────────
# Request shapes
# ─────────────────────────────────────────────────────────────────────


class CreateAccountRequest(BaseModel):
    account_type: Literal["shared", "personal"]
    display_name: str = Field(min_length=1, max_length=200)
    primary_email_address: str = Field(min_length=3, max_length=320)
    provider_type: Literal["google_calendar", "msgraph", "local"]
    provider_config: dict[str, Any] = Field(default_factory=dict)
    default_event_timezone: str = Field(default="America/New_York", max_length=64)
    is_default: bool = False

    @field_validator("primary_email_address")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("primary_email_address must contain '@'")
        return v.strip().lower()


class UpdateAccountRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    default_event_timezone: str | None = Field(default=None, max_length=64)
    is_default: bool | None = None
    is_active: bool | None = None
    outbound_enabled: bool | None = None
    provider_config_patch: dict[str, Any] | None = None


class GrantAccessRequest(BaseModel):
    user_id: str = Field(min_length=1)
    access_level: Literal["read", "read_write", "admin"]


# ─────────────────────────────────────────────────────────────────────
# Error translation
# ─────────────────────────────────────────────────────────────────────


def _translate(exc: CalendarAccountError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=exc.message)


# ─────────────────────────────────────────────────────────────────────
# Provider catalog endpoint — frontend reads this to render the
# provider picker.
# ─────────────────────────────────────────────────────────────────────


@router.get("/providers", response_model=list[ProviderInfo])
def list_providers(
    current_user: User = Depends(get_current_user),
) -> list[ProviderInfo]:
    """Return the catalog of registered calendar providers.

    Used by the Settings → Calendar Accounts UI to render the provider
    picker dropdown when creating a new account.

    Per Q3 architectural decision (confirmed pre-build): CalDAV
    omitted entirely from Step 1 catalog. Catalog returns 3 providers:
    google_calendar, msgraph, local.
    """
    return [
        ProviderInfo(
            provider_type=ptype,
            display_label=pcls.display_label,
            supports_inbound=pcls.supports_inbound,
            supports_realtime=pcls.supports_realtime,
            supports_freebusy=pcls.supports_freebusy,
        )
        for ptype, pcls in sorted(PROVIDER_REGISTRY.items())
    ]


# ─────────────────────────────────────────────────────────────────────
# Account CRUD
# ─────────────────────────────────────────────────────────────────────


@router.get("", response_model=list[CalendarAccountResponse])
def list_accounts(
    include_inactive: bool = False,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[CalendarAccountResponse]:
    """List all calendar accounts in the tenant (admin-only).

    Per-user filtered list (the actual user-visible accounts) is
    served by ``GET /calendar-accounts/mine``.
    """
    accounts = account_service.list_accounts_for_tenant(
        db,
        tenant_id=current_user.company_id,
        include_inactive=include_inactive,
    )
    return [CalendarAccountResponse.from_model(a) for a in accounts]


@router.get("/mine", response_model=list[CalendarAccountResponse])
def list_my_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CalendarAccountResponse]:
    """List accounts the current user has any active access grant on.

    Future event endpoints (Step 2) call this to populate the account
    selector. Step 1 ships the endpoint so the CalendarAccountsPage
    can render "your accounts" alongside the admin-only full tenant
    list.
    """
    accounts = account_service.list_accounts_for_user(
        db,
        tenant_id=current_user.company_id,
        user_id=current_user.id,
    )
    return [CalendarAccountResponse.from_model(a) for a in accounts]


@router.post("", response_model=CalendarAccountResponse, status_code=201)
def create_account_endpoint(
    request: CreateAccountRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CalendarAccountResponse:
    """Create a new CalendarAccount.

    The creator is auto-granted ``admin`` access on the new account so
    they can manage access scope without a second round-trip.
    """
    try:
        account = account_service.create_account(
            db,
            tenant_id=current_user.company_id,
            actor_user_id=current_user.id,
            account_type=request.account_type,
            display_name=request.display_name,
            primary_email_address=request.primary_email_address,
            provider_type=request.provider_type,
            provider_config=request.provider_config,
            default_event_timezone=request.default_event_timezone,
            is_default=request.is_default,
        )
        # Auto-grant creator admin access.
        account_service.grant_access(
            db,
            account_id=account.id,
            tenant_id=current_user.company_id,
            user_id=current_user.id,
            access_level="admin",
            actor_user_id=current_user.id,
        )
        db.commit()
        db.refresh(account)
        return CalendarAccountResponse.from_model(account)
    except CalendarAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


@router.get("/{account_id}", response_model=CalendarAccountResponse)
def get_account_endpoint(
    account_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CalendarAccountResponse:
    try:
        account = account_service.get_account(
            db,
            account_id=account_id,
            tenant_id=current_user.company_id,
        )
        return CalendarAccountResponse.from_model(account)
    except CalendarAccountError as exc:
        raise _translate(exc) from exc


@router.patch("/{account_id}", response_model=CalendarAccountResponse)
def update_account_endpoint(
    account_id: str,
    request: UpdateAccountRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CalendarAccountResponse:
    try:
        account = account_service.update_account(
            db,
            account_id=account_id,
            tenant_id=current_user.company_id,
            actor_user_id=current_user.id,
            display_name=request.display_name,
            default_event_timezone=request.default_event_timezone,
            is_default=request.is_default,
            is_active=request.is_active,
            outbound_enabled=request.outbound_enabled,
            provider_config_patch=request.provider_config_patch,
        )
        db.commit()
        db.refresh(account)
        return CalendarAccountResponse.from_model(account)
    except CalendarAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


@router.delete("/{account_id}", status_code=200)
def delete_account_endpoint(
    account_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    """Soft-delete (``is_active=False``) a calendar account.

    The account row + its events + attendees + audit log all stay for
    audit compliance. Subsequent reads filter by ``is_active=True`` by
    default.
    """
    try:
        account_service.delete_account(
            db,
            account_id=account_id,
            tenant_id=current_user.company_id,
            actor_user_id=current_user.id,
        )
        db.commit()
        return {"deleted": True}
    except CalendarAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


# ─────────────────────────────────────────────────────────────────────
# Access scope management
# ─────────────────────────────────────────────────────────────────────


@router.get(
    "/{account_id}/access",
    response_model=list[CalendarAccountAccessResponse],
)
def list_access_grants(
    account_id: str,
    include_revoked: bool = False,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[CalendarAccountAccessResponse]:
    try:
        grants = account_service.list_access_grants_for_account(
            db,
            account_id=account_id,
            tenant_id=current_user.company_id,
            include_revoked=include_revoked,
        )
        return [CalendarAccountAccessResponse.from_model(g) for g in grants]
    except CalendarAccountError as exc:
        raise _translate(exc) from exc


@router.post(
    "/{account_id}/access",
    response_model=CalendarAccountAccessResponse,
    status_code=201,
)
def grant_access_endpoint(
    account_id: str,
    request: GrantAccessRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CalendarAccountAccessResponse:
    try:
        grant = account_service.grant_access(
            db,
            account_id=account_id,
            tenant_id=current_user.company_id,
            user_id=request.user_id,
            access_level=request.access_level,
            actor_user_id=current_user.id,
        )
        db.commit()
        db.refresh(grant)
        return CalendarAccountAccessResponse.from_model(grant)
    except CalendarAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


@router.delete("/{account_id}/access/{user_id}", status_code=200)
def revoke_access_endpoint(
    account_id: str,
    user_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    try:
        revoked = account_service.revoke_access(
            db,
            account_id=account_id,
            tenant_id=current_user.company_id,
            user_id=user_id,
            actor_user_id=current_user.id,
        )
        db.commit()
        return {"revoked": revoked}
    except CalendarAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


# ─────────────────────────────────────────────────────────────────────
# Step 2 — OAuth scaffolding
# ─────────────────────────────────────────────────────────────────────


class OAuthAuthorizeUrlResponse(BaseModel):
    """Returned to the frontend so it can navigate the user to the
    provider's consent screen. Returns a placeholder client_id when
    GOOGLE_OAUTH_CLIENT_ID / MICROSOFT_OAUTH_CLIENT_ID env vars are
    unset (allows UI flow verification without real credentials).
    """

    authorize_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    """Posted by the frontend after the provider redirects back with a
    code. Backend validates state, exchanges code, persists encrypted
    tokens, kicks off backfill.
    """

    provider_type: Literal["google_calendar", "msgraph"]
    code: str = Field(min_length=1)
    state: str = Field(min_length=1)
    redirect_uri: str = Field(min_length=1)
    # Optional: caller may pre-create a CalendarAccount row + pass id.
    # When omitted, the callback creates a new account + grants admin
    # access to the calling user.
    account_id: str | None = None
    primary_email_address: str | None = None
    display_name: str | None = None
    account_type: Literal["shared", "personal"] = "personal"


class OAuthCallbackResponse(BaseModel):
    account_id: str
    primary_email_address: str
    backfill_status: str
    backfill_progress_pct: int


class SyncStatusResponse(BaseModel):
    account_id: str
    sync_status: str
    sync_error_message: str | None
    consecutive_error_count: int
    last_sync_at: str | None
    sync_in_progress: bool
    backfill_status: str
    backfill_progress_pct: int
    backfill_started_at: str | None
    backfill_completed_at: str | None
    last_credential_op: str | None
    last_credential_op_at: str | None
    token_expires_at: str | None


@router.get(
    "/oauth/{provider_type}/authorize-url",
    response_model=OAuthAuthorizeUrlResponse,
)
def oauth_authorize_url(
    provider_type: str,
    redirect_uri: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> OAuthAuthorizeUrlResponse:
    """Build a provider OAuth authorize URL with CSRF-protected state.

    Issues a signed state nonce (10-min expiry, single-use) stored in
    the platform-shared ``oauth_state_nonces`` table. Real client_id
    pulled from ``GOOGLE_OAUTH_CLIENT_ID`` / ``MICROSOFT_OAUTH_CLIENT_ID``
    env vars; placeholder string returned when env vars are unset.
    """
    if provider_type not in ("google_calendar", "msgraph"):
        raise HTTPException(
            status_code=400,
            detail=f"Provider {provider_type!r} does not use OAuth",
        )
    state = oauth_service.issue_state_nonce(
        db,
        tenant_id=current_user.company_id,
        user_id=current_user.id,
        provider_type=provider_type,
        redirect_uri=redirect_uri,
    )
    db.commit()
    authorize_url = oauth_service.build_authorize_url(
        provider_type=provider_type,
        state=state,
        redirect_uri=redirect_uri,
    )
    return OAuthAuthorizeUrlResponse(
        authorize_url=authorize_url,
        state=state,
    )


@router.post(
    "/oauth/callback",
    response_model=OAuthCallbackResponse,
    status_code=200,
)
def oauth_callback(
    request: OAuthCallbackRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> OAuthCallbackResponse:
    """Exchange an OAuth authorization code → encrypted tokens.

    Validates the state nonce (CSRF + tenant/user/provider match,
    single-use) before exchange. On success: persists encrypted
    credentials onto the CalendarAccount + bootstraps backfill.

    Two creation modes:
      - Existing account (caller passes ``account_id``): credentials
        get attached to the existing row. Used for the "reconnect"
        flow.
      - New account (caller omits ``account_id``): backend creates a
        new CalendarAccount + grants admin access to the caller, then
        attaches credentials.
    """
    try:
        oauth_service.validate_and_consume_state_nonce(
            db,
            nonce=request.state,
            tenant_id=current_user.company_id,
            user_id=current_user.id,
            provider_type=request.provider_type,
        )
    except CalendarAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc

    # Resolve or create the CalendarAccount.
    account = None
    if request.account_id:
        try:
            account = account_service.get_account(
                db,
                account_id=request.account_id,
                tenant_id=current_user.company_id,
            )
        except CalendarAccountError as exc:
            raise _translate(exc) from exc
        if account.provider_type != request.provider_type:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Account provider_type {account.provider_type!r} "
                    f"does not match callback provider {request.provider_type!r}"
                ),
            )
    else:
        if not request.primary_email_address:
            raise HTTPException(
                status_code=400,
                detail="primary_email_address required when account_id omitted",
            )
        try:
            account = account_service.create_account(
                db,
                tenant_id=current_user.company_id,
                actor_user_id=current_user.id,
                account_type=request.account_type,
                display_name=request.display_name or request.primary_email_address,
                primary_email_address=request.primary_email_address,
                provider_type=request.provider_type,
                provider_config={},
            )
            account_service.grant_access(
                db,
                account_id=account.id,
                tenant_id=current_user.company_id,
                user_id=current_user.id,
                access_level="admin",
                actor_user_id=current_user.id,
            )
        except CalendarAccountError as exc:
            db.rollback()
            raise _translate(exc) from exc

    try:
        oauth_service.complete_oauth_exchange(
            db,
            account=account,
            code=request.code,
            redirect_uri=request.redirect_uri,
            actor_user_id=current_user.id,
        )
    except CalendarAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc

    db.commit()
    db.refresh(account)
    return OAuthCallbackResponse(
        account_id=account.id,
        primary_email_address=account.primary_email_address,
        backfill_status=account.backfill_status,
        backfill_progress_pct=account.backfill_progress_pct,
    )


@router.get("/{account_id}/sync-status", response_model=SyncStatusResponse)
def get_sync_status(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyncStatusResponse:
    """Return sync + backfill + credential status for an account.

    Available to any authenticated tenant user (filtered by tenant_id);
    no admin requirement — read-only status surfacing.
    """
    try:
        account = account_service.get_account(
            db,
            account_id=account_id,
            tenant_id=current_user.company_id,
        )
    except CalendarAccountError as exc:
        raise _translate(exc) from exc

    state = account.sync_state
    return SyncStatusResponse(
        account_id=account.id,
        sync_status=state.sync_status if state else "pending",
        sync_error_message=(state.sync_error_message if state else None),
        consecutive_error_count=(state.consecutive_error_count if state else 0),
        last_sync_at=(
            state.last_sync_at.isoformat()
            if state and state.last_sync_at
            else None
        ),
        sync_in_progress=(state.sync_in_progress if state else False),
        backfill_status=account.backfill_status,
        backfill_progress_pct=account.backfill_progress_pct,
        backfill_started_at=(
            account.backfill_started_at.isoformat()
            if account.backfill_started_at
            else None
        ),
        backfill_completed_at=(
            account.backfill_completed_at.isoformat()
            if account.backfill_completed_at
            else None
        ),
        last_credential_op=account.last_credential_op,
        last_credential_op_at=(
            account.last_credential_op_at.isoformat()
            if account.last_credential_op_at
            else None
        ),
        token_expires_at=(
            account.token_expires_at.isoformat()
            if account.token_expires_at
            else None
        ),
    )


@router.post("/{account_id}/sync-now", status_code=202)
def sync_now(
    account_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Manually trigger an initial backfill or incremental sync.

    Step 2 ships synchronous backfill (works fine for the small
    test-fixture inboxes; large production calendars will move to
    APScheduler-deferred backfill in Step 2.1). Returns 202 + the
    new backfill_status.

    For OAuth providers, ensures fresh access token + injects into
    provider_config so the sync engine has it. For local provider,
    sync_initial is a no-op.
    """
    try:
        account = account_service.get_account(
            db,
            account_id=account_id,
            tenant_id=current_user.company_id,
        )
    except CalendarAccountError as exc:
        raise _translate(exc) from exc

    # For OAuth providers, ensure fresh access token + inject into
    # provider_config so sync_engine's provider call has it.
    if account.provider_type in ("google_calendar", "msgraph"):
        try:
            access_token = oauth_service.ensure_fresh_token(
                db, account=account
            )
            cfg = dict(account.provider_config or {})
            cfg["access_token"] = access_token
            account.provider_config = cfg
        except oauth_service.OAuthAuthError as exc:
            db.rollback()
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    # Run backfill (Step 2 keeps it as full backfill; Step 2.1
    # differentiates first-vs-subsequent via cursor).
    if account.backfill_status in ("not_started", "error"):
        result = run_initial_backfill(db, account=account)
    else:
        # Already-completed account: Step 2 stub for incremental sync.
        # Real incremental sync ships in Step 2.1 alongside
        # webhook-driven event fetch.
        result = {"status": "incremental_sync_stub"}

    db.commit()
    return {"status": "queued", **{k: str(v) for k, v in result.items()}}
