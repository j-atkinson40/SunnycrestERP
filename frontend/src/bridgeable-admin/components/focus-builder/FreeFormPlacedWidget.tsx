/**
 * FreeFormPlacedWidget — sub-arc FF-2.
 *
 * Absolute-positioned shell for free-form placements. Reads
 * `placement.x` / `.y` / `.width` / `.height` / `.z_index` and emits
 * an inline `position: absolute` style with pixel-typed `left` /
 * `top` / `width` / `height` / `zIndex`. Delegates chrome / selection
 * / click / keyboard / widget render to the shared `PlacedWidgetCore`.
 *
 * Per investigation Q-4 + Q-22 + Q-29:
 *   - Q-4 — pixel position is the placement's authored coordinate
 *     (centered on cursor at drop time; FF-3 brings drag-to-move).
 *   - Q-22 — overlap with the inherited core is permitted; `z_index`
 *     governs. Default `z_index: 0`. The inherited core renders with
 *     implicit z_index 0; widgets default to z_index 0 too — DOM
 *     ordering breaks ties (FF-2 ships widgets AFTER the core in DOM
 *     order so they paint above the core by default).
 *   - Q-29 — shared inner wrapper. Free-form is a positioning shell;
 *     the wrapper handles chrome, selection, click, render.
 *
 * Defensive coords: `placement.x` / `.y` may be `undefined` for
 * round-trip legacy / mixed-shape inputs. Falls back to `0` for x/y
 * and the platform free-form default for width/height (registry
 * lookup happens at drop-time, not here — by the time a placement
 * arrives at this component it MUST carry concrete dimensions).
 * Defensive fallback to 0 / 320 / 180 is a structural safety net for
 * malformed JSONB.
 */
import type { WidgetPlacement } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"
import { FREE_FORM_DEFAULT_DIMENSIONS } from "@/lib/visual-editor/registry"

import { PlacedWidgetCore } from "./PlacedWidgetCore"

export interface FreeFormPlacedWidgetProps {
  placement: WidgetPlacement
  selected: boolean
  onSelect: (id: string) => void
  themeTokens: Record<string, string>
}

export function FreeFormPlacedWidget(props: FreeFormPlacedWidgetProps) {
  const { placement, selected, onSelect, themeTokens } = props
  const x = typeof placement.x === "number" ? placement.x : 0
  const y = typeof placement.y === "number" ? placement.y : 0
  const width =
    typeof placement.width === "number" && placement.width > 0
      ? placement.width
      : FREE_FORM_DEFAULT_DIMENSIONS.width
  const height =
    typeof placement.height === "number" && placement.height > 0
      ? placement.height
      : FREE_FORM_DEFAULT_DIMENSIONS.height
  const zIndex =
    typeof placement.z_index === "number" ? placement.z_index : 0

  return (
    <PlacedWidgetCore
      placement={placement}
      selected={selected}
      onSelect={onSelect}
      themeTokens={themeTokens}
      outerStyle={{
        position: "absolute",
        left: `${x}px`,
        top: `${y}px`,
        width: `${width}px`,
        height: `${height}px`,
        zIndex,
      }}
    />
  )
}

export default FreeFormPlacedWidget
