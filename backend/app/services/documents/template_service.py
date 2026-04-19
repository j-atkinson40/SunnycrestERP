"""Admin-side template registry operations — Phase D-2 + D-3.

D-2 shipped read-only: list, get, get_versions, get_version.
D-3 adds draft creation, update, activation, rollback, forking, and
audit log writes.

Pattern mirrors the Intelligence prompt_registry + prompt_service split.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.document_template import (
    DocumentTemplate,
    DocumentTemplateAuditLog,
    DocumentTemplateVersion,
)


def _scope_label(company_id: str | None) -> str:
    return "platform" if company_id is None else "tenant"


def _version_summary(v: DocumentTemplateVersion | None) -> dict | None:
    if v is None:
        return None
    return {
        "id": v.id,
        "version_number": v.version_number,
        "status": v.status,
        "changelog": v.changelog,
        "activated_at": v.activated_at,
        "created_at": v.created_at,
    }


def list_templates(
    db: Session,
    *,
    current_company_id: str | None,
    document_type: str | None = None,
    output_format: str | None = None,
    scope: str | None = None,  # "platform" | "tenant" | "both"
    search: str | None = None,
    status: str | None = None,  # "active" | "all"
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """List templates visible to the caller.

    Visibility:
      - Admins see all platform templates (always)
      - Admins see their tenant's templates (if scope != 'platform')
      - Admins never see other tenants' templates

    Returns (items, total_count).
    """
    q = db.query(DocumentTemplate).filter(
        DocumentTemplate.deleted_at.is_(None)
    )

    # Scope filtering
    if scope == "platform":
        q = q.filter(DocumentTemplate.company_id.is_(None))
    elif scope == "tenant":
        if current_company_id is None:
            # Super admin in tenant-only mode — show nothing
            q = q.filter(DocumentTemplate.id == "__no_match__")
        else:
            q = q.filter(DocumentTemplate.company_id == current_company_id)
    else:
        # Default / "both" — platform + own tenant
        if current_company_id is None:
            q = q.filter(DocumentTemplate.company_id.is_(None))
        else:
            q = q.filter(
                or_(
                    DocumentTemplate.company_id.is_(None),
                    DocumentTemplate.company_id == current_company_id,
                )
            )

    if document_type:
        q = q.filter(DocumentTemplate.document_type == document_type)
    if output_format:
        q = q.filter(DocumentTemplate.output_format == output_format)
    if status == "active":
        q = q.filter(DocumentTemplate.is_active.is_(True))
    if search:
        pattern = f"%{search.lower()}%"
        q = q.filter(
            or_(
                DocumentTemplate.template_key.ilike(pattern),
                DocumentTemplate.description.ilike(pattern),
            )
        )

    total = q.count()
    rows = (
        q.order_by(DocumentTemplate.template_key)
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Preload which template IDs have a draft (avoids N+1)
    template_ids = [t.id for t in rows]
    draft_ids: set[str] = set()
    if template_ids:
        draft_rows = (
            db.query(DocumentTemplateVersion.template_id)
            .filter(
                DocumentTemplateVersion.template_id.in_(template_ids),
                DocumentTemplateVersion.status == "draft",
            )
            .all()
        )
        draft_ids = {r[0] for r in draft_rows}

    items: list[dict[str, Any]] = []
    for t in rows:
        cv = t.current_version
        items.append(
            {
                "id": t.id,
                "company_id": t.company_id,
                "template_key": t.template_key,
                "document_type": t.document_type,
                "output_format": t.output_format,
                "description": t.description,
                "supports_variants": t.supports_variants,
                "is_active": t.is_active,
                "current_version_number": cv.version_number if cv else None,
                "current_version_activated_at": cv.activated_at if cv else None,
                "scope": _scope_label(t.company_id),
                "has_draft": t.id in draft_ids,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
            }
        )
    return items, total


def get_template_detail(
    db: Session,
    template_id: str,
    *,
    current_company_id: str | None,
) -> dict[str, Any] | None:
    """Full detail for a template — current version content + summary of
    all versions. Returns None if the template isn't visible to the caller.
    """
    t = (
        db.query(DocumentTemplate)
        .filter(
            DocumentTemplate.id == template_id,
            DocumentTemplate.deleted_at.is_(None),
        )
        .first()
    )
    if t is None:
        return None
    # Access check: platform (null) is fine; tenant must match caller
    if t.company_id is not None and t.company_id != current_company_id:
        return None

    versions = (
        db.query(DocumentTemplateVersion)
        .filter(DocumentTemplateVersion.template_id == t.id)
        .order_by(DocumentTemplateVersion.version_number.desc())
        .all()
    )
    current = t.current_version

    return {
        "id": t.id,
        "company_id": t.company_id,
        "template_key": t.template_key,
        "document_type": t.document_type,
        "output_format": t.output_format,
        "description": t.description,
        "supports_variants": t.supports_variants,
        "is_active": t.is_active,
        "scope": _scope_label(t.company_id),
        "created_at": t.created_at,
        "updated_at": t.updated_at,
        "current_version": {
            "id": current.id,
            "template_id": current.template_id,
            "version_number": current.version_number,
            "status": current.status,
            "body_template": current.body_template,
            "subject_template": current.subject_template,
            "variable_schema": current.variable_schema,
            "sample_context": current.sample_context,
            "css_variables": current.css_variables,
            "changelog": current.changelog,
            "activated_at": current.activated_at,
            "activated_by_user_id": current.activated_by_user_id,
            "created_at": current.created_at,
        }
        if current is not None
        else None,
        "version_summaries": [_version_summary(v) for v in versions],
    }


def get_version(
    db: Session,
    template_id: str,
    version_id: str,
    *,
    current_company_id: str | None,
) -> dict[str, Any] | None:
    """Full content of a specific version. Access gated by template scope."""
    t = (
        db.query(DocumentTemplate)
        .filter(
            DocumentTemplate.id == template_id,
            DocumentTemplate.deleted_at.is_(None),
        )
        .first()
    )
    if t is None:
        return None
    if t.company_id is not None and t.company_id != current_company_id:
        return None
    v = (
        db.query(DocumentTemplateVersion)
        .filter(
            and_(
                DocumentTemplateVersion.id == version_id,
                DocumentTemplateVersion.template_id == t.id,
            )
        )
        .first()
    )
    if v is None:
        return None
    return {
        "id": v.id,
        "template_id": v.template_id,
        "version_number": v.version_number,
        "status": v.status,
        "body_template": v.body_template,
        "subject_template": v.subject_template,
        "variable_schema": v.variable_schema,
        "sample_context": v.sample_context,
        "css_variables": v.css_variables,
        "changelog": v.changelog,
        "activated_at": v.activated_at,
        "activated_by_user_id": v.activated_by_user_id,
        "created_at": v.created_at,
    }


# ── Phase D-3 editing operations ───────────────────────────────────────


class TemplateEditError(Exception):
    """Raised when an edit operation is rejected for semantic reasons
    (conflict, not-found, not-in-draft, etc). The API layer maps these
    onto HTTP 4xx responses."""

    def __init__(self, message: str, *, http_status: int = 400) -> None:
        super().__init__(message)
        self.http_status = http_status


def get_template(db: Session, template_id: str) -> DocumentTemplate | None:
    """Raw template lookup — no scope check. Callers enforce visibility."""
    return (
        db.query(DocumentTemplate)
        .filter(
            DocumentTemplate.id == template_id,
            DocumentTemplate.deleted_at.is_(None),
        )
        .first()
    )


def get_draft(db: Session, template_id: str) -> DocumentTemplateVersion | None:
    """Return the single draft version for this template, or None."""
    return (
        db.query(DocumentTemplateVersion)
        .filter(
            DocumentTemplateVersion.template_id == template_id,
            DocumentTemplateVersion.status == "draft",
        )
        .first()
    )


def get_active_version(
    db: Session, template_id: str
) -> DocumentTemplateVersion | None:
    return (
        db.query(DocumentTemplateVersion)
        .filter(
            DocumentTemplateVersion.template_id == template_id,
            DocumentTemplateVersion.status == "active",
        )
        .first()
    )


def _next_version_number(db: Session, template_id: str) -> int:
    return int(
        db.query(
            func.coalesce(func.max(DocumentTemplateVersion.version_number), 0)
            + 1
        )
        .filter(DocumentTemplateVersion.template_id == template_id)
        .scalar()
    )


def write_audit(
    db: Session,
    *,
    template: DocumentTemplate,
    version: DocumentTemplateVersion | None,
    action: str,
    actor_user_id: str | None,
    actor_email: str | None,
    changelog_summary: str | None = None,
    meta: dict[str, Any] | None = None,
) -> DocumentTemplateAuditLog:
    entry = DocumentTemplateAuditLog(
        id=str(uuid.uuid4()),
        template_id=template.id,
        version_id=version.id if version else None,
        action=action,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        changelog_summary=changelog_summary,
        meta_json=meta or {},
    )
    db.add(entry)
    return entry


def create_draft(
    db: Session,
    *,
    template: DocumentTemplate,
    base_version_id: str | None,
    changelog: str | None,
    actor_user_id: str | None,
    actor_email: str | None,
) -> DocumentTemplateVersion:
    """Clone a base version (active by default) into a new draft.

    Only one draft per template — raises TemplateEditError(409) if one
    already exists.
    """
    existing = get_draft(db, template.id)
    if existing is not None:
        raise TemplateEditError(
            "A draft already exists for this template. Continue editing "
            "it or discard it first.",
            http_status=409,
        )

    if base_version_id:
        base = (
            db.query(DocumentTemplateVersion)
            .filter(
                DocumentTemplateVersion.id == base_version_id,
                DocumentTemplateVersion.template_id == template.id,
            )
            .first()
        )
        if base is None:
            raise TemplateEditError(
                "base_version_id does not belong to this template",
                http_status=404,
            )
    else:
        base = get_active_version(db, template.id)
        if base is None:
            raise TemplateEditError(
                "No active version to clone. Pass base_version_id explicitly.",
                http_status=400,
            )

    next_number = _next_version_number(db, template.id)
    draft = DocumentTemplateVersion(
        id=str(uuid.uuid4()),
        template_id=template.id,
        version_number=next_number,
        status="draft",
        body_template=base.body_template,
        subject_template=base.subject_template,
        variable_schema=(
            dict(base.variable_schema) if base.variable_schema else None
        ),
        sample_context=(
            dict(base.sample_context) if base.sample_context else None
        ),
        css_variables=(
            dict(base.css_variables) if base.css_variables else None
        ),
        changelog=changelog,
    )
    db.add(draft)
    db.flush()
    write_audit(
        db,
        template=template,
        version=draft,
        action="create_draft",
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        changelog_summary=changelog,
        meta={
            "base_version_id": base.id,
            "base_version_number": base.version_number,
        },
    )
    return draft


def update_draft(
    db: Session,
    *,
    template: DocumentTemplate,
    version: DocumentTemplateVersion,
    fields: dict[str, Any],
    actor_user_id: str | None,
    actor_email: str | None,
) -> DocumentTemplateVersion:
    """Mutate a draft. `fields` is the pydantic exclude_unset dict.

    Raises TemplateEditError if version isn't a draft.
    """
    if version.status != "draft":
        raise TemplateEditError(
            f"Version is {version.status!r} — only drafts are editable. "
            f"Create a new draft via POST /versions/draft to propose changes.",
            http_status=409,
        )
    for field_name, value in fields.items():
        setattr(version, field_name, value)
    write_audit(
        db,
        template=template,
        version=version,
        action="update_draft",
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        changelog_summary=version.changelog,
        meta={"fields_changed": sorted(fields.keys())},
    )
    return version


def delete_draft(
    db: Session,
    *,
    template: DocumentTemplate,
    version: DocumentTemplateVersion,
    actor_user_id: str | None,
    actor_email: str | None,
) -> None:
    if version.status != "draft":
        raise TemplateEditError(
            f"Only draft versions can be deleted (got {version.status!r}).",
            http_status=409,
        )
    write_audit(
        db,
        template=template,
        version=None,  # Version row is being deleted — FK would break
        action="delete_draft",
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        changelog_summary=version.changelog,
        meta={
            "version_number": version.version_number,
            "deleted_version_id": version.id,
        },
    )
    db.delete(version)


def activate_version(
    db: Session,
    *,
    template: DocumentTemplate,
    version: DocumentTemplateVersion,
    changelog: str,
    actor_user_id: str | None,
    actor_email: str | None,
) -> DocumentTemplateVersion:
    """Transition a draft to active. Retires the current active version
    (if any) and updates template.current_version_id.

    Caller is responsible for variable-schema validation (done at the
    API layer so we can emit a structured 400 with the issue list).
    """
    if version.status != "draft":
        raise TemplateEditError(
            f"Only drafts can be activated — got status {version.status!r}.",
            http_status=409,
        )
    if not (changelog or "").strip():
        raise TemplateEditError("changelog is required", http_status=400)

    meta: dict[str, Any] = {}
    prior_active = get_active_version(db, template.id)
    if prior_active is not None and prior_active.id != version.id:
        prior_active.status = "retired"
        meta["previous_active_version_id"] = prior_active.id
        meta["previous_active_version_number"] = prior_active.version_number

    version.status = "active"
    version.changelog = changelog
    version.activated_at = datetime.now(timezone.utc)
    version.activated_by_user_id = actor_user_id
    template.current_version_id = version.id
    template.updated_at = datetime.now(timezone.utc)

    write_audit(
        db,
        template=template,
        version=version,
        action="activate",
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        changelog_summary=changelog,
        meta=meta,
    )
    return version


def rollback_to_version(
    db: Session,
    *,
    template: DocumentTemplate,
    target: DocumentTemplateVersion,
    changelog: str,
    actor_user_id: str | None,
    actor_email: str | None,
) -> DocumentTemplateVersion:
    """Clone a retired version into a new active version. Version numbers
    stay monotonic — rolling back to v5 while v8 is active produces v9 as
    a copy of v5's content; v8 transitions to retired.
    """
    if target.template_id != template.id:
        raise TemplateEditError(
            "Target version does not belong to this template",
            http_status=404,
        )
    if target.status != "retired":
        raise TemplateEditError(
            f"Only retired versions can be rolled back to. "
            f"Version {target.version_number} is {target.status!r}.",
            http_status=409,
        )
    if not (changelog or "").strip():
        raise TemplateEditError("changelog is required", http_status=400)

    next_number = _next_version_number(db, template.id)
    new_version = DocumentTemplateVersion(
        id=str(uuid.uuid4()),
        template_id=template.id,
        version_number=next_number,
        status="active",
        body_template=target.body_template,
        subject_template=target.subject_template,
        variable_schema=(
            dict(target.variable_schema) if target.variable_schema else None
        ),
        sample_context=(
            dict(target.sample_context) if target.sample_context else None
        ),
        css_variables=(
            dict(target.css_variables) if target.css_variables else None
        ),
        changelog=changelog,
        activated_at=datetime.now(timezone.utc),
        activated_by_user_id=actor_user_id,
    )
    db.add(new_version)
    db.flush()

    meta: dict[str, Any] = {
        "rolled_back_to_version_id": target.id,
        "rolled_back_to_version_number": target.version_number,
    }
    prior_active = (
        db.query(DocumentTemplateVersion)
        .filter(
            DocumentTemplateVersion.template_id == template.id,
            DocumentTemplateVersion.status == "active",
            DocumentTemplateVersion.id != new_version.id,
        )
        .first()
    )
    if prior_active is not None:
        prior_active.status = "retired"
        meta["previous_active_version_id"] = prior_active.id
        meta["previous_active_version_number"] = prior_active.version_number

    template.current_version_id = new_version.id
    template.updated_at = datetime.now(timezone.utc)

    write_audit(
        db,
        template=template,
        version=new_version,
        action="rollback",
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        changelog_summary=changelog,
        meta=meta,
    )
    return new_version


def fork_platform_to_tenant(
    db: Session,
    *,
    source_template: DocumentTemplate,
    target_company_id: str,
    actor_user_id: str | None,
    actor_email: str | None,
) -> DocumentTemplate:
    """Copy a platform-global template into a tenant-scoped template.

    The new row starts with one active version whose content is a copy
    of the source's current active version. Version numbering on the
    tenant template restarts at 1 — it is an independent history.
    """
    if source_template.company_id is not None:
        raise TemplateEditError(
            "Only platform templates can be forked. Source is tenant-scoped.",
            http_status=400,
        )

    active = get_active_version(db, source_template.id)
    if active is None:
        raise TemplateEditError(
            "Source platform template has no active version to fork from",
            http_status=400,
        )

    existing = (
        db.query(DocumentTemplate)
        .filter(
            DocumentTemplate.company_id == target_company_id,
            DocumentTemplate.template_key == source_template.template_key,
            DocumentTemplate.deleted_at.is_(None),
        )
        .first()
    )
    if existing is not None:
        raise TemplateEditError(
            f"Tenant already has a template with key "
            f"{source_template.template_key!r}",
            http_status=409,
        )

    new_template = DocumentTemplate(
        id=str(uuid.uuid4()),
        company_id=target_company_id,
        template_key=source_template.template_key,
        document_type=source_template.document_type,
        output_format=source_template.output_format,
        description=source_template.description,
        supports_variants=source_template.supports_variants,
        is_active=True,
    )
    db.add(new_template)
    db.flush()

    version = DocumentTemplateVersion(
        id=str(uuid.uuid4()),
        template_id=new_template.id,
        version_number=1,
        status="active",
        body_template=active.body_template,
        subject_template=active.subject_template,
        variable_schema=(
            dict(active.variable_schema) if active.variable_schema else None
        ),
        sample_context=(
            dict(active.sample_context) if active.sample_context else None
        ),
        css_variables=(
            dict(active.css_variables) if active.css_variables else None
        ),
        changelog=(
            f"Forked from platform template "
            f"{source_template.template_key!r} "
            f"(v{active.version_number})"
        ),
        activated_at=datetime.now(timezone.utc),
        activated_by_user_id=actor_user_id,
    )
    db.add(version)
    db.flush()
    new_template.current_version_id = version.id

    fork_meta = {
        "source_template_id": source_template.id,
        "source_version_id": active.id,
        "source_version_number": active.version_number,
        "target_company_id": target_company_id,
    }
    # Audit row on the source (so the platform template's activity
    # timeline shows who forked it)
    write_audit(
        db,
        template=source_template,
        version=None,
        action="fork_to_tenant",
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        changelog_summary=(
            f"Forked to tenant {target_company_id}"
        ),
        meta=fork_meta,
    )
    # Audit row on the new tenant template (so its own timeline has an
    # origin entry)
    write_audit(
        db,
        template=new_template,
        version=version,
        action="create_draft",  # Re-using — "create from fork" would be
        actor_user_id=actor_user_id,  # a 7th action; keep the vocabulary
        actor_email=actor_email,  # small for the UI.
        changelog_summary=(
            f"Created by forking platform template "
            f"{source_template.template_key!r}"
        ),
        meta={**fork_meta, "was_forked": True},
    )

    return new_template


def list_audit(
    db: Session, template_id: str, limit: int = 50, offset: int = 0
) -> list[DocumentTemplateAuditLog]:
    return (
        db.query(DocumentTemplateAuditLog)
        .filter(DocumentTemplateAuditLog.template_id == template_id)
        .order_by(DocumentTemplateAuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
