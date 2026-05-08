"""Focus Composition model — canvas-based Focus layout composition
for the Admin Visual Editor (May 2026 composition layer; R-3.0
rows model June 2026).

A composition record specifies WHAT'S ON THE CANVAS via the `rows`
array, where each row declares its own column_count (1-12) and
contains its own placements.

Inheritance chain:
    platform_default
        + vertical_default(vertical)
            + tenant_override(tenant_id)

Resolution at READ time. Each Focus type has at most one active
composition per scope; absence falls back to the Focus's
hard-coded layout.

Row record shape (within `rows` JSONB array):
    {
        "row_id": str,               # UUID; stable across edits
        "column_count": int 1..12,
        "row_height": "auto" | int,  # pixels OR "auto" for content-driven
        "column_widths": list[float] | None,  # Variant B; null = equal-width
        "nested_rows": list[Row] | None,      # bounded-nesting extension; ignored in R-3.0
        "placements": [
            {
                "placement_id": str, # unique within composition
                "component_kind": str,
                "component_name": str,
                "starting_column": int 0-indexed,
                "column_span": int 1..column_count,
                "prop_overrides": dict,
                "display_config": {"show_header": bool?, "show_border": bool?, "z_index": int?},
                "nested_rows": list[Row] | None,  # bounded-nesting extension
            }
        ]
    }

R-3.2 (May 2026) dropped the legacy `placements` JSONB column via
r90_drop_legacy_composition_columns. The pre-R-3.0 flat-placements
shape was migrated to `rows` via r88's backfill helper before being
removed; rows-shape is the only canonical form post-R-3.2.

`canvas_config` JSONB column is retained — still actively used for
cosmetic settings.

Canvas config shape:
    {
        "gap_size": int,
        "background_treatment": str?,
        "padding": dict?,
    }
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


SCOPE_PLATFORM_DEFAULT = "platform_default"
SCOPE_VERTICAL_DEFAULT = "vertical_default"
SCOPE_TENANT_OVERRIDE = "tenant_override"

# R-5.0 — kind discriminator canonical values.
KIND_FOCUS = "focus"
KIND_EDGE_PANEL = "edge_panel"
CANONICAL_KINDS = (KIND_FOCUS, KIND_EDGE_PANEL)


class FocusComposition(Base):
    """Canvas-based Focus layout composition.

    Versioned via service layer (each save deactivates the prior
    active row + inserts a new active row with version + 1). One
    active row per (scope, vertical, tenant_id, focus_type) tuple
    enforced via partial unique index.
    """

    __tablename__ = "focus_compositions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    vertical: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
    )
    focus_type: Mapped[str] = mapped_column(String(96), nullable=False)

    # R-3.0 introduced `rows` as the source of truth; R-3.2 dropped
    # the legacy `placements` flat-array column. Each row declares
    # its own column_count + carries its own placements (0-indexed
    # starting_column + column_span). `canvas_config` carries cosmetic
    # settings only (gap_size, background_treatment, padding).
    rows: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    canvas_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    # R-5.0 (May 2026) — kind discriminator + pages JSONB.
    # `kind='focus'` rows: `pages` is NULL; `rows` carries the
    # single-page Focus accessory rail (existing semantics).
    # `kind='edge_panel'` rows: `rows` is `[]`; `pages` is a
    # non-empty list of `{page_id, name, rows: [...], canvas_config}`
    # records, each page being its own row-set. The column-name
    # `focus_type` carries panel slugs for kind=edge_panel — accepted
    # naming compromise; rename deferred per /tmp/r5_edge_panel_scope.md
    # Section 2.
    kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default="focus", server_default="focus"
    )
    pages: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=None)

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

    __table_args__ = (
        CheckConstraint(
            "scope IN ('platform_default', 'vertical_default', 'tenant_override')",
            name="ck_focus_compositions_scope",
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
            name="ck_focus_compositions_scope_keys",
        ),
        CheckConstraint(
            "kind IN ('focus', 'edge_panel')",
            name="ck_focus_compositions_kind",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<FocusComposition(id={self.id}, focus_type={self.focus_type}, "
            f"scope={self.scope}, version={self.version}, "
            f"is_active={self.is_active})>"
        )
