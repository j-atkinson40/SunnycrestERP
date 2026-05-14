"""FocusCore — Tier 1 of the Focus Template Inheritance chain (r96).

Platform-owned core registry. Each row represents a pickable Focus
core: a code-implemented operational surface (dispatcher kanban,
arrangement scribe, decision flow) that templates inherit from.

Inheritance chain:

    focus_cores (Tier 1, platform-owned)
        ← focus_templates (Tier 2, platform_default | vertical_default)
            ← focus_compositions (Tier 3, per-tenant delta)

Cores are NOT composed in the visual editor — they're code. The
core registry surfaces them for selection. Templates inherit a core
and arrange accessory widgets around it on the composition canvas
(per the May 2026 core-plus-accessories canon). On the canvas the
core appears as a fixed-but-visible placement: movable + resizable
within `min_column_span` / `max_column_span` bounds, but not
deletable and not decomposable.

`registered_component_kind` + `registered_component_name` resolve
against the in-memory component registry
(`frontend/src/lib/visual-editor/registry/`). The actual React
component implementation lives in code.

Versioning: each save deactivates the prior active row + inserts a
new active row with version + 1. Partial unique index on
`is_active=true` enforces "at most one active row per core_slug."

Service layer + endpoints land in sub-arc B. This file is
data-shape only.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FocusCore(Base):
    """Tier 1 — platform-owned, code-implemented Focus core registry."""

    __tablename__ = "focus_cores"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    core_slug: Mapped[str] = mapped_column(String(96), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)

    # Resolves against the in-memory component registry. The actual
    # React component implementation lives in TS/React code.
    registered_component_kind: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    registered_component_name: Mapped[str] = mapped_column(
        String(96), nullable=False
    )

    # Default canvas geometry for this core when first placed onto
    # a template's `rows`. Operators can override per-template within
    # min_column_span / max_column_span bounds (service-layer enforced
    # in sub-arc B).
    default_starting_column: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    default_column_span: Mapped[int] = mapped_column(
        Integer, nullable=False, default=12
    )
    default_row_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    min_column_span: Mapped[int] = mapped_column(
        Integer, nullable=False, default=6
    )
    max_column_span: Mapped[int] = mapped_column(
        Integer, nullable=False, default=12
    )

    # Cosmetic canvas-level configuration carried with the core
    # (gap_size, background_treatment, padding, etc.). Shape mirrors
    # `focus_templates.canvas_config` + `focus_compositions.canvas_config_overrides`.
    canvas_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Backref populated via FocusTemplate.core relationship.
    templates: Mapped[list["FocusTemplate"]] = relationship(  # noqa: F821
        "FocusTemplate", back_populates="core"
    )

    __table_args__ = (
        CheckConstraint(
            "default_starting_column >= 0 AND default_starting_column < 12",
            name="ck_focus_cores_default_starting_column",
        ),
        CheckConstraint(
            "default_column_span >= 1 AND default_column_span <= 12",
            name="ck_focus_cores_default_column_span",
        ),
        CheckConstraint(
            "default_starting_column + default_column_span <= 12",
            name="ck_focus_cores_default_geometry_within_grid",
        ),
        CheckConstraint(
            "min_column_span >= 1 AND min_column_span <= 12",
            name="ck_focus_cores_min_column_span",
        ),
        CheckConstraint(
            "max_column_span >= min_column_span AND max_column_span <= 12",
            name="ck_focus_cores_max_column_span",
        ),
        CheckConstraint(
            "default_column_span >= min_column_span "
            "AND default_column_span <= max_column_span",
            name="ck_focus_cores_default_within_min_max",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<FocusCore(id={self.id}, slug={self.core_slug}, "
            f"version={self.version}, is_active={self.is_active})>"
        )
