/**
 * Legacy editor types — pre-R-3.0 flat-placements + grid coords shape.
 *
 * R-3.0 ships the new rows-based composition data model end-to-end
 * (renderer + API + service + seeds). The legacy CompositionEditorPage +
 * InteractivePlacementCanvas + use-canvas-interactions stack uses
 * grid-coords-on-flat-placements (column_start / column_span / row_start
 * / row_span) for its drag-drop authoring model. Per the R-3.0 patch
 * contract, the legacy editor STAYS AS-IS in R-3.0 and only authors
 * single-row layouts (always column_count=12, single row).
 *
 * To keep the editor's internal model unchanged WITHOUT breaking the
 * load + save IO boundary against the new rows-shaped API, the editor
 * imports `LegacyPlacement` + `LegacyCanvasConfig` from this module +
 * translates at IO via the `flattenRowsToLegacy` / `wrapLegacyAsRows`
 * helpers below.
 *
 * **R-3.1 retires this module.** Once the editor learns to author
 * multi-row layouts natively against the new types, the legacy
 * shapes + helpers here delete cleanly.
 */
import type {
  CompositionRow,
  CanvasConfig,
} from "@/lib/visual-editor/compositions/types"
import type { ComponentKind } from "@/lib/visual-editor/registry"


/** Pre-R-3.0 grid-coords shape. */
export interface LegacyPlacementGrid {
  /** 1-indexed column start (1..12). */
  column_start: number
  /** Cells. starting + span <= 13. */
  column_span: number
  /** 1-indexed row start (1..N). */
  row_start: number
  /** Cells. */
  row_span: number
}


export interface LegacyPlacementDisplayConfig {
  show_header?: boolean
  show_border?: boolean
  z_index?: number
}


/** Pre-R-3.0 flat-placement shape (drag-drop editor's internal model). */
export interface LegacyPlacement {
  placement_id: string
  component_kind: ComponentKind
  component_name: string
  grid: LegacyPlacementGrid
  prop_overrides: Record<string, unknown>
  display_config: LegacyPlacementDisplayConfig
}


/** Pre-R-3.0 canvas_config shape. Carries `total_columns` + `row_height`
 * + `gap_size` + `background_treatment`. New `rows` model puts
 * `column_count` + `row_height` on each row record; canvas_config
 * keeps `gap_size` + `background_treatment`. The legacy editor uses
 * `total_columns` + `row_height` from canvas_config for its drag/grid
 * math; at IO we convert. */
export type LegacyCanvasConfig = CanvasConfig


/**
 * Flatten rows-shape composition data into the legacy editor's
 * internal model.
 *
 * Each row in the new shape maps to one or more LegacyPlacements at a
 * shared `row_start` value. Rows order in the array determines
 * `row_start`: rows[0] gets row_start=1, rows[1] gets row_start=Δ+1
 * where Δ is the sum of preceding rows' row_spans. Per-row row_height
 * is converted to row_span via the canvas-config row_height fallback.
 *
 * For R-3.0 the editor only AUTHORS single-row layouts, but it READS
 * multi-row layouts for back-compat (e.g., admin opens a composition
 * pre-authored elsewhere). Reading multi-row produces multiple
 * row_start values; saving collapses back to a single row regardless
 * (single-row authoring constraint).
 */
export function flattenRowsToLegacy(
  rows: CompositionRow[],
  canvas_config: CanvasConfig,
): { placements: LegacyPlacement[]; total_columns: number } {
  const defaultPxRowHeight = 64
  const editorRowHeightPx =
    typeof canvas_config.row_height === "number"
      ? canvas_config.row_height
      : defaultPxRowHeight

  // Determine the editor's display column_count: for back-compat with
  // multi-row layouts of differing column_counts, take the MAX
  // column_count across all rows (so wider rows fit in the editor's
  // single grid). Single-row authoring will always be column_count=12.
  const total_columns = Math.max(
    12,
    ...rows.map((r) => r.column_count),
  )

  const placements: LegacyPlacement[] = []
  let nextRowStart = 1

  for (const row of rows) {
    const rowSpan = Math.max(
      1,
      typeof row.row_height === "number"
        ? Math.ceil(row.row_height / editorRowHeightPx)
        : 3,
    )
    for (const p of row.placements) {
      placements.push({
        placement_id: p.placement_id,
        component_kind: p.component_kind,
        component_name: p.component_name,
        grid: {
          // 0-indexed → 1-indexed
          column_start: p.starting_column + 1,
          column_span: p.column_span,
          row_start: nextRowStart,
          row_span: rowSpan,
        },
        prop_overrides: p.prop_overrides,
        display_config: p.display_config,
      })
    }
    nextRowStart += rowSpan
  }

  return { placements, total_columns }
}


/**
 * Wrap legacy editor draft state into the canonical rows shape.
 *
 * R-3.0 single-row authoring constraint: the legacy editor always
 * produces ONE row at column_count=12 containing every placement.
 * Per-placement `row_start` + `row_span` from the editor are
 * preserved as **row_height** on the single output row (max of
 * placement row_spans × pixel-per-row), but the actual stacking
 * is collapsed — multi-row visual layouts authored in the legacy
 * editor will render as a single row in the new renderer.
 *
 * R-3.1 retires this single-row constraint by teaching the editor
 * to produce native multi-row output. Until then, admins authoring
 * compositions via this editor produce single-row outputs only.
 */
export function wrapLegacyAsRows(
  placements: LegacyPlacement[],
  canvas_config: CanvasConfig,
): CompositionRow[] {
  if (placements.length === 0) return []
  const total_columns = canvas_config.total_columns ?? 12
  const editorRowHeightPx =
    typeof canvas_config.row_height === "number"
      ? canvas_config.row_height
      : 64

  // Collapse: build a single row at column_count = total_columns.
  // Each placement keeps its starting_column (translated 1→0-indexed)
  // and column_span; row_start + row_span are dropped.
  // Row height = max placement row_span * editorRowHeightPx.
  const maxRowSpan = placements.reduce(
    (m, p) => Math.max(m, p.grid.row_start + p.grid.row_span - 1),
    1,
  )
  const rowHeightPx = maxRowSpan * editorRowHeightPx

  return [
    {
      // R-3.0 single-row: deterministic row_id so re-saves don't
      // churn the row_id in the persisted composition (idempotent
      // single-row identity for the legacy editor).
      row_id: "legacy-single-row",
      column_count: total_columns,
      row_height: rowHeightPx,
      column_widths: null,
      nested_rows: null,
      placements: placements.map((p) => ({
        placement_id: p.placement_id,
        component_kind: p.component_kind,
        component_name: p.component_name,
        // 1-indexed → 0-indexed
        starting_column: Math.max(0, p.grid.column_start - 1),
        column_span: p.grid.column_span,
        prop_overrides: p.prop_overrides,
        display_config: p.display_config,
        nested_rows: null,
      })),
    },
  ]
}
