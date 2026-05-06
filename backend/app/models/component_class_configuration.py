"""Component Class Configuration model — class-scoped prop override
storage for the Admin Visual Editor's class layer (May 2026).

The class layer slots into the inheritance chain between
registration defaults and platform-specific defaults:

    registration_default
        + class_default (THIS TABLE)
            + platform_default (component_configurations table)
                + vertical_default
                    + tenant_override

Class scope is single — there's no vertical/tenant variant of a
class default. A class default applies platform-wide. Per-component
overrides live in `component_configurations` and override class
defaults at the per-component layer.

v1 invariant: each component belongs to exactly one class
(`componentClasses: [type]` derived from ComponentKind unless
explicitly declared). The class vocabulary is enumerated by the
table's CHECK constraint — see migration r83.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ComponentClassConfiguration(Base):
    """Class-scoped configuration overrides.

    Written via `component_class_config_service.create_class_config`
    + `update_class_config` (versioned: every save deactivates the
    prior active row + inserts a new active row with version + 1).
    Resolution at READ time via
    `component_class_config_service.resolve_class_config`.
    """

    __tablename__ = "component_class_configurations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    component_class: Mapped[str] = mapped_column(String(64), nullable=False)
    prop_overrides: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
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
            f"<ComponentClassConfiguration(id={self.id}, "
            f"class={self.component_class}, version={self.version}, "
            f"is_active={self.is_active})>"
        )
