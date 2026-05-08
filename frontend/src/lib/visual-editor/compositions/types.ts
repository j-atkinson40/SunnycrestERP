/**
 * Focus composition types — frontend mirror of the backend's
 * `focus_compositions.rows` shape (R-3.0).
 *
 * R-3.0 — composition is a sequence of rows. Each row declares its
 * own column_count (1-12) and carries its own placements with
 * 0-indexed `starting_column` + `column_span`.
 *
 * Pre-R-3.0 flat-`placements` shape is removed from the TypeScript
 * surface. The DB columns remain temporarily (one-release grace);
 * R-3.2 drops them. Application code post-R-3.0 reads/writes only
 * `rows`.
 */
import type { ComponentKind } from "@/lib/visual-editor/registry"


/** Display affordances per placement (cosmetic — render-time only). */
export interface PlacementDisplayConfig {
  show_header?: boolean
  show_border?: boolean
  z_index?: number
}


/** A single placement within a row.
 *
 * `starting_column` is **0-indexed** (R-3.0 API change from R-2.x's
 * 1-indexed `column_start`). `column_span` is in cells.
 *
 * `nested_rows` is the bounded-nesting extension point — null in
 * R-3.0; future activation lands without schema migration.
 */
export interface Placement {
  placement_id: string
  component_kind: ComponentKind
  component_name: string
  /** 0-indexed; in [0, row.column_count - 1]. */
  starting_column: number
  /** In cells; starting_column + column_span <= row.column_count. */
  column_span: number
  prop_overrides: Record<string, unknown>
  display_config: PlacementDisplayConfig
  /** Bounded-nesting extension point. Null in R-3.0. */
  nested_rows: CompositionRow[] | null
  /** R-5.1 — used by edge-panel user overrides to indicate which row
   * this placement should be appended to when arriving via
   * `additional_placements`. NOT a persisted placement attribute on
   * tenant-default rows; the resolver strips it before placing the
   * placement into the row's `placements` array. Optional; defaults
   * to 0 (first row). */
  row_index?: number
}


/** A single row within a composition.
 *
 * `column_count` is the row-local grid (1-12). Placements within
 * this row are positioned via 0-indexed `starting_column` and span
 * up to `column_count` cells.
 *
 * `column_widths` is the Variant B extension point — null in R-3.0;
 * future activation enables non-equal-width column distributions.
 *
 * `nested_rows` is the bounded-nesting extension point — null in
 * R-3.0; future activation lets a row contain sub-rows.
 *
 * `row_height` content-driven default ("auto") OR explicit pixel
 * height. The renderer respects either; gestures clamp accordingly.
 */
export interface CompositionRow {
  row_id: string
  column_count: number
  row_height: "auto" | number
  /** Variant B extension point. Null in R-3.0. */
  column_widths: number[] | null
  /** Bounded-nesting extension point. Null in R-3.0. */
  nested_rows: CompositionRow[] | null
  placements: Placement[]
}


/** Canvas-level cosmetic settings — gap between rows, background
 * treatment, padding. Per-row column_count + row_height live on each
 * row record post-R-3.0.
 *
 * R-3.2 removed the deprecated `total_columns`, `row_height`
 * (canvas-level), and `responsive_breakpoints` optional fields. They
 * had no consumers and existed in no seeded DB row; declaring them
 * caused future code to typo `canvas_config.row_height` when it meant
 * the canonical per-row `row.row_height`. Drop is type-only —
 * removing them surfaces typos as TS errors.
 */
export interface CanvasConfig {
  /** Pixels between rows. */
  gap_size?: number
  background_treatment?: string
  padding?: { token?: string }
}


export interface ResolvedComposition {
  focus_type: string
  vertical: string | null
  tenant_id: string | null
  source: "platform_default" | "vertical_default" | "tenant_override" | null
  source_id: string | null
  source_version: number | null
  rows: CompositionRow[]
  canvas_config: CanvasConfig
}


export interface CompositionRecord {
  id: string
  scope: "platform_default" | "vertical_default" | "tenant_override"
  vertical: string | null
  tenant_id: string | null
  focus_type: string
  rows: CompositionRow[]
  canvas_config: CanvasConfig
  version: number
  is_active: boolean
  created_at: string
  updated_at: string
  created_by: string | null
  updated_by: string | null
}
