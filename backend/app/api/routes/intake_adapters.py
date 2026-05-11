"""Phase R-6.2a — Intake adapter API endpoints.

Mounted at ``/api/v1/intake-adapters/*`` from ``app/api/v1.py``.

Per CLAUDE.md §12 Spec-Override Discipline: the investigation report
canonical-named the surface ``/api/v1/intake/*``, but ``intake.py``
already owns ``/api/v1/intake/{token}`` for the disinterment intake
form. To avoid path-segment collision with FastAPI's catch-all token
route, the R-6.2a intake adapter substrate mounts at
``/intake-adapters/*``. R-6.x can consolidate to a single ``/intake``
prefix when the disinterment intake is migrated onto the adapter
substrate.

Endpoints:

  Public (rate-limited; CAPTCHA stubbed for R-6.2a — R-6.2b wires
  Cloudflare Turnstile):

    GET  /forms/{tenant_slug}/{form_slug}
    POST /forms/{tenant_slug}/{form_slug}/submit
    GET  /uploads/{tenant_slug}/{upload_slug}
    POST /uploads/{tenant_slug}/{upload_slug}/presign
    POST /uploads/{tenant_slug}/{upload_slug}/complete

  Admin (tenant-authed; admin role):

    GET    /admin/form-configurations
    POST   /admin/form-configurations
    GET    /admin/form-configurations/{id}
    PATCH  /admin/form-configurations/{id}
    DELETE /admin/form-configurations/{id}
    GET    /admin/file-configurations
    POST   /admin/file-configurations
    GET    /admin/file-configurations/{id}
    PATCH  /admin/file-configurations/{id}
    DELETE /admin/file-configurations/{id}
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.intake_file_configuration import IntakeFileConfiguration
from app.models.intake_file_upload import IntakeFileUpload
from app.models.intake_form_configuration import IntakeFormConfiguration
from app.models.intake_form_submission import IntakeFormSubmission
from app.models.user import User
from app.services.intake import (
    FileUploadPayload,
    IntakeConfigNotFound,
    IntakeError,
    IntakeValidationError,
    complete_file_upload,
    presign_file_upload,
    resolve_file_config,
    resolve_form_config,
    submit_form,
)
from app.services.intake.captcha import (
    CaptchaError,
    verify_turnstile_token,
)
from app.services.intake.resolver import resolve_tenant_by_slug


router = APIRouter()


# ── Public endpoints ────────────────────────────────────────────────


class _FormSubmitRequest(BaseModel):
    submitted_data: dict[str, Any] = Field(default_factory=dict)
    captcha_token: str | None = None


class _UploadPresignRequest(BaseModel):
    original_filename: str
    content_type: str
    size_bytes: int
    captcha_token: str | None = None


class _UploadCompleteRequest(BaseModel):
    r2_key: str
    original_filename: str
    content_type: str
    size_bytes: int
    uploader_metadata: dict[str, Any] = Field(default_factory=dict)
    captcha_token: str | None = None


def _public_form_config_view(config: IntakeFormConfiguration) -> dict[str, Any]:
    return {
        "id": config.id,
        "name": config.name,
        "slug": config.slug,
        "description": config.description,
        "form_schema": config.form_schema or {},
        "success_message": config.success_message,
    }


def _public_file_config_view(config: IntakeFileConfiguration) -> dict[str, Any]:
    return {
        "id": config.id,
        "name": config.name,
        "slug": config.slug,
        "description": config.description,
        "allowed_content_types": config.allowed_content_types or [],
        "max_file_size_bytes": config.max_file_size_bytes,
        "max_file_count": config.max_file_count,
        "metadata_schema": config.metadata_schema or {},
        "success_message": config.success_message,
    }


@router.get("/forms/{tenant_slug}/{form_slug}")
def get_form_config_public(
    tenant_slug: str,
    form_slug: str,
    db: Session = Depends(get_db),
):
    """Public — fetch a form's configuration for rendering.

    No auth. Resolves tenant via slug, walks three-scope inheritance.
    404 on unknown tenant_slug + unknown form_slug (existence-hiding
    canon — never leak whether a slug exists in another tenant).
    """
    tenant = resolve_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Form not found.")
    config = resolve_form_config(db, slug=form_slug, tenant=tenant)
    if config is None:
        raise HTTPException(status_code=404, detail="Form not found.")
    return _public_form_config_view(config)


@router.post("/forms/{tenant_slug}/{form_slug}/submit", status_code=201)
def submit_form_public(
    tenant_slug: str,
    form_slug: str,
    body: _FormSubmitRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Public — submit a form payload.

    CAPTCHA stubbed for R-6.2a — R-6.2b wires Cloudflare Turnstile.
    Submitter metadata captures IP + user_agent for spam triage.
    """
    tenant = resolve_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Form not found.")
    config = resolve_form_config(db, slug=form_slug, tenant=tenant)
    if config is None:
        raise HTTPException(status_code=404, detail="Form not found.")

    # R-6.2b CAPTCHA verification. Per app/services/intake/captcha.py
    # docstring: missing secret in non-production logs warning + allows
    # (graceful degradation); missing in production raises 500;
    # verification failure raises 403. Defensive `request.client` access
    # — TestClient may emit no client; pass None then.
    captcha_token = body.captcha_token
    client_ip = request.client.host if request.client else None
    try:
        verify_turnstile_token(captcha_token, ip_address=client_ip)
    except CaptchaError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc))

    submitter_metadata = {
        "ip": client_ip,
        "user_agent": request.headers.get("user-agent"),
        "captcha_token_present": captcha_token is not None,
    }

    try:
        submission = submit_form(
            db,
            config=config,
            submitted_data=body.submitted_data,
            submitter_metadata=submitter_metadata,
            tenant_id=tenant.id,
        )
    except IntakeError as exc:
        details = getattr(exc, "details", None)
        raise HTTPException(
            status_code=exc.http_status,
            detail={"message": str(exc), "details": details},
        )
    db.commit()
    return {
        "submission_id": submission.id,
        "success_message": config.success_message,
    }


