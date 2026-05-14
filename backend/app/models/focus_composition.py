"""FocusComposition — Tier 3 of the Focus Template Inheritance chain (r96).

Per-tenant delta over a chosen `FocusTemplate`. Greenfield repurpose
of the May 2026 `focus_compositions` table: prior rows were dropped
in the r96 migration (no production tenants depended on the layer).

Inheritance chain:

    focus_cores (Tier 1)
        ← focus_templates (Tier 2)
            ← focus_compositions (Tier 3)            ← THIS FILE

A composition expresses a tenant's tweaks to a chosen template:
hidden placements, additional placements, reordered placements,
geometry overrides per placement, optional core geometry override.
The composition does NOT redeclare the template — it deltas over
it. The resolver (sub-arc B) walks template → composition and
materializes the effective layout at READ time.

deltas shape (informational; service-layer in sub-arc B validates):

    {
        "hidden_placement_ids": [str],
        "additional_placements": [
            {
                "placement_id": str,
                "component_kind": str,
                "component_name": str,
                "row_index": int,
                "starting_column": int 0-indexed,
                "column_span": int,
                "prop_overrides": dict,
                "display_config": dict,
            }
        ],
        "placement_order": [placement_id],
        "placement_geometry_overrides": {
            placement_id: {
                "starting_column": int,
                "column_span": int,
            }
        },
        "core_geometry_override": {
            "starting_column": int,
            "column_span": int,
            "row_index": int,
        }
    }

`canvas_config_overrides` JSONB carries cosmetic overrides on top
of the template's `canvas_config` (gap_size, background_treatment,
padding). Same shape as `FocusTemplate.canvas_config`.

Forward-compat: `inherits_from_template_version` ships now so a
future sub-arc can introduce versioned-snapshot inheritance without
schema migration. The v1 resolver (sub-arc B) ignores the version
and uses live-pointer semantics.

Versioning: each save deactivates the prior active row + inserts a
new active row with version + 1. Partial unique index on
`is_active=true` enforces "at most one active composition per
(tenant_id, inherits_from_template_id) tuple."

Service layer + endpoints + resolver land in sub-arc B. This file
is data-shape only — no validates_* decorators on the JSONB
columns; JSONB-shape validation is service-layer responsibility.

──── Sub-arc B-2 shim removal (May 2026) ───────────────────────────

The sub-arc A import-compatibility shim (SCOPE_*, KIND_*,
CANONICAL_KINDS module-level constants retained for legacy
consumers) was removed in sub-arc B-2 once all consumers had
migrated to the new substrates:

  - composition_service.py            → deleted; consumers moved to
                                          focus_template_inheritance
                                          and edge_panel_inheritance
  - vertical_inventory/service.py     → anchors on focus_templates +
                                          edge_panel_templates
  - api/routes/admin/visual_editor_compositions.py → deleted
  - api/routes/edge_panel.py          → uses edge_panel_inheritance
  - tests/{test_focus_compositions,
            test_edge_panel_r50,
            test_edge_panel_user_override,
            test_vertical_inventory}.py → rewritten against the new
                                          substrates

No remaining consumer imports SCOPE_*, KIND_*, or CANONICAL_KINDS.
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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FocusComposition(Base):
    """Tier 3 — per-tenant delta over a chosen FocusTemplate."""

    __tablename__ = "focus_compositions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Tier 2 reference + forward-compat version pointer.
    inherits_from_template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("focus_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    inherits_from_template_version: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    deltas: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    canvas_config_overrides: Mapped[dict] = mapped_column(
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

    template: Mapped["FocusTemplate"] = relationship(  # noqa: F821
        "FocusTemplate", back_populates="compositions"
    )

    def __repr__(self) -> str:
        return (
            f"<FocusComposition(id={self.id}, "
            f"tenant_id={self.tenant_id}, "
            f"template_id={self.inherits_from_template_id}, "
            f"version={self.version}, is_active={self.is_active})>"
        )
