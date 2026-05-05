"""Personalization Studio API routes — Phase 1B canvas implementation.

Per §3.26.11.12.19 Personalization Studio canonical category +
§3.26.11.12 Generation Focus canon: this router exposes the canonical
Generation Focus instance lifecycle service to frontend consumers
(Phase 1B canvas implementation).

**Canonical endpoint set** (Phase 1A canonical-pattern-establisher
service + Phase 1B canvas commit boundary):

- ``POST /personalization-studio/instances`` — open new instance
  (canonical Document substrate + GenerationFocusInstance row created)
- ``GET /personalization-studio/instances/{id}`` — fetch instance
  metadata (lifecycle + linkage + Document FK)
- ``GET /personalization-studio/instances/{id}/canvas-state`` — read
  current canvas state from canonical Document substrate
- ``POST /personalization-studio/instances/{id}/commit-canvas-state``
  — persist canvas state to new DocumentVersion (canonical canvas
  commit boundary at edit-finish per Phase 1B)
- ``POST /personalization-studio/instances/{id}/commit`` — transition
  lifecycle ``active`` → ``committed`` (canonical bounded-output
  closure per §3.26.11.12.4)
- ``POST /personalization-studio/instances/{id}/abandon`` — transition
  lifecycle ``active`` → ``abandoned``
- ``GET /personalization-studio/instances`` — list instances for a
  linked entity (canonical query pattern: "what Generation Focus
  instances exist for FH case X?" or "for sales order Y?")

**Authorization**: caller must be authenticated tenant member.
Cross-tenant access returns canonical existence-hiding 404.

**Canonical anti-pattern guards explicit at API substrate**:
- §3.26.11.12.16 Anti-pattern 1 (auto-commit on extraction confidence
  rejected): canvas commit is canonical operator-decision boundary;
  frontend canonical operator agency required at canonical commit
  affordance
- §2.4.4 Anti-pattern 8 (vertical-specific code creep): API is canonical
  Generation Focus substrate, NOT FH-vertical or Mfg-vertical specific
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models import User
from app.models.company import Company
from app.models.fh_case import FHCase
from app.services.delivery import delivery_service
from app.services.personalization_studio import (
    ai_extraction_review,
    family_approval,
    instance_service,
)
from app.services.personalization_studio.instance_service import (
    PersonalizationStudioError,
    PersonalizationStudioInvalidTransition,
    PersonalizationStudioNotFound,
)
from app.services.platform.action_service import build_magic_link_url


router = APIRouter()


# ─────────────────────────────────────────────────────────────────────
# Pydantic schemas — canonical API request/response shapes
# ─────────────────────────────────────────────────────────────────────


class OpenInstanceRequest(BaseModel):
    """Canonical request to open a new Generation Focus instance.

    Canonical authoring_context ↔ linked_entity_type Q3 pairing
    enforced at service layer (§3.26.11.12.19.3 baked).
    """

    template_type: Literal["burial_vault_personalization_studio"] = Field(
        ...,
        description=(
            "Canonical Generation Focus template type per Phase 1A "
            "canonical-pattern-establisher. Step 2 extends with "
            "``urn_vault_personalization_studio``."
        ),
    )
    authoring_context: Literal[
        "funeral_home_with_family",
        "manufacturer_without_family",
        "manufacturer_from_fh_share",
    ] = Field(
        ...,
        description=(
            "Canonical 3-value authoring_context discriminator per "
            "§3.26.11.12.19.3 Q3 baked canonical."
        ),
    )
    linked_entity_id: str = Field(
        ...,
        description=(
            "Canonical linked entity UUID. Q3 canonical pairing: "
            "``funeral_home_with_family`` ↔ fh_case; "
            "``manufacturer_without_family`` ↔ sales_order; "
            "``manufacturer_from_fh_share`` ↔ document_share."
        ),
    )


class InstanceResponse(BaseModel):
    """Canonical Generation Focus instance metadata response."""

    id: str
    company_id: str
    template_type: str
    authoring_context: str
    lifecycle_state: str
    linked_entity_type: str
    linked_entity_id: str
    document_id: str | None
    opened_at: str
    opened_by_user_id: str | None
    last_active_at: str
    committed_at: str | None
    committed_by_user_id: str | None
    abandoned_at: str | None
    abandoned_by_user_id: str | None
    family_approval_status: str | None
    family_approval_requested_at: str | None
    family_approval_decided_at: str | None


class CanvasStateResponse(BaseModel):
    """Canonical canvas state response — JSON shape from Document substrate."""

    canvas_state: dict[str, Any] | None = Field(
        ...,
        description=(
            "Canonical canvas state JSON. None when no canvas commit "
            "has been made yet (instance opened but no commit)."
        ),
    )


class CommitCanvasStateRequest(BaseModel):
    """Canonical canvas commit request — canvas state JSON payload.

    Per Phase A Session 3.8.3 canonical compositor pattern: canvas
    commits at canonical edit-finish boundary (NOT every drag frame).
    Frontend canonical operator agency required at canonical commit
    affordance per §3.26.11.12.16 Anti-pattern 1.
    """

    canvas_state: dict[str, Any] = Field(
        ...,
        description=(
            "Canonical canvas state per discovery output Section 2a + "
            "Phase 1A canonical-pattern-establisher schema."
        ),
    )


class CommitCanvasStateResponse(BaseModel):
    """Canonical canvas commit response — DocumentVersion metadata."""

    document_version_id: str
    version_number: int
    storage_key: str


# ─────────────────────────────────────────────────────────────────────
# Error translation — service errors → HTTPException
# ─────────────────────────────────────────────────────────────────────


def _translate(exc: PersonalizationStudioError) -> HTTPException:
    """Translate canonical service errors to HTTP exceptions per service substrate."""
    return HTTPException(status_code=exc.http_status, detail=str(exc))


def _instance_to_response(instance) -> InstanceResponse:
    """Serialize canonical GenerationFocusInstance to canonical API response shape."""

    def _iso(ts):
        return ts.isoformat() if ts else None

    return InstanceResponse(
        id=instance.id,
        company_id=instance.company_id,
        template_type=instance.template_type,
        authoring_context=instance.authoring_context,
        lifecycle_state=instance.lifecycle_state,
        linked_entity_type=instance.linked_entity_type,
        linked_entity_id=instance.linked_entity_id,
        document_id=instance.document_id,
        opened_at=_iso(instance.opened_at),
        opened_by_user_id=instance.opened_by_user_id,
        last_active_at=_iso(instance.last_active_at),
        committed_at=_iso(instance.committed_at),
        committed_by_user_id=instance.committed_by_user_id,
        abandoned_at=_iso(instance.abandoned_at),
        abandoned_by_user_id=instance.abandoned_by_user_id,
        family_approval_status=instance.family_approval_status,
        family_approval_requested_at=_iso(instance.family_approval_requested_at),
        family_approval_decided_at=_iso(instance.family_approval_decided_at),
    )


# ─────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────


@router.post(
    "/instances",
    response_model=InstanceResponse,
    status_code=201,
)
def post_open_instance(
    body: OpenInstanceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InstanceResponse:
    """Open new canonical Generation Focus instance.

    Creates canonical ``GenerationFocusInstance`` row + canonical
    ``Document`` substrate row (per D-9). First ``DocumentVersion``
    created on first canvas commit per §3.26.11.12.5 substrate-consumption
    canonical.
    """
    try:
        instance = instance_service.open_instance(
            db,
            company_id=current_user.company_id,
            template_type=body.template_type,
            authoring_context=body.authoring_context,
            linked_entity_id=body.linked_entity_id,
            opened_by_user_id=current_user.id,
        )
        db.commit()
        db.refresh(instance)
        return _instance_to_response(instance)
    except PersonalizationStudioError as exc:
        db.rollback()
        raise _translate(exc) from exc


@router.get(
    "/instances/{instance_id}",
    response_model=InstanceResponse,
)
def get_instance(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InstanceResponse:
    """Fetch canonical Generation Focus instance metadata.

    Tenant-scoped per canonical multi-tenant isolation; cross-tenant
    access returns canonical existence-hiding 404.
    """
    try:
        instance = instance_service.get_instance(
            db,
            instance_id=instance_id,
            company_id=current_user.company_id,
        )
        return _instance_to_response(instance)
    except PersonalizationStudioError as exc:
        raise _translate(exc) from exc


@router.get(
    "/instances/{instance_id}/canvas-state",
    response_model=CanvasStateResponse,
)
def get_canvas_state(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CanvasStateResponse:
    """Read canonical canvas state from canonical Document substrate.

    Returns the current ``DocumentVersion``'s canvas state JSON (most
    recently committed). Returns ``canvas_state: null`` when no commit
    has been made.
    """
    try:
        # Canonical multi-tenant isolation via get_instance.
        instance_service.get_instance(
            db,
            instance_id=instance_id,
            company_id=current_user.company_id,
        )
        canvas_state = instance_service.get_canvas_state(
            db, instance_id=instance_id
        )
        return CanvasStateResponse(canvas_state=canvas_state)
    except PersonalizationStudioError as exc:
        raise _translate(exc) from exc


@router.post(
    "/instances/{instance_id}/commit-canvas-state",
    response_model=CommitCanvasStateResponse,
    status_code=200,
)
def post_commit_canvas_state(
    instance_id: str,
    body: CommitCanvasStateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommitCanvasStateResponse:
    """Commit canonical canvas state to canonical Document substrate.

    Per Phase A Session 3.8.3 canonical compositor pattern: canvas
    commits canonical at canonical edit-finish boundary. Each commit
    creates new ``DocumentVersion`` with ``is_current=True`` flip per
    canonical D-9 versioning. FH-vertical authoring context triggers
    canonical ``case_merchandise.vault_personalization`` JSONB
    denormalization (best-effort).
    """
    try:
        # Canonical multi-tenant isolation: verify ownership before commit.
        instance_service.get_instance(
            db,
            instance_id=instance_id,
            company_id=current_user.company_id,
        )
        version = instance_service.commit_canvas_state(
            db,
            instance_id=instance_id,
            canvas_state=body.canvas_state,
            committed_by_user_id=current_user.id,
        )
        db.commit()
        db.refresh(version)
        return CommitCanvasStateResponse(
            document_version_id=version.id,
            version_number=version.version_number,
            storage_key=version.storage_key,
        )
    except PersonalizationStudioInvalidTransition as exc:
        db.rollback()
        raise _translate(exc) from exc
    except PersonalizationStudioError as exc:
        db.rollback()
        raise _translate(exc) from exc


@router.post(
    "/instances/{instance_id}/commit",
    response_model=InstanceResponse,
    status_code=200,
)
def post_commit_instance(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InstanceResponse:
    """Commit canonical Generation Focus instance — bounded-output closure.

    Transitions canonical lifecycle_state ``active`` → ``committed``
    per §3.26.11.12.4 closure semantics. The current
    ``DocumentVersion`` becomes the canonical final canvas state for
    the linked entity.

    Phase 1G — canonical Mfg-side post-commit cascade fires when
    canonical instance is at canonical ``manufacturer_from_fh_share``
    authoring context (canonical "Mark reviewed" semantics per Phase
    1F flagged scope). Cascade canonical-emits canonical V-1d Mfg-
    tenant admin notification + canonical D-6 ``reviewed`` audit event.
    Canonical separation: cascade failures do NOT roll back canonical
    Phase 1F lifecycle commit.
    """
    try:
        instance_service.get_instance(
            db,
            instance_id=instance_id,
            company_id=current_user.company_id,
        )
        instance = instance_service.commit_instance(
            db,
            instance_id=instance_id,
            committed_by_user_id=current_user.id,
        )
        db.commit()
        db.refresh(instance)

        # Phase 1G — canonical Mfg-from-FH-share post-commit cascade.
        # Canonical no-op canonical-skip on canonical FH-vertical +
        # canonical manufacturer_without_family contexts.
        try:
            instance_service.manufacturer_from_fh_share_post_commit_cascade(
                db, instance=instance
            )
            db.commit()
        except Exception:  # noqa: BLE001 — canonical best-effort cascade
            db.rollback()
            import logging
            logging.getLogger(__name__).exception(
                "personalization_studio.commit_instance canonical-"
                "cascade-failure instance_id=%s",
                instance.id,
            )

        return _instance_to_response(instance)
    except PersonalizationStudioError as exc:
        db.rollback()
        raise _translate(exc) from exc


@router.post(
    "/instances/{instance_id}/abandon",
    response_model=InstanceResponse,
    status_code=200,
)
def post_abandon_instance(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InstanceResponse:
    """Abandon canonical Generation Focus instance.

    Canonical lifecycle abandon path per §3.26.11.12.5; symmetric with
    canonical ``commit`` path. Used for incomplete / cancelled /
    superseded instances.
    """
    try:
        instance_service.get_instance(
            db,
            instance_id=instance_id,
            company_id=current_user.company_id,
        )
        instance = instance_service.abandon_instance(
            db,
            instance_id=instance_id,
            abandoned_by_user_id=current_user.id,
        )
        db.commit()
        db.refresh(instance)
        return _instance_to_response(instance)
    except PersonalizationStudioError as exc:
        db.rollback()
        raise _translate(exc) from exc


# ─────────────────────────────────────────────────────────────────────
# Phase 1C — AI-extraction-review pipeline endpoints
#
# Per §3.26.11.12.20 Generation Focus extraction adapter category +
# §3.26.11.12.21 operational modes + §3.26.11.12.16 Anti-pattern 1
# (auto-commit on extraction confidence rejected) + DESIGN_LANGUAGE
# §14.14.3 visual canon.
#
# Three canonical operator-initiated endpoints:
#  - POST /instances/{id}/suggest-layout
#  - POST /instances/{id}/suggest-text-style
#  - POST /instances/{id}/extract-decedent-info (multimodal)
#
# All return canonical confidence-scored suggestion payload for
# canonical AI-extraction-review chrome rendering per §14.14.3.
# Canonical anti-pattern guard: endpoints return canonical line items;
# canonical Confirm action canonical at chrome substrate applies
# canonical line item to canvas state via canonical operator agency.
# ─────────────────────────────────────────────────────────────────────


class SuggestionLineItem(BaseModel):
    """Canonical confidence-scored line item per §14.14.3 visual canon.

    Canonical anti-pattern guard at schema substrate: confidence per
    line item is canonically REQUIRED; canonical confidence_tier
    annotation enables canonical chrome substrate visual treatment per
    §14.14.3 (≥0.85 success / 0.70-0.85 warning / <0.70 error).
    """

    line_item_key: str | None
    value: Any
    confidence: float = Field(..., ge=0, le=1)
    rationale: str | None = None
    confidence_tier: str = Field(
        ...,
        description=(
            "Canonical confidence tier per §14.14.3: 'high' (≥0.85) | "
            "'medium' (0.70-0.85) | 'low' (<0.70). Enables canonical "
            "chrome substrate visual treatment per canonical Pattern 2 "
            "sub-cards."
        ),
    )


class SuggestionPayloadResponse(BaseModel):
    """Canonical AI-extraction-review pipeline response payload.

    Canonical anti-pattern guard at schema substrate per §3.26.11.12.16
    Anti-pattern 11: canonical line items canonical at canonical
    Intelligence prompt substrate; canonical chrome substrate consumes
    canonical line items via canonical Pattern 2 sub-cards per §14.14.3.
    """

    line_items: list[SuggestionLineItem]
    execution_id: str | None = None
    model_used: str | None = None
    latency_ms: int | None = None


class SuggestTextStyleRequest(BaseModel):
    """Canonical suggest_text_style request — canonical family preferences
    optional canonical text context."""

    family_preferences: str | None = None


class ContentBlock(BaseModel):
    """Canonical Phase 2c-0b multimodal content block.

    Mirrors canonical Anthropic content_block shape per
    ``intelligence_service._validate_content_blocks``:
      {"type": "image" | "document",
       "source": {"type": "base64", "media_type": ..., "data": ...}}
    """

    type: str = Field(..., pattern="^(image|document)$")
    source: dict[str, Any]


class ExtractDecedentInfoRequest(BaseModel):
    """Canonical extract_decedent_info request — canonical multimodal
    content_blocks per Phase 2c-0b substrate.

    Canonical anti-pattern guard: canonical operator-supplied source
    materials canonical at canonical content_blocks; canonical
    Intelligence prompt receives canonical multimodal payload via
    canonical execute() content_blocks kwarg.
    """

    content_blocks: list[ContentBlock] = Field(
        ...,
        min_length=1,
        description=(
            "Canonical Phase 2c-0b multimodal content blocks. At least "
            "one canonical content block (PDF or image) required."
        ),
    )
    context_summary: str | None = None


@router.post(
    "/instances/{instance_id}/suggest-layout",
    response_model=SuggestionPayloadResponse,
    status_code=200,
)
def post_suggest_layout(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SuggestionPayloadResponse:
    """Canonical operator-initiated canvas layout suggestion request.

    Invokes canonical ``intelligence_service.execute()`` with canonical
    case data + canonical selected vault product + canonical 4-options
    selections per canonical post-r74 vocabulary. Returns canonical
    confidence-scored canvas layout suggestion line items for canonical
    AI-extraction-review chrome rendering per §14.14.3.

    Canonical anti-pattern guard per §3.26.11.12.16 Anti-pattern 1:
    endpoint returns canonical line items only; canonical Confirm action
    canonical at chrome substrate applies canonical line item to canvas
    state via canonical operator agency. No canonical canvas-state
    mutation at endpoint substrate.
    """
    try:
        payload = ai_extraction_review.suggest_layout(
            db,
            instance_id=instance_id,
            company_id=current_user.company_id,
        )
        return SuggestionPayloadResponse(**payload)
    except PersonalizationStudioError as exc:
        raise _translate(exc) from exc


@router.post(
    "/instances/{instance_id}/suggest-text-style",
    response_model=SuggestionPayloadResponse,
    status_code=200,
)
def post_suggest_text_style(
    instance_id: str,
    body: SuggestTextStyleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SuggestionPayloadResponse:
    """Canonical operator-initiated text style suggestion request.

    Invokes canonical ``intelligence_service.execute()`` with canonical
    deceased name + family preferences. Returns canonical confidence-
    scored font + size + color suggestion line items.

    Canonical anti-pattern guard per §3.26.11.12.16 Anti-pattern 1:
    canonical Confirm action canonical at chrome substrate.
    """
    try:
        payload = ai_extraction_review.suggest_text_style(
            db,
            instance_id=instance_id,
            company_id=current_user.company_id,
            family_preferences=body.family_preferences,
        )
        return SuggestionPayloadResponse(**payload)
    except PersonalizationStudioError as exc:
        raise _translate(exc) from exc


@router.post(
    "/instances/{instance_id}/extract-decedent-info",
    response_model=SuggestionPayloadResponse,
    status_code=200,
)
def post_extract_decedent_info(
    instance_id: str,
    body: ExtractDecedentInfoRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SuggestionPayloadResponse:
    """Canonical operator-initiated decedent info extraction request.

    Invokes canonical ``intelligence_service.execute()`` with canonical
    multimodal content_blocks (PDFs + images) per canonical Phase 2c-0b
    multimodal substrate. Returns canonical confidence-scored decedent
    extraction line items.

    Canonical anti-pattern guard per §3.26.11.12.16 Anti-pattern 1:
    canonical Confirm action canonical at chrome substrate applies
    canonical line item to canvas state via canonical operator agency.

    Canonical anti-pattern guard per §3.26.11.12.16 Anti-pattern 12:
    canonical AI-extraction-review pipeline single canonical architecture
    across canonical adapter source categories — canonical multimodal
    content_blocks substrate canonical at canonical extraction adapter
    category per §3.26.11.12.20.
    """
    try:
        payload = ai_extraction_review.extract_decedent_info(
            db,
            instance_id=instance_id,
            company_id=current_user.company_id,
            content_blocks=[block.model_dump() for block in body.content_blocks],
            context_summary=body.context_summary,
        )
        return SuggestionPayloadResponse(**payload)
    except PersonalizationStudioError as exc:
        raise _translate(exc) from exc


@router.get(
    "/instances",
    response_model=list[InstanceResponse],
)
def list_instances(
    linked_entity_type: str,
    linked_entity_id: str,
    template_type: str | None = None,
    lifecycle_state: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[InstanceResponse]:
    """List canonical Generation Focus instances for a linked entity.

    Canonical query pattern per Phase 1A canonical-pattern-establisher:
    "what personalization Generation Focus instances exist for FH
    case X?" or "what instances exist for sales order Y?"

    Filtered to caller's company_id for canonical multi-tenant isolation.
    """
    try:
        instances = instance_service.list_instances_for_linked_entity(
            db,
            company_id=current_user.company_id,
            linked_entity_type=linked_entity_type,
            linked_entity_id=linked_entity_id,
            template_type=template_type,
            lifecycle_state=lifecycle_state,
        )
        return [_instance_to_response(i) for i in instances]
    except PersonalizationStudioError as exc:
        raise _translate(exc) from exc


# ─────────────────────────────────────────────────────────────────────
# Phase 1E — FH director-initiated family approval request
# ─────────────────────────────────────────────────────────────────────


class RequestFamilyApprovalRequest(BaseModel):
    """Canonical FH-director-initiated family approval request body."""

    family_email: str = Field(
        ...,
        description=(
            "Family recipient email — magic-link delivered here per "
            "§3.26.11.9 + Path B substrate consumption."
        ),
    )
    family_first_name: str | None = Field(
        default=None,
        description="Optional family recipient first name for email greeting.",
    )
    optional_message: str | None = Field(
        default=None,
        description=(
            "Optional FH director note to family. Phase 1E ships the "
            "canonical email template variable schema; the optional "
            "message is currently captured at audit-only level. Future "
            "phase canonical extension at template variable substrate."
        ),
        max_length=2000,
    )


class RequestFamilyApprovalResponse(BaseModel):
    """Canonical response — does NOT leak the raw token to the FH-realm
    caller (token goes only via the magic-link email to the family
    recipient per §3.26.11.9 kill-the-portal canon)."""

    instance_id: str
    action_idx: int
    family_email: str
    family_approval_status: str
    delivery_id: str | None = Field(
        default=None,
        description=(
            "DocumentDelivery row id for audit traceability. None when "
            "delivery dispatch fails (best-effort canon — substrate "
            "state still mutates per Step 4.1 contract)."
        ),
    )


@router.post(
    "/instances/{instance_id}/request-family-approval",
    response_model=RequestFamilyApprovalResponse,
    status_code=200,
)
def post_request_family_approval(
    instance_id: str,
    body: RequestFamilyApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RequestFamilyApprovalResponse:
    """Canonical FH-director-initiated family approval request.

    Issues a Path B platform_action_token + dispatches the
    ``email.personalization_studio_family_approval_request`` managed
    email template carrying the magic-link URL. The family clicks the
    link; the family portal Space at
    ``/portal/<slug>/personalization-studio/family-approval/<token>``
    renders the read-only canvas + 3-outcome approval surface.

    Canonical anti-pattern guards explicit at API substrate:
      - §2.5.4 Anti-pattern 13 (net-new portal substrate construction
        rejected) — Path B platform_action_tokens substrate consumption.
      - §2.5.4 Anti-pattern 16 (cross-realm privilege bleed) —
        tenant-realm endpoint requires authenticated User; magic-link
        token (returned only via family email) is the family's sole
        auth factor at the portal endpoint.
      - §3.26.11.12.16 Anti-pattern 1 (operator agency at canonical
        commit affordance) — family approval is canonical operator
        decision at family side; canonical Confirm chrome lives in the
        FH director's RequestFamilyApprovalDialog.
    """
    try:
        # Tenant-scoped instance lookup (existence-hiding 404 cross-tenant).
        instance = instance_service.get_instance(
            db,
            instance_id=instance_id,
            company_id=current_user.company_id,
        )

        # Resolve canonical context for email template rendering.
        company = (
            db.query(Company)
            .filter(Company.id == current_user.company_id)
            .first()
        )
        if company is None:
            raise HTTPException(
                status_code=404,
                detail="Tenant context not found.",
            )
        tenant_name = company.name

        # Resolve canonical decedent name (Q3 canonical pairing —
        # authoring_context=funeral_home_with_family ↔ linked_entity_type
        # =fh_case; family approval canonical to FH-vertical only).
        decedent_name: str | None = None
        if instance.linked_entity_type == "fh_case":
            fh_case = (
                db.query(FHCase)
                .filter(
                    FHCase.id == instance.linked_entity_id,
                    FHCase.company_id == current_user.company_id,
                )
                .first()
            )
            if fh_case is not None:
                first = fh_case.deceased_first_name or ""
                last = fh_case.deceased_last_name or ""
                decedent_name = f"{first} {last}".strip() or None

        fh_director_name = (
            f"{(current_user.first_name or '').strip()} "
            f"{(current_user.last_name or '').strip()}".strip()
            or current_user.email
        )

        # Issue Path B platform_action_token + append action to instance.
        action_idx, token = family_approval.request_family_approval(
            db,
            instance=instance,
            family_email=body.family_email,
            fh_director_user_id=current_user.id,
            fh_director_name=fh_director_name,
            decedent_name=decedent_name,
            vault_product_name=None,
        )

        # Build canonical magic-link URL per §3.26.11.9 + Path B
        # build_magic_link_url. Path-scoped routing under /portal/<slug>
        # canonical per Phase 8e.2 portal foundation.
        base_url = (settings.FRONTEND_URL or "").rstrip("/")
        magic_link_url = (
            f"{base_url}/portal/{company.slug}/personalization-studio/"
            f"family-approval/{token}"
        )

        # Dispatch family-approval-request email via canonical D-7
        # delivery substrate. Best-effort discipline per Step 4.1
        # contract — email failure NEVER blocks substrate state mutation.
        delivery_id: str | None = None
        try:
            delivery = delivery_service.send_email_with_template(
                db,
                company_id=current_user.company_id,
                to_email=body.family_email,
                to_name=body.family_first_name,
                template_key=(
                    "email.personalization_studio_family_approval_request"
                ),
                template_context={
                    "decedent_name": decedent_name or "your loved one",
                    "fh_director_name": fh_director_name,
                    "tenant_name": tenant_name,
                    "approval_url": magic_link_url,
                    # 7-day TTL per Path B canonical TOKEN_TTL_DAYS.
                    "expires_in_copy": "expires in 7 days",
                },
                caller_module=(
                    "personalization_studio.request_family_approval"
                ),
                metadata={
                    "instance_id": instance.id,
                    "action_idx": action_idx,
                    "phase": "phase_1e_family_approval_request",
                },
            )
            delivery_id = delivery.id
        except Exception:  # noqa: BLE001 — best-effort per Step 4.1 contract
            # Per Step 4.1 best-effort discipline: log + continue.
            # Substrate state already mutated; family can be re-invited
            # via fresh request_family_approval call.
            import logging
            logging.getLogger(__name__).exception(
                "Family approval email dispatch failed for instance_id=%s",
                instance.id,
            )

        db.commit()
        db.refresh(instance)

        return RequestFamilyApprovalResponse(
            instance_id=instance.id,
            action_idx=action_idx,
            family_email=body.family_email,
            family_approval_status=instance.family_approval_status or "",
            delivery_id=delivery_id,
        )
    except family_approval.FamilyApprovalInvalidContext as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except family_approval.FamilyApprovalError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PersonalizationStudioError as exc:
        db.rollback()
        raise _translate(exc) from exc


# ─────────────────────────────────────────────────────────────────────
# Phase 1F — Manufacturer-side from-share entry point
# ─────────────────────────────────────────────────────────────────────


class FromShareInstanceResponse(BaseModel):
    """Canonical Mfg-tenant from-share entry point response.

    Surfaces canonical Generation Focus instance metadata + canonical
    canvas state read + canonical attribution from canonical FH-tenant
    owner per Phase 1F build prompt + §14.10.5 canonical magic-link-
    contextual-surface canon (mirrors canonical Phase 1E
    FamilyApprovalContextResponse shape at canonical Mfg-tenant scope).
    """

    instance: InstanceResponse
    canvas_state: dict[str, Any] | None
    document_share_id: str
    owner_company_id: str
    owner_company_name: str | None
    granted_at: str
    decedent_name: str | None


@router.post(
    "/from-share/{document_share_id}",
    response_model=FromShareInstanceResponse,
    status_code=200,
)
def post_open_instance_from_share(
    document_share_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FromShareInstanceResponse:
    """Canonical Mfg-tenant operator-initiated open-from-share entry point.

    Per Phase 1F build prompt + §3.26.11.12.19.3 Q3 canonical pairing:
    Mfg-tenant operator opens canonical share-granted Document at
    canonical ``manufacturer_from_fh_share`` authoring context. Service
    layer canonical-creates ``GenerationFocusInstance`` at canonical
    Mfg-tenant scope + emits canonical D-6 ``accessed`` event +
    returns canonical canvas state read.

    Canonical anti-pattern guards explicit at API substrate:
      - §3.26.11.12.16 Anti-pattern 12 (parallel architectures rejected)
        — canonical Mfg-tenant entry point shares canonical service
        layer with canonical FH-tenant entry point per Q3 canonical
        pairing dispatch; no parallel architecture.
      - Canonical full-disclosure-per-instance per §3.26.11.12.19.4 —
        canonical canvas state surfaces verbatim to canonical Mfg-
        tenant scope (no field-level masking).
    """
    from app.models.canonical_document import Document
    from app.models.company import Company
    from app.models.document_share import DocumentShare

    try:
        instance = instance_service.open_instance_from_share(
            db,
            document_share_id=document_share_id,
            mfg_company_id=current_user.company_id,
            opened_by_user_id=current_user.id,
        )
        db.commit()
        db.refresh(instance)
    except PersonalizationStudioError as exc:
        db.rollback()
        raise _translate(exc) from exc

    # Canonical canvas state read at canonical Document substrate
    # (canonical D-6 ``Document.visible_to`` query path; canonical
    # cross-tenant Document visibility per existing D-6 substrate).
    canvas_state = instance_service.get_canvas_state(
        db, instance_id=instance.id
    )

    # Canonical share + owner metadata for canonical FE chrome
    # consumption (canonical "shared from {fh_tenant_name}" attribution
    # per §14.10.5 canonical canvas-frame-level chrome distinction).
    share = (
        db.query(DocumentShare)
        .filter(DocumentShare.id == document_share_id)
        .first()
    )
    if share is None:
        # Should not happen — open_instance_from_share already validated.
        raise HTTPException(
            status_code=404,
            detail=f"DocumentShare {document_share_id!r} not found.",
        )
    owner_company = (
        db.query(Company)
        .filter(Company.id == share.owner_company_id)
        .first()
    )
    owner_company_name = (
        owner_company.name if owner_company is not None else None
    )

    # Canonical decedent name canonical-resolution at canonical FH-side
    # action_payload (Phase 1E action_metadata snapshot canonical-
    # captured at canonical request_family_approval call).
    fh_owner_instance = (
        db.query(instance_service.GenerationFocusInstance)
        .filter(
            instance_service.GenerationFocusInstance.document_id
            == share.document_id,
            instance_service.GenerationFocusInstance.company_id
            == share.owner_company_id,
        )
        .first()
    )
    decedent_name: str | None = None
    if fh_owner_instance is not None:
        actions = (fh_owner_instance.action_payload or {}).get("actions") or []
        if actions:
            metadata = actions[-1].get("action_metadata") or {}
            decedent_name = metadata.get("decedent_name")

    return FromShareInstanceResponse(
        instance=_instance_to_response(instance),
        canvas_state=canvas_state,
        document_share_id=document_share_id,
        owner_company_id=share.owner_company_id,
        owner_company_name=owner_company_name,
        granted_at=share.granted_at.isoformat(),
        decedent_name=decedent_name,
    )
