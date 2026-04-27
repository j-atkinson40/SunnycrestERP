"""WidgetDefinition — platform-wide widget catalog.

Each row describes a widget that can appear on one or more surfaces.
Visibility is gated via the 4-axis filter (Widget Library §12.4):
permission + module + extension + vertical.

See `DESIGN_LANGUAGE.md` Section 12 for the canonical Widget Library
Architecture spec. Phase W-1 of that spec adds:
  • variants (JSONB) — per Section 12.3 / 12.10 per-widget variant
    declarations (Glance / Brief / Detail / Deep)
  • default_variant_id (str) — references one of the variants
  • required_vertical (JSONB array | "*") — Section 12.4 4-axis
    filter axis 4
  • supported_surfaces (JSONB) — Section 12.5 per-surface
    composition rules
  • default_surfaces (JSONB) — surfaces where widget seeds in
    default layouts (subset of supported_surfaces)
  • intelligence_keywords (JSONB) — Section 12 phase W-5 prep

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
from sqlalchemy.dialects.postgresql import JSONB
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
