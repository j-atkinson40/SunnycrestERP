"""Component Configuration model — per-component prop override
storage for the Admin Visual Editor (Phase 3).

Inheritance chain at READ time:
    platform_default
        + vertical_default(vertical=X) overrides
            + tenant_override(tenant_id=Y) overrides

Same architectural pattern as PlatformTheme (r79) — write-side
versioning with `is_active` partial unique, scope-key CHECK
constraint, READ-time inheritance walk in
`component_config_service.resolve_configuration`.
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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# Reuse the same scope vocabulary as PlatformTheme; importing the
# constants would create a circular dependency through __init__,
# so we redeclare the literals here.
SCOPE_PLATFORM_DEFAULT = "platform_default"
SCOPE_VERTICAL_DEFAULT = "vertical_default"
SCOPE_TENANT_OVERRIDE = "tenant_override"


class ComponentConfiguration(Base):
    """One row per (scope, vertical?, tenant_id?, component_kind,
    component_name) version. Active rows are unique per the partial
    index defined in r80; inactive rows accumulate as a version trail.
    """

    __tablename__ = "component_configurations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    vertical: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
    )
    component_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    component_name: Mapped[str] = mapped_column(String(96), nullable=False)
    prop_overrides: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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
            "scope IN ('platform_default', 'vertical_default', 'tenant_override')",
            name="ck_component_configs_scope",
        ),
        CheckConstraint(
            """(
                (scope = 'platform_default'
                    AND vertical IS NULL AND tenant_id IS NULL)
                OR (scope = 'vertical_default'
                    AND vertical IS NOT NULL AND tenant_id IS NULL)
                OR (scope = 'tenant_override'
                    AND vertical IS NULL AND tenant_id IS NOT NULL)
            )""",
            name="ck_component_configs_scope_keys",
        ),
        CheckConstraint(
            "component_kind IN ('widget', 'focus', 'focus-template', "
            "'document-block', 'pulse-widget', 'workflow-node', 'layout', "
            "'composite')",
            name="ck_component_configs_kind",
        ),
    )

    def __repr__(self) -> str:
        ident = self.vertical or self.tenant_id or "platform"
        return (
            f"<ComponentConfiguration {self.scope}:{ident}:"
            f"{self.component_kind}:{self.component_name} "
            f"v{self.version} active={self.is_active}>"
        )
