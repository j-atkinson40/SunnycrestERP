"""Phase 1E family portal route — magic-link contextual surface.

Per §3.26.11.9 + Path B platform_action_tokens substrate + Phase 1E
build prompt: family approval is rendered through a public token-
authenticated portal endpoint. The family is non-Bridgeable identity;
the magic-link token IS the canonical authentication factor (no JWT,
no PortalUser identity, no password).

**Mounted at** ``/api/v1/portal`` prefix in ``api/v1.py``. Endpoints:

- ``GET /portal/{tenant_slug}/personalization-studio/family-approval/{token}``
  — render the family portal Space chrome + read-only canvas state +
  3-outcome action vocabulary; consumes the FAMILY_PORTAL_SPACE_TEMPLATE.
- ``POST /portal/{tenant_slug}/personalization-studio/family-approval/{token}``
  — commit family decision (approve / request_changes / decline);
  consumes the token atomically.

**Canonical anti-pattern guards explicit at portal-route substrate**:
  - §2.5.4 Anti-pattern 13 (net-new portal substrate construction
    rejected) — magic-link via Path B platform_action_tokens substrate;
    no separate ``family_portal_action_tokens`` table.
  - §2.5.4 Anti-pattern 15 (portal authentication-substrate
    fragmentation rejected) — token is sole authentication factor;
    family is NOT a PortalUser identity.
  - §2.5.4 Anti-pattern 16 (cross-realm privilege bleed rejected) —
    portal endpoint accepts NO JWT; tenant-realm callers cannot reach
    the portal endpoints. Cross-primitive token isolation enforced at
    substrate layer (token's linked_entity_type must be
    'generation_focus_instance').
  - §2.5.4 Anti-pattern 18 (portal-as-replacement-for-tenant-UX
    rejected) — narrow scope: read-only canvas + 3-outcome action
    vocabulary; no parallel tenant UX.
  - §2.5.4 Anti-pattern 19 (per-portal authentication mechanism
    proliferation rejected) — magic-link is single canonical mechanism
    for family approval at September scope.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.canonical_document import Document, DocumentVersion
from app.models.company import Company
from app.services import legacy_r2_client
from app.services.personalization_studio import (
    family_approval,
    instance_service,
)
from app.services.platform.action_service import (
    ActionAlreadyCompleted,
    ActionError,
    ActionNotFound,
    ActionTokenAlreadyConsumed,
    ActionTokenExpired,
    ActionTokenInvalid,
)
from app.services.portal.branding import get_portal_branding
from app.services.spaces.registry import FAMILY_PORTAL_SPACE_TEMPLATE


router = APIRouter()


# ─────────────────────────────────────────────────────────────────────
# Pydantic response shapes — family portal Space rendering
# ─────────────────────────────────────────────────────────────────────


class _PortalSpaceShape(BaseModel):
    """Canonical SpaceConfig modifier slice per §2.5 Portal Extension
    Pattern. The frontend uses these flags to gate the chrome —
    bounded affordances filtered, FH-tenant-branded surface, write_mode
    bounded to limited 3-outcome action vocabulary."""

    template_id: str
    name: str
    icon: str
    accent: str
    access_mode: Literal["portal_external"]
    tenant_branding: bool
    write_mode: Literal["limited"]
    session_timeout_minutes: int


class _PortalBrandingShape(BaseModel):
    """Tenant-branded surface chrome — wash, not reskin (§10.6)."""

    display_name: str
    logo_url: str | None
    brand_color: str


class _CanvasSnapshot(BaseModel):
    """Read-only canvas snapshot for family approval surface.

    Phase 1E ships the canonical canvas state JSON read; presigned
    R2 URLs for any embedded images would be canonical in Phase 1F.
    Family does NOT see the underlying Document storage_key — only
    the canvas-state JSON read at the most recent committed version.
    """

    canvas_state: dict[str, Any] | None
    version_number: int | None


class FamilyApprovalContextResponse(BaseModel):
    """Canonical GET response — full family-portal-rendering payload."""

    instance_id: str
    decedent_name: str | None
    fh_director_name: str | None
    action_status: Literal[
        "pending", "approved", "changes_requested", "declined"
    ]
    outcomes: tuple[str, ...] = family_approval.ACTION_OUTCOMES_FAMILY_APPROVAL
    requires_completion_note: tuple[str, ...] = (
        family_approval.REQUIRES_COMPLETION_NOTE
    )
    canvas: _CanvasSnapshot
    space: _PortalSpaceShape
    branding: _PortalBrandingShape


class FamilyApprovalCommitRequest(BaseModel):
    """Canonical POST request body — family decision."""

    outcome: Literal["approve", "request_changes", "decline"] = Field(
        ...,
        description=(
            "Canonical 3-outcome reviewer-paths per "
            "§3.26.11.12.21. ``request_changes`` + ``decline`` require "
            "completion_note rationale per canonical-rationale discipline."
        ),
    )
    completion_note: str | None = Field(
        default=None,
        description=(
            "Family rationale. REQUIRED for ``request_changes`` + "
            "``decline``; OPTIONAL for ``approve``. Free text, max 4000 "
            "chars."
        ),
        max_length=4000,
    )


class FamilyApprovalCommitResponse(BaseModel):
    """Canonical POST response — terminal action state.

    Phase 1F extends with canonical post-commit dispatch outcome at
    ``share_dispatch`` field. Surfaces canonical D-6 grant fire result
    (granted | ptr_missing | consent_default | consent_pending_outbound
    | consent_pending_inbound) for canonical FE chrome consumption.
    Field is None on non-approve outcomes (request_changes / decline
    do NOT fire canonical cross-tenant share).
    """

    instance_id: str
    outcome: Literal["approve", "request_changes", "decline"]
    action_status: Literal["approved", "changes_requested", "declined"]
    family_approval_status: str | None
    lifecycle_state: str
    share_dispatch: dict[str, Any] | None = None


# ─────────────────────────────────────────────────────────────────────
# Helpers — token validation + tenant-slug binding
# ─────────────────────────────────────────────────────────────────────


def _resolve_tenant_or_404(db: Session, tenant_slug: str) -> Company:
    """Resolve tenant by slug. Returns 404 (existence-hiding) if not
    found — preserves Anti-pattern 16 cross-realm guard at the route
    boundary (no slug-existence leak)."""
    company = (
        db.query(Company).filter(Company.slug == tenant_slug).first()
    )
    if company is None:
        raise HTTPException(
            status_code=404,
            detail="Approval link not found.",
        )
    return company


def _validate_token_tenant_match(
    *,
    token_row: dict[str, Any],
    company: Company,
) -> None:
    """Cross-realm guard — token's tenant_id MUST match URL's tenant
    slug. Prevents a token issued for tenant A from being consumed at
    tenant B's portal URL (existence-hiding 404)."""
    if token_row["tenant_id"] != company.id:
        # Existence-hiding: same shape as token-not-found.
        raise HTTPException(
            status_code=404,
            detail="Approval link not found.",
        )


