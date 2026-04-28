/**
 * computeLayerRowCount — Phase W-4a Step 6 Commit 2 (deduplicated).
 *
 * Walks a layer's items + simulates dense-flow tetris placement.
 * Returns the row count that layer consumes under the given column
 * count. Mirrors CSS Grid `grid-auto-flow: row dense`.
 *
 * Per DESIGN_LANGUAGE.md §13.3.4 Step 3 — `total_row_count` (sum of
 * per-layer row counts across populated layers) is the §13.3.4 Step 4
 * cell-height solver's denominator.
 *
 * Commit 1 had this duplicated across PulseSurface (for the aggregate
 * measurement) and PulseLayer (for the per-layer render). Commit 2
 * hoists to a single shared util — both consumers import from here.
 *
 * Algorithm: dense-flow placement, same as CSS Grid `grid-auto-flow:
 * row dense`. Returns 0 for empty layers.
 *
 * @param items - LayerContent.items array
 * @param filtered_ids - Set of dismissed item_ids to exclude
 * @param column_count - Tier-resolved column count (2/4/6 per §13.3.1)
 * @returns Row count consumed under tetris packing; 0 if empty.
 */

import type { LayerContent } from "@/types/pulse"


export function computeLayerRowCount(
  items: LayerContent["items"],
  filtered_ids: Set<string>,
  column_count: number,
): number {
  const visible = items.filter((it) => !filtered_ids.has(it.item_id))
  if (visible.length === 0) return 0

  // Bitmap of occupied cells, one row at a time. Grows as needed.
  const occupied: boolean[][] = []

  function ensureRow(row: number) {
    while (occupied.length <= row) {
      occupied.push(new Array(column_count).fill(false))
    }
  }

  function fits(
    start_row: number,
    start_col: number,
    cols: number,
    rows: number,
  ): boolean {
    if (start_col + cols > column_count) return false
    for (let r = start_row; r < start_row + rows; r++) {
      ensureRow(r)
      for (let c = start_col; c < start_col + cols; c++) {
        if (occupied[r][c]) return false
      }
    }
    return true
  }

  function place(
    start_row: number,
    start_col: number,
    cols: number,
    rows: number,
  ) {
    for (let r = start_row; r < start_row + rows; r++) {
      ensureRow(r)
      for (let c = start_col; c < start_col + cols; c++) {
        occupied[r][c] = true
      }
    }
  }

  // Dense flow: for each piece (in priority order — caller supplies
  // pre-sorted items), find the first cell (row-major) where its
  // span fits. Same algorithm CSS Grid `grid-auto-flow: row dense`
  // uses.
  for (const item of visible) {
    const cols = Math.min(Math.max(1, item.cols ?? 1), column_count)
    const rows = Math.max(1, item.rows ?? 1)

    let placed = false
    let r = 0
    while (!placed) {
      ensureRow(r)
      for (let c = 0; c <= column_count - cols; c++) {
        if (fits(r, c, cols, rows)) {
          place(r, c, cols, rows)
          placed = true
          break
        }
      }
      if (!placed) r++
    }
  }

  return occupied.length
}
