"""WidgetDefinition — platform-wide widget catalog.

Each row describes a widget that can appear on one or more surfaces.
Visibility is gated via the 5-axis filter (Widget Library §12.4):
permission + module + extension + vertical + product_line.

See `DESIGN_LANGUAGE.md` Section 12 for the canonical Widget Library
Architecture spec. Phase W-1 added the foundation. Phase W-3a (April
2026) added the 5th axis (`required_product_line`) per Product Line +
Operating Mode canon — see [BRIDGEABLE_MASTER §5.2.1](../../BRIDGEABLE_MASTER.md)
for the canonical Extension-vs-ProductLine distinction:
**Extension = how a line gets installed (or not — vault is built-in).
Product line = the operational reality once installed.**

Phase W-1 columns:
  • variants (JSONB) — per Section 12.3 / 12.10 per-widget variant
    declarations (Glance / Brief / Detail / Deep)
  • default_variant_id (str) — references one of the variants
  • required_vertical (JSONB array | "*") — Section 12.4 axis 4
  • supported_surfaces (JSONB) — Section 12.5 per-surface
    composition rules
  • default_surfaces (JSONB) — surfaces where widget seeds in
    default layouts (subset of supported_surfaces)
  • intelligence_keywords (JSONB) — Section 12 phase W-5 prep

Phase W-3a column:
  • required_product_line (JSONB array | "*") — Section 12.4 axis 5.
    JSONB array of TenantProductLine.line_key values (e.g.
    ["vault"]) or ["*"] for cross-line (default).

Legacy columns kept for one release window per Decision 10:
  • required_preset — DEPRECATED. The bug at widget_service.py:304
    (reading non-existent Company.preset) was fixed by switching the
    filter to `required_vertical` consuming Company.vertical. This
    column is no longer read by the filter; awaiting Phase W-5
    cleanup migration to drop.
  • default_size + supported_sizes — kept while existing dashboard
    widgets continue rendering at their current sizes. New variant-
    aware consumers read `variants[].grid_size` instead.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WidgetDefinition(Base):
    __tablename__ = "widget_definitions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    widget_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Page contexts this widget can appear on (JSON array of slugs)
    page_contexts: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Legacy size constraints (kept for one release window per
    # Decision 10; new consumers read variants[].grid_size).
    default_size: Mapped[str] = mapped_column(String(10), default="1x1")
    min_size: Mapped[str] = mapped_column(String(10), default="1x1")
    max_size: Mapped[str] = mapped_column(String(10), default="4x4")
    supported_sizes: Mapped[list] = mapped_column(JSONB, default=lambda: ["1x1"])

    # Visibility rules — 4-axis filter per Section 12.4.
    required_extension: Mapped[str | None] = mapped_column(String(100), nullable=True)
    required_permission: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # DEPRECATED — kept for one release window per Decision 10.
    # Previously consumed by a broken filter (Company.preset doesn't
    # exist on the model). Replaced by `required_vertical` below.
    required_preset: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Phase W-1 — Section 12.4 4-axis filter axis 4: vertical scoping.
    # JSONB array of vertical strings (e.g. ["funeral_home"]) or
    # ["*"] for cross-vertical (the default per Decision 9).
    required_vertical: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=lambda: ["*"]
    )

    # Phase W-3a — Section 12.4 5-axis filter axis 5: product line scoping.
    # JSONB array of TenantProductLine.line_key values (e.g. ["vault"]) or
    # ["*"] for cross-line (default). Per [BRIDGEABLE_MASTER §5.2.1](../../BRIDGEABLE_MASTER.md):
    # distinct from `required_extension` because vault is a baseline
    # product line that is NOT extension-gated, but vault widgets need
    # to scope to "vault product line activated for this tenant".
    # Filter resolves against TenantProductLine.line_key with
    # is_enabled=True; widget visible iff at least one of its declared
    # line_keys appears in the tenant's enabled set, OR the widget
    # declares ["*"].
    required_product_line: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=lambda: ["*"]
    )

    # Phase W-1 — Section 12.3 variant declarations.
    variants: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    default_variant_id: Mapped[str] = mapped_column(
        String(50), nullable=False, default="brief"
    )

    # Phase W-1 — Section 12.5 surface composition rules.
    # Surfaces: pulse_grid, focus_canvas, focus_stack, spaces_pin,
    # floating_tablet, dashboard_grid, peek_inline.
    supported_surfaces: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=lambda: ["dashboard_grid"]
    )
    default_surfaces: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=lambda: ["dashboard_grid"]
    )

    # Phase W-1 — Section 12 Phase W-5 prep (Intelligence variant
    # selection). Empty array now; populated as widgets ship.
    intelligence_keywords: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )

    # Defaults
    default_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    default_position: Mapped[int] = mapped_column(Integer, default=99)

    # Metadata
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # ── Widget Builder substrate (WB-1, May 2026) ─────────────────────
    #
    # Composition-driven widget shape per investigation Area 7 (Q-29
    # through Q-32). Existing hand-coded widget definitions carry
    # composition_blob = NULL + composition_version = NULL; the
    # ComposedWidget runtime renderer (ships in WB-2/3) walks the blob
    # at render time for composed widgets, while legacy widgets stay
    # code-rendered via the existing widget renderer registry.
    #
    # CHECK constraint at the DB level (r105 migration) enforces that
    # composition_blob + composition_version are jointly present or
    # jointly absent. Pydantic schema in `app/schemas/widget_composition.py`
    # validates the blob shape. Frontend mirror at
    # `frontend/src/lib/widget-builder/types/composition-blob.ts`.

    composition_blob: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    composition_version: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    # Tier scope per Q-38: Tier-1 ('platform') + Tier-2 ('vertical').
    # Tier-3 lives at placement level via existing prop_overrides
    # (focus_compositions.deltas) — no DB column needed here. Existing
    # rows backfilled to 'platform' by r105.
    tier_scope: Mapped[str] = mapped_column(
        String(20), nullable=False, default="platform"
    )

    # Session-aware versioning per Q-31, mirroring r102/r103 focus
    # cores/templates pattern. The auto-save authoring hook (WB-3)
    # consults these fields to decide mutate-in-place (same session +
    # within window) vs version-bump (new session OR window elapsed).
    last_edit_session_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), nullable=True
    )
    last_edit_session_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_edit_session_actor_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), nullable=True
    )

    # WB-4a (r106) — load-bearing for the Area 2 "draft-then-publish"
    # lock. `composition_blob` is the DRAFT (auto-saved per-tick by the
    # Widget Builder shell, 200 ms debounce). `published_composition_blob`
    # is the LIVE render surface; mutated ONLY on explicit Publish.
    # Tenant render paths read published first, fall back to draft ONLY
    # when published is NULL AND draft is non-NULL (legacy r105-backfill
    # rows). r106 upgrade backfills existing composed widgets so they
    # keep rendering immediately on deploy.
    #
    # CHECK constraint (`ck_widget_definitions_published_requires_draft`):
    #   (published IS NULL) OR (composition_blob IS NOT NULL)
    # i.e., can't publish without a draft.
    published_composition_blob: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