def _read_current_canvas_snapshot(
    db: Session, *, instance: Any
) -> _CanvasSnapshot:
    """Read the most recent committed canvas state from canonical
    Document substrate (D-9 substrate consumption per §3.26.11.12.5).

    Returns canvas_state=None when no commit has been made yet (instance
    opened but no canvas commit). Per substrate canon — does NOT raise.
    """
    if instance.document_id is None:
        return _CanvasSnapshot(canvas_state=None, version_number=None)

    document = (
        db.query(Document)
        .filter(Document.id == instance.document_id)
        .first()
    )
    if document is None:
        return _CanvasSnapshot(canvas_state=None, version_number=None)

    current = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id == document.id,
            DocumentVersion.is_current.is_(True),
        )
        .first()
    )
    if current is None:
        return _CanvasSnapshot(canvas_state=None, version_number=None)

    # Read canvas state JSON from R2.
    try:
        body = legacy_r2_client.download_bytes(current.storage_key)
        if body is None:
            return _CanvasSnapshot(
                canvas_state=None,
                version_number=current.version_number,
            )
        import json
        canvas_state = json.loads(body.decode("utf-8"))
        return _CanvasSnapshot(
            canvas_state=canvas_state,
            version_number=current.version_number,
        )
    except Exception:  # noqa: BLE001 — defensive R2 read
        return _CanvasSnapshot(
            canvas_state=None,
            version_number=current.version_number,
        )


def _build_space_shape() -> _PortalSpaceShape:
    """Canonical FAMILY_PORTAL_SPACE_TEMPLATE → _PortalSpaceShape.

    Surfaces the canonical Space modifier slice the frontend uses to
    gate chrome (bounded affordances, FH-tenant-branded surface,
    write_mode=limited 3-outcome action vocabulary).
    """
    tpl = FAMILY_PORTAL_SPACE_TEMPLATE
    return _PortalSpaceShape(
        template_id=tpl.template_id,
        name=tpl.name,
        icon=tpl.icon,
        accent=tpl.accent,
        access_mode="portal_external",
        tenant_branding=tpl.tenant_branding,
        write_mode="limited",
        session_timeout_minutes=tpl.session_timeout_minutes or 60,
    )


def _build_branding_shape(
    db: Session, *, company: Company
) -> _PortalBrandingShape:
    """Canonical tenant branding payload — falls back to display_name +
    None logo + canonical default brand_color when branding is unset."""
    branding = get_portal_branding(db, slug=company.slug)
    if branding is None:
        # Defensive default — branding service returns None only when
        # slug doesn't exist; we already verified existence.
        return _PortalBrandingShape(
            display_name=company.name,
            logo_url=None,
            brand_color="#1E40AF",
        )
    return _PortalBrandingShape(
        display_name=branding.display_name,
        logo_url=branding.logo_url,
        brand_color=branding.brand_color,
    )


# ─────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────