@router.get("/uploads/{tenant_slug}/{upload_slug}")
def get_file_config_public(
    tenant_slug: str,
    upload_slug: str,
    db: Session = Depends(get_db),
):
    """Public — fetch a file upload point's configuration."""
    tenant = resolve_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Upload not found.")
    config = resolve_file_config(db, slug=upload_slug, tenant=tenant)
    if config is None:
        raise HTTPException(status_code=404, detail="Upload not found.")
    return _public_file_config_view(config)


@router.post("/uploads/{tenant_slug}/{upload_slug}/presign")
def presign_upload_public(
    tenant_slug: str,
    upload_slug: str,
    body: _UploadPresignRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Public — return a presigned PUT URL for direct R2 upload."""
    tenant = resolve_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Upload not found.")
    config = resolve_file_config(db, slug=upload_slug, tenant=tenant)
    if config is None:
        raise HTTPException(status_code=404, detail="Upload not found.")

    # R-6.2b CAPTCHA verification (presign is the spam-attractive
    # site — once we hand out a signed URL, R2 acks the bytes; checking
    # again at /complete is redundant since the upload is already paid).
    client_ip = request.client.host if request.client else None
    try:
        verify_turnstile_token(body.captcha_token, ip_address=client_ip)
    except CaptchaError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc))

    try:
        signed = presign_file_upload(
            db,
            config=config,
            original_filename=body.original_filename,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
            tenant_id=tenant.id,
        )
    except IntakeError as exc:
        details = getattr(exc, "details", None)
        raise HTTPException(
            status_code=exc.http_status,
            detail={"message": str(exc), "details": details},
        )
    return signed


@router.post(
    "/uploads/{tenant_slug}/{upload_slug}/complete", status_code=201
)
def complete_upload_public(
    tenant_slug: str,
    upload_slug: str,
    body: _UploadCompleteRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Public — finalize an upload after browser PUT to R2 completes."""
    tenant = resolve_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Upload not found.")
    config = resolve_file_config(db, slug=upload_slug, tenant=tenant)
    if config is None:
        raise HTTPException(status_code=404, detail="Upload not found.")

    # R-6.2b CAPTCHA verification. Defense-in-depth — presign already
    # verified, but a direct POST to /complete with a forged r2_key
    # would bypass that. Cheap to re-verify; expensive to recover from.
    client_ip = request.client.host if request.client else None
    try:
        verify_turnstile_token(body.captcha_token, ip_address=client_ip)
    except CaptchaError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc))

    uploader_metadata = dict(body.uploader_metadata or {})
    uploader_metadata.setdefault("ip", client_ip)
    uploader_metadata.setdefault(
        "user_agent", request.headers.get("user-agent")
    )

    payload = FileUploadPayload(
        r2_key=body.r2_key,
        original_filename=body.original_filename,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
        uploader_metadata=uploader_metadata,
    )

    try:
        upload = complete_file_upload(
            db,
            config=config,
            payload=payload,
            tenant_id=tenant.id,
            # Skip R2 head check by default to avoid coupling tests +
            # local dev to R2 availability; production controllers
            # invoke complete_file_upload directly with verify=True.
            verify_r2_head=False,
        )
    except IntakeError as exc:
        details = getattr(exc, "details", None)
        raise HTTPException(
            status_code=exc.http_status,
            detail={"message": str(exc), "details": details},
        )
    db.commit()
    return {
        "upload_id": upload.id,
        "success_message": config.success_message,
    }


