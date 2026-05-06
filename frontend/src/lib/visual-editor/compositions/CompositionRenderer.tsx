/**
 * CompositionRenderer — runtime + editor renderer for canvas-based
 * Focus compositions (May 2026 composition layer).
 *
 * Two render paths split on `editorMode`:
 *
 *   editorMode=false (RUNTIME): each placement dispatches via
 *     `getWidgetRenderer(component_name)` from the canvas widget
 *     registry — same path Pulse + Focus canvas use. Real
 *     production widgets render with operational data fetched via
 *     their own hooks/services. Placements that don't resolve to a
 *     registered renderer fall through `getWidgetRenderer`'s
 *     `MissingWidgetEmptyState` branch (honest "Widget unavailable"
 *     state with widget_id surfaced — same canon as Pulse).
 *
 *   editorMode=true (EDITOR PREVIEW): each placement dispatches via
 *     `renderComponentPreview` — the visual editor's stylized stand-in
 *     renderer. Stand-ins use design tokens but have no operational
 *     behavior (correct for preview where stable visual structure
 *     matters more than live data).
 *
 * Callers MAY override per-placement rendering via the `renderPlacement`
 * prop. When provided, it wins over both default paths.
 *
 * Used in:
 *   1. The composition editor's canvas pane (editorMode=true).
 *   2. The Focus runtime accessory layer (editorMode=false; ComposedFocus
 *      mounts CompositionRenderer here).
 *
 * Empty composition renders a subtle "no composition defined"
 * placeholder visible only in editor mode (the runtime caller falls
 * back to the Focus's hard-coded layout when source === null).
 */
import type { CSSProperties, ReactNode } from "react"
import { renderComponentPreview } from "@/lib/visual-editor/components/preview-renderers"
import {
  getWidgetRenderer,
  type WidgetRendererProps,
} from "@/components/focus/canvas/widget-renderers"
import type { CanvasConfig, Placement, ResolvedComposition } from "./types"


interface Props {
  composition: ResolvedComposition
  /** Editor-mode renders grid lines + selection affordances. */
  editorMode?: boolean
  /** When editorMode is true, the placement_id of the currently
   * selected placement is highlighted. */
  selectedPlacementId?: string | null
  /** Click handler for placements (editor mode). */
  onPlacementClick?: (placementId: string) => void
  /** Override for individual placement preview content (editor uses
   * this to render real components with merged config). When
   * omitted, falls back to renderComponentPreview defaults. */
  renderPlacement?: (placement: Placement) => ReactNode
}


function defaultCanvasConfig(): Required<
  Pick<CanvasConfig, "total_columns" | "row_height" | "gap_size">
> {
  return {
    total_columns: 12,
    row_height: 64,
    gap_size: 12,
  }
}


/** Runtime placement renderer — dispatches widget-kind placements via
 *  `getWidgetRenderer(component_name)` from the canvas widget registry.
 *
 *  Convention: a placement's `component_kind` is the registry's
 *  ComponentKind discriminator (`widget`, `focus`, etc.) and its
 *  `component_name` is the canonical widget_id used in the canvas
 *  widget registry (e.g. `today`, `recent_activity`, `anomalies`,
 *  `vault_schedule`).
 *
 *  For non-widget kinds (focus / focus-template / document-block /
 *  workflow-node), the runtime path returns a graceful empty state
 *  pointing at the missing component_kind. Production runtime today
 *  composes widget-kind placements only; richer kinds activate as
 *  their corresponding production primitives ship.
 *
 *  Per-instance prop overrides flow through:
 *    - `widgetId`: placement's `component_name` (canonical id)
 *    - `surface`: `"focus_canvas"` (composition lives in Focus
 *      canvas; renderers may inspect this to adjust internal density)
 *    - `variant_id`: read from `prop_overrides.variant_id` if set,
 *      else undefined (component picks canvas-tier default per
 *      §12.10)
 *    - `config`: the rest of `prop_overrides` (excluding variant_id)
 *      passed transparently — same shape as Pulse + sidebar-pin
 *      dispatch.
 */
function renderRuntimePlacement(p: Placement): ReactNode {
  if (p.component_kind !== "widget") {
    return (
      <div
        className="flex h-full items-center justify-center px-3 py-4 text-caption text-content-muted"
        data-testid="composition-runtime-non-widget"
      >
        <span>
          Runtime renderer not available for {p.component_kind}:
          {p.component_name}
        </span>
      </div>
    )
  }
  const Renderer = getWidgetRenderer(p.component_name)
  const overrides = p.prop_overrides ?? {}
  const variant_id = overrides["variant_id"] as
    | WidgetRendererProps["variant_id"]
    | undefined
  const config = { ...overrides }
  delete config["variant_id"]
  return (
    <Renderer
      widgetId={p.component_name}
      surface="focus_canvas"
      variant_id={variant_id}
      config={config}
    />
  )
}


