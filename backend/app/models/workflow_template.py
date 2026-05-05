"""Workflow Template + Tenant Workflow Fork models — Phase 4 of
the Admin Visual Editor.

Inheritance chain at READ time (`workflow_template_service.resolve_workflow`):

    platform_default(workflow_type)
        + vertical_default(vertical, workflow_type) overrides on top
            + tenant_workflow_forks(tenant_id, workflow_type)
              REPLACES if active

Tenant forks REPLACE the template chain (locked-to-fork semantics)
rather than overlaying — once a tenant customizes a workflow,
their fork's canvas_state is the truth until they accept an
upstream merge. This differs from theme + component config
inheritance (which always overlays) because workflow canvas_state
is a graph, not a flat map of overrides.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


SCOPE_PLATFORM_DEFAULT = "platform_default"
SCOPE_VERTICAL_DEFAULT = "vertical_default"


class WorkflowTemplate(Base):
    """Admin-authored workflow template at platform_default OR
    vertical_default scope. Tenants don't have their own template
    rows — tenant customization happens via TenantWorkflowFork.
    """

    __tablename__ = "workflow_templates"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    vertical: Mapped[str | None] = mapped_column(String(32), nullable=True)
    workflow_type: Mapped[str] = mapped_column(String(96), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    canvas_state: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "scope IN ('platform_default', 'vertical_default')",
            name="ck_workflow_templates_scope",
        ),
        CheckConstraint(
            """(
                (scope = 'platform_default' AND vertical IS NULL)
                OR (scope = 'vertical_default' AND vertical IS NOT NULL)
            )""",
            name="ck_workflow_templates_scope_keys",
        ),
    )

    def __repr__(self) -> str:
        ident = self.vertical or "platform"
        return (
            f"<WorkflowTemplate {self.scope}:{ident}:{self.workflow_type} "
            f"v{self.version} active={self.is_active}>"
        )


class TenantWorkflowFork(Base):
    """Per-tenant fork of a workflow template.

    Created lazily — when a tenant first customizes a workflow,
    a fork record is inserted with canvas_state cloned from the
    upstream template. Until then the tenant rides the vertical
    default directly (no fork row).

    Locked-to-fork merge: when the upstream template advances
    past `forked_from_version`, this fork's
    `pending_merge_available` flag flips true but its
    `canvas_state` is unchanged. The tenant explicitly accepts
    or rejects the upstream changes via the Workshop UI (Phase 5+).
    """

    __tablename__ = "tenant_workflow_forks"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_type: Mapped[str] = mapped_column(String(96), nullable=False)
    forked_from_template_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("workflow_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    forked_from_version: Mapped[int] = mapped_column(Integer, nullable=False)
    canvas_state: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    pending_merge_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    pending_merge_template_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("workflow_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<TenantWorkflowFork tenant={self.tenant_id}:"
            f"{self.workflow_type} v{self.version} "
            f"pending_merge={self.pending_merge_available} "
            f"active={self.is_active}>"
        )
