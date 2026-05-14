"""EdgePanelTemplate — Tier 2 of the Edge Panel Substrate (r97).

Platform-owned (`platform_default`) or per-vertical-default
(`vertical_default`) edge-panel templates. Edge-panels are pure
composition; there is no Tier 1 core analogous to FocusCore.

Inheritance chain:

    edge_panel_templates (Tier 2)            ← THIS FILE
        ← edge_panel_compositions (Tier 3, per-tenant delta)

Scope rules (CHECK-enforced + service-layer-validated):
  - `scope='platform_default'` ⇒ `vertical IS NULL`
  - `scope='vertical_default'` ⇒ `vertical IS NOT NULL`

`vertical` FKs to `verticals.slug` per the verticals-lite convention
(r95).

`pages` JSONB shape (informational; service layer validates):

    [
        {
            "page_id": str,                  # unique within template
            "name": str,
            "rows": [                        # same shape as Focus rows
                {
                    "row_id": str,
                    "column_count": int 1..12,
                    "row_height": "auto" | int,
                    "column_widths": list | None,
                    "nested_rows": None,     # forward-compat
                    "placements": [
                        {
                            "placement_id": str,
                            "component_kind": str,
                            "component_name": str,
                            "starting_column": int,
                            "column_span": int,
                            "prop_overrides": dict,
                            "display_config": dict,
                            "nested_rows": None,
                        }
                    ]
                }
            ],
            "canvas_config": dict (optional)
        }
    ]

`canvas_config` carries top-level cosmetic settings (gap_size,
background_treatment, padding); per-page `canvas_config` lives inside
each page record. The resolver composes both layers in order:
template top-level → tenant overrides → page-level template →
page-level tenant overrides.

Forward-compat: NO `inherits_from_*` columns deliberately. Edge-panels
are two-tier. If a future Tier 1 ever lands (shared chrome / shells)
it's a new migration; carrying vestigial NULLable FKs forward is
worse than honest two-tier schema today.

Versioning: each save deactivates the prior active row + inserts a
new active row with version + 1. Partial unique index on
`is_active=true` enforces "at most one active row per
(scope, vertical, panel_key) tuple."

Audit-attribution: `created_by` / `updated_by` are unconstrained
VARCHAR(36) per the relocation-phase convention (PlatformUser ids
cannot satisfy `users.id` FK). Tenant-realm writes carry user_id;
platform-realm writes leave the column null.

Service layer + endpoints land in companion B-1.5 modules. This
file is data-shape only.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


SCOPE_PLATFORM_DEFAULT = "platform_default"
SCOPE_VERTICAL_DEFAULT = "vertical_default"


class EdgePanelTemplate(Base):
    """Tier 2 — platform_default or vertical_default edge-panel template."""

    __tablename__ = "edge_panel_templates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    vertical: Mapped[str | None] = mapped_column(String(32), nullable=True)
    panel_key: Mapped[str] = mapped_column(String(96), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)

    pages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
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

    compositions: Mapped[list["EdgePanelComposition"]] = relationship(  # noqa: F821
        "EdgePanelComposition", back_populates="template"
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["vertical"],
            ["verticals.slug"],
            name="fk_edge_panel_templates_vertical",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "scope IN ('platform_default', 'vertical_default')",
            name="ck_edge_panel_templates_scope",
        ),
        CheckConstraint(
            "("
            "(scope = 'platform_default' AND vertical IS NULL)"
            " OR (scope = 'vertical_default' AND vertical IS NOT NULL)"
            ")",
            name="ck_edge_panel_templates_scope_vertical_correlation",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<EdgePanelTemplate(id={self.id}, panel_key={self.panel_key}, "
            f"scope={self.scope}, vertical={self.vertical}, "
            f"version={self.version}, is_active={self.is_active})>"
        )
