/**
 * Cross-surface compatibility mapping (WB-8 Lock 3a) — TypeScript mirror
 * of `backend/app/services/widget_definitions/surface_mapping.py`.
 *
 * Symmetry MUST be preserved across the two files. Future surface
 * vocabulary changes update both sides in lockstep.
 *
 * Two parallel vocabularies (see investigation Area 4):
 *   • `WidgetSurface` (7 values) — top-level `supported_surfaces`.
 *     pulse_grid / focus_canvas / focus_stack / spaces_pin /
 *     floating_tablet / dashboard_grid / peek_inline.
 *   • `TargetSurface` (3 values) — per-variant `target_surface`.
 *     focus_canvas / page_canvas / palette_preview.
 *
 * The mapping table answers: "Given a variant authored against
 * TargetSurface X, which WidgetSurface values is it compatible with?"
 */

import type { AtomType, TargetSurface } from "./composition-blob"

export type WidgetSurface =
  | "pulse_grid"
  | "focus_canvas"
  | "focus_stack"
  | "spaces_pin"
  | "floating_tablet"
  | "dashboard_grid"
  | "peek_inline"

/** Lock 3a mapping: TargetSurface → set of compatible WidgetSurfaces. */
export const TARGET_TO_WIDGET_SURFACES: Record<
  TargetSurface,
  ReadonlySet<WidgetSurface>
> = {
  focus_canvas: new Set(["focus_canvas", "focus_stack"] as WidgetSurface[]),
  page_canvas: new Set(["pulse_grid", "dashboard_grid"] as WidgetSurface[]),
  palette_preview: new Set([
    "pulse_grid",
    "focus_canvas",
    "focus_stack",
    "spaces_pin",
    "floating_tablet",
    "dashboard_grid",
    "peek_inline",
  ] as WidgetSurface[]),
}

/** Phase 1 atom_kind compatibility status per target_surface. */
export type AtomSurfaceCompat = "allowed" | "warned"

const WARNED_ATOM_KINDS_BY_TARGET: Record<
  TargetSurface,
  ReadonlySet<AtomType>
> = {
  focus_canvas: new Set<AtomType>(),
  page_canvas: new Set<AtomType>(),
  palette_preview: new Set<AtomType>([
    "repeater_atom",
    "button",
  ] as AtomType[]),
}

const KNOWN_TARGET_SURFACES: ReadonlySet<string> = new Set<TargetSurface>([
  "focus_canvas",
  "page_canvas",
  "palette_preview",
])

/** Mirrors backend `check_atom_surface_compat`.
 *  Unknown atom_kind / target_surface → "allowed" (forward-compat). */
export function checkAtomSurfaceCompat(
  atom_kind: string,
  target_surface: string,
): AtomSurfaceCompat {
  if (!KNOWN_TARGET_SURFACES.has(target_surface)) return "allowed"
  const warned =
    WARNED_ATOM_KINDS_BY_TARGET[target_surface as TargetSurface]
  if (!warned) return "allowed"
  return warned.has(atom_kind as AtomType) ? "warned" : "allowed"
}

/** Mirrors backend
 *  `variant_target_compatible_with_supported_surfaces`. */
export function variantTargetCompatibleWithSupportedSurfaces(
  target_surface: string,
  supported_surfaces: ReadonlyArray<string>,
): boolean {
  if (!KNOWN_TARGET_SURFACES.has(target_surface)) return true
  const allowed =
    TARGET_TO_WIDGET_SURFACES[target_surface as TargetSurface]
  for (const s of supported_surfaces) {
    if (allowed.has(s as WidgetSurface)) return true
  }
  return false
}

/** WB-8 Lock 5b — canonical_dimensions surface-default fallback.
 *  Returns the canvas dimensions a variant should render against when
 *  its `canonical_dimensions` field is absent. Per the Phase 1
 *  research (R9 — operator-validation-sensitive constants). */
export function surfaceDefaultDimensions(
  target_surface: string,
): { width: number; height: number } {
  switch (target_surface) {
    case "focus_canvas":
      return { width: 800, height: 600 }
    case "page_canvas":
      return { width: 480, height: 320 }
    case "palette_preview":
      return { width: 320, height: 240 }
    default:
      // Forward-compat fallback for unknown surfaces.
      return { width: 480, height: 320 }
  }
}
