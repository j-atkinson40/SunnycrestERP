// Widget framework types — shared across all dashboard pages

export interface WidgetDefinition {
  widget_id: string
  title: string
  description: string | null
  icon: string | null
  category: string | null
  default_size: string
  min_size?: string
  max_size?: string
  supported_sizes: string[]
  default_enabled: boolean
  default_position: number
  required_extension: string | null
  required_permission?: string | null
  is_available: boolean
  unavailable_reason: string | null
}

export interface WidgetLayoutItem {
  widget_id: string
  enabled: boolean
  position: number
  size: string
  config: Record<string, unknown>
  // Enriched from definition
  title?: string
  description?: string | null
  icon?: string | null
  category?: string | null
  supported_sizes?: string[]
  required_extension?: string | null
}

export interface WidgetLayout {
  page_context: string
  widgets: WidgetLayoutItem[]
}

export interface WidgetProps {
  onAction?: (action: string, data?: unknown) => void
  // Internal props passed by WidgetGrid — widgets forward these to WidgetWrapper
  [key: string]: unknown
}

/** Maps widget_id → React component */
export type WidgetComponentMap = Record<string, React.ComponentType<WidgetProps>>

/** Parse "NxM" size string into col/row spans */
export function parseSize(size: string): { cols: number; rows: number } {
  const [c, r] = size.split("x").map(Number)
  return { cols: c || 1, rows: r || 1 }
}
