/**
 * CompositionRenderer — runtime + editor renderer for canvas-based
 * Focus compositions.
 *
 * R-3.0 — composition is a sequence of rows. Each row declares its
 * own column_count (1-12) and renders as an inner CSS Grid. Outer
 * container is flex-col with consistent gap between rows.
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
import { RegisteredButton } from "@/lib/runtime-host/buttons/RegisteredButton"
import type {
  CanvasConfig,
  CompositionRow,
  Placement,
  ResolvedComposition,
} from "./types"


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


function defaultGapSize(canvasConfig: CanvasConfig): number {
  return canvasConfig.gap_size ?? 12
}


/** Runtime placement renderer — dispatches widget-kind placements via
 *  `getWidgetRenderer(component_name)` from the canvas widget registry.
 *
 *  For non-widget kinds (focus / focus-template / document-block /
 *  workflow-node), returns a graceful empty state pointing at the
 *  missing component_kind. Production runtime today composes
 *  widget-kind placements only.
 */
function renderRuntimePlacement(p: Placement): ReactNode {
  // R-4.0 — buttons dispatch through RegisteredButton, which looks up
  // its own metadata via getByName("button", slug) at click-time. No
  // parallel button-renderers registry needed; the registry's
  // canonical introspection API + a single `if` branch here is
  // sufficient. Per /tmp/r4_0_renderer_dispatch_probe.md.
  if (p.component_kind === "button") {
    return (
      <RegisteredButton
        componentName={p.component_name}
        propOverrides={p.prop_overrides}
      />
    )
  }
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


function rowGridStyle(row: CompositionRow): CSSProperties {
  const rowHeight = row.row_height ?? "auto"
  return {
    display: "grid",
    gridTemplateColumns: `repeat(${row.column_count}, minmax(0, 1fr))`,
    gridAutoRows: typeof rowHeight === "number" ? `${rowHeight}px` : "auto",
    minHeight: typeof rowHeight === "number" ? `${rowHeight}px` : undefined,
    gap: "var(--composition-row-gap, 12px)",
  }
}


function placementCellStyle(p: Placement): CSSProperties {
  // CSS Grid is 1-indexed; our placements carry 0-indexed
  // starting_column. Translate at render time.
  return {
    gridColumn: `${p.starting_column + 1} / span ${p.column_span}`,
    zIndex: p.display_config?.z_index ?? "auto",
  }
}


/** Render a single placement card chrome. Body content is the
 * editor preview OR runtime widget (or caller-supplied override). */
function PlacementCard({
  placement,
  isSelected,
  editorMode,
  onClick,
  body,
}: {
  placement: Placement
  isSelected: boolean
  editorMode: boolean
  onClick?: () => void
  body: ReactNode
}) {
  const showBorder = placement.display_config?.show_border !== false
  const baseRingClass = isSelected
    ? "ring-2 ring-accent ring-offset-2 ring-offset-surface-base"
    : showBorder
      ? "border border-border-subtle"
      : ""
  const cursorClass = editorMode ? "cursor-pointer" : ""

  return (
    <div
      style={placementCellStyle(placement)}
      data-testid={`composition-placement-${placement.placement_id}`}
      data-component-kind={placement.component_kind}
      data-component-name={placement.component_name}
      data-selected={isSelected ? "true" : "false"}
      onClick={onClick}
      className={`overflow-hidden rounded-md bg-surface-elevated shadow-level-1 ${baseRingClass} ${cursorClass}`}
    >
      {placement.display_config?.show_header !== false && (
        <div className="flex items-center justify-between border-b border-border-subtle px-3 py-1.5 text-caption">
          <span className="font-medium text-content-strong">
            {placement.component_name}
          </span>
          <span className="text-content-subtle">
            {placement.component_kind}
          </span>
        </div>
      )}
      <div className="h-full p-2">{body}</div>
    </div>
  )
}


export function CompositionRenderer({
  composition,
  editorMode = false,
  selectedPlacementId,
  onPlacementClick,
  renderPlacement,
}: Props) {
  const cfg = composition.canvas_config ?? {}
  const gapSize = defaultGapSize(cfg)

  const outerStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    gap: `${gapSize}px`,
    padding: editorMode ? "1rem" : "0.5rem",
    minHeight: "100%",
    // Per-row inner grid reads gap from the CSS variable; setting it
    // here keeps row + column gaps in step.
    ["--composition-row-gap" as never]: `${gapSize}px`,
  }

  const isEmpty = composition.rows.length === 0

  function renderBody(p: Placement): ReactNode {
    if (renderPlacement) return renderPlacement(p)
    if (editorMode) {
      return renderComponentPreview(
        `${p.component_kind}:${p.component_name}`,
        p.prop_overrides ?? {},
        `${p.component_name}`,
      )
    }
    return renderRuntimePlacement(p)
  }

  return (
    <div
      className={`${backgroundClassFor(cfg.background_treatment)} h-full w-full overflow-auto`}
      data-testid="composition-renderer"
      data-source={composition.source ?? "none"}
    >
      <div style={outerStyle} data-testid="composition-grid">
        {isEmpty && editorMode && (
          <div
            className="flex items-center justify-center py-8 text-content-subtle"
            data-testid="composition-empty"
          >
            <span className="text-caption">
              No rows yet — add a row to start composing.
            </span>
          </div>
        )}

        {composition.rows.map((row, rowIdx) => (
          <div
            key={row.row_id}
            style={rowGridStyle(row)}
            data-testid={`composition-row-${row.row_id}`}
            data-row-index={rowIdx}
            data-column-count={row.column_count}
          >
            {row.placements.map((p) => {
              const isSelected =
                editorMode && selectedPlacementId === p.placement_id
              return (
                <PlacementCard
                  key={p.placement_id}
                  placement={p}
                  isSelected={isSelected}
                  editorMode={editorMode}
                  onClick={
                    editorMode && onPlacementClick
                      ? () => onPlacementClick(p.placement_id)
                      : undefined
                  }
                  body={renderBody(p)}
                />
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
