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
 * `User.preferences.edge_panel_overrides[panel_key]`. */
export interface EdgePanelUserOverride {
  schema_version?: 1
  page_overrides?: Record<string, {
    rows?: CompositionRow[]
    canvas_config?: CanvasConfig
  }>
  page_order_override?: string[]
  hidden_page_ids?: string[]
}


export interface EdgePanelTenantConfig {
  enabled: boolean
  width: number
}