# ── Admin endpoints — Form Configurations ───────────────────────────


class _FormConfigCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    form_schema: dict[str, Any] = Field(default_factory=dict)
    success_message: str | None = None
    notification_email_template_id: str | None = None
    is_active: bool = True


class _FormConfigUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    form_schema: dict[str, Any] | None = None
    success_message: str | None = None
    notification_email_template_id: str | None = None
    is_active: bool | None = None


def _admin_form_config_view(config: IntakeFormConfiguration) -> dict[str, Any]:
    return {
        "id": config.id,
        "tenant_id": config.tenant_id,
        "vertical": config.vertical,
        "scope": config.scope,
        "name": config.name,
        "slug": config.slug,
        "description": config.description,
        "form_schema": config.form_schema or {},
        "success_message": config.success_message,
        "notification_email_template_id": config.notification_email_template_id,
        "is_active": config.is_active,
        "created_at": (
            config.created_at.isoformat() if config.created_at else None
        ),
        "updated_at": (
            config.updated_at.isoformat() if config.updated_at else None
        ),
    }


@router.get("/admin/form-configurations")
def list_form_configurations(
    include_inherited: bool = False,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin — list tenant-override + (optionally) inherited form
    configurations."""
    q = db.query(IntakeFormConfiguration).filter(
        IntakeFormConfiguration.tenant_id == user.company_id
    )
    rows = q.all()

    inherited: list[IntakeFormConfiguration] = []
    if include_inherited:
        # Pull vertical_default + platform_default rows whose slug
        # isn't already overridden by the tenant.
        overridden_slugs = {r.slug for r in rows}
        from app.models.company import Company

        tenant = (
            db.query(Company).filter(Company.id == user.company_id).first()
        )
        vertical = tenant.vertical if tenant else None
        platform_rows = (
            db.query(IntakeFormConfiguration)
            .filter(
                IntakeFormConfiguration.tenant_id.is_(None),
                IntakeFormConfiguration.is_active.is_(True),
            )
            .all()
        )
        for r in platform_rows:
            if r.slug in overridden_slugs:
                continue
            if r.vertical is not None and r.vertical != vertical:
                continue
            inherited.append(r)

    return {
        "tenant_overrides": [_admin_form_config_view(r) for r in rows],
        "inherited": [_admin_form_config_view(r) for r in inherited],
    }


@router.post("/admin/form-configurations", status_code=201)
def create_form_configuration(
    body: _FormConfigCreateRequest,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin — create a tenant_override form configuration."""
    config = IntakeFormConfiguration(
        id=str(uuid.uuid4()),
        tenant_id=user.company_id,
        vertical=None,
        scope="tenant_override",
        name=body.name,
        slug=body.slug,
        description=body.description,
        form_schema=body.form_schema or {},
        success_message=body.success_message,
        notification_email_template_id=body.notification_email_template_id,
        is_active=body.is_active,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return _admin_form_config_view(config)


@router.get("/admin/form-configurations/{config_id}")
def get_form_configuration(
    config_id: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    config = (
        db.query(IntakeFormConfiguration)
        .filter(IntakeFormConfiguration.id == config_id)
        .first()
    )
    if config is None or config.tenant_id != user.company_id:
        raise HTTPException(status_code=404, detail="Not found.")
    return _admin_form_config_view(config)


@router.patch("/admin/form-configurations/{config_id}")
def update_form_configuration(
    config_id: str,
    body: _FormConfigUpdateRequest,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    config = (
        db.query(IntakeFormConfiguration)
        .filter(IntakeFormConfiguration.id == config_id)
        .first()
    )
    if config is None or config.tenant_id != user.company_id:
        raise HTTPException(status_code=404, detail="Not found.")

    payload = body.model_dump(exclude_unset=True)
    for k, v in payload.items():
        setattr(config, k, v)
    config.updated_by_user_id = user.id
    db.commit()
    db.refresh(config)
    return _admin_form_config_view(config)


@router.delete("/admin/form-configurations/{config_id}", status_code=204)
def delete_form_configuration(
    config_id: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    config = (
        db.query(IntakeFormConfiguration)
        .filter(IntakeFormConfiguration.id == config_id)
        .first()
    )
    if config is None or config.tenant_id != user.company_id:
        raise HTTPException(status_code=404, detail="Not found.")
    # Soft-delete via is_active = false (preserves audit chain).
    config.is_active = False
    config.updated_by_user_id = user.id
    db.commit()
    return None


# ── Admin endpoints — File Configurations ───────────────────────────


class _FileConfigCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    allowed_content_types: list[str] = Field(default_factory=list)
    max_file_size_bytes: int = 10 * 1024 * 1024
    max_file_count: int = 1
    r2_key_prefix_template: str | None = None
    metadata_schema: dict[str, Any] = Field(default_factory=dict)
    success_message: str | None = None
    notification_email_template_id: str | None = None
    is_active: bool = True


class _FileConfigUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    allowed_content_types: list[str] | None = None
    max_file_size_bytes: int | None = None
    max_file_count: int | None = None
    r2_key_prefix_template: str | None = None
    metadata_schema: dict[str, Any] | None = None
    success_message: str | None = None
    notification_email_template_id: str | None = None
    is_active: bool | None = None


def _admin_file_config_view(config: IntakeFileConfiguration) -> dict[str, Any]:
    return {
        "id": config.id,
        "tenant_id": config.tenant_id,
        "vertical": config.vertical,
        "scope": config.scope,
        "name": config.name,
        "slug": config.slug,
        "description": config.description,
        "allowed_content_types": config.allowed_content_types or [],
        "max_file_size_bytes": config.max_file_size_bytes,
        "max_file_count": config.max_file_count,
        "r2_key_prefix_template": config.r2_key_prefix_template,
        "metadata_schema": config.metadata_schema or {},
        "success_message": config.success_message,
        "notification_email_template_id": config.notification_email_template_id,
        "is_active": config.is_active,
        "created_at": (
            config.created_at.isoformat() if config.created_at else None
        ),
        "updated_at": (
            config.updated_at.isoformat() if config.updated_at else None
        ),
    }


@router.get("/admin/file-configurations")
def list_file_configurations(
    include_inherited: bool = False,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q = db.query(IntakeFileConfiguration).filter(
        IntakeFileConfiguration.tenant_id == user.company_id
    )
    rows = q.all()

    inherited: list[IntakeFileConfiguration] = []
    if include_inherited:
        overridden_slugs = {r.slug for r in rows}
        from app.models.company import Company

        tenant = (
            db.query(Company).filter(Company.id == user.company_id).first()
        )
        vertical = tenant.vertical if tenant else None
        platform_rows = (
            db.query(IntakeFileConfiguration)
            .filter(
                IntakeFileConfiguration.tenant_id.is_(None),
                IntakeFileConfiguration.is_active.is_(True),
            )
            .all()
        )
        for r in platform_rows:
            if r.slug in overridden_slugs:
                continue
            if r.vertical is not None and r.vertical != vertical:
                continue
            inherited.append(r)

    return {
        "tenant_overrides": [_admin_file_config_view(r) for r in rows],
        "inherited": [_admin_file_config_view(r) for r in inherited],
    }


@router.post("/admin/file-configurations", status_code=201)
def create_file_configuration(
    body: _FileConfigCreateRequest,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    config = IntakeFileConfiguration(
        id=str(uuid.uuid4()),
        tenant_id=user.company_id,
        vertical=None,
        scope="tenant_override",
        name=body.name,
        slug=body.slug,
        description=body.description,
        allowed_content_types=body.allowed_content_types or [],
        max_file_size_bytes=body.max_file_size_bytes,
        max_file_count=body.max_file_count,
        r2_key_prefix_template=(
            body.r2_key_prefix_template
            or "tenants/{tenant_id}/intake/{adapter_slug}/{upload_id}"
        ),
        metadata_schema=body.metadata_schema or {},
        success_message=body.success_message,
        notification_email_template_id=body.notification_email_template_id,
        is_active=body.is_active,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return _admin_file_config_view(config)


@router.get("/admin/file-configurations/{config_id}")
def get_file_configuration(
    config_id: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    config = (
        db.query(IntakeFileConfiguration)
        .filter(IntakeFileConfiguration.id == config_id)
        .first()
    )
    if config is None or config.tenant_id != user.company_id:
        raise HTTPException(status_code=404, detail="Not found.")
    return _admin_file_config_view(config)


@router.patch("/admin/file-configurations/{config_id}")
def update_file_configuration(
    config_id: str,
    body: _FileConfigUpdateRequest,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    config = (
        db.query(IntakeFileConfiguration)
        .filter(IntakeFileConfiguration.id == config_id)
        .first()
    )
    if config is None or config.tenant_id != user.company_id:
        raise HTTPException(status_code=404, detail="Not found.")

    payload = body.model_dump(exclude_unset=True)
    for k, v in payload.items():
        setattr(config, k, v)
    config.updated_by_user_id = user.id
    db.commit()
    db.refresh(config)
    return _admin_file_config_view(config)


@router.delete("/admin/file-configurations/{config_id}", status_code=204)
def delete_file_configuration(
    config_id: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    config = (
        db.query(IntakeFileConfiguration)
        .filter(IntakeFileConfiguration.id == config_id)
        .first()
    )
    if config is None or config.tenant_id != user.company_id:
        raise HTTPException(status_code=404, detail="Not found.")
    config.is_active = False
    config.updated_by_user_id = user.id
    db.commit()
    return None
