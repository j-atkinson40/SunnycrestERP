"""EdgePanelComposition — Tier 3 of the Edge Panel Substrate (r97).

Per-tenant lazy-fork delta over a chosen `EdgePanelTemplate`. A row
exists for a tenant only after their first edit; pre-edit, the
resolver returns the bare Tier 2 template (with optional User-layer
overrides applied).

Inheritance chain:

    edge_panel_templates (Tier 2)
        ← edge_panel_compositions (Tier 3)         ← THIS FILE

deltas shape (informational; service-layer validates):

    {
        "hidden_page_ids": [str],
        "additional_pages": [
            { "page_id": str, "name": str, "rows": [...],
              "canvas_config": dict }
        ],
        "page_order": [str],
        "page_overrides": {
            <page_id>: {
                "hidden_placement_ids": [str],
                "additional_placements": [
                    { "placement_id": str,
                      "component_kind": str,
                      "component_name": str,
                      "row_index": int,
                      "starting_column": int,
                      "column_span": int,
                      "prop_overrides": dict,
                      "display_config": dict }
                ],
                "placement_geometry_overrides": {
                    <placement_id>: {
                        "starting_column": int,
                        "column_span": int
                    }
                },
                "placement_order": [str],
                "canvas_config": dict        # optional, full-replace
            }
        }
    }

The vocabulary is recursive (page-keyed outer, placement-keyed inner)
and matches the R-5.0 + R-5.1 User-preference shape verbatim — plus
the Tier 3 addition of per-page `placement_geometry_overrides`. The
resolver reuses `_apply_placement_overrides` from the legacy
composition_service for per-page placement-level merges.

`canvas_config_overrides` carries top-level cosmetic overrides on top
of the template's `canvas_config`. Per-page canvas overrides live
inside `deltas.page_overrides[<page_id>].canvas_config`.

Forward-compat: `inherits_from_template_version` ships now per
Option B; v1 resolver ignores it (live cascade). Versioned cascade
lands additively at the service layer.

Versioning: each save deactivates the prior active row + inserts a
new active row with version + 1. Partial unique index on
`is_active=true` enforces "at most one active composition per
(tenant_id, inherits_from_template_id) tuple."

Service layer + endpoints + resolver land in companion B-1.5
modules. This file is data-shape only.
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


class EdgePanelComposition(Base):
    """Tier 3 — per-tenant delta over a chosen EdgePanelTemplate."""

    __tablename__ = "edge_panel_compositions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )

    inherits_from_template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("edge_panel_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    inherits_from_template_version: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    deltas: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
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

    template: Mapped["EdgePanelTemplate"] = relationship(  # noqa: F821
        "EdgePanelTemplate", back_populates="compositions"
    )

    def __repr__(self) -> str:
        return (
            f"<EdgePanelComposition(id={self.id}, "
            f"tenant_id={self.tenant_id}, "
            f"template_id={self.inherits_from_template_id}, "
            f"version={self.version}, is_active={self.is_active})>"
        )
