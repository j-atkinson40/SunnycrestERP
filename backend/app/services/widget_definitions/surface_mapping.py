"""Cross-surface compatibility mapping table (WB-8 Lock 3a).

Two parallel surface vocabularies coexist in the widget substrate
(see `docs/investigations/2026-05-24-widget-builder-variants.md`
Area 4):

  • `WidgetSurface` (7 values) on `widget_definitions.supported_surfaces`
    — declares WHERE the widget can render: pulse_grid, focus_canvas,
    focus_stack, spaces_pin, floating_tablet, dashboard_grid,
    peek_inline.
  • `TargetSurface` (3 values) on
    `composition_blob.variants[].target_surface` — declares the
    AUTHORING-time canvas a given variant is composed against:
    focus_canvas, page_canvas, palette_preview.

The two were authored independently (Phase W-1 / WB-1). Lock 3a
introduces this mapping table as the canonical cross-vocabulary
substrate. Frontend mirror lives at
`frontend/src/lib/widget-builder/types/surface-mapping.ts` — same
constants + helpers. Symmetry MUST be preserved.

The mapping is intentionally narrow at Phase 1 (focus_canvas /
page_canvas / palette_preview cover the canonical cases). Surfaces
that don't appear in `TargetSurface` (spaces_pin, peek_inline,
floating_tablet) are handled via the "variant_id='glance'"
convention — a Glance variant authored against focus_canvas
target renders correctly at spaces_pin in production. The Lock
3a.2 + 3a.3 rules enforce the surface-variant requirements
(spaces_pin → Glance variant required; focus_canvas → Brief
variant required) at the validator level.

Phase 1 compatibility matrix (TargetSurface → allowed/warned
status):

  • focus_canvas, page_canvas — allow ALL 9 atom_kinds.
  • palette_preview — warn on repeater_atom + button (preview
    surfaces don't typically iterate or dispatch).

Behavior of `check_atom_surface_compat`:
  • Returns "allowed" when the atom_kind is unrestricted for the
    given target_surface.
  • Returns "warned" when the combination is permitted but flagged
    as non-canonical (authoring-time warning chip; not Publish-
    blocking by itself).
"""
from __future__ import annotations

from typing import Dict, FrozenSet, Literal

# Stay in sync with `widget_composition.TargetSurface` Literal.
_TARGET_SURFACES: FrozenSet[str] = frozenset({
    "focus_canvas",
    "page_canvas",
    "palette_preview",
})

# Stay in sync with the 9 atom_types in `widget_composition.AtomType`.
_ATOM_KINDS: FrozenSet[str] = frozenset({
    "text_label",
    "value_display",
    "icon",
    "status_badge",
    "divider",
    "button",
    "image",
    "conditional_container",
    "repeater_atom",
})

# Cross-vocabulary mapping (Lock 3a): TargetSurface ↔ the set of
# top-level WidgetSurface entries that a variant authored for this
# canvas may legitimately render against.
TARGET_TO_WIDGET_SURFACES: Dict[str, FrozenSet[str]] = {
    # focus_canvas + focus_stack (mobile shape of canvas) — both
    # focus-class surfaces inherit the focus_canvas variant.
    "focus_canvas": frozenset({"focus_canvas", "focus_stack"}),
    # page_canvas — the dashboard/pulse grid surfaces.
    "page_canvas": frozenset({"pulse_grid", "dashboard_grid"}),
    # palette_preview — unscoped preview surface. Compatible with
    # every WidgetSurface in the catalog (used by Focus Builder
    # palette + WB canvas preview itself).
    "palette_preview": frozenset({
        "pulse_grid",
        "focus_canvas",
        "focus_stack",
        "spaces_pin",
        "floating_tablet",
        "dashboard_grid",
        "peek_inline",
    }),
}


# Phase 1 atom_kind compatibility matrix. Each target_surface declares
# the set of atom_kinds flagged as "warned" — i.e. permitted but
# non-canonical. Atom_kinds NOT in the warned set are "allowed".
_WARNED_ATOM_KINDS_BY_TARGET: Dict[str, FrozenSet[str]] = {
    "focus_canvas": frozenset(),
    "page_canvas": frozenset(),
    # palette_preview is a static preview surface; iterating
    # (repeater_atom) and dispatching (button) at a preview surface
    # is non-canonical though not strictly invalid.
    "palette_preview": frozenset({"repeater_atom", "button"}),
}


AtomSurfaceCompat = Literal["allowed", "warned"]


def check_atom_surface_compat(
    atom_kind: str,
    target_surface: str,
) -> AtomSurfaceCompat:
    """Return the compatibility status for (atom_kind, target_surface).

    Unknown atom_kind or unknown target_surface yields "allowed" — the
    matrix is forward-compatible (atom catalog growth post-WB-8 should
    not break authoring).
    """
    if target_surface not in _TARGET_SURFACES:
        return "allowed"
    if atom_kind not in _ATOM_KINDS:
        return "allowed"
    warned = _WARNED_ATOM_KINDS_BY_TARGET.get(target_surface, frozenset())
    return "warned" if atom_kind in warned else "allowed"


def variant_target_compatible_with_supported_surfaces(
    target_surface: str,
    supported_surfaces: list[str] | tuple[str, ...] | frozenset[str],
) -> bool:
    """Lock 3a cross-vocabulary check.

    True when the given variant's target_surface maps to at least one
    surface in the widget's top-level supported_surfaces. Used at draft
    (authoring-time warning chip) AND at Publish (blocking error).

    Unknown target_surface → True (forward-compat with future canvases).
    """
    if target_surface not in TARGET_TO_WIDGET_SURFACES:
        return True
    allowed = TARGET_TO_WIDGET_SURFACES[target_surface]
    return any(s in allowed for s in supported_surfaces)


__all__ = [
    "AtomSurfaceCompat",
    "TARGET_TO_WIDGET_SURFACES",
    "check_atom_surface_compat",
    "variant_target_compatible_with_supported_surfaces",
]
