/**
 * FreeFormPlacedWidget — sub-arc FF-2 (positioning shell) + FF-3 (drag).
 *
 * Absolute-positioned shell for free-form placements. Reads
 * `placement.x` / `.y` / `.width` / `.height` / `.z_index` and emits
 * an inline `position: absolute` style with pixel-typed `left` /
 * `top` / `width` / `height` / `zIndex`.
 *
 * FF-3 (this revision) wraps the positioning shell with @dnd-kit's
 * `useDraggable` so operators can drag the widget to reposition. The
 * shell:
 *
 *   - Owns position:absolute + left/top/width/height/zIndex (the FF-2
 *     positioning contract — UNCHANGED in semantics; the carrying
 *     element shifts up one level from PlacedWidgetCore's outer div
 *     to the new draggable wrapper).
 *   - Owns the drag transform during gesture (dnd-kit's `transform`
 *     applied as a CSS translate3d so the visual moves with the
 *     pointer/keyboard arrow; the COMMIT (drag-end) updates
 *     placement.x/y via the page-level handler + clears the transform
 *     on the next render).
 *   - Owns the drag listeners (`{...listeners}` from `useDraggable`)
 *     spread at the wrapper level per Q-9 (drag initiation from
 *     anywhere on the widget body).
 *   - Owns cursor styling (grab idle → grabbing during drag).
 *   - Owns the drag-active visual feedback (subtle opacity shift +
 *     elevated shadow accent).
 *
 * Inside the draggable wrapper, PlacedWidgetCore renders untouched —
 * it owns chrome, selection, click, keyboard activation, widget
 * render. F-2 selection model + F-3.1c chrome editing + FF-2 palette
 * drop continue working unchanged.
 *
 * Per investigation Q-29: shared inner wrapper. Free-form is a
 * positioning + drag shell; the wrapper handles chrome / selection /
 * click / render. PlacedWidgetCore stays as the canonical chrome
 * surface across grid + free-form shapes.
 *
 * Per Q-9: click-vs-drag disambiguation defers to PointerSensor's
 * 3px activation constraint (configured in FocusBuilderPage). A
 * pointerdown that moves <3px before pointerup is treated as a click
 * → fires PlacedWidgetCore's onClick → selection flips to this
 * widget. A pointerdown that moves ≥3px starts a drag → PlacedWidgetCore's
 * onClick does NOT fire on pointerup (dnd-kit suppresses).
 *
 * Per Q-14: canvas-bounds clamp happens at commit time in the page-
 * level drag-end handler (`computeDragMoveCommit`). During the
 * gesture the transform may overshoot; the commit pulls back.
 *
 * Per Q-40: integration tests drive @dnd-kit's KeyboardSensor (Space
 * to grab, arrows to nudge, Space to drop). Pointer coverage in
 * JSDOM is unreliable; that lands in Playwright at FF-7.
 *
 * Defensive coords: `placement.x` / `.y` may be `undefined` for
 * round-trip legacy / mixed-shape inputs. Falls back to `0` for x/y
 * and the platform free-form default for width/height. Defensive
 * fallback to 0 / 320 / 180 is a structural safety net for malformed
 * JSONB.
 */
import type * as React from "react"
import { useDraggable } from "@dnd-kit/core"

import type { WidgetPlacement } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"
import { FREE_FORM_DEFAULT_DIMENSIONS } from "@/lib/visual-editor/registry"

import { PlacedWidgetCore } from "./PlacedWidgetCore"
import { ResizeHandleOverlay } from "./ResizeHandleOverlay"

export interface FreeFormPlacedWidgetProps {
  placement: WidgetPlacement
  selected: boolean
  onSelect: (id: string) => void
  themeTokens: Record<string, string>
  /**
   * FF-5 — right-click context-menu request. Fired with the
   * placement id + cursor position (viewport coords) when the
   * operator right-clicks anywhere on the widget body. Per the
   * selection-model preservation contract: right-click does NOT
   * change selection; the menu acts on the right-clicked target
   * regardless of current selection (Figma / Sketch precedent).
   * Optional — when absent the default browser context menu shows.
   */
  onContextMenuRequest?: (
    placementId: string,
    position: { x: number; y: number },
  ) => void
  /**
   * FF-7 — shift+click handler. Forwarded to PlacedWidgetCore so the
   * operator can compose multi-select from the canvas per Q-16 (a).
   */
  onShiftSelect?: (id: string) => void
}

/**
 * FF-3 — draggable id prefix. Distinguishes a draggable existing
 * placement from a palette item (`palette-widget:<slug>`) in the
 * page-level `onDragEnd` handler. The placement id follows the
 * colon.
 */
