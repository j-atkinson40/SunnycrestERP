"""Canonical Documents API — Phase D-1 read surface + Phase D-2 admin
template registry read surface.

Mounted at `/api/v1/documents-v2/*` (the legacy `/documents` routes keep
their semantics against the `documents_legacy` table + old Document
model).

Document endpoints (unchanged from D-1):
  GET    /documents-v2                       — list documents (filters)
  GET    /documents-v2/{document_id}         — detail + version history
  GET    /documents-v2/{document_id}/download
  GET    /documents-v2/{document_id}/versions/{version_id}/download
  POST   /documents-v2/{document_id}/regenerate

D-2 additions:
  GET    /documents-v2/admin/templates                       — list
  GET    /documents-v2/admin/templates/{template_id}         — detail
  GET    /documents-v2/admin/templates/{template_id}/versions/{version_id}

All endpoints are tenant-scoped via `current_user.company_id` and
admin-gated via `require_admin`. Platform super admins see platform
templates + their own tenant's (if any); regular admins see platform
(read-only) + their tenant's (also read-only in D-2 — D-3 adds editing).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models.canonical_document import Document, DocumentVersion
from app.models.document_template import (
    DocumentTemplate,
    DocumentTemplateVersion,
)
from app.models.user import User
from app.schemas.canonical_document import (
    DocumentDetailResponse,
    DocumentListItem,
    DocumentRegenerateRequest,
    DocumentResponse,
    DocumentVersionResponse,
)
from app.schemas.document_template import (
    DeliveryAdHocSendRequest,
    DeliveryDetailResponse,
    DeliveryListItem,
    DocumentLogItem,
    DocumentShareCreateRequest,
    DocumentShareEventResponse,
    DocumentShareResponse,
    DocumentShareRevokeRequest,
    DocumentTemplateDetailResponse,
    DocumentTemplateFilterResponse,
    DocumentTemplateListItem,
    DocumentTemplateVersionResponse,
    DraftCreateRequest,
    DraftUpdateRequest,
    InboxItemResponse,
    MarkInboxReadResponse,
    TemplateActivateRequest,
    TemplateAuditLogEntry,
    TemplateEditPermissionResponse,
    TemplateForkRequest,
    TemplateRollbackRequest,
    TemplateTestRenderRequest,
    TemplateTestRenderResponse,
    ValidationIssueResponse,
    # Phase D-10 — block authoring + document type catalog
    BlockKindResponse,
    DocumentTypeCatalogResponse,
    DocumentTypeCategoryResponse,
    DocumentTypeResponse,
    DocumentTypeStarterBlockResponse,
    TemplateBlockCreateRequest,
    TemplateBlockReorderRequest,
    TemplateBlockResponse,
    TemplateBlockUpdateRequest,
    # Arc 4b.2a — mention substrate
    MentionResolveRequest,
    MentionResolveResponse,
    MentionResolveResponseItem,
)
from app.services.documents import document_renderer, document_sharing_service
from app.services.documents import template_service
from app.services.documents.document_sharing_service import SharingError
from app.services.documents.template_service import TemplateEditError
from app.services.documents.template_validator import (
    validate_template_content,
)
from app.services.documents.block_registry import list_block_kinds
from app.services.documents.block_service import (
    BlockServiceError,
    add_block,
    delete_block,
    list_blocks,
    reorder_blocks,
    update_block,
)
from app.services.documents.document_types import (
    list_categories,
    list_document_types,
)
from app.services.documents.mention_filter import (
    MENTION_PICKER_VOCAB,
    substrate_to_picker_ui_label,
)
from app.services.command_bar.resolver import resolve as resolver_resolve

router = APIRouter()


def _get_visible_document(
    db: Session, document_id: str, company_id: str
) -> Document:
    """Resolve a Document visible to `company_id` — either they own it
    OR an active DocumentShare grants read access.

    Phase D-6: routes through `Document.visible_to()` so shared documents
    are accessible to target tenants. Pre-D-6 this was owner-only.
    """
    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.visible_to(company_id),
            Document.deleted_at.is_(None),
        )
        .first()
    )
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return doc


@router.get("", response_model=list[DocumentListItem])
def list_documents(
    document_type: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    template_key: str | None = Query(None),
    intelligence_generated: bool | None = Query(
        None,
        description=(
            "If true, return only docs with intelligence_execution_id set. "
            "If false, only docs without."
        ),
    ),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List documents visible to the current tenant, newest first.

    D-2 additions: `template_key` filter, `intelligence_generated` filter.
    D-6: uses `Document.visible_to()` so the list includes both owned
    documents AND documents shared TO this tenant via an active
    DocumentShare. Add `?scope=owned` to restrict to owned-only.
    """
    q = db.query(Document).filter(
        Document.visible_to(current_user.company_id),
        Document.deleted_at.is_(None),
    )
    if document_type:
        q = q.filter(Document.document_type == document_type)
    if entity_type:
        q = q.filter(Document.entity_type == entity_type)
    if entity_id:
        q = q.filter(Document.entity_id == entity_id)
    if status_filter:
        q = q.filter(Document.status == status_filter)
    if date_from:
        q = q.filter(Document.created_at >= date_from)
    if date_to:
        q = q.filter(Document.created_at <= date_to)
    if template_key:
        q = q.filter(Document.template_key == template_key)
    if intelligence_generated is True:
        q = q.filter(Document.intelligence_execution_id.isnot(None))
    elif intelligence_generated is False:
        q = q.filter(Document.intelligence_execution_id.is_(None))

    rows = (
        q.order_by(desc(Document.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return rows


@router.get("/log", response_model=list[DocumentLogItem])
def list_document_log(
    document_type: str | None = Query(None),
    template_key: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    entity_type: str | None = Query(None),
    intelligence_generated: bool | None = Query(None),
    include_test_renders: bool = Query(
        False,
        description=(
            "If true, include documents with is_test_render=True "
            "(admin template-editor test runs)."
        ),
    ),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """D-2 Document Log endpoint — richer schema than the /documents list,
    exposing template_key, intelligence_execution_id, caller_module,
    caller_workflow_run_id for the admin Document Log UI.

    Defaults to last 7 days when no date range is specified. D-3: test
    renders are excluded by default; pass `include_test_renders=true` to
    include them.
    """
    if date_from is None and date_to is None:
        date_from = datetime.now(timezone.utc) - timedelta(days=7)

    q = db.query(Document).filter(
        Document.visible_to(current_user.company_id),
        Document.deleted_at.is_(None),
    )
    if not include_test_renders:
        q = q.filter(Document.is_test_render.is_(False))
    if document_type:
        q = q.filter(Document.document_type == document_type)
    if template_key:
        q = q.filter(Document.template_key == template_key)
    if status_filter:
        q = q.filter(Document.status == status_filter)
    if entity_type:
        q = q.filter(Document.entity_type == entity_type)
    if intelligence_generated is True:
        q = q.filter(Document.intelligence_execution_id.isnot(None))
    elif intelligence_generated is False:
        q = q.filter(Document.intelligence_execution_id.is_(None))
    if date_from:
        q = q.filter(Document.created_at >= date_from)
    if date_to:
        q = q.filter(Document.created_at <= date_to)

    rows = (
        q.order_by(desc(Document.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return rows


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document_detail(
    document_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Full document detail, including all version history ordered by
    version_number ascending."""
    doc = _get_visible_document(db, document_id, current_user.company_id)
    versions = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == doc.id)
        .order_by(DocumentVersion.version_number)
        .all()
    )
    resp = DocumentDetailResponse.model_validate(doc)
    resp.versions = [
        DocumentVersionResponse.model_validate(v) for v in versions
    ]
    return resp


@router.get("/{document_id}/download")
def download_document(
    document_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """307 redirect to a presigned R2 URL for the current version."""
    doc = _get_visible_document(db, document_id, current_user.company_id)
    try:
        url = document_renderer.presigned_url(doc, expires_in=3600)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Could not generate download URL: {exc}",
        )
    return RedirectResponse(url=url, status_code=307)


@router.get("/{document_id}/versions/{version_id}/download")
def download_version(
    document_id: str,
    version_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """307 redirect to a presigned R2 URL for a specific version."""
    doc = _get_visible_document(db, document_id, current_user.company_id)
    version = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == doc.id,
        )
        .first()
    )
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")

    # Reuse legacy_r2_client directly — the renderer.presigned_url helper
    # only knows about the current-version storage_key.
    from app.services import legacy_r2_client

    try:
        url = legacy_r2_client.generate_signed_url(
            version.storage_key, expires_in=3600,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Could not generate download URL: {exc}",
        )
    return RedirectResponse(url=url, status_code=307)


@router.post("/{document_id}/regenerate", response_model=DocumentResponse)
def regenerate_document(
    document_id: str,
    body: DocumentRegenerateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Re-render an existing document.

    Creates a new DocumentVersion, flips the prior version's is_current,
    updates the Document row's mirrored fields. Optional
    `context_override` merges into whatever context the renderer would
    otherwise build; for D-1, the context override is the ONLY context
    source (the generator-specific services aren't re-invoked here).

    Callers that want a regeneration with a freshly-built context should
    invoke the source generator (e.g. `generate_invoice_document`)
    instead.
    """
    doc = _get_visible_document(db, document_id, current_user.company_id)
    if not doc.template_key:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Document has no template_key — cannot regenerate",
        )
    # Use the context from the last version's stored inputs if we had them.
    # For D-1 we don't persist the input context on DocumentVersion, so
    # callers must pass context_override if they want different data.
    context = body.context_override or {}
    try:
        doc = document_renderer.rerender(
            db,
            document_id=document_id,
            context=context,
            render_reason=body.reason,
            rendered_by_user_id=current_user.id,
        )
    except document_renderer.DocumentRenderError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc),
        )
    db.commit()
    db.refresh(doc)
    return doc


# ── Phase D-2 admin template registry — read surface ───────────────────


@router.get(
    "/admin/templates",
    response_model=DocumentTemplateFilterResponse,
)
def list_document_templates(
    document_type: str | None = Query(None),
    output_format: str | None = Query(None),
    scope: str | None = Query(
        None,
        description="'platform' | 'tenant' | 'both' (default: both for tenant admins, platform only for super admins with no tenant)",
    ),
    search: str | None = Query(None),
    status_filter: str | None = Query(
        None,
        alias="status",
        description="'active' shows only is_active=True; 'all' includes inactive",
    ),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List templates visible to the caller. See
    `template_service.list_templates` for visibility rules."""
    items, total = template_service.list_templates(
        db,
        current_company_id=current_user.company_id,
        document_type=document_type,
        output_format=output_format,
        scope=scope,
        search=search,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return DocumentTemplateFilterResponse(
        items=[DocumentTemplateListItem(**i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/admin/templates/{template_id}",
    response_model=DocumentTemplateDetailResponse,
)
def get_document_template_detail(
    template_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Full template detail — includes the active version body + all
    version summaries."""
    detail = template_service.get_template_detail(
        db, template_id, current_company_id=current_user.company_id
    )
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    return detail


@router.get(
    "/admin/templates/{template_id}/versions/{version_id}",
    response_model=DocumentTemplateVersionResponse,
)
def get_document_template_version(
    template_id: str,
    version_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Full content of a specific version."""
    version = template_service.get_version(
        db,
        template_id,
        version_id,
        current_company_id=current_user.company_id,
    )
    if version is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Version not found"
        )
    return version


# ── Phase D-3 editing: draft CRUD, activate, rollback, fork, test-render, audit ──


def _get_visible_template_or_404(
    db: Session, template_id: str, current_company_id: str | None
) -> DocumentTemplate:
    """404 unless the template is this tenant's or platform-global."""
    t = template_service.get_template(db, template_id)
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    if t.company_id is not None and t.company_id != current_company_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    return t


def _validate_edit_permission(
    user: User, template: DocumentTemplate
) -> TemplateEditPermissionResponse:
    """Two-tier permission: super_admin for platform-global, admin for
    tenant. Forks are allowed for tenant admins from platform templates
    (creates a tenant-scoped copy)."""
    is_super = bool(getattr(user, "is_super_admin", False))
    if template.company_id is None:
        # Platform-global
        if is_super:
            return TemplateEditPermissionResponse(
                can_edit=True,
                requires_super_admin=True,
                requires_confirmation_text=True,
                can_fork=True,
            )
        return TemplateEditPermissionResponse(
            can_edit=False,
            reason=(
                "Editing platform-global templates requires super_admin "
                "role. You can fork this template to your tenant to "
                "customize it."
            ),
            requires_super_admin=True,
            requires_confirmation_text=True,
            can_fork=user.company_id is not None,
        )
    # Tenant-scoped
    return TemplateEditPermissionResponse(
        can_edit=True,
        requires_super_admin=False,
        requires_confirmation_text=False,
        can_fork=False,
    )


def _enforce_edit_permission(
    user: User, template: DocumentTemplate
) -> None:
    perm = _validate_edit_permission(user, template)
    if not perm.can_edit:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            perm.reason or "Edit permission denied",
        )


def _assert_confirmation_text(
    template: DocumentTemplate, provided: str | None
) -> None:
    """Platform-global edits require the template_key typed verbatim."""
    if template.company_id is None:
        if (provided or "").strip() != template.template_key:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Confirmation text must match the template_key "
                f"({template.template_key!r}) for platform-global edits.",
            )


def _get_version_on_template(
    db: Session, template_id: str, version_id: str
) -> DocumentTemplateVersion:
    v = (
        db.query(DocumentTemplateVersion)
        .filter(
            DocumentTemplateVersion.id == version_id,
            DocumentTemplateVersion.template_id == template_id,
        )
        .first()
    )
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    return v


def _raise_edit_error(exc: TemplateEditError) -> None:
    raise HTTPException(exc.http_status, str(exc))


@router.get(
    "/admin/templates/{template_id}/edit-permission",
    response_model=TemplateEditPermissionResponse,
)
def get_template_edit_permission(
    template_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Preflight — UI calls this to decide whether to show the Edit + Fork buttons."""
    t = _get_visible_template_or_404(
        db, template_id, current_user.company_id
    )
    return _validate_edit_permission(current_user, t)


@router.post(
    "/admin/templates/{template_id}/versions/draft",
    response_model=DocumentTemplateVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_template_draft(
    template_id: str,
    body: DraftCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Clone a base version (active by default) into a new draft."""
    t = _get_visible_template_or_404(
        db, template_id, current_user.company_id
    )
    _enforce_edit_permission(current_user, t)
    try:
        draft = template_service.create_draft(
            db,
            template=t,
            base_version_id=body.base_version_id,
            changelog=body.changelog,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
        )
    except TemplateEditError as exc:
        _raise_edit_error(exc)
    db.commit()
    db.refresh(draft)
    return draft


@router.patch(
    "/admin/templates/{template_id}/versions/{version_id}",
    response_model=DocumentTemplateVersionResponse,
)
def update_template_draft(
    template_id: str,
    version_id: str,
    body: DraftUpdateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Mutate a draft. Returns 409 on active/retired versions."""
    t = _get_visible_template_or_404(
        db, template_id, current_user.company_id
    )
    _enforce_edit_permission(current_user, t)
    version = _get_version_on_template(db, t.id, version_id)
    updates = body.model_dump(exclude_unset=True)
    try:
        updated = template_service.update_draft(
            db,
            template=t,
            version=version,
            fields=updates,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
        )
    except TemplateEditError as exc:
        _raise_edit_error(exc)
    db.commit()
    db.refresh(updated)
    return updated


@router.delete(
    "/admin/templates/{template_id}/versions/{version_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_template_draft(
    template_id: str,
    version_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    t = _get_visible_template_or_404(
        db, template_id, current_user.company_id
    )
    _enforce_edit_permission(current_user, t)
    version = _get_version_on_template(db, t.id, version_id)
    try:
        template_service.delete_draft(
            db,
            template=t,
            version=version,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
        )
    except TemplateEditError as exc:
        _raise_edit_error(exc)
    db.commit()
    return None


@router.post(
    "/admin/templates/{template_id}/versions/{version_id}/activate",
    response_model=DocumentTemplateVersionResponse,
)
def activate_template_version(
    template_id: str,
    version_id: str,
    body: TemplateActivateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Activate a draft. Retires the current active, updates
    template.current_version_id, writes audit row. Variable schema
    validation errors block (returns 400 with issue list)."""
    t = _get_visible_template_or_404(
        db, template_id, current_user.company_id
    )
    _enforce_edit_permission(current_user, t)
    _assert_confirmation_text(t, body.confirmation_text)
    version = _get_version_on_template(db, t.id, version_id)
    if version.status != "draft":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Only drafts can be activated — version {version.version_number} is "
            f"{version.status!r}.",
        )

    # Variable schema validation — hard block on errors
    validation = validate_template_content(
        body_template=version.body_template,
        subject_template=version.subject_template,
        variable_schema=version.variable_schema or {},
    )
    if validation.has_errors:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Variable schema validation failed",
                "issues": [i.to_dict() for i in validation.issues],
            },
        )

    try:
        activated = template_service.activate_version(
            db,
            template=t,
            version=version,
            changelog=body.changelog,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
        )
    except TemplateEditError as exc:
        _raise_edit_error(exc)
    db.commit()
    db.refresh(activated)
    return activated


@router.post(
    "/admin/templates/{template_id}/versions/{version_id}/rollback",
    response_model=DocumentTemplateVersionResponse,
)
def rollback_template_version(
    template_id: str,
    version_id: str,
    body: TemplateRollbackRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Roll back by cloning a retired version into a new active one.
    Version numbers stay monotonic — no version is ever reactivated
    directly."""
    t = _get_visible_template_or_404(
        db, template_id, current_user.company_id
    )
    _enforce_edit_permission(current_user, t)
    _assert_confirmation_text(t, body.confirmation_text)
    target = _get_version_on_template(db, t.id, version_id)
    try:
        new_version = template_service.rollback_to_version(
            db,
            template=t,
            target=target,
            changelog=body.changelog,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
        )
    except TemplateEditError as exc:
        _raise_edit_error(exc)
    db.commit()
    db.refresh(new_version)
    return new_version


@router.post(
    "/admin/templates/{template_id}/fork-to-tenant",
    response_model=DocumentTemplateDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def fork_template_to_tenant(
    template_id: str,
    body: TemplateForkRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Fork a platform-global template to a tenant. Only works when the
    source is a platform template AND the caller has admin rights on
    the target tenant (or is super_admin)."""
    source = _get_visible_template_or_404(
        db, template_id, current_user.company_id
    )
    if source.company_id is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Only platform templates can be forked. Source is tenant-scoped.",
        )
    is_super = bool(getattr(current_user, "is_super_admin", False))
    if not is_super and body.target_company_id != current_user.company_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You can only fork platform templates into your own tenant.",
        )
    try:
        new_template = template_service.fork_platform_to_tenant(
            db,
            source_template=source,
            target_company_id=body.target_company_id,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
        )
    except TemplateEditError as exc:
        _raise_edit_error(exc)
    db.commit()
    db.refresh(new_template)
    # Return the new template's detail (mirrors get_document_template_detail)
    detail = template_service.get_template_detail(
        db, new_template.id, current_company_id=current_user.company_id
    )
    if detail is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Forked template created but not readable — check visibility",
        )
    return detail


@router.post(
    "/admin/templates/{template_id}/versions/{version_id}/test-render",
    response_model=TemplateTestRenderResponse,
)
def test_render_template_version(
    template_id: str,
    version_id: str,
    body: TemplateTestRenderRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Test-render a specific version against caller-supplied context.
    Flagged as a test render (is_test_render=True for PDF output).

    Admin is enough — test renders are safe. Both PDF and HTML/text
    paths work; any version (draft / active / retired) can be test-rendered.

    D-9: delegates to `document_renderer.render` with the new
    `template_version_id` kwarg. Previously the endpoint duplicated the
    Jinja render + R2 upload + Document insert pipeline; the renderer
    now owns all of it and this route is a thin adapter that shapes the
    response.
    """
    t = _get_visible_template_or_404(
        db, template_id, current_user.company_id
    )
    version = _get_version_on_template(db, t.id, version_id)
    context = body.context or {}

    from app.services.documents import document_renderer

    if t.output_format in ("html", "text"):
        try:
            result = document_renderer.render(
                db,
                template_version_id=version.id,
                context=context,
                company_id=current_user.company_id,
                output_format=t.output_format,
                is_test_render=True,
            )
        except document_renderer.DocumentRenderError as exc:
            return TemplateTestRenderResponse(
                output_format=t.output_format,
                errors=[str(exc)],
            )
        # html/text path returns RenderResult
        return TemplateTestRenderResponse(
            output_format=t.output_format,
            rendered_content=(
                result.rendered_content
                if isinstance(result.rendered_content, str)
                else result.rendered_content.decode("utf-8")
            ),
            rendered_subject=result.rendered_subject,
        )

    # PDF path — the renderer persists a flagged Document row so the
    # admin can click through to the Document Log with the test toggle
    # on.
    try:
        doc = document_renderer.render(
            db,
            template_version_id=version.id,
            context=context,
            company_id=current_user.company_id,
            document_type=t.document_type,
            title=f"[TEST] {t.template_key} v{version.version_number}",
            description=(
                f"Test render of template {t.template_key} version "
                f"{version.version_number} ({version.status})"
            ),
            caller_module="documents_v2.test_render",
            rendered_by_user_id=current_user.id,
            render_reason="test_render",
            is_test_render=True,
        )
    except document_renderer.DocumentRenderError as exc:
        return TemplateTestRenderResponse(
            output_format="pdf",
            errors=[str(exc)],
        )
    db.commit()
    # render() returns the Document for PDF output (D-1 contract).
    assert isinstance(doc, Document)
    return TemplateTestRenderResponse(
        output_format="pdf",
        document_id=doc.id,
        download_url=f"/api/v1/documents-v2/{doc.id}/download",
    )


@router.get(
    "/admin/templates/{template_id}/audit",
    response_model=list[TemplateAuditLogEntry],
)
def list_template_audit(
    template_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Audit log for this template, most recent first."""
    _get_visible_template_or_404(
        db, template_id, current_user.company_id
    )
    return template_service.list_audit(db, template_id, limit=limit, offset=offset)


# ── Phase D-6: cross-tenant sharing ────────────────────────────────


def _raise_sharing_error(exc: SharingError) -> None:
    raise HTTPException(exc.http_status, str(exc))


def _get_owned_document_or_404(
    db: Session, document_id: str, company_id: str
) -> Document:
    """Stricter than _get_visible_document — requires OWNERSHIP.
    Used on write paths where shared tenants can't act (grant, revoke)."""
    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.company_id == company_id,
            Document.deleted_at.is_(None),
        )
        .first()
    )
    if doc is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Document not found or not owned by this tenant",
        )
    return doc


