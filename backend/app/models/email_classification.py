"""Phase R-6.1a — Email classification ORM models.

Three tables backing the three-tier inbound email classification
cascade:

  - ``TenantWorkflowEmailRule`` — Tier 1 deterministic rule list.
    Per-tenant, ordered by ``priority`` ascending. ``match_conditions``
    JSONB carries the operator dict; ``fire_action.workflow_id`` may
    be ``null`` to deliberately suppress (Tier 1 escape hatch).

  - ``TenantWorkflowEmailCategory`` — Tier 2 taxonomy nodes. Tree
    via ``parent_id`` self-FK. ``mapped_workflow_id`` is the workflow
    fired when the AI classifier picks this category. Depth bounded
    at 3 by convention; v1 ships flat.

  - ``WorkflowEmailClassification`` — append-only audit log; one
    row per inbound EmailMessage that traversed the cascade
    regardless of outcome. Replays + manual reroutes write NEW rows
    (preserves the canonical audit chain).

Tenant scope: every row has ``tenant_id`` FK to companies. Cross-
tenant id lookups in admin endpoints return 404 (existence-hiding
canon per CLAUDE.md §4 cross-realm boundary discipline).

Migration: r93_workflow_email_classification.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TenantWorkflowEmailRule(Base):
    """Tier 1 deterministic rule. First match in a tenant's rule list
    (ordered by ``priority`` ascending) wins. ``fire_action.workflow_id``
    may be ``null`` to suppress (drop without firing OR routing to
    triage)."""

    __tablename__ = "tenant_workflow_email_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # R-6.2a — discriminator for intake adapter the rule applies to.
    # "email" (default) preserves R-6.1 backward compat; "form" + "file"
    # added for R-6.2 form/file intake adapters.
    adapter_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="email"
    )
    match_conditions: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    # Shape: {"workflow_id": str | None, "suppress": bool} — only
    # workflow_id needed today; suppress is implicit (workflow_id=null).
    fire_action: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        onupdate=_now,
    )


class TenantWorkflowEmailCategory(Base):
    """Tier 2 taxonomy node. Tree via ``parent_id`` self-FK. Root
    nodes have ``parent_id=None``. ``mapped_workflow_id`` is the
    workflow fired when the AI classifier picks this category; null
    means the category exists for organization but doesn't dispatch
    a workflow (cascade falls through to Tier 3)."""

    __tablename__ = "tenant_workflow_email_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "tenant_workflow_email_categories.id", ondelete="CASCADE"
        ),
        nullable=True,
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    mapped_workflow_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("workflows.id", ondelete="SET NULL"),
        nullable=True,
    )
    position: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        onupdate=_now,
    )


class WorkflowEmailClassification(Base):
    """Append-only audit log. One row per inbound EmailMessage that
    traversed the cascade regardless of outcome (Tier 1 / 2 / 3 /
    unclassified / suppressed). Replays + manual reroutes write
    NEW rows; never UPDATE existing rows. This preserves the
    canonical audit chain — historical classification decisions
    remain visible after re-classification.

    The latest classification per message is read via
    ``ORDER BY created_at DESC LIMIT 1`` filtered by
    ``email_message_id``.
    """

    __tablename__ = "workflow_email_classifications"
    __table_args__ = (
        CheckConstraint(
            "tier IS NULL OR tier IN (1, 2, 3)",
            name="ck_workflow_email_classifications_tier",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email_message_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("email_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 1 / 2 / 3 = which tier dispatched. NULL = unclassified
    # (cascade exhausted, message routed to triage queue).
    tier: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    tier1_rule_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "tenant_workflow_email_rules.id", ondelete="SET NULL"
        ),
        nullable=True,
    )
    tier2_category_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "tenant_workflow_email_categories.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    tier2_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    tier3_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    # The workflow that was fired (null = unclassified or suppressed).
    selected_workflow_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("workflows.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Tier 1 fire_action.workflow_id == null path. Distinct from
    # ``tier IS NULL AND selected_workflow_id IS NULL`` (unclassified)
    # because suppressed messages do NOT route to triage; they're
    # dropped on the floor by operator design.
    is_suppressed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    workflow_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Replay tracking — when an admin replays a classification (after
    # editing rules/taxonomy/Tier 3 enrollment), the new row carries
    # ``is_replay=True`` and ``replay_of_classification_id`` points
    # at the original. Forms a linear replay chain queryable via
    # the FK.
    is_replay: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    replay_of_classification_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "workflow_email_classifications.id", ondelete="SET NULL"
        ),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Per-tier reasoning + debug payload. Shape:
    # {
    #   "tier1": {"matched_rule_id": ...} | null,
    #   "tier2": {"category_id": ..., "confidence": 0.78,
    #             "reasoning": "...", "error": null} | null,
    #   "tier3": {"workflow_id": ..., "confidence": 0.72,
    #             "reasoning": "...", "error": null} | null,
    # }
    tier_reasoning: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
