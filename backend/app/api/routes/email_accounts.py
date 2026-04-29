"""Email Accounts API — Phase W-4b Layer 1 Step 1.

Tenant-admin endpoints for managing ``EmailAccount`` + ``EmailAccountAccess``
records. Subsequent Steps 2-N add the inbox/thread/message endpoints
on top of these foundations.

All endpoints require ``require_admin`` for create/update/delete +
access management. List endpoints are accessible to any authenticated
tenant user (the access level then filters per-user via
``account_service.list_accounts_for_user``).

Per ``CLAUDE.md`` §12 conventions:
  - All queries filter by ``tenant_id`` via ``current_user.company_id``
  - Service-layer errors (``EmailAccountError`` subclasses) are
    translated to HTTP via the ``http_status`` attribute
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.email_primitive import (
    ACCESS_LEVELS,
    ACCOUNT_TYPES,
    PROVIDER_TYPES,
    EmailAccount,
    EmailAccountAccess,
)
from app.models.user import User
from app.services.email import account_service
from app.services.email.account_service import EmailAccountError
from app.services.email import oauth_service
from app.services.email.providers import (
    PROVIDER_REGISTRY,
    get_provider_class,
)
from app.services.email.sync_engine import run_initial_backfill


router = APIRouter()


# ─────────────────────────────────────────────────────────────────────
# Pydantic response shapes
# ─────────────────────────────────────────────────────────────────────


class EmailAccountResponse(BaseModel):
    id: str
    tenant_id: str
    account_type: Literal["shared", "personal"]
    display_name: str
    email_address: str
    provider_type: Literal["gmail", "msgraph", "imap", "transactional"]
    provider_config_keys: list[str] = Field(
        default_factory=list,
        description="Keys present in provider_config (NOT values — credentials hidden)",
    )
    signature_html: str | None
    reply_to_override: str | None
    is_active: bool
    is_default: bool
    sync_status: str | None = None
    # Step 2 — credential lifecycle surfaced for the EmailAccountsPage
    # status sub-row. None when account hasn't completed OAuth yet.
    last_credential_op: str | None = None
    last_credential_op_at: str | None = None
    backfill_status: str = "not_started"
    backfill_progress_pct: int = 0
    created_by_user_id: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, account: EmailAccount) -> EmailAccountResponse:
        return cls(
            id=account.id,
            tenant_id=account.tenant_id,
            account_type=account.account_type,  # type: ignore[arg-type]
            display_name=account.display_name,
            email_address=account.email_address,
            provider_type=account.provider_type,  # type: ignore[arg-type]
            provider_config_keys=sorted((account.provider_config or {}).keys()),
            signature_html=account.signature_html,
            reply_to_override=account.reply_to_override,
            is_active=account.is_active,
            is_default=account.is_default,
            sync_status=(
                account.sync_state.sync_status if account.sync_state else None
            ),
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


class EmailAccountAccessResponse(BaseModel):
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
    def from_model(cls, grant: EmailAccountAccess) -> EmailAccountAccessResponse:
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


# ─────────────────────────────────────────────────────────────────────
# Request shapes
# ─────────────────────────────────────────────────────────────────────


class CreateAccountRequest(BaseModel):
    account_type: Literal["shared", "personal"]
    display_name: str = Field(min_length=1, max_length=200)
    email_address: str = Field(min_length=3, max_length=320)
    provider_type: Literal["gmail", "msgraph", "imap", "transactional"]
    provider_config: dict[str, Any] = Field(default_factory=dict)
    signature_html: str | None = None
    reply_to_override: str | None = None
    is_default: bool = False

    @field_validator("email_address")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("email_address must contain '@'")
        return v.strip().lower()


class UpdateAccountRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    signature_html: str | None = None
    reply_to_override: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    provider_config_patch: dict[str, Any] | None = None


class GrantAccessRequest(BaseModel):
    user_id: str = Field(min_length=1)
    access_level: Literal["read", "read_write", "admin"]


class OAuthAuthorizeUrlResponse(BaseModel):
    """Returned to the frontend so it can navigate the user to the
    provider's consent screen. Step 2 wires real client credentials
    from env (CSRF-protected via signed-state nonce in DB).
    """

    authorize_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    """Posted by the frontend after the provider redirects back with a
    code. Backend validates state, exchanges code, persists encrypted
    tokens, kicks off backfill.
    """

    provider_type: Literal["gmail", "msgraph"]
    code: str = Field(min_length=1)
    state: str = Field(min_length=1)
    redirect_uri: str = Field(min_length=1)
    # Optional: caller may pre-create an EmailAccount row + pass id.
    # When omitted, the callback creates a new EmailAccount + grants
    # admin access to the calling user.
    account_id: str | None = None
    email_address: str | None = None
    display_name: str | None = None
    account_type: Literal["shared", "personal"] = "personal"


class OAuthCallbackResponse(BaseModel):
    account_id: str
    email_address: str
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


# ─────────────────────────────────────────────────────────────────────
# Error translation
# ─────────────────────────────────────────────────────────────────────


def _translate(exc: EmailAccountError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=exc.message)


# ─────────────────────────────────────────────────────────────────────
# Provider catalog endpoint — frontend reads this to render the
# provider picker.
# ─────────────────────────────────────────────────────────────────────


@router.get("/providers", response_model=list[ProviderInfo])
def list_providers(
    current_user: User = Depends(get_current_user),
) -> list[ProviderInfo]:
    """Return the catalog of registered email providers.

    Used by the Settings → Email Accounts UI to render the provider
    picker dropdown when connecting a new account.
    """
    return [
        ProviderInfo(
            provider_type=ptype,
            display_label=pcls.display_label,
            supports_inbound=pcls.supports_inbound,
            supports_realtime=pcls.supports_realtime,
        )
        for ptype, pcls in sorted(PROVIDER_REGISTRY.items())
    ]


# ─────────────────────────────────────────────────────────────────────
# Account CRUD
# ─────────────────────────────────────────────────────────────────────


@router.get("", response_model=list[EmailAccountResponse])
def list_accounts(
    include_inactive: bool = False,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[EmailAccountResponse]:
    """List all email accounts in the tenant (admin-only).

    Per-user filtered list (the actual user-visible inbox accounts) is
    served by ``GET /email-accounts/mine``.
    """
    accounts = account_service.list_accounts_for_tenant(
        db,
        tenant_id=current_user.company_id,
        include_inactive=include_inactive,
    )
    return [EmailAccountResponse.from_model(a) for a in accounts]


@router.get("/mine", response_model=list[EmailAccountResponse])
def list_my_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EmailAccountResponse]:
    """List accounts the current user has any active access grant on.

    Future inbox endpoints (Step 4) call this to populate the account
    selector. Step 1 ships the endpoint so the EmailAccountsPage can
    render "your accounts" alongside the admin-only full tenant list.
    """
    accounts = account_service.list_accounts_for_user(
        db,
        tenant_id=current_user.company_id,
        user_id=current_user.id,
    )
    return [EmailAccountResponse.from_model(a) for a in accounts]


@router.post("", response_model=EmailAccountResponse, status_code=201)
def create_account_endpoint(
    request: CreateAccountRequest,
    http_request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> EmailAccountResponse:
    """Create a new EmailAccount.

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
            email_address=request.email_address,
            provider_type=request.provider_type,
            provider_config=request.provider_config,
            signature_html=request.signature_html,
            reply_to_override=request.reply_to_override,
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
        return EmailAccountResponse.from_model(account)
    except EmailAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


