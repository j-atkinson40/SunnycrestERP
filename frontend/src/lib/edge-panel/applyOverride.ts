/**
 * R-5.1 — applyUserOverride: client-side mirror of the backend
 * `_apply_placement_overrides` + `resolve_edge_panel` override merge
 * semantics. Powers instant in-page preview on the
 * `/settings/edge-panel` settings surface (no round-trip per
 * keystroke).
 *
 * Parity contract: this helper MUST produce the same EdgePanelPage[]
 * shape that `GET /api/v1/edge-panel/resolve` would return for the
 * same `(tenant_default, user_override)` pair. Backend resolver lives
 * at `backend/app/services/focus_compositions/composition_service.py`
 * (`resolve_edge_panel` + `_apply_placement_overrides`). Drift between
 * the two is a defect — vitest tests assert per-step parity for the
 * canonical override types.
 *
 * Order of operations (matches backend):
 *   1. Per-page overrides:
 *      - If `rows` set → R-5.0 full-replace escape hatch (per-
 *        placement fields ignored for that page).
 *      - Else → R-5.1 per-placement overrides (drop hidden →
 *        append additional → reorder by placement_order).
 *      - `canvas_config` always replaces if set.
 *   2. Append `additional_pages` (personal pages). Personal pages
 *      with page_id colliding with a tenant page_id are silently
 *      dropped (tenant wins).
 *   3. Drop pages whose page_id is in `hidden_page_ids`.
 *   4. Reorder pages by `page_order_override` (UUIDs not mentioned
 *      keep relative position, appended at end).
 *
 * Orphan IDs (placement_id or page_id no longer present in the
 * tenant default) are silently dropped.
 */
import type {
  CompositionRow,
  Placement,
} from "@/lib/visual-editor/compositions/types"
import type {
  EdgePanelPage,
  EdgePanelUserOverride,
  ResolvedEdgePanel,
} from "./types"


/** Apply per-placement overrides to a single tenant page's rows.
 *  Pure — never mutates the input rows array. */
export function applyPlacementOverridesToRows(
  rows: CompositionRow[],
  override: {
    hidden_placement_ids?: string[]
    additional_placements?: Placement[]
    placement_order?: string[]
  },
): CompositionRow[] {
  const hiddenSet = new Set(override.hidden_placement_ids ?? [])

  // Step 1: deep-copy + filter hidden.
  const newRows: CompositionRow[] = rows.map((row) => ({
    ...row,
    placements: row.placements.filter((p) => !hiddenSet.has(p.placement_id)),
  }))

  // Step 2: append additional placements.
  for (const add of override.additional_placements ?? []) {
    if (!add || typeof add !== "object") continue
    // Strip row_index from the persisted shape — it's a placement
    // resolution hint, not a placement attribute.
    const { row_index, ...rest } = add
    const placement = rest as Placement
    let targetRowIdx = typeof row_index === "number" && row_index >= 0
      ? row_index
      : 0

    if (newRows.length === 0) {
      // Empty rows: synthesize a row containing this placement.
      newRows.push({
        row_id: `user-row-${placement.placement_id ?? "unknown"}`,
        column_count: 12,
        row_height: "auto",
        column_widths: null,
        nested_rows: null,
        placements: [placement],
      })
    } else {
      targetRowIdx = Math.min(targetRowIdx, newRows.length - 1)
      newRows[targetRowIdx] = {
        ...newRows[targetRowIdx],
        placements: [...newRows[targetRowIdx].placements, placement],
      }
    }
  }

  // Step 3: reorder placements within each row.
  const order = override.placement_order
  if (order && order.length > 0) {
    const orderIndex = new Map<string, number>()
    order.forEach((pid, i) => orderIndex.set(pid, i))

    for (let i = 0; i < newRows.length; i++) {
      const row = newRows[i]
      const placements = row.placements
      const inOrder: { p: Placement; idx: number }[] = []
      const remaining: Placement[] = []
      for (const p of placements) {
        const found = orderIndex.get(p.placement_id)
        if (found !== undefined) {
          inOrder.push({ p, idx: found })
        } else {
          remaining.push(p)
        }
      }
      inOrder.sort((a, b) => a.idx - b.idx)
      newRows[i] = {
        ...row,
        placements: [...inOrder.map((entry) => entry.p), ...remaining],
      }
    }
  }

  return newRows
}


/** Apply the full per-user override blob to a tenant default and
 *  return the effective EdgePanelPage[] (post-override). */
export function applyUserOverride(
  tenantDefault: ResolvedEdgePanel | null,
  override: EdgePanelUserOverride | null | undefined,
): EdgePanelPage[] {
  if (!tenantDefault) return []
  let pages: EdgePanelPage[] = [...(tenantDefault.pages ?? [])]
  if (!override) return pages

  // Step 1: per-page overrides.
  const pageOverrides = override.page_overrides ?? {}
  pages = pages.map((page) => {
    const ov = pageOverrides[page.page_id]
    if (!ov) return page

    let nextRows = page.rows
    if (ov.rows !== undefined) {
      // R-5.0 full-replace escape hatch.
      nextRows = ov.rows
    } else if (
      (ov.hidden_placement_ids && ov.hidden_placement_ids.length > 0) ||
      (ov.additional_placements && ov.additional_placements.length > 0) ||
      ov.placement_order !== undefined
    ) {
      nextRows = applyPlacementOverridesToRows(page.rows, ov)
    }

    return {
      ...page,
      rows: nextRows,
      canvas_config:
        ov.canvas_config !== undefined ? ov.canvas_config : page.canvas_config,
    }
  })

  // Step 2: append additional_pages (personal pages).
  const additional = override.additional_pages ?? []
  if (additional.length > 0) {
    const existing = new Set(pages.map((p) => p.page_id))
    for (const ap of additional) {
      if (!ap || typeof ap !== "object") continue
      if (existing.has(ap.page_id)) continue // tenant wins
      pages.push(ap)
      existing.add(ap.page_id)
    }
  }

  // Step 3: drop hidden pages.
  const hidden = override.hidden_page_ids ?? []
  if (hidden.length > 0) {
    const hiddenSet = new Set(hidden)
    pages = pages.filter((p) => !hiddenSet.has(p.page_id))
  }

  // Step 4: reorder per page_order_override.
  const order = override.page_order_override
  if (order && order.length > 0) {
    const byId = new Map<string, EdgePanelPage>()
    pages.forEach((p) => byId.set(p.page_id, p))
    const reordered: EdgePanelPage[] = []
    for (const pid of order) {
      const found = byId.get(pid)
      if (found) {
        reordered.push(found)
        byId.delete(pid)
      }
    }
    // Append any pages not mentioned in order.
    for (const remaining of byId.values()) {
      reordered.push(remaining)
    }
    pages = reordered
  }

  return pages
}
