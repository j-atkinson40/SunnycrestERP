/**
 * Phase W-4a Pulse types — frontend mirror of backend dataclasses
 * in `app/services/pulse/types.py`.
 *
 * Per BRIDGEABLE_MASTER §3.26 + DESIGN_LANGUAGE §13. The shapes are
 * the wire contract for `GET /api/v1/pulse/composition`; any change
 * to one side requires a coordinated change to the other.
 */

export type LayerName = "personal" | "operational" | "anomaly" | "activity"
export type ItemKind = "widget" | "stream"
export type VariantId = "glance" | "brief" | "detail" | "deep"
export type TimeOfDaySignal =
  | "morning"
  | "midday"
  | "end_of_day"
  | "off_hours"


export interface LayerItem {
  /** Stable per-render identifier — frontend keys components on it
   * and signal tracking identifies dismissed pieces by it. */
  item_id: string
  kind: ItemKind
  /** Renderer key. For widgets: widget_id (e.g., "vault_schedule").
   * For streams: stream key (e.g., "anomaly_intelligence_stream"). */
  component_key: string
  variant_id: VariantId
  /** Tetris layout sizing per §13.4.1. */
  cols: number
  rows: number
  /** Layer-internal priority; higher = more prominent. Already
   * applied as the in-layer sort order by the backend. */
  priority: number
  /** Pre-fetched content for streams; usually empty for widgets
   * (widgets self-fetch via useWidgetData). */
  payload?: Record<string, unknown>
  /** Phase W-4a Commit 4 — surfaces dismiss state from
   * pulse_signals so frontend can suppress recently-dismissed
   * items. Backend currently writes false; per-piece dismiss-state
   * read-through is a post-W-4a refinement. */
  dismissed?: boolean
}


export interface LayerContent {
  layer: LayerName
  items: LayerItem[]
  /** Optional layer-level advisory for empty / partial states. */
  advisory: string | null
}


export interface ReferencedItem {
  /** "anomaly" | "delivery" | "task" | etc. Renderer dispatches
   * on kind to produce an appropriately-shaped chip. */
  kind: string
  entity_id: string
  label: string
  href: string | null
}


export interface IntelligenceStream {
  stream_id: string
  layer: LayerName
  title: string
  synthesized_text: string
  referenced_items: ReferencedItem[]
  priority: number
}


export interface PulseCompositionMetadata {
  work_areas_used: string[]
  vertical_default_applied: boolean
  time_of_day_signal: TimeOfDaySignal
}


export interface PulseComposition {
  user_id: string
  /** ISO-8601 timestamp the composition was computed (or cached
   * from). Frontend uses for dwell-time calculation on signals. */
  composed_at: string
  layers: LayerContent[]
  intelligence_streams: IntelligenceStream[]
  metadata: PulseCompositionMetadata
}


/**
 * Phase W-4a Commit 4 — signal tracking request bodies.
 * Backend forces user_id + company_id from the auth token; these
 * shapes deliberately omit those fields.
 */


export interface DismissSignalRequest {
  component_key: string
  layer: LayerName
  time_of_day: TimeOfDaySignal
  work_areas_at_dismiss?: string[]
}


export interface NavigateSignalRequest {
  from_component_key: string
  to_route: string
  dwell_time_seconds: number
  layer: LayerName
}
