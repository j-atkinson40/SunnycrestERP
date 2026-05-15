"""FocusTemplate — Tier 2 of the Focus Template Inheritance chain (r96).

Platform-owned (`platform_default`) or per-vertical-default
(`vertical_default`) Focus templates. Each template inherits a single
`FocusCore` and arranges accessory widgets/placements around it on
the composition canvas.

Inheritance chain:

    focus_cores (Tier 1)
        ← focus_templates (Tier 2)            ← THIS FILE
            ← focus_compositions (Tier 3, per-tenant delta)

Scope rules (CHECK-enforced + service-layer-validated in sub-arc B):
  - `scope='platform_default'` ⇒ `vertical IS NULL`
  - `scope='vertical_default'` ⇒ `vertical IS NOT NULL`

`vertical` FKs to `verticals.slug` per the verticals-lite convention
(r95). Tenant-tier (Tier 3) lives in `focus_compositions`, NOT in
this table.

`rows` JSONB shape (informational; sub-arc B service layer
validates):

    [
        {
            "row_id": str,                       # UUID; stable across edits
            "column_count": int 1..12,
            "row_height": "auto" | int,
            "column_widths": list[float] | None,
            "placements": [
                {
                    "placement_id": str,         # unique within template
                    "is_core": bool,             # core-as-placement discriminator
                    "component_kind": str,
                    "component_name": str,
                    "starting_column": int 0-indexed,
                    "column_span": int 1..column_count,
                    "prop_overrides": dict,
                    "display_config": {
                        "show_header": bool?,
                        "show_border": bool?,
                        "z_index": int?,
                    },
                }
            ]
        }
    ]

Exactly one placement per template has `is_core=true`; its
`component_kind` + `component_name` must match the inherited
core's `registered_component_kind` + `registered_component_name`.
Validation lives in sub-arc B's service layer, not in this model.

`canvas_config` carries cosmetic canvas-level settings (gap_size,
background_treatment, padding). Mirrors the same field on
`FocusCore` and is overlaid by `FocusComposition.canvas_config_overrides`.

Forward-compat: `inherits_from_core_version` ships now so a future
sub-arc can introduce versioned-snapshot inheritance without
schema migration. The v1 resolver (sub-arc B) ignores the version
and uses live-pointer semantics.

Versioning: each save deactivates the prior active row + inserts a
new active row with version + 1. Partial unique index on
`is_active=true` enforces "at most one active row per
(scope, vertical, template_slug) tuple."

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
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# Canonical scope values for FocusTemplate. Tenant-tier lives in
# focus_compositions, not in this table — that's why there's no
# `tenant_override` value here.
SCOPE_PLATFORM_DEFAULT = "platform_default"
SCOPE_VERTICAL_DEFAULT = "vertical_default"


class FocusTemplate(Base):
    """Tier 2 — platform_default or vertical_default Focus template
    inheriting a single FocusCore.
    """

    __tablename__ = "focus_templates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    vertical: Mapped[str | None] = mapped_column(String(32), nullable=True)
    template_slug: Mapped[str] = mapped_column(String(96), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)

    # Tier 1 reference + forward-compat version pointer.
    inherits_from_core_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("focus_cores.id", ondelete="RESTRICT"),
        nullable=False,
    )
    inherits_from_core_version: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    rows: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    canvas_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    # Sub-arc B-3 (r98): Tier 2 chrome overrides. Field-level cascade
    # over `focus_cores.chrome`. Each present key overrides Tier 1;
    # absent keys inherit. Explicit None values DO override (key-
    # presence check). Service-layer validator:
    # chrome_validation.validate_chrome_blob.
    chrome_overrides: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    # Sub-arc B-4 (r100): Tier 2 page-background substrate. Distinct
    # from chrome (per-surface composition) — substrate is the Focus-
    # level atmospheric backdrop (warm-gradient page background
    # behind core + accessories). Tier 3 (focus_compositions.deltas
    # key `substrate_overrides`) overrides field-by-field; Tier 1
    # cores stay substrate-free by design. Service-layer validator:
    # substrate_validation.validate_substrate_blob.
    substrate: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    # Sub-arc B-5 (r101): Tier 2 typography defaults (heading + body
    # weights + color tokens). Distinct from chrome (per-surface
    # composition) and substrate (atmospheric backdrop). Tier 3
    # (focus_compositions.deltas key `typography_overrides`) overrides
    # field-by-field; Tier 1 cores stay typography-free by design.
    # Service-layer validator: typography_validation.
    # validate_typography_blob.
    typography: Mapped[dict] = mapped_column(
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

    # Sub-arc C-2.1.2 (r103): edit-session tracking, mirroring r102's
    # focus_cores columns. Updates carrying `edit_session_id` that
    # match the row's `last_edit_session_id` AND fall within 5 minutes
    # of `last_edit_session_at` mutate in place (no version bump). All
    # other updates version-bump per B-1. Both fields NULL on rows
    # pre-r103 + on rows that have never been touched by a session-
    # aware writer.
    last_edit_session_id: Mapped[str | None] = mapped_column(
        PGUUID(as_uuid=False), nullable=True
    )
    last_edit_session_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    core: Mapped["FocusCore"] = relationship(  # noqa: F821
        "FocusCore", back_populates="templates"
    )
    compositions: Mapped[list["FocusComposition"]] = relationship(  # noqa: F821
        "FocusComposition", back_populates="template"
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["vertical"],
            ["verticals.slug"],
            name="fk_focus_templates_vertical",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "scope IN ('platform_default', 'vertical_default')",
            name="ck_focus_templates_scope",
        ),
        CheckConstraint(
            "("
            "(scope = 'platform_default' AND vertical IS NULL)"
            " OR (scope = 'vertical_default' AND vertical IS NOT NULL)"
            ")",
            name="ck_focus_templates_scope_vertical_correlation",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<FocusTemplate(id={self.id}, slug={self.template_slug}, "
            f"scope={self.scope}, vertical={self.vertical}, "
            f"version={self.version}, is_active={self.is_active})>"
        )
