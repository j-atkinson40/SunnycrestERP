"""Document template registry — Phase D-2.

Two tables:
  DocumentTemplate         — platform or tenant-scoped template key
  DocumentTemplateVersion  — versioned body + subject + schema

Scope rule: template_key is unique per (company_id, template_key) — a
platform template has company_id=NULL, a tenant override has company_id
set. Lookup prefers the tenant-specific row, falls back to platform.

Versioning: mirrors `IntelligencePrompt`/`IntelligencePromptVersion`.
Exactly one version per template has status='active'; older are 'retired'
or still 'draft'. D-2 ships read-only; D-3 adds editing + activation.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DocumentTemplate(Base):
    __tablename__ = "document_templates"
    __table_args__ = (
        # Partial unique (company_id, template_key) WHERE deleted_at IS NULL
        # is enforced at the DB layer via migration; declaring a regular
        # UniqueConstraint here too would collide with the partial index on
        # Postgres. We rely on the migration's partial unique.
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,  # NULL = platform-global
        index=True,
    )

    template_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # Phase D-11 (June 2026) — three-tier scope. NULL on platform_default
    # AND tenant_override rows; set on vertical_default rows. CHECK
    # constraint at the migration level enforces `vertical IS NULL OR
    # company_id IS NULL` so vertical-scoped templates are platform-level
    # only (tenants inherit through their vertical at resolution time).
    vertical: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # "pdf" | "html" | "text"
    output_format: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    supports_variants: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    current_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("document_template_versions.id", ondelete="SET NULL"),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────────────
    versions = relationship(
        "DocumentTemplateVersion",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="DocumentTemplateVersion.version_number",
        foreign_keys="DocumentTemplateVersion.template_id",
    )
    current_version = relationship(
        "DocumentTemplateVersion",
        foreign_keys=[current_version_id],
        post_update=True,
        uselist=False,
    )

    def __repr__(self) -> str:
        scope = "platform" if self.company_id is None else "tenant"
        return (
            f"<DocumentTemplate id={self.id[:8]} key={self.template_key!r} "
            f"format={self.output_format} scope={scope}>"
        )


class DocumentTemplateVersion(Base):
    __tablename__ = "document_template_versions"
    __table_args__ = (
        UniqueConstraint(
            "template_id",
            "version_number",
            name="uq_document_template_version_number",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # "draft" | "active" | "retired"
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft"
    )

    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    subject_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    variable_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sample_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    css_variables: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)

    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    activated_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    template = relationship(
        "DocumentTemplate",
        back_populates="versions",
        foreign_keys=[template_id],
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentTemplateVersion template={self.template_id[:8]} "
            f"v{self.version_number} status={self.status}>"
        )


class DocumentTemplateAuditLog(Base):
    """Append-only audit trail for template state transitions.

    Phase D-3 — every draft create/update/delete, activate, rollback,
    fork-to-tenant writes a row here. Never mutated once written; queried
    for the DocumentTemplateDetail Activity section.
    """

    __tablename__ = "document_template_audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "document_template_versions.id", ondelete="SET NULL"
        ),
        nullable=True,
    )
    # create_draft | update_draft | delete_draft | activate | rollback |
    # fork_to_tenant
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    changelog_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentTemplateAuditLog template={self.template_id[:8]} "
            f"action={self.action}>"
        )