@router.post(
    "/{document_id}/shares",
    response_model=DocumentShareResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_document_share(
    document_id: str,
    body: DocumentShareCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Grant read access to `target_company_id` on this document.

    Requires an active PlatformTenantRelationship between the owning
    tenant (caller's tenant) and the target. Returns 403 if no
    relationship exists.
    """
    doc = _get_owned_document_or_404(
        db, document_id, current_user.company_id
    )
    try:
        share = document_sharing_service.grant_share(
            db,
            document=doc,
            target_company_id=body.target_company_id,
            granted_by_user_id=current_user.id,
            reason=body.reason,
            source_module="admin.documents_v2",
            enforce_relationship=True,
        )
    except SharingError as exc:
        _raise_sharing_error(exc)
    db.commit()
    db.refresh(share)
    return share


@router.get(
    "/{document_id}/shares",
    response_model=list[DocumentShareResponse],
)
def list_document_shares(
    document_id: str,
    include_revoked: bool = Query(False),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List shares originated from this document (outbox for document)."""
    doc = _get_owned_document_or_404(
        db, document_id, current_user.company_id
    )
    return document_sharing_service.list_outgoing_shares(
        db,
        owner_company_id=current_user.company_id,
        document_id=doc.id,
        include_revoked=include_revoked,
        limit=200,
    )


@router.post(
    "/shares/{share_id}/revoke",
    response_model=DocumentShareResponse,
)
def revoke_document_share(
    share_id: str,
    body: DocumentShareRevokeRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Revoke a share. Future-access-only — previously-downloaded
    copies remain under the recipient's control."""
    share = document_sharing_service.get_share(db, share_id)
    if share is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Share not found")
    # Only the OWNER tenant can revoke
    if share.owner_company_id != current_user.company_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Share not found (not owned by this tenant)",
        )
    try:
        share = document_sharing_service.revoke_share(
            db,
            share=share,
            revoked_by_user_id=current_user.id,
            revoke_reason=body.revoke_reason,
        )
    except SharingError as exc:
        _raise_sharing_error(exc)
    db.commit()
    db.refresh(share)
    return share


@router.get(
    "/shares/{share_id}/events",
    response_model=list[DocumentShareEventResponse],
)
def list_document_share_events(
    share_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Audit timeline for a share. Visible to owner OR target."""
    share = document_sharing_service.get_share(db, share_id)
    if share is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Share not found")
    if current_user.company_id not in (
        share.owner_company_id,
        share.target_company_id,
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Share not found")
    return document_sharing_service.list_events_for_share(db, share_id)


@router.get(
    "/inbox",
    response_model=list[InboxItemResponse],
)
def list_incoming_shares(
    document_type: str | None = Query(None),
    include_revoked: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin inbox: documents shared TO this tenant from others.

    Each row shows the share + the underlying document metadata (type,
    title, status, owner). Tenant-user-facing version of this inbox is
    a later phase; D-6 ships admin-only.
    """
    from app.models.company import Company
    from app.models.document_share import DocumentShare

    q = (
        db.query(DocumentShare, Document, Company)
        .join(Document, Document.id == DocumentShare.document_id)
        .outerjoin(
            Company, Company.id == DocumentShare.owner_company_id
        )
        .filter(DocumentShare.target_company_id == current_user.company_id)
    )
    if document_type:
        q = q.filter(Document.document_type == document_type)
    if not include_revoked:
        q = q.filter(DocumentShare.revoked_at.is_(None))
    rows = (
        q.order_by(DocumentShare.granted_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    # Phase D-8: overlay this user's read state onto the rows via a
    # single map lookup (left-join semantics done in Python to keep
    # the select tight).
    read_map = document_sharing_service.get_read_share_ids(
        db,
        user_id=current_user.id,
        share_ids=[share.id for share, _doc, _own in rows],
    )
    return [
        InboxItemResponse(
            share_id=share.id,
            document_id=doc.id,
            document_type=doc.document_type,
            document_title=doc.title,
            document_status=doc.status,
            owner_company_id=share.owner_company_id,
            owner_company_name=(
                owner_company.name if owner_company else None
            ),
            granted_at=share.granted_at,
            revoked_at=share.revoked_at,
            reason=share.reason,
            source_module=share.source_module,
            is_read=share.id in read_map,
            read_at=read_map.get(share.id),
        )
        for share, doc, owner_company in rows
    ]


# ── Phase D-8: inbox read tracking ─────────────────────────────────


@router.post(
    "/inbox/mark-all-read",
    response_model=MarkInboxReadResponse,
)
def mark_all_inbox_read(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Mark every active incoming share read for the current user."""
    count = document_sharing_service.mark_all_incoming_read(
        db,
        target_company_id=current_user.company_id,
        user_id=current_user.id,
    )
    return MarkInboxReadResponse(marked_count=count)


@router.post(
    "/shares/{share_id}/mark-read",
    response_model=MarkInboxReadResponse,
)
def mark_share_read(
    share_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Mark a single incoming share read for the current user.

    Target-tenant check — users only mark shares that were shared TO
    their tenant. No error if already read (idempotent: count=0 means
    "was already read").
    """
    share = document_sharing_service.get_share(db, share_id)
    if share is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Share not found")
    if share.target_company_id != current_user.company_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Share not found")
    # Idempotent: if this user already read it, we count 0; otherwise 1.
    already_read = document_sharing_service.get_read_share_ids(
        db, user_id=current_user.id, share_ids=[share_id]
    )
    if share_id in already_read:
        return MarkInboxReadResponse(marked_count=0)
    document_sharing_service.mark_share_read(
        db, share_id=share_id, user_id=current_user.id
    )
    return MarkInboxReadResponse(marked_count=1)


# ── Phase D-7: delivery log ────────────────────────────────────────


@router.get(
    "/deliveries",
    response_model=list[DeliveryListItem],
)
def list_deliveries(
    channel: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    document_id: str | None = Query(None),
    template_key: str | None = Query(None),
    recipient_search: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List deliveries for this tenant, newest first. Defaults to the
    last 7 days if no date range is specified."""
    from app.models.document_delivery import DocumentDelivery

    if date_from is None and date_to is None:
        date_from = datetime.now(timezone.utc) - timedelta(days=7)

    q = db.query(DocumentDelivery).filter(
        DocumentDelivery.company_id == current_user.company_id
    )
    if channel:
        q = q.filter(DocumentDelivery.channel == channel)
    if status_filter:
        q = q.filter(DocumentDelivery.status == status_filter)
    if document_id:
        q = q.filter(DocumentDelivery.document_id == document_id)
    if template_key:
        q = q.filter(DocumentDelivery.template_key == template_key)
    if recipient_search:
        pattern = f"%{recipient_search.lower()}%"
        q = q.filter(DocumentDelivery.recipient_value.ilike(pattern))
    if date_from:
        q = q.filter(DocumentDelivery.created_at >= date_from)
    if date_to:
        q = q.filter(DocumentDelivery.created_at <= date_to)

    return (
        q.order_by(desc(DocumentDelivery.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get(
    "/deliveries/{delivery_id}",
    response_model=DeliveryDetailResponse,
)
def get_delivery_detail(
    delivery_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Full delivery detail including provider response and linkage."""
    from app.models.document_delivery import DocumentDelivery

    row = (
        db.query(DocumentDelivery)
        .filter(
            DocumentDelivery.id == delivery_id,
            DocumentDelivery.company_id == current_user.company_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Delivery not found"
        )
    return row


@router.post(
    "/deliveries/{delivery_id}/resend",
    response_model=DeliveryDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def resend_delivery(
    delivery_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new delivery that reuses the original's parameters.

    The underlying template (if any) re-renders with current template
    content, so a resend AFTER a template edit will use the newer
    version. If the original used a raw body, that body is resent.
    """
    from app.models.document_delivery import DocumentDelivery
    from app.services.delivery import delivery_service

    original = (
        db.query(DocumentDelivery)
        .filter(
            DocumentDelivery.id == delivery_id,
            DocumentDelivery.company_id == current_user.company_id,
        )
        .first()
    )
    if original is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Delivery not found"
        )

    # Reuse the original's inputs. template_context isn't persisted,
    # so resend-with-template relies on the template rendering with
    # whatever context the ORIGINAL body_preview was built from — which
    # we don't have. Resends with template_key thus fall back to
    # re-sending the preserved body.
    try:
        new_delivery = delivery_service.send(
            db,
            delivery_service.SendParams(
                company_id=current_user.company_id,
                channel=original.channel,
                recipient=delivery_service.RecipientInput(
                    type=original.recipient_type,
                    value=original.recipient_value,
                    name=original.recipient_name,
                ),
                document_id=original.document_id,
                subject=original.subject,
                # Resend uses preserved body content (safest path).
                body=original.body_preview,
                body_html=original.body_preview,
                caller_module="admin.resend",
                metadata={"resent_from_delivery_id": original.id},
            ),
        )
    except delivery_service.DeliveryError as exc:
        raise HTTPException(exc.http_status, str(exc))
    db.commit()
    db.refresh(new_delivery)
    return new_delivery


@router.post(
    "/deliveries",
    response_model=DeliveryDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def ad_hoc_send(
    body: DeliveryAdHocSendRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create an ad-hoc delivery — admin manual-send path. Most sends
    happen automatically from generators / workflow / signing flows;
    this endpoint exists for one-off manual sends from the admin UI."""
    from app.services.delivery import delivery_service

    try:
        delivery = delivery_service.send(
            db,
            delivery_service.SendParams(
                company_id=current_user.company_id,
                channel=body.channel,
                recipient=delivery_service.RecipientInput(
                    type=body.recipient_type,
                    value=body.recipient_value,
                    name=body.recipient_name,
                ),
                document_id=body.document_id,
                subject=body.subject,
                template_key=body.template_key,
                template_context=body.template_context,
                body=body.body,
                body_html=body.body_html,
                reply_to=body.reply_to,
                caller_module="admin.ad_hoc_send",
            ),
        )
    except delivery_service.DeliveryError as exc:
        raise HTTPException(exc.http_status, str(exc))
    db.commit()
    db.refresh(delivery)
    return delivery


# ─────────────────────────────────────────────────────────────────────
# Phase D-10 — Block-based template authoring
# ─────────────────────────────────────────────────────────────────────


def _raise_block_error(exc: BlockServiceError) -> None:
    raise HTTPException(exc.http_status, str(exc))


@router.get(
    "/admin/templates/{template_id}/versions/{version_id}/blocks",
    response_model=list[TemplateBlockResponse],
)
def list_template_blocks(
    template_id: str,
    version_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all blocks for a version, ordered by position. Top-level
    blocks appear first (parent_block_id NULL), then nested blocks."""
    t = _get_visible_template_or_404(
        db, template_id, current_user.company_id
    )
    version = _get_version_on_template(db, t.id, version_id)
    blocks = list_blocks(db, version.id)
    return blocks


@router.post(
    "/admin/templates/{template_id}/versions/{version_id}/blocks",
    response_model=TemplateBlockResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_template_block(
    template_id: str,
    version_id: str,
    body: TemplateBlockCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Add a block to a draft version. Returns the created block."""
    t = _get_visible_template_or_404(
        db, template_id, current_user.company_id
    )
    _enforce_edit_permission(current_user, t)
    version = _get_version_on_template(db, t.id, version_id)
    try:
        block = add_block(
            db,
            version_id=version.id,
            block_kind=body.block_kind,
            position=body.position,
            config=body.config,
            condition=body.condition,
            parent_block_id=body.parent_block_id,
        )
    except BlockServiceError as exc:
        _raise_block_error(exc)
    db.commit()
    db.refresh(block)
    return block


@router.patch(
    "/admin/templates/{template_id}/versions/{version_id}/blocks/{block_id}",
    response_model=TemplateBlockResponse,
)
def update_template_block(
    template_id: str,
    version_id: str,
    block_id: str,
    body: TemplateBlockUpdateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a block's config and/or condition."""
    t = _get_visible_template_or_404(
        db, template_id, current_user.company_id
    )
    _enforce_edit_permission(current_user, t)
    _get_version_on_template(db, t.id, version_id)
    try:
        block = update_block(
            db,
            block_id=block_id,
            config=body.config,
            condition=body.condition,
        )
    except BlockServiceError as exc:
        _raise_block_error(exc)
    db.commit()
    db.refresh(block)
    return block


@router.delete(
    "/admin/templates/{template_id}/versions/{version_id}/blocks/{block_id}",
)
def delete_template_block(
    template_id: str,
    version_id: str,
    block_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a block. CASCADE handles children of conditional_wrapper."""
    t = _get_visible_template_or_404(
        db, template_id, current_user.company_id
    )
    _enforce_edit_permission(current_user, t)
    _get_version_on_template(db, t.id, version_id)
    try:
        delete_block(db, block_id=block_id)
    except BlockServiceError as exc:
        _raise_block_error(exc)
    db.commit()
    return {"deleted": True, "block_id": block_id}


@router.post(
    "/admin/templates/{template_id}/versions/{version_id}/blocks/reorder",
    response_model=list[TemplateBlockResponse],
)
def reorder_template_blocks(
    template_id: str,
    version_id: str,
    body: TemplateBlockReorderRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Reorder blocks within one parent context (top-level OR within a
    single conditional_wrapper). Atomic — either all reorder or none."""
    t = _get_visible_template_or_404(
        db, template_id, current_user.company_id
    )
    _enforce_edit_permission(current_user, t)
    version = _get_version_on_template(db, t.id, version_id)
    try:
        blocks = reorder_blocks(
            db,
            version_id=version.id,
            block_id_order=body.block_id_order,
            parent_block_id=body.parent_block_id,
        )
    except BlockServiceError as exc:
        _raise_block_error(exc)
    db.commit()
    return blocks


# ─── Block kind picker (read-only catalog) ──────────────────────


@router.get(
    "/admin/block-kinds",
    response_model=list[BlockKindResponse],
)
def list_block_kinds_endpoint(
    current_user: User = Depends(require_admin),
):
    """Return all registered block kinds with their config schemas.
    Powers the block-kind picker in the editor."""
    return [
        BlockKindResponse(
            kind=k.kind,
            display_name=k.display_name,
            description=k.description,
            config_schema=k.config_schema,
            accepts_children=k.accepts_children,
        )
        for k in list_block_kinds()
    ]


# ─── Document type catalog ──────────────────────────────────────


@router.get(
    "/admin/document-types",
    response_model=DocumentTypeCatalogResponse,
)
def list_document_types_endpoint(
    current_user: User = Depends(require_admin),
):
    """Return the curated document type catalog for the editor's
    create-template flow + browser categorization."""
    types = [
        DocumentTypeResponse(
            type_id=t.type_id,
            display_name=t.display_name,
            category=t.category,
            description=t.description,
            starter_blocks=[
                DocumentTypeStarterBlockResponse(
                    block_kind=b.block_kind,
                    config=b.config,
                    condition=b.condition,
                )
                for b in t.starter_blocks
            ],
            recommended_variables=t.recommended_variables,
        )
        for t in list_document_types()
    ]
    categories = [
        DocumentTypeCategoryResponse(category_id=cid, display_name=cname)
        for cid, cname in list_categories()
    ]
    return DocumentTypeCatalogResponse(categories=categories, types=types)


# ─── Arc 4b.2a — Dedicated mention endpoint (Q-DISPATCH-5) ──────────
#
# Per per-consumer endpoint shaping canon: shared underlying substrate
# (Phase 1 pg_trgm entity resolver — `app.services.command_bar.resolver`)
# with consumer-specific endpoint shape. The command bar consumer at
# `/api/v1/command-bar/query` does intent classification + multi-shape
# result merging; this picker consumer returns RECORD-shape hits only,
# narrower picker entity-type subset (Q-COUPLING-1: 4 entity types).
#
# UI vocabulary translation boundary: picker submits `case` / `order` /
# `contact` / `product`; substrate uses `fh_case` / `sales_order` /
# `contact` / `product`. Pydantic Literal in MentionResolveRequest
# enforces the picker subset (out-of-subset entity_types → 422 before
# this handler runs).


@router.post(
    "/admin/mentions/resolve",
    response_model=MentionResolveResponse,
)
def resolve_mention(
    payload: MentionResolveRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Resolve entity candidates for the mention picker.

    Tenant-scoped via `current_user.company_id` — the Phase 1 resolver
    enforces tenant isolation on every query, so cross-tenant leakage
    is structurally prevented.

    Empty/whitespace `query` returns an empty result set (resolver
    requires non-empty query text). Picker UX may surface this as
    "Start typing to search…" copy.

    Picker subset enforcement via Pydantic Literal on
    `entity_type` — invalid values return 422 at request validation.
    """
    substrate_type = MENTION_PICKER_VOCAB.get(payload.entity_type)
    if substrate_type is None:
        # Defensive — Pydantic should have rejected this at the request
        # layer. If we somehow get here, surface as 422.
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown entity_type {payload.entity_type!r}",
        )

    query_text = (payload.query or "").strip()
    if not query_text:
        return MentionResolveResponse(results=[], total=0)

    hits = resolver_resolve(
        db,
        query_text=query_text,
        company_id=current_user.company_id,
        limit=payload.limit,
        entity_types=(substrate_type,),
    )

    results = [
        MentionResolveResponseItem(
            entity_type=payload.entity_type,  # echo picker vocab
            entity_id=hit.entity_id,
            display_name=hit.primary_label,
            preview_snippet=hit.secondary_context,
        )
        for hit in hits
    ]
    return MentionResolveResponse(results=results, total=len(results))
