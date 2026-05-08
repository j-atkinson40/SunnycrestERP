/**
 * R-5.0 — edge-panel frontend types.
 *
 * Mirrors the backend's `kind="edge_panel"` composition shape. The
 * pages array is the canonical multi-page model: each page carries
 * its own row-set + per-page canvas_config.
 */
import type {
  CanvasConfig,
  CompositionRow,
} from "@/lib/visual-editor/compositions/types"


/** A single page within an edge panel composition. */
export interface EdgePanelPage {
  page_id: string
  name: string
  rows: CompositionRow[]
  canvas_config: CanvasConfig
}


/** Resolved edge panel composition — what the tenant-realm
 * `/api/v1/edge-panel/resolve` endpoint returns after the inheritance
 * chain walk + per-user override merge. */
export interface ResolvedEdgePanel {
  panel_key: string
  vertical: string | null
  tenant_id: string | null
  source: "platform_default" | "vertical_default" | "tenant_override" | null
  source_id: string | null
  source_version: number | null
  pages: EdgePanelPage[]
  canvas_config: CanvasConfig
}


/** Per-user override blob shape. Stored at
 * `User.preferences.edge_panel_overrides[panel_key]`.
 *
 * R-5.1 extends the per-page override shape with per-placement
 * granularity (`hidden_placement_ids`, `additional_placements`,
 * `placement_order`) plus top-level `additional_pages` for the user's
 * personal pages.
 *
 * Resolver merge semantics:
 *   - When `rows` set → R-5.0 full-replace escape hatch; per-placement
 *     fields are ignored for that page.
 *   - Else → R-5.1 per-placement layer applies on top of tenant
 *     placements (filter by `hidden_placement_ids` → append
 *     `additional_placements` → reorder by `placement_order`).
 *   - `canvas_config` always replaces the page's canvas_config when
 *     set, regardless of which path is taken.
 */
export interface EdgePanelUserOverride {
  schema_version?: 1
  page_overrides?: Record<string, {
    /** R-5.0 full-replace escape hatch. When set, per-placement
     * fields below are ignored for this page. */
    rows?: CompositionRow[]
    canvas_config?: CanvasConfig
    /** R-5.1 — drop these placement_ids from the tenant page's rows.
     * Orphan IDs (referencing placements that no longer exist in
     * the tenant default) are silently dropped. */
    hidden_placement_ids?: string[]
    /** R-5.1 — append these placements onto the tenant page's rows.
     * Each placement may carry `row_index` (default 0) indicating
     * which row to append to; clamped to last row if too high. */
    additional_placements?: import("@/lib/visual-editor/compositions/types").Placement[]
    /** R-5.1 — reorder placements within each row by placement_id.
     * Orphan IDs silently dropped. Placements not mentioned keep
     * their relative position appended at end. */
    placement_order?: string[]
  }>
  page_order_override?: string[]
  hidden_page_ids?: string[]
  /** R-5.1 — user's personal pages appended after per-page overrides
   * apply. Personal pages with page_id colliding with a tenant page
   * are silently dropped (tenant wins). Personal pages participate in
   * `hidden_page_ids` and `page_order_override` like any tenant page. */
  additional_pages?: EdgePanelPage[]
}


export interface EdgePanelTenantConfig {
  enabled: boolean
  width: number
}
