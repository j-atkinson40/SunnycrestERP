/**
 * Canonical R-3.0 composition fixtures.
 *
 * These four fixtures cover the composition shapes the renderer + future
 * editor must handle correctly. New tests for either the runtime path
 * or the editor canvas path should pull from this module rather than
 * minting bespoke shapes inline — keeps the contract surface stable
 * across tests + visible in one place.
 *
 * Shapes:
 *  1. one_row_one_placement_full_width — minimal canonical row
 *  2. one_row_four_equal_placements    — 4-up uniform row
 *  3. two_rows_kanban_plus_widgets     — 4-col row (3-of-4 + 1) + 4-up row
 *  4. three_rows_mixed_column_counts   — 1, 4, 12 (stress: per-row variation)
 *
 * IDs are stable across test runs so assertions can match by id.
 */
import type { ResolvedComposition } from "@/lib/visual-editor/compositions/types"


function baseComposition(
  overrides: Partial<ResolvedComposition>,
): ResolvedComposition {
  return {
    focus_type: "scheduling",
    vertical: "funeral_home",
    tenant_id: null,
    source: "vertical_default",
    source_id: "fixture-id",
    source_version: 1,
    rows: [],
    canvas_config: {
      gap_size: 12,
      background_treatment: "surface-base",
    },
    ...overrides,
  }
}


/** Fixture 1 — one row, one placement spanning the full row.
 *
 * Smallest non-empty composition. Verifies the basic row → placement
 * dispatch path.
 */
export const oneRowOnePlacementFullWidth: ResolvedComposition = baseComposition(
  {
    rows: [
      {
        row_id: "row-solo",
        column_count: 1,
        row_height: 192,
        column_widths: null,
        nested_rows: null,
        placements: [
          {
            placement_id: "today",
            component_kind: "widget",
            component_name: "today",
            starting_column: 0,
            column_span: 1,
            prop_overrides: {},
            display_config: { show_header: true, show_border: true },
            nested_rows: null,
          },
        ],
      },
    ],
  },
)


/** Fixture 2 — one row, four equal placements at column_count=4.
 *
 * Uniform 4-up row; verifies per-row column_count drives the inner
 * CSS Grid + 0-indexed starting_column translates correctly.
 */
export const oneRowFourEqualPlacements: ResolvedComposition = baseComposition({
  rows: [
    {
      row_id: "row-quad",
      column_count: 4,
      row_height: 240,
      column_widths: null,
      nested_rows: null,
      placements: [
        {
          placement_id: "today",
          component_kind: "widget",
          component_name: "today",
          starting_column: 0,
          column_span: 1,
          prop_overrides: {},
          display_config: { show_header: true, show_border: true },
          nested_rows: null,
        },
        {
          placement_id: "recent",
          component_kind: "widget",
          component_name: "recent_activity",
          starting_column: 1,
          column_span: 1,
          prop_overrides: {},
          display_config: { show_header: true, show_border: true },
          nested_rows: null,
        },
        {
          placement_id: "anomalies",
          component_kind: "widget",
          component_name: "anomalies",
          starting_column: 2,
          column_span: 1,
          prop_overrides: {},
          display_config: { show_header: true, show_border: true },
          nested_rows: null,
        },
        {
          placement_id: "operator",
          component_kind: "widget",
          component_name: "operator-profile",
          starting_column: 3,
          column_span: 1,
          prop_overrides: {},
          display_config: { show_header: true, show_border: true },
          nested_rows: null,
        },
      ],
    },
  ],
})


/** Fixture 3 — two rows: kanban (3-of-4 + 1) + 4 widgets.
 *
 * Canonical operational shape per the R-3 investigation report:
 * top row is a 4-column grid where the kanban widget spans 3 cells +
 * a single supporting widget at column 4; bottom row is a 4-up
 * widget rail. Stresses cross-row composition where row[0] and row[1]
 * have the same column_count but different placement counts.
 */
