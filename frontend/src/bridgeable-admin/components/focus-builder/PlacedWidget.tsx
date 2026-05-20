/**
 * PlacedWidget — sub-arc FF-2 (extracted from FocusBuilderCanvas).
 *
 * Grid-shape positioning shell. Computes the placement's CSS grid
 * column span from `column_start` + `column_span` clamped to the
 * row's `columns`. Delegates chrome / selection / click / keyboard /
 * widget render to the shared `PlacedWidgetCore`.
 *
 * Behaviorally equivalent to F-3.1c's inline implementation — the
 * extraction is mechanical (Q-29 (c) decomposition). The visual
 * rendering and DOM shape are byte-identical for grid placements; the
 * only DOM additive is the inner `data-testid="focus-builder-placed-
 * widget-core"` wrapper added by `PlacedWidgetCore` (one extra div).
 */
import type { WidgetPlacement } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"

import { PlacedWidgetCore } from "./PlacedWidgetCore"

export interface PlacedWidgetProps {
  placement: WidgetPlacement
  selected: boolean
  onSelect: (id: string) => void
  /** Row's column count (12 by default); used to clamp grid math. */
  columns: number
  themeTokens: Record<string, string>
}

export function PlacedWidget(props: PlacedWidgetProps) {
  const { placement, selected, onSelect, columns, themeTokens } = props
  const span = Math.max(1, Math.min(columns, placement.column_span || 4))
  const start = Math.max(1, Math.min(columns, placement.column_start || 1))
  return (
    <PlacedWidgetCore
      placement={placement}
      selected={selected}
      onSelect={onSelect}
      themeTokens={themeTokens}
      outerStyle={{ gridColumn: `${start} / span ${span}` }}
    />
  )
}

export default PlacedWidget