@router.get(
    "/{tenant_slug}/personalization-studio/family-approval/{token}",
    response_model=FamilyApprovalContextResponse,
)
def get_family_approval_context(
    tenant_slug: str,
    token: str,
    db: Session = Depends(get_db),
) -> FamilyApprovalContextResponse:
    """Render the family portal Space chrome at the magic-link surface.

    PUBLIC endpoint — token is sole authentication factor. NO JWT
    accepted (Anti-pattern 16 cross-realm privilege bleed guard).

    Consumes the canonical FAMILY_PORTAL_SPACE_TEMPLATE +
    canonical Document substrate (canvas state JSON).
    """
    company = _resolve_tenant_or_404(db, tenant_slug)
    try:
        instance, action = family_approval.process_family_approval_token(
            db, token=token
        )
    except (ActionTokenInvalid, ActionNotFound) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ActionTokenExpired as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except ActionTokenAlreadyConsumed as exc:
        # Render terminal-state surface honestly via 410 — frontend
        # surfaces "this approval has already been recorded" copy.
        raise HTTPException(status_code=410, detail=str(exc)) from exc

    # Cross-tenant token mismatch guard (existence-hiding 404).
    if instance.company_id != company.id:
        raise HTTPException(
            status_code=404,
            detail="Approval link not found.",
        )

    metadata = (action.get("action_metadata") or {})
    canvas = _read_current_canvas_snapshot(db, instance=instance)
    space = _build_space_shape()
    branding = _build_branding_shape(db, company=company)

    return FamilyApprovalContextResponse(
        instance_id=instance.id,
        decedent_name=metadata.get("decedent_name"),
        fh_director_name=metadata.get("fh_director_name"),
        action_status=action.get("action_status", "pending"),
        canvas=canvas,
        space=space,
        branding=branding,
    )


@router.post(
    "/{tenant_slug}/personalization-studio/family-approval/{token}",
    response_model=FamilyApprovalCommitResponse,
    status_code=200,
)
def post_family_approval_commit(
    tenant_slug: str,
    token: str,
    body: FamilyApprovalCommitRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> FamilyApprovalCommitResponse:
    """Commit family decision atomically.

    Validates token + dispatches per-outcome handler + consumes token.
    Per §3.26.11.9 single-shot magic-link discipline — re-commit on a
    consumed token returns 409.
    """
    company = _resolve_tenant_or_404(db, tenant_slug)

    # Pre-fetch token row for tenant-match validation (existence-hiding
    # 404 on cross-tenant attempts).
    from app.services.platform.action_service import lookup_action_token

    try:
        token_row = lookup_action_token(db, token=token)
    except (ActionTokenInvalid, ActionNotFound) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ActionTokenExpired as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except ActionTokenAlreadyConsumed as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _validate_token_tenant_match(token_row=token_row, company=company)

    # Audit trail — capture client IP + user-agent per §3.26.15.8 audit
    # canon. Canonical Path B substrate consumption discipline.
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        family_approval.commit_family_approval_via_token(
            db,
            token=token,
            outcome=body.outcome,
            completion_note=body.completion_note,
            ip_address=client_ip,
            user_agent=user_agent,
        )
    except (ActionTokenInvalid, ActionNotFound) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ActionTokenExpired as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except (ActionTokenAlreadyConsumed, ActionAlreadyCompleted) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ActionError as exc:
        raise HTTPException(
            status_code=getattr(exc, "http_status", 400),
            detail=str(exc),
        ) from exc

    db.commit()

    # Fetch refreshed instance for response.
    instance = instance_service.get_instance(
        db,
        instance_id=token_row["linked_entity_id"],
        company_id=company.id,
    )

    # Phase 1F post-commit DocumentShare grant dispatch — fires only on
    # canonical ``approve`` outcome. Per canonical separation: failures
    # at Phase 1F do NOT roll back the canonical Phase 1E lifecycle
    # commit (the family's canonical decision is durable regardless of
    # canonical cross-tenant share fate). Outcomes surface canonically
    # via ``share_dispatch`` field on response for canonical FE chrome
    # consumption + canonical V-1d FH-tenant admin notification.
    share_dispatch: dict[str, Any] | None = None
    if body.outcome == "approve":
        try:
            share_dispatch = (
                family_approval.family_approval_post_commit_dispatch(
                    db,
                    instance=instance,
                )
            )
            db.commit()
        except Exception:  # noqa: BLE001 — post-commit best-effort
            # Canonical Phase 1E commit is durable; log + continue.
            # FH-tenant admin sees canonical notification via dispatch
            # internals when failure mode is canonical PTR consent
            # gating; unexpected exceptions log here without surfacing
            # to family.
            db.rollback()
            import logging
            logging.getLogger(__name__).exception(
                "personalization_studio.post_commit_dispatch unexpected "
                "failure instance_id=%s",
                instance.id,
            )

    # Map outcome → canonical action_status.
    action_status_map = {
        "approve": "approved",
        "request_changes": "changes_requested",
        "decline": "declined",
    }

    return FamilyApprovalCommitResponse(
        instance_id=instance.id,
        outcome=body.outcome,
        action_status=action_status_map[body.outcome],
        family_approval_status=instance.family_approval_status,
        lifecycle_state=instance.lifecycle_state,
        share_dispatch=share_dispatch,
    )