export const twoRowsKanbanPlusWidgets: ResolvedComposition = baseComposition({
  rows: [
    {
      row_id: "row-kanban",
      column_count: 4,
      row_height: 480,
      column_widths: null,
      nested_rows: null,
      placements: [
        {
          placement_id: "vault-schedule",
          component_kind: "widget",
          component_name: "vault_schedule",
          starting_column: 0,
          column_span: 3,
          prop_overrides: {},
          display_config: { show_header: true, show_border: true },
          nested_rows: null,
        },
        {
          placement_id: "today",
          component_kind: "widget",
          component_name: "today",
          starting_column: 3,
          column_span: 1,
          prop_overrides: {},
          display_config: { show_header: true, show_border: true },
          nested_rows: null,
        },
      ],
    },
    {
      row_id: "row-widgets",
      column_count: 4,
      row_height: 200,
      column_widths: null,
      nested_rows: null,
      placements: [
        {
          placement_id: "recent",
          component_kind: "widget",
          component_name: "recent_activity",
          starting_column: 0,
          column_span: 1,
          prop_overrides: {},
          display_config: { show_header: true, show_border: true },
          nested_rows: null,
        },
        {
          placement_id: "anomalies",
          component_kind: "widget",
          component_name: "anomalies",
          starting_column: 1,
          column_span: 1,
          prop_overrides: {},
          display_config: { show_header: true, show_border: true },
          nested_rows: null,
        },
        {
          placement_id: "operator",
          component_kind: "widget",
          component_name: "operator-profile",
          starting_column: 2,
          column_span: 1,
          prop_overrides: {},
          display_config: { show_header: true, show_border: true },
          nested_rows: null,
        },
        {
          placement_id: "anomalies-2",
          component_kind: "widget",
          component_name: "anomalies",
          starting_column: 3,
          column_span: 1,
          prop_overrides: {},
          display_config: { show_header: true, show_border: true },
          nested_rows: null,
        },
      ],
    },
  ],
})


/** Fixture 4 — three rows with column_counts 1, 4, 12.
 *
 * Stress fixture: each row picks its own column_count. Verifies the
 * renderer doesn't bleed column-count semantics across rows + that
 * 0-indexed starting_column scales correctly across grids of
 * different sizes.
 */
export const threeRowsMixedColumnCounts: ResolvedComposition = baseComposition({
  rows: [
    {
      row_id: "row-1col",
      column_count: 1,
      row_height: 100,
      column_widths: null,
      nested_rows: null,
      placements: [
        {
          placement_id: "today",
          component_kind: "widget",
          component_name: "today",
          starting_column: 0,
          column_span: 1,
          prop_overrides: {},
          display_config: { show_header: true, show_border: true },
          nested_rows: null,
        },
      ],
    },
    {
      row_id: "row-4col",
      column_count: 4,
      row_height: 200,
      column_widths: null,
      nested_rows: null,
      placements: [
        {
          placement_id: "recent",
          component_kind: "widget",
          component_name: "recent_activity",
          starting_column: 0,
          column_span: 2,
          prop_overrides: {},
          display_config: { show_header: true, show_border: true },
          nested_rows: null,
        },
        {
          placement_id: "anomalies",
          component_kind: "widget",
          component_name: "anomalies",
          starting_column: 2,
          column_span: 2,
          prop_overrides: {},
          display_config: { show_header: true, show_border: true },
          nested_rows: null,
        },
      ],
    },
    {
      row_id: "row-12col",
      column_count: 12,
      row_height: 300,
      column_widths: null,
      nested_rows: null,
      placements: [
        {
          placement_id: "vault-schedule",
          component_kind: "widget",
          component_name: "vault_schedule",
          starting_column: 0,
          column_span: 8,
          prop_overrides: {},
          display_config: { show_header: true, show_border: true },
          nested_rows: null,
        },
        {
          placement_id: "operator",
          component_kind: "widget",
          component_name: "operator-profile",
          starting_column: 8,
          column_span: 4,
          prop_overrides: {},
          display_config: { show_header: true, show_border: true },
          nested_rows: null,
        },
      ],
    },
  ],
})


export const ALL_FIXTURES = {
  oneRowOnePlacementFullWidth,
  oneRowFourEqualPlacements,
  twoRowsKanbanPlusWidgets,
  threeRowsMixedColumnCounts,
} as const