function backgroundClassFor(treatment?: string): string {
  switch (treatment) {
    case "surface-base":
      return "bg-surface-base"
    case "surface-elevated":
      return "bg-surface-elevated"
    case "surface-sunken":
      return "bg-surface-sunken"
    default:
      return "bg-surface-base"
  }
}


export function CompositionRenderer({
  composition,
  editorMode = false,
  selectedPlacementId,
  onPlacementClick,
  renderPlacement,
}: Props) {
  const cfg = { ...defaultCanvasConfig(), ...composition.canvas_config }
  const totalColumns = cfg.total_columns ?? 12
  const rowHeight = cfg.row_height ?? 64
  const gapSize = cfg.gap_size ?? 12

  const gridStyle: CSSProperties = {
    display: "grid",
    gridTemplateColumns: `repeat(${totalColumns}, minmax(0, 1fr))`,
    gridAutoRows: typeof rowHeight === "number" ? `${rowHeight}px` : "auto",
    gap: `${gapSize}px`,
    padding: editorMode ? "1rem" : "0.5rem",
    minHeight: "100%",
    position: "relative",
  }

  // Editor-mode grid line overlay (subtle dotted background).
  const editorChrome: CSSProperties = editorMode
    ? {
        backgroundImage: `linear-gradient(to right, var(--border-subtle) 1px, transparent 1px), linear-gradient(to bottom, var(--border-subtle) 1px, transparent 1px)`,
        backgroundSize: `calc((100% - ${(totalColumns - 1) * gapSize}px) / ${totalColumns} + ${gapSize}px) ${
          typeof rowHeight === "number" ? `${rowHeight + gapSize}px` : "32px"
        }`,
        backgroundPosition: `0 0`,
      }
    : {}

  const isEmpty = composition.placements.length === 0

  return (
    <div
      className={`${backgroundClassFor(cfg.background_treatment)} h-full w-full overflow-auto`}
      data-testid="composition-renderer"
      data-source={composition.source ?? "none"}
    >
      <div style={{ ...gridStyle, ...editorChrome }} data-testid="composition-grid">
        {isEmpty && editorMode && (
          <div
            className="col-span-full flex items-center justify-center py-8 text-content-subtle"
            data-testid="composition-empty"
          >
            <span className="text-caption">
              No placements yet — drag a component from the palette to start
              composing.
            </span>
          </div>
        )}

        {composition.placements.map((p) => {
          const isSelected = editorMode && selectedPlacementId === p.placement_id
          const cellStyle: CSSProperties = {
            gridColumn: `${p.grid.column_start} / span ${p.grid.column_span}`,
            gridRow: `${p.grid.row_start} / span ${p.grid.row_span}`,
            zIndex: p.display_config?.z_index ?? "auto",
          }
          const showBorder = p.display_config?.show_border !== false
          const baseRingClass = isSelected
            ? "ring-2 ring-accent ring-offset-2 ring-offset-surface-base"
            : showBorder
              ? "border border-border-subtle"
              : ""
          const cursorClass = editorMode ? "cursor-pointer" : ""

          return (
            <div
              key={p.placement_id}
              style={cellStyle}
              data-testid={`composition-placement-${p.placement_id}`}
              data-component-kind={p.component_kind}
              data-component-name={p.component_name}
              data-selected={isSelected ? "true" : "false"}
              onClick={
                editorMode && onPlacementClick
                  ? () => onPlacementClick(p.placement_id)
                  : undefined
              }
              className={`overflow-hidden rounded-md bg-surface-elevated shadow-level-1 ${baseRingClass} ${cursorClass}`}
            >
              {p.display_config?.show_header !== false && (
                <div className="flex items-center justify-between border-b border-border-subtle px-3 py-1.5 text-caption">
                  <span className="font-medium text-content-strong">
                    {p.component_name}
                  </span>
                  <span className="text-content-subtle">
                    {p.component_kind}
                  </span>
                </div>
              )}
              <div className="h-full p-2">
                {renderPlacement
                  ? renderPlacement(p)
                  : editorMode
                    ? renderComponentPreview(
                        `${p.component_kind}:${p.component_name}`,
                        p.prop_overrides ?? {},
                        `${p.component_name}`,
                      )
                    : renderRuntimePlacement(p)}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
