"""GenerationFocusInstance — canonical Generation Focus instance entity per
§3.26.11.12 Generation Focus canon + §3.26.11.12.20 single-entity-with-discriminator
meta-pattern (5th canonical application post-Session-7).

**Phase 1A canonical-pattern-establisher**: ships the canonical Generation
Focus instance entity model that Step 2 (Urn Vault Personalization Studio)
inherits via discriminator differentiation + future Generation Focus templates
(per §3.26.11.12 strategic vision: Wall Designer, Drawing Takeoff, Audit
Prep, Mix Design, Legacy Studio, monument customizer, engraved urn customizer,
Surgical Planning, Treatment Plan, Discharge Planning, Invoice Factoring
Decision Focus) extend the same single-entity table.

**Canonical anti-pattern guards explicit at canonical-pattern-establisher
boundary**:

- §2.4.4 Anti-pattern 8 (vertical-specific code creep) — entity model is
  canonical Generation Focus instance substrate, NOT FH-vertical or
  Mfg-vertical specific. Vertical-specific behavior canonicalized at
  service-layer (template_type + authoring_context discriminator dispatch).
- §2.4.4 Anti-pattern 9 (primitive proliferation under composition pressure)
  — ``generation_focus_instances`` is canonical instance entity of existing
  Generation Focus primitive type, NOT new platform primitive.
- §3.26.11.12.16 Anti-pattern 11 (UI-coupled Generation Focus design rejected)
  — entity model output schema independent from interactive UI; canvas
  state lives in Document substrate per D-9 polymorphic substrate; entity
  model carries only canonical lifecycle + linkage + discriminator metadata.

**Canonical Document substrate consumption per D-9** (§3.26.11.12.5
substrate-consumption-only canonical commitment): canvas state persists
to ``documents.id`` FK (canonical Document) + each canvas commit creates
a new ``DocumentVersion`` with ``is_current=True`` flip per D-9 versioning
canonical. Entity model holds ``document_id`` FK only; full canvas state
lives in Document substrate.

**JSONB denormalization** at ``case_merchandise.vault_personalization``
shipping at service-layer per Phase 1A — this entity model is canonical;
the JSONB denormalization is canonical case-record-level visibility
substrate consumed by case detail views per existing FH-vertical canonical
case data shape.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# Canonical enumerations — keep in sync with migration r76 + r80 + service
# layer. Phase 1A canonical-pattern-establisher set + Step 2 substrate-
# consumption-follower extension. Future migrations extend.
CANONICAL_TEMPLATE_TYPES: tuple[str, ...] = (
    "burial_vault_personalization_studio",
    "urn_vault_personalization_studio",
)

CANONICAL_AUTHORING_CONTEXTS: tuple[str, ...] = (
    "funeral_home_with_family",
    "manufacturer_without_family",
    "manufacturer_from_fh_share",
)

CANONICAL_LIFECYCLE_STATES: tuple[str, ...] = (
    "active",
    "draft",
    "committed",
    "abandoned",
)

CANONICAL_LINKED_ENTITY_TYPES: tuple[str, ...] = (
    "fh_case",
    "sales_order",
    "document_share",
)

CANONICAL_FAMILY_APPROVAL_STATUSES: tuple[str, ...] = (
    "not_requested",
    "requested",
    "approved",
    "rejected",
)


# Q3 canonical pairing per §3.26.11.12.19.3 baked: authoring_context ↔
# linked_entity_type. Service layer enforces this on row creation; CHECK
# constraint at DB layer enforces canonical-quality at substrate boundary.
AUTHORING_CONTEXT_TO_LINKED_ENTITY_TYPE: dict[str, str] = {
    "funeral_home_with_family": "fh_case",
    "manufacturer_without_family": "sales_order",
    "manufacturer_from_fh_share": "document_share",
}


class GenerationFocusInstance(Base):
    """Canonical Generation Focus instance entity per §3.26.11.12 + Phase 1A.

    Single-entity-with-discriminator pattern: ``template_type`` discriminator
    routes to per-template canonical service-layer dispatch. Phase 1A
    canonical value: ``burial_vault_personalization_studio``.
    """

    __tablename__ = "generation_focus_instances"
    __table_args__ = (
        CheckConstraint(
            "template_type IN ("
            + ", ".join(f"'{v}'" for v in CANONICAL_TEMPLATE_TYPES)
            + ")",
            name="ck_gen_focus_template_type",
        ),
        CheckConstraint(
            "authoring_context IN ("
            + ", ".join(f"'{v}'" for v in CANONICAL_AUTHORING_CONTEXTS)
            + ")",
            name="ck_gen_focus_authoring_context",
        ),
        CheckConstraint(
            "lifecycle_state IN ("
            + ", ".join(f"'{v}'" for v in CANONICAL_LIFECYCLE_STATES)
            + ")",
            name="ck_gen_focus_lifecycle_state",
        ),
        CheckConstraint(
            "linked_entity_type IN ("
            + ", ".join(f"'{v}'" for v in CANONICAL_LINKED_ENTITY_TYPES)
            + ")",
            name="ck_gen_focus_linked_entity_type",
        ),
        CheckConstraint(
            "("
            "(authoring_context = 'funeral_home_with_family' AND linked_entity_type = 'fh_case') "
            "OR (authoring_context = 'manufacturer_without_family' AND linked_entity_type = 'sales_order') "
            "OR (authoring_context = 'manufacturer_from_fh_share' AND linked_entity_type = 'document_share')"
            ")",
            name="ck_gen_focus_authoring_linked_entity_pair",
        ),
        CheckConstraint(
            "family_approval_status IS NULL OR family_approval_status IN ("
            + ", ".join(f"'{v}'" for v in CANONICAL_FAMILY_APPROVAL_STATUSES)
            + ")",
            name="ck_gen_focus_family_approval_status",
        ),
        Index(
            "ix_gen_focus_company_template_lifecycle",
            "company_id",
            "template_type",
            "lifecycle_state",
        ),
        Index(
            "ix_gen_focus_linked_entity",
            "linked_entity_type",
            "linked_entity_id",
        ),
        Index("ix_gen_focus_document_id", "document_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Canonical discriminators per Phase 1A canonical-pattern-establisher.
    template_type: Mapped[str] = mapped_column(String(64), nullable=False)
    authoring_context: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active"
    )

    # Polymorphic linked entity per Q3 canonical pairing.
    linked_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    linked_entity_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # Canonical Document substrate consumption per D-9. Nullable until
    # first canvas commit per §3.26.11.12.5 substrate-consumption canonical.
    document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Canonical Generation Focus instance lifecycle metadata per §3.26.11.12.5.
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    opened_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    committed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    committed_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    abandoned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    abandoned_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Family approval canonical (FH-vertical authoring context per Q7b).
    # Nullable for Mfg-vertical authoring contexts (manufacturer_without_family,
    # manufacturer_from_fh_share) — those don't have family canonical
    # participation per §3.26.11.12.19.3.
    family_approval_status: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    family_approval_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    family_approval_decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Canonical Path B substrate consumption per Phase 1E (§3.26.11.12 +
    # §3.26.11.12.19 Personalization Studio canonical category).
    # ``action_payload['actions'][]`` carries the canonical action shape per
    # §3.26.15.17 + §3.26.16.18 (mirrors ``email_messages.message_payload``
    # + ``calendar_events.action_payload`` precedents). Phase 1E ships the
    # ``personalization_studio_family_approval`` action_type. Migration r78.
    action_payload: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        server_default=text("'{}'::jsonb"),
        default=dict,
    )

    # Standard timestamps.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        onupdate=_now,
    )

    # Relationship to canonical Document — use the fully-qualified module
    # string so SQLAlchemy disambiguates from legacy Document model. Both
    # `app.models.canonical_document.Document` and
    # `app.models.document.Document` register under bare class name
    # "Document" in the SQLAlchemy registry; canonical pattern is the
    # fully-qualified module string per CLAUDE.md §14 D-1 backbone notes.
    document = relationship(
        "app.models.canonical_document.Document",
        foreign_keys=[document_id],
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<GenerationFocusInstance id={self.id[:8]} "
            f"template={self.template_type} "
            f"authoring={self.authoring_context} "
            f"lifecycle={self.lifecycle_state}>"
        )
