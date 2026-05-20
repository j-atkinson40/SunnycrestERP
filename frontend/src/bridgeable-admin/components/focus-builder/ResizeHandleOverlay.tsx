/**
 * ResizeHandleOverlay — sub-arc FF-4.
 *
 * Renders 8 absolutely-positioned resize handles (4 corners + 4
 * edges) overlaying a free-form placed widget. Each handle is its
 * own @dnd-kit `useDraggable` with id `<placementId>-handle-<position>`.
 * The page-level drag-end handler parses the id, looks up the
 * placement + canvas + min dimensions, and dispatches to
 * `computeResizeCommit`.
 *
 * Per Q-10: 8 handles (nw / n / ne / w / e / sw / s / se), visible
 * only when the widget is selected. The parent FreeFormPlacedWidget
 * mounts this conditionally on `isSelected`.
 *
 * Architectural design: ResizeHandleOverlay is a SIBLING of
 * PlacedWidgetCore inside the FF-3 draggable wrapper — NOT a child of
 * PlacedWidgetCore. Drag-whole-widget vs. manipulate-specific-edge
 * are distinct gestures; isolating them keeps the event semantics
 * clean (Figma/Sketch/Framer precedent — selection-handle overlay is
 * a sibling layer to the rendered object).
 *
 * Per Q-40: KeyboardSensor reuse — same JSDOM mitigation strategy as
 * FF-3 whole-widget drag. Handles are keyboard-focusable
 * (tabIndex=0); operators press Space on a focused handle to
 * activate, arrows to nudge, Space to commit.
 *
 * Visual treatment: 8×8 px squares positioned at the 8 cardinal
 * points of the parent's bounding box. White fill, 1px accent border.
 * Cursor per position (nw-resize / n-resize / etc.) signals the axis
 * of motion to operators.
 *
 * Note on pointer-events contract (per CLAUDE.md "Focus Canvas
 * tier-renderer pointer-events contract"): each handle is itself
 * a pointer-events:auto interactive surface. The draggable wrapper
 * around the widget continues to receive whole-widget drag gestures
 * EXCEPT where a handle covers it — @dnd-kit's per-draggable
 * activation handlers naturally route the gesture to the most-
 * specific draggable element clicked, so a pointerdown on a handle
 * activates the handle's draggable, not the wrapper's.
 */
import type { CSSProperties } from "react"
import { useDraggable } from "@dnd-kit/core"

export type ResizeHandlePosition =
  | "nw"
  | "n"
  | "ne"
  | "w"
  | "e"
  | "sw"
  | "s"
  | "se"

export const RESIZE_HANDLE_ID_PREFIX = "" // empty — full id format is `<placementId>-handle-<position>`
export const RESIZE_HANDLE_POSITIONS: readonly ResizeHandlePosition[] = [
  "nw",
  "n",
  "ne",
  "w",
  "e",
  "sw",
  "s",
  "se",
] as const

const HANDLE_ID_REGEX = /^(.+)-handle-(nw|n|ne|w|e|sw|s|se)$/

/**
 * Build a stable handle id for a (placement, position) pair.
 */
export function resizeHandleIdFor(
  placementId: string,
  position: ResizeHandlePosition,
): string {
  return `${placementId}-handle-${position}`
}

/**
 * Parse a handle id back into its placement id + position. Returns
 * null when the id doesn't match the resize-handle shape.
 */
export function parseResizeHandleId(
  id: string,
): { placementId: string; position: ResizeHandlePosition } | null {
  const m = HANDLE_ID_REGEX.exec(id)
  if (!m) return null
  return {
    placementId: m[1],
    position: m[2] as ResizeHandlePosition,
  }
}

const CURSORS: Record<ResizeHandlePosition, string> = {
  nw: "nw-resize",
  n: "n-resize",
  ne: "ne-resize",
  w: "w-resize",
  e: "e-resize",
  sw: "sw-resize",
  s: "s-resize",
  se: "se-resize",
}

const HANDLE_SIZE_PX = 8
const HANDLE_OFFSET_PX = -4 // half of HANDLE_SIZE so handles center on the edge

/** Position-specific CSS positioning rules. */
function positionStyleFor(
  position: ResizeHandlePosition,
): CSSProperties {
  switch (position) {
    case "nw":
      return { top: HANDLE_OFFSET_PX, left: HANDLE_OFFSET_PX }
    case "n":
      return {
        top: HANDLE_OFFSET_PX,
        left: `calc(50% - ${HANDLE_SIZE_PX / 2}px)`,
      }
    case "ne":
      return { top: HANDLE_OFFSET_PX, right: HANDLE_OFFSET_PX }
    case "w":
      return {
        top: `calc(50% - ${HANDLE_SIZE_PX / 2}px)`,
        left: HANDLE_OFFSET_PX,
      }
    case "e":
      return {
        top: `calc(50% - ${HANDLE_SIZE_PX / 2}px)`,
        right: HANDLE_OFFSET_PX,
      }
    case "sw":
      return { bottom: HANDLE_OFFSET_PX, left: HANDLE_OFFSET_PX }
    case "s":
      return {
        bottom: HANDLE_OFFSET_PX,
        left: `calc(50% - ${HANDLE_SIZE_PX / 2}px)`,
      }
    case "se":
      return { bottom: HANDLE_OFFSET_PX, right: HANDLE_OFFSET_PX }
  }
}

interface ResizeHandleProps {
  placementId: string
  position: ResizeHandlePosition
}

function ResizeHandle({ placementId, position }: ResizeHandleProps) {
  const id = resizeHandleIdFor(placementId, position)
  const { attributes, listeners, setNodeRef } = useDraggable({
    id,
    data: {
      kind: "free-form-resize-handle",
      placementId,
      position,
    },
  })
  const positionStyle = positionStyleFor(position)
  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      data-testid="focus-builder-resize-handle"
      data-handle-position={position}
      data-placement-id={placementId}
      tabIndex={0}
      role="button"
      aria-label={`Resize ${position}`}
      style={{
        position: "absolute",
        width: HANDLE_SIZE_PX,
        height: HANDLE_SIZE_PX,
        backgroundColor: "var(--surface-base, #ffffff)",
        border: "1px solid var(--accent, #9C5640)",
        borderRadius: 1,
        cursor: CURSORS[position],
        // Self-assert pointer-events: auto so the handle receives
        // events even when the overlay parent is pointer-events: none.
        pointerEvents: "auto",
        // Handles must paint above the widget core but below floating
        // overlays. z-index 2 sits just above the selection ring (1)
        // applied by PlacedWidgetCore in selected state.
        zIndex: 2,
        ...positionStyle,
      }}
    />
  )
}

export interface ResizeHandleOverlayProps {
  /** The free-form placement these handles attach to. */
  placementId: string
}

/**
 * Renders all 8 resize handles for a placement. The component itself
 * is positioned absolutely to cover the parent (inset: 0) so the
 * 8 handles can position relative to the parent's edges/corners
 * without each handle needing a measured rect.
 */
export function ResizeHandleOverlay(props: ResizeHandleOverlayProps) {
  const { placementId } = props
  return (
    <div
      data-testid="focus-builder-resize-handle-overlay"
      style={{
        position: "absolute",
        inset: 0,
        // Overlay itself is non-interactive — handles inside are
        // pointer-events: auto by default. Per the platform
        // pointer-events contract, the overlay is a transparent
        // positioning shell.
        pointerEvents: "none",
      }}
    >
      {RESIZE_HANDLE_POSITIONS.map((p) => (
        <ResizeHandle key={p} placementId={placementId} position={p} />
      ))}
    </div>
  )
}

export default ResizeHandleOverlay
