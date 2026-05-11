"""Phase R-6.2a — Three-scope resolver for intake adapter configurations.

Canonical pattern (mirrors visual editor's platform_themes /
component_configurations from May 2026 + R-6.1's classification
cascade): tenant_override → vertical_default → platform_default.
First match wins. Resolution happens at READ time so platform /
vertical edits propagate instantly without per-tenant backfill.

Tenants without an override inherit vertical_default for their
vertical; without a vertical_default they inherit platform_default.
Without a platform_default the resolver returns None and the caller
raises ``IntakeConfigNotFound`` for HTTP 404 surfacing.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.intake_file_configuration import IntakeFileConfiguration
from app.models.intake_form_configuration import IntakeFormConfiguration


class IntakeError(Exception):
    """Base for intake-adapter errors. Carries http_status for the
    API layer."""

    def __init__(self, message: str, http_status: int = 400):
        super().__init__(message)
        self.http_status = http_status


class IntakeConfigNotFound(IntakeError):
    """Slug not resolvable for tenant — surfaced as 404."""

    def __init__(self, message: str = "Intake configuration not found"):
        super().__init__(message, http_status=404)


class IntakeValidationError(IntakeError):
    """Form-schema or upload validation failure — surfaced as 400."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, http_status=400)
        self.details = details or {}


def _resolve_tenant(db: Session, tenant_slug_or_id: str) -> Company | None:
    """Resolve tenant by slug or id. Returns None if not found."""
    return (
        db.query(Company)
        .filter(or_(Company.slug == tenant_slug_or_id, Company.id == tenant_slug_or_id))
        .filter(Company.is_active.is_(True))
        .first()
    )


def resolve_form_config(
    db: Session,
    *,
    slug: str,
    tenant: Company | None = None,
    tenant_slug: str | None = None,
) -> IntakeFormConfiguration | None:
    """Three-scope walk for a form configuration.

    Accepts either a Company instance (``tenant``) or a tenant slug
    (``tenant_slug``). When both are None, only platform_default
    rows are considered.

    Returns the resolved IntakeFormConfiguration or None.
    """
    if tenant is None and tenant_slug is not None:
        tenant = _resolve_tenant(db, tenant_slug)
        if tenant is None:
            # Public endpoints surface this as 404 — no information
            # leakage about tenant existence.
            return None

    tenant_id = tenant.id if tenant else None
    vertical = tenant.vertical if tenant else None

    # Tier 1: tenant_override (only when tenant resolved).
    if tenant_id is not None:
        row = (
            db.query(IntakeFormConfiguration)
            .filter(
                IntakeFormConfiguration.tenant_id == tenant_id,
                IntakeFormConfiguration.slug == slug,
                IntakeFormConfiguration.is_active.is_(True),
            )
            .first()
        )
        if row is not None:
            return row

    # Tier 2: vertical_default (only when tenant has a vertical).
    if vertical is not None:
        row = (
            db.query(IntakeFormConfiguration)
            .filter(
                IntakeFormConfiguration.tenant_id.is_(None),
                IntakeFormConfiguration.vertical == vertical,
                IntakeFormConfiguration.slug == slug,
                IntakeFormConfiguration.is_active.is_(True),
            )
            .first()
        )
        if row is not None:
            return row

    # Tier 3: platform_default.
    row = (
        db.query(IntakeFormConfiguration)
        .filter(
            IntakeFormConfiguration.tenant_id.is_(None),
            IntakeFormConfiguration.vertical.is_(None),
            IntakeFormConfiguration.slug == slug,
            IntakeFormConfiguration.is_active.is_(True),
        )
        .first()
    )
    return row


def resolve_file_config(
    db: Session,
    *,
    slug: str,
    tenant: Company | None = None,
    tenant_slug: str | None = None,
) -> IntakeFileConfiguration | None:
    """Three-scope walk for a file configuration. Mirror of
    ``resolve_form_config``."""
    if tenant is None and tenant_slug is not None:
        tenant = _resolve_tenant(db, tenant_slug)
        if tenant is None:
            return None

    tenant_id = tenant.id if tenant else None
    vertical = tenant.vertical if tenant else None

    if tenant_id is not None:
        row = (
            db.query(IntakeFileConfiguration)
            .filter(
                IntakeFileConfiguration.tenant_id == tenant_id,
                IntakeFileConfiguration.slug == slug,
                IntakeFileConfiguration.is_active.is_(True),
            )
            .first()
        )
        if row is not None:
            return row

    if vertical is not None:
        row = (
            db.query(IntakeFileConfiguration)
            .filter(
                IntakeFileConfiguration.tenant_id.is_(None),
                IntakeFileConfiguration.vertical == vertical,
                IntakeFileConfiguration.slug == slug,
                IntakeFileConfiguration.is_active.is_(True),
            )
            .first()
        )
        if row is not None:
            return row

    row = (
        db.query(IntakeFileConfiguration)
        .filter(
            IntakeFileConfiguration.tenant_id.is_(None),
            IntakeFileConfiguration.vertical.is_(None),
            IntakeFileConfiguration.slug == slug,
            IntakeFileConfiguration.is_active.is_(True),
        )
        .first()
    )
    return row


def resolve_tenant_by_slug(db: Session, slug: str) -> Company | None:
    """Public helper for API routes that need tenant resolution."""
    return _resolve_tenant(db, slug)
