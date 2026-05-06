/**
 * Focus composition types — frontend mirror of the backend's
 * `focus_compositions` table shape (May 2026 composition layer).
 */
import type { ComponentKind } from "@/lib/visual-editor/registry"


export interface PlacementGrid {
  column_start: number
  column_span: number
  row_start: number
  row_span: number
}


export interface PlacementDisplayConfig {
  show_header?: boolean
  show_border?: boolean
  z_index?: number
}


export interface Placement {
  placement_id: string
  component_kind: ComponentKind
  component_name: string
  grid: PlacementGrid
  prop_overrides: Record<string, unknown>
  display_config: PlacementDisplayConfig
}


export interface ResponsiveBreakpoints {
  mobile?: { columns: number }
  tablet?: { columns: number }
  desktop?: { columns: number }
}


export interface CanvasConfig {
  total_columns?: number
  row_height?: "auto" | number
  gap_size?: number
  responsive_breakpoints?: ResponsiveBreakpoints
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
  placements: Placement[]
  canvas_config: CanvasConfig
}


export interface CompositionRecord {
  id: string
  scope: "platform_default" | "vertical_default" | "tenant_override"
  vertical: string | null
  tenant_id: string | null
  focus_type: string
  placements: Placement[]
  canvas_config: CanvasConfig
  version: number
  is_active: boolean
  created_at: string
  updated_at: string
  created_by: string | null
  updated_by: string | null
}
