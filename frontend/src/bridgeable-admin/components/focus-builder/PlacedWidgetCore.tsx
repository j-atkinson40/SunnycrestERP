/**
 * PlacedWidgetCore — sub-arc FF-2.
 *
 * Shared widget wrapper for placed widgets on the Focus Builder
 * canvas. Extracted per investigation Q-29 from F-3.1c's `PlacedWidget`
 * inline implementation so both grid-shape (`PlacedWidget` via
 * `WidgetRowsLayer`) and free-form-shape (`FreeFormPlacedWidget` via
 * `WidgetFreeFormLayer`) callers consume the same chrome + selection
 * + click-handler substrate. The positioning shells (grid / absolute)
 * are thin layout-only adapters that compute their own positioning
 * style and hand it to `PlacedWidgetCore` via `outerStyle`.
 *
 * This component owns:
 *
 *   - chrome resolution via canonical `chrome-resolver` pipeline
 *     (`DEFAULT_WIDGET_CHROME` <- placement.chrome cascade — same
 *     semantics as F-3.1c)
 *   - selection chrome (brass outline when `selected`)
 *   - click handler firing `onSelect` with `placement.id`
 *   - keyboard activation (Enter / Space → onSelect)
 *   - the actual widget component render via the visual-editor registry
 *
 * Data-testid contract:
 *   - outer `data-testid="focus-builder-placed-widget"` — preserved
 *     for F-3.1c and earlier integration-test selector continuity
 *   - inner `data-testid="focus-builder-placed-widget-core"` — new
 *     operator-observable assertion target per the 2026-05-20
 *     late-evening canon (FF-2 integration tests target the inner
 *     core when the assertion is about the widget itself rather than
 *     the outer positioning shell)
 *
 * NOTE: Chrome + selection + click + keyboard handling all live on
 * the OUTER `focus-builder-placed-widget` div. This keeps the
 * F-3.1c-era render output byte-equivalent for grid placements; the
 * inner core is a structural-only wrapper around the widget component
 * that exposes the inner test-id for FF-2 assertions about widget
 * positioning that need to drill past the outer shell's positioning
 * style.
 */
import * as React from "react"

import { getByName } from "@/lib/visual-editor/registry"
import {
  expandPreset,
  mergeChromeWithOverrides,
  resolveChromeStyle,
} from "@/bridgeable-admin/lib/visual-editor/chrome-resolver"
import type { WidgetPlacement } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"

import { DEFAULT_WIDGET_CHROME } from "./WidgetInspectorSection"

export interface PlacedWidgetCoreProps {
  placement: WidgetPlacement
  selected: boolean
  onSelect: (id: string) => void
  themeTokens: Record<string, string>
  /**
   * Positioning style supplied by the outer shell. Grid path passes
   * `{ gridColumn: "..." }`; free-form path passes `{ position:
   * "absolute", left, top, width, height, zIndex }`. The shared
   * wrapper spreads chrome FIRST, then this positioning style, so
   * layout values override conflicting chrome keys (matches the
   * F-3.1c pre-extraction ordering of `...resolvedChromeStyle,
   * gridColumn: ...`).
   */
  outerStyle: React.CSSProperties
  /**
   * FF-7 — shift+click handler. When the operator clicks the widget
   * with Shift held, `onShiftSelect` fires (and `onSelect` does NOT).
   * Callers wire this to `addToSelection`/`removeFromSelection` so
   * the operator can compose multi-select from the canvas per Q-16
   * (a). Optional — when absent, all clicks fall through to
   * `onSelect` (single-select model unchanged from F-3.1c).
   */
  onShiftSelect?: (id: string) => void
}

/**
 * F-3.1c canon — resolve per-placement chrome through the canonical
 * chrome-resolver pipeline. Widgets have no Tier-1 cascade (chrome is
 * stamped at placement creation), so we merge the placement's chrome
 * ON TOP of `DEFAULT_WIDGET_CHROME` and resolve.
 *
 * Exported so callers that need to inspect or compose the chrome
 * style separately (e.g., future drag-preview overlays) can reuse
 * the exact resolver pipeline.
 */
export function resolvePlacementChromeStyle(
  placement: WidgetPlacement,
  themeTokens: Record<string, string>,
): React.CSSProperties {
  const view = expandPreset(
    mergeChromeWithOverrides(
      DEFAULT_WIDGET_CHROME as unknown as Record<string, unknown>,
      placement.chrome ?? {},
    ),
  )
  return resolveChromeStyle(view, themeTokens)
}

export function PlacedWidgetCore(props: PlacedWidgetCoreProps) {
  const { placement, selected, onSelect, themeTokens, outerStyle, onShiftSelect } =
    props
  const entry = React.useMemo(
    () => getByName("widget", placement.widget_slug),
    [placement.widget_slug],
  )
  const Component = entry?.component as
    | React.ComponentType<unknown>
    | undefined

  const resolvedChromeStyle = React.useMemo(
    () => resolvePlacementChromeStyle(placement, themeTokens),
    [placement, themeTokens],
  )

  return (
    <div
      data-testid="focus-builder-placed-widget"
      data-widget-id={placement.id}
      data-widget-slug={placement.widget_slug}
      data-selected={selected ? "true" : "false"}
      role="button"
      tabIndex={0}
      onClick={(e) => {
        e.stopPropagation()
        if (e.shiftKey && onShiftSelect) {
          onShiftSelect(placement.id)
          return
        }
        onSelect(placement.id)
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          e.stopPropagation()
          onSelect(placement.id)
        }
      }}
      style={{
        // Chrome-resolved styles first (background / borderRadius /
        // boxShadow / padding / border / backdropFilter / transition).
        // Outer positioning style (grid cell OR absolute coords) wins
        // on conflict per F-3.1c ordering. Selection outline + cursor
        // come last and override the chrome's transition.
        ...resolvedChromeStyle,
        ...outerStyle,
        outline: selected
          ? "2px solid var(--accent)"
          : "2px solid transparent",
        outlineOffset: "2px",
        transition: "outline-color var(--duration-instant) var(--ease-settle)",
        cursor: "pointer",
        minHeight: outerStyle.minHeight ?? 56,
      }}
    >
      <div data-testid="focus-builder-placed-widget-core">
        {Component ? (
          <Component {...(placement.chrome ?? {})} />
        ) : (
          <div className="rounded-md border border-dashed border-[color:var(--border-subtle)] bg-surface-base px-3 py-2 text-[12px] text-content-muted">
            Unknown widget: {placement.widget_slug}
          </div>
        )}
      </div>
    </div>
  )
}

export default PlacedWidgetCore