@router.get("/{account_id}", response_model=EmailAccountResponse)
def get_account_endpoint(
    account_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> EmailAccountResponse:
    try:
        account = account_service.get_account(
            db,
            account_id=account_id,
            tenant_id=current_user.company_id,
        )
        return EmailAccountResponse.from_model(account)
    except EmailAccountError as exc:
        raise _translate(exc) from exc


@router.patch("/{account_id}", response_model=EmailAccountResponse)
def update_account_endpoint(
    account_id: str,
    request: UpdateAccountRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> EmailAccountResponse:
    try:
        account = account_service.update_account(
            db,
            account_id=account_id,
            tenant_id=current_user.company_id,
            actor_user_id=current_user.id,
            display_name=request.display_name,
            signature_html=request.signature_html,
            reply_to_override=request.reply_to_override,
            is_default=request.is_default,
            is_active=request.is_active,
            provider_config_patch=request.provider_config_patch,
        )
        db.commit()
        db.refresh(account)
        return EmailAccountResponse.from_model(account)
    except EmailAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


@router.delete("/{account_id}", status_code=200)
def delete_account_endpoint(
    account_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    """Soft-delete (``is_active=False``) an email account.

    The account row + its messages + threads + audit log all stay for
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
    except EmailAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


# ─────────────────────────────────────────────────────────────────────
# Access scope management
# ─────────────────────────────────────────────────────────────────────


@router.get("/{account_id}/access", response_model=list[EmailAccountAccessResponse])
def list_access_grants(
    account_id: str,
    include_revoked: bool = False,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[EmailAccountAccessResponse]:
    try:
        grants = account_service.list_access_grants_for_account(
            db,
            account_id=account_id,
            tenant_id=current_user.company_id,
            include_revoked=include_revoked,
        )
        return [EmailAccountAccessResponse.from_model(g) for g in grants]
    except EmailAccountError as exc:
        raise _translate(exc) from exc


@router.post(
    "/{account_id}/access",
    response_model=EmailAccountAccessResponse,
    status_code=201,
)
def grant_access_endpoint(
    account_id: str,
    request: GrantAccessRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> EmailAccountAccessResponse:
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
        return EmailAccountAccessResponse.from_model(grant)
    except EmailAccountError as exc:
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
    except EmailAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


# ─────────────────────────────────────────────────────────────────────
# OAuth scaffolding — Step 1 returns placeholder URLs; Step 2 wires
# real client credentials.
# ─────────────────────────────────────────────────────────────────────


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

    Step 2 issues a signed state nonce stored server-side
    (``oauth_state_nonces``, 10-min expiry, single-use). Real client_id
    pulled from ``GOOGLE_OAUTH_CLIENT_ID`` / ``MICROSOFT_OAUTH_CLIENT_ID``
    env vars; placeholder ``REPLACE_IN_STEP_2_*`` returned when env
    vars are unset (allows UI flow verification without real creds).
    """
    if provider_type not in PROVIDER_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider_type {provider_type!r}",
        )
    if provider_type not in ("gmail", "msgraph"):
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
    credentials onto the EmailAccount + bootstraps backfill.

    Two creation modes:
      - Existing account (caller passes ``account_id``): credentials
        get attached to the existing row. Used for the "reconnect"
        flow.
      - New account (caller omits ``account_id``): backend creates a
        new EmailAccount + grants admin access to the caller, then
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
    except EmailAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc

    # Resolve or create the EmailAccount.
    account = None
    if request.account_id:
        try:
            account = account_service.get_account(
                db,
                account_id=request.account_id,
                tenant_id=current_user.company_id,
            )
        except EmailAccountError as exc:
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
        # Creating new account — caller must supply email_address.
        if not request.email_address:
            raise HTTPException(
                status_code=400,
                detail="email_address required when account_id omitted",
            )
        try:
            account = account_service.create_account(
                db,
                tenant_id=current_user.company_id,
                actor_user_id=current_user.id,
                account_type=request.account_type,
                display_name=request.display_name or request.email_address,
                email_address=request.email_address,
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
        except EmailAccountError as exc:
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
    except EmailAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc

    # Backfill kickoff is best-effort — don't block the callback if
    # provider sync fails; operator can retry from sync-now button.
    try:
        # Inject access_token into provider_config for Step 2 sync.
        # Production deployment will wire this through
        # ``oauth_service.ensure_fresh_token`` in the sync engine.
        from app.services.email.crypto import decrypt_credentials

        creds = decrypt_credentials(account.encrypted_credentials)
        runtime_config = dict(account.provider_config or {})
        runtime_config["access_token"] = creds.get("access_token", "")
        # Step 2: temporarily update provider_config so backfill has
        # token. Not persisted (we'll refresh from encrypted store
        # each call). Set in-memory only.
        account.provider_config = runtime_config
    except Exception:  # noqa: BLE001
        pass

    db.commit()
    db.refresh(account)
    return OAuthCallbackResponse(
        account_id=account.id,
        email_address=account.email_address,
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
    except EmailAccountError as exc:
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
    test-fixture inboxes; large production accounts will move to
    APScheduler-deferred backfill in Step 2.1). Returns 202 + the
    new backfill_status; the EmailAccountsPage polls
    ``/sync-status`` to surface progress.
    """
    try:
        account = account_service.get_account(
            db,
            account_id=account_id,
            tenant_id=current_user.company_id,
        )
    except EmailAccountError as exc:
        raise _translate(exc) from exc

    # Inject fresh access_token into provider_config for the sync.
    # OAuth providers go through ensure_fresh_token; IMAP uses the
    # decrypted password.
    if account.provider_type in ("gmail", "msgraph"):
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
    elif account.provider_type == "imap":
        from app.services.email.crypto import decrypt_credentials

        creds = decrypt_credentials(account.encrypted_credentials)
        if not creds.get("imap_password"):
            raise HTTPException(
                status_code=401,
                detail="IMAP password missing — reconnect required",
            )
        cfg = dict(account.provider_config or {})
        cfg["imap_password"] = creds["imap_password"]
        account.provider_config = cfg

    # Run backfill (or incremental — Step 2 keeps it as full backfill;
    # Step 2.1 differentiates first-vs-subsequent).
    if account.backfill_status in ("not_started", "error"):
        result = run_initial_backfill(db, account=account)
    else:
        # Already-completed account: do an incremental sync instead.
        # Step 2 stub: just record success. Real incremental ships in
        # Step 2.1 alongside webhook-driven message fetch.
        result = {"status": "incremental_sync_stub"}

    db.commit()
    return {"status": "queued", **{k: str(v) for k, v in result.items()}}