export const FREE_FORM_DRAGGABLE_ID_PREFIX = "free-form-placed-widget:"

export function freeFormDraggableIdFor(placementId: string): string {
  return `${FREE_FORM_DRAGGABLE_ID_PREFIX}${placementId}`
}

export function parseFreeFormDraggableId(id: string): string | null {
  if (!id.startsWith(FREE_FORM_DRAGGABLE_ID_PREFIX)) return null
  return id.slice(FREE_FORM_DRAGGABLE_ID_PREFIX.length)
}

export function FreeFormPlacedWidget(props: FreeFormPlacedWidgetProps) {
  const {
    placement,
    selected,
    onSelect,
    themeTokens,
    onContextMenuRequest,
    onShiftSelect,
  } = props
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

  const draggableId = freeFormDraggableIdFor(placement.id)
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    isDragging,
  } = useDraggable({
    id: draggableId,
    data: { kind: "free-form-placed-widget", placementId: placement.id },
  })

  // dnd-kit's transform during the drag gesture (CSS translate3d).
  // After drag-end, the page-level handler commits the new x/y via
  // updateWidget; React re-renders with the new placement.x/y and
  // transform resets to null (no translate).
  const translate = transform
    ? `translate3d(${transform.x}px, ${transform.y}px, 0)`
    : undefined

  // FF-5 — right-click handler. Fires preventDefault to suppress the
  // browser context menu, then forwards the placement id + viewport
  // coordinates to the parent. Per the selection-model preservation
  // contract: this handler does NOT call onSelect. Selection state is
  // owned by left-click; right-click acts on the target regardless.
  // Declared AFTER the attribute spread below so it is NOT overwritten
  // by @dnd-kit's `{...attributes}` (the May 2026 FF-4 plumbing
  // discovery: spread order matters — explicit props must come AFTER
  // the spread to win).
  const handleContextMenu = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!onContextMenuRequest) return
    e.preventDefault()
    e.stopPropagation()
    onContextMenuRequest(placement.id, { x: e.clientX, y: e.clientY })
  }

  return (
    <div
      ref={setNodeRef}
      data-testid="focus-builder-freeform-placed-widget-draggable"
      data-placement-id={placement.id}
      data-dragging={isDragging ? "true" : "false"}
      // Listeners + attributes spread on the wrapper itself per Q-9
      // (drag initiation from anywhere on the widget body). The
      // `attributes` include keyboard-drag a11y bindings used by
      // @dnd-kit's KeyboardSensor.
      {...listeners}
      {...attributes}
      // FF-5 — declared AFTER the spread so @dnd-kit's attributes
      // can't overwrite it.
      onContextMenu={handleContextMenu}
      style={{
        position: "absolute",
        left: `${x}px`,
        top: `${y}px`,
        width: `${width}px`,
        height: `${height}px`,
        zIndex: isDragging ? Math.max(zIndex, 9999) : zIndex,
        transform: translate,
        // Q-9 cursor: grab idle, grabbing during drag.
        cursor: isDragging ? "grabbing" : "grab",
        // Drag-active visual feedback. Subtle opacity shift + elevated
        // shadow accent (brass tint) so operators see the widget is
        // "lifted" without overpowering the canvas composition.
        opacity: isDragging ? 0.85 : 1,
        boxShadow: isDragging
          ? "0 10px 24px -4px var(--shadow-color-level-2, rgba(0,0,0,0.18))"
          : undefined,
        transition: isDragging
          ? "none"
          : "opacity 120ms ease-out, box-shadow 120ms ease-out",
        // No padding/margin — the PlacedWidgetCore fills the shell.
      }}
    >
      <PlacedWidgetCore
        placement={placement}
        selected={selected}
        onSelect={onSelect}
        onShiftSelect={onShiftSelect}
        themeTokens={themeTokens}
        outerStyle={{
          // Inner core fills the draggable wrapper. The wrapper owns
          // absolute positioning + size; the core renders chrome,
          // selection, click, and the widget itself within.
          width: "100%",
          height: "100%",
        }}
      />
      {/* FF-4 — resize handles as a SIBLING of PlacedWidgetCore.
          Rendered only when the widget is selected (canonical
          Figma/Sketch UX). The overlay positions 8 handles relative
          to the FreeFormPlacedWidget wrapper's bounding box. */}
      {selected ? <ResizeHandleOverlay placementId={placement.id} /> : null}
    </div>
  )
}

export default FreeFormPlacedWidget
