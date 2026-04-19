"""Canonical Document model — Phase D-1 backbone.

Two tables:
  documents           — the canonical record (tenant-scoped, polymorphic
                        entity linkage + specialty FKs)
  document_versions   — immutable per-render history. Exactly one version
                        per document has is_current=True.

Naming — the class is `Document` to match the domain, but the module is
`canonical_document` to disambiguate from the legacy model in
`app.models.document`. Import via `from app.models.canonical_document
import Document` OR via the alias re-exported from `app.models.__init__`
as `CanonicalDocument`.
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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Classification + presentation
    document_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Storage — R2-only. storage_key mirrors the current DocumentVersion
    # for convenience (one hop instead of JOIN for the common list case).
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(
        String(100), nullable=False, default="application/pdf"
    )
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Lifecycle — draft | rendered | signed | delivered | archived | failed
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft"
    )

    # Template identity — template_key references the current template_loader.
    # D-2 turns this into an FK to document_templates.
    template_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    template_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Render metadata — mirrors the current DocumentVersion for convenience.
    rendered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rendered_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rendering_duration_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    rendering_context_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )

    # Polymorphic entity linkage — either use these + one of the specialty
    # FKs below, or just these, or just the specialty FK. All are
    # nullable; populate what applies.
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Specialty linkage — most common entity types get a proper FK so
    # queries don't need the polymorphic join.
    sales_order_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("sales_orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    fh_case_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("fh_cases.id", ondelete="SET NULL"),
        nullable=True,
    )
    disinterment_case_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("disinterment_cases.id", ondelete="SET NULL"),
        nullable=True,
    )
    invoice_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
    )
    customer_statement_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("customer_statements.id", ondelete="SET NULL"),
        nullable=True,
    )
    price_list_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("price_list_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    safety_program_generation_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("safety_program_generations.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Source linkage — what produced this document
    caller_module: Mapped[str | None] = mapped_column(String(256), nullable=True)
    caller_workflow_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    caller_workflow_step_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    intelligence_execution_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("intelligence_executions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Phase D-3 — test-render flag. Test renders from the admin template
    # editor are excluded from the Document Log by default.
    is_test_render: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Timestamps + soft delete
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
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentVersion.version_number",
    )

    def __repr__(self) -> str:
        return (
            f"<Document id={self.id[:8]} type={self.document_type} "
            f"title={self.title!r} status={self.status}>"
        )

    # ── Phase D-6: cross-tenant visibility filter ─────────────────────
    @classmethod
    def visible_to(cls, company_id: str):
        """Return a SQLAlchemy filter expression selecting documents
        visible to `company_id`:

        - The caller OWNS the document (`documents.company_id = X`), OR
        - An active (non-revoked) `document_shares` row grants `X` read
          access.

        Use this in EVERY cross-tenant-relevant Document query. Raw
        `Document.company_id == company_id` filters return only owned
        documents and will miss shared documents — a security + UX bug.
        A pytest lint gate enforces this (see
        `tests/test_documents_d6_lint.py`).

        Usage:
            rows = (
                db.query(Document)
                .filter(Document.visible_to(user.company_id))
                .filter(Document.deleted_at.is_(None))
                .all()
            )

        The filter returns `sqlalchemy.or_(...)` so you can compose it
        with additional `.filter()` calls.
        """
        # Local import to avoid circular registration at module load
        from sqlalchemy import and_, exists, or_
        from app.models.document_share import DocumentShare

        share_exists = exists().where(
            and_(
                DocumentShare.document_id == cls.id,
                DocumentShare.target_company_id == company_id,
                DocumentShare.revoked_at.is_(None),
            )
        )
        return or_(cls.company_id == company_id, share_exists)

    def is_visible_to(self, company_id: str, db=None) -> bool:
        """Instance-level check: is this document visible to the given
        tenant? Owner-check is free; shared-check requires a DB query
        so callers must pass `db`."""
        if self.company_id == company_id:
            return True
        if db is None:
            return False
        from app.models.document_share import DocumentShare

        return (
            db.query(DocumentShare)
            .filter(
                DocumentShare.document_id == self.id,
                DocumentShare.target_company_id == company_id,
                DocumentShare.revoked_at.is_(None),
            )
            .first()
            is not None
        )


class DocumentVersion(Base):
    """Immutable per-render history.

    A new row is created every time a document is rendered. The `is_current`
    flag is True for exactly one row per document_id — the current rendering.
    """

    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(
        String(100), nullable=False, default="application/pdf"
    )
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    rendered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    rendered_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rendering_context_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    # "initial" | "data_updated" | "template_changed" | "manual_regenerate"
    render_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    # Use direct class reference — both legacy and canonical share the
    # bare string "Document" in the SQLAlchemy registry.
    document = relationship(Document, back_populates="versions")

    def __repr__(self) -> str:
        return (
            f"<DocumentVersion doc={self.document_id[:8]} "
            f"v{self.version_number} current={self.is_current}>"
        )
