/**
 * WidgetChrome — drag/resize/dismiss chrome for canvas widgets.
 *
 * Phase A Session 3.5 refactor:
 *
 * 1. Drag from anywhere on widget body. @dnd-kit listeners attach
 *    to the wrapper instead of a drag-handle button. The grip icon
 *    remains as a visual affordance (ghosted top-left, purely
 *    decorative — it doesn't intercept pointer events, it just hints
 *    that the widget is draggable).
 *
 * 2. Resize from any of 8 zones: 4 corners + 4 edges. Each zone is
 *    an invisible element with an appropriate cursor (nwse-resize /
 *    nesw-resize / ew-resize / ns-resize). Cursor-based affordance
 *    replaces the visible resize-corner icon — discoverability comes
 *    from the cursor change on hover. Per DESIGN_LANGUAGE §6
 *    restraint principle: affordances visible when needed, invisible
 *    when not. Dismiss X + resize zones use stopPropagation so they
 *    don't initiate drag.
 *
 * 3. Zone-relative position. Resolved at render time via
 *    resolvePosition(pos, vw, vh). Widget stays in its anchor zone
 *    regardless of viewport changes. Live resize feedback uses the
 *    absolute rect from useResize's liveRect.
 *
 * Session 3.8 initially added `transition-[left,top,width,height]`
 * so widgets glided on viewport resize. Session 3.8.2 REMOVED those
 * transitions after profiling showed the classic transition-lag
 * problem: each viewport resize event set a new target, and CSS
 * started a fresh 300ms ease to the new target. At 60Hz resize the
 * widget was always ~100-150ms behind where it should be, reading
 * as choppy "swimming" during drag.
 *
 * Session 3.8.3 — position via `transform: translate3d(x, y, 0)`
 * instead of `left/top`. Per tldraw pattern research + user approval:
 * `transform` updates are composite-only (GPU layer push, no layout,
 * no paint) while `left/top` trigger full layout + paint per frame.
 * At our scale (3-10 widgets per Focus) layer 1 of the tldraw stack
 * (transform for position) provides the perceptible improvement;
 * layers 2-3 (signals + ref-based direct DOM writes) are overkill
 * vs. state-management complexity. During a window resize, widget
 * width/height are STABLE (they come from stored position.width /
 * height); only x/y change per frame. Moving only x/y to transform
 * keeps per-frame updates off the layout path entirely.
 *
 * Transform composition: base position-translate is written first,
 * then @dnd-kit's drag translate (active during drag), then drag-
 * scale. Multiple transforms in a single `transform` string compose
 * left-to-right via matrix multiplication — equivalent to applying
 * each translate in sequence.
 */

import { useDraggable } from "@dnd-kit/core"
import { CSS } from "@dnd-kit/utilities"
import { GripVertical, X } from "lucide-react"

import { useFocus } from "@/contexts/focus-context"
import type { WidgetId, WidgetPosition } from "@/contexts/focus-registry"
import { cn } from "@/lib/utils"

import { resolvePosition, type ResizeZone } from "./geometry"
import { useResize } from "./useResize"


export interface WidgetChromeProps {
  widgetId: WidgetId
  position: WidgetPosition
  canvasWidth: number
  canvasHeight: number
  minWidth?: number
  minHeight?: number
  onDismiss?: () => void
  children: React.ReactNode
}


const DEFAULT_MIN_WIDTH = 200
const DEFAULT_MIN_HEIGHT = 100


/** Edge/corner resize zone metadata. Thickness = 8px; corners are
 *  square 8×8 regions. */
const RESIZE_ZONES: Array<{
  zone: ResizeZone
  className: string
  cursor: string
  ariaLabel: string
}> = [
  // Corners — 8×8 squares
  {
    zone: "nw",
    className: "left-0 top-0 h-2 w-2",
    cursor: "nwse-resize",
    ariaLabel: "Resize from top-left corner",
  },
  {
    zone: "ne",
    className: "right-0 top-0 h-2 w-2",
    cursor: "nesw-resize",
    ariaLabel: "Resize from top-right corner",
  },
  {
    zone: "sw",
    className: "bottom-0 left-0 h-2 w-2",
    cursor: "nesw-resize",
    ariaLabel: "Resize from bottom-left corner",
  },
  {
    zone: "se",
    className: "bottom-0 right-0 h-2 w-2",
    cursor: "nwse-resize",
    ariaLabel: "Resize from bottom-right corner",
  },
  // Edges — 8px strips between corners
  {
    zone: "n",
    className: "left-2 right-2 top-0 h-2",
    cursor: "ns-resize",
    ariaLabel: "Resize from top edge",
  },
  {
    zone: "s",
    className: "left-2 right-2 bottom-0 h-2",
    cursor: "ns-resize",
    ariaLabel: "Resize from bottom edge",
  },
  {
    zone: "w",
    className: "left-0 top-2 bottom-2 w-2",
    cursor: "ew-resize",
    ariaLabel: "Resize from left edge",
  },
  {
    zone: "e",
    className: "right-0 top-2 bottom-2 w-2",
    cursor: "ew-resize",
    ariaLabel: "Resize from right edge",
  },
]


export function WidgetChrome({
  widgetId,
  position,
  canvasWidth,
  canvasHeight,
  minWidth = DEFAULT_MIN_WIDTH,
  minHeight = DEFAULT_MIN_HEIGHT,
  onDismiss,
  children,
}: WidgetChromeProps) {
  const { updateSessionLayout } = useFocus()

  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({ id: widgetId })

  const resize = useResize({
    anchor: position.anchor,
    position,
    minWidth,
    minHeight,
    canvasWidth,
    canvasHeight,
    onResizeEnd: (next) => {
      updateSessionLayout({
        widgets: {
          [widgetId]: { position: next },
        },
      })
    },
  })

  // Resolve anchor-based position to viewport-absolute rect at
  // render time. During resize, the liveRect from useResize drives
  // visual feedback so the widget tracks the cursor in real time.
  const resolved = resolvePosition(position, canvasWidth, canvasHeight)
  const displayRect = resize.liveRect ?? resolved
  const chromeActive = isDragging || resize.isResizing

  // Session 3.8.3 — compose transform. Base position-translate comes
  // first; @dnd-kit's drag translate (`translate3d(dx, dy, 0)` during
  // drag) stacks via CSS matrix multiplication; drag-scale last. When
  // @dnd-kit's `transform` is null (not dragging), `CSS.Translate.
  // toString` returns null/empty — filter it out of the composition.
  const dragTransformStr = transform ? CSS.Translate.toString(transform) : null
  const composedTransform = [
    `translate3d(${displayRect.x}px, ${displayRect.y}px, 0)`,
    dragTransformStr || null,
    isDragging ? "scale(1.02)" : null,
  ]
    .filter(Boolean)
    .join(" ")

  return (
    <div
      ref={setNodeRef}
      data-slot="focus-widget-chrome"
      data-widget-id={widgetId}
      data-chrome-active={chromeActive ? "true" : "false"}
      className={cn(
        // `group` drives chrome opacity via group-hover on children.
        "group absolute",
        "rounded-md border border-border-subtle bg-surface-elevated shadow-level-1",
        "transition-shadow duration-quick ease-settle",
        // Session 3.8.2 — NO transition on left/top/width/height.
        // Session 3.8.3 — position is now on transform, not left/top;
        // width/height stay as inline style (stable during window
        // resize, only change during user-initiated widget resize
        // gesture which is a rare event).
        chromeActive && "shadow-level-2",
        // Drag cursor on wrapper — widget body is draggable. The
        // chrome sub-elements (dismiss, resize zones) override this
        // via their own cursor styles + stopPropagation.
        !isDragging && "cursor-grab",
        isDragging && "cursor-grabbing",
      )}
      style={{
        // Anchor at (0,0) of containing block (the data-tier-renderer,
        // which is `absolute inset-0` of the fixed-inset Canvas). The
        // transform then translates to the resolved position. Keeping
        // left/top explicit prevents browser auto-placement quirks.
        left: 0,
        top: 0,
        width: displayRect.width,
        height: displayRect.height,
        transform: composedTransform,
        zIndex: chromeActive ? 2 : 1,
      }}
      {...listeners}
      {...attributes}
    >
      {/* Decorative grip — visual affordance only, not a drag
          handle. pointer-events-none so it doesn't intercept drag
          listeners on the wrapper.
          Session 3.6 restraint: hidden during active drag/resize —
          cursor change IS the affordance during interaction, per
          PLATFORM_QUALITY_BAR.md §4. Order matters here: the
          active-state selector MUST come after group-hover so it
          wins specificity when both conditions are true during a
          drag (cursor is over the widget ∧ drag is active). */}
      <div
        data-slot="focus-widget-grip"
        aria-hidden
        className={cn(
          "pointer-events-none absolute left-2 top-2 z-10 flex h-6 w-6 items-center justify-center rounded",
          "bg-surface-raised/80 text-content-muted",
          "opacity-0 group-hover:opacity-100 transition-opacity duration-arrive ease-settle",
          "group-data-[chrome-active=true]:opacity-0",
        )}
      >
        <GripVertical className="h-3.5 w-3.5" />
      </div>

      {/* Dismiss X — top-right. stopPropagation on pointerdown so the
          wrapper's drag listeners don't initiate drag when clicking
          X. Stays as a real button for accessibility + keyboard.
          Session 3.6: also hidden during active interaction. */}
      {onDismiss && (
        <button
          type="button"
          data-slot="focus-widget-dismiss"
          aria-label="Dismiss widget"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => {
            e.stopPropagation()
            onDismiss()
          }}
          className={cn(
            "absolute right-2 top-2 z-10 flex h-6 w-6 items-center justify-center rounded",
            "bg-surface-raised/80 text-content-muted",
            "opacity-0 group-hover:opacity-100 transition-opacity duration-arrive ease-settle",
            "group-data-[chrome-active=true]:opacity-0",
            "group-data-[chrome-active=true]:pointer-events-none",
            "hover:bg-status-error-muted hover:text-status-error",
            "focus-ring-brass",
            "cursor-pointer",
          )}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}

      {/* Widget content — fills the chrome bounds. Children inherit
          drag listeners from the wrapper (drag-from-anywhere), but
          interactive content (buttons, links) within the widget body
          should use stopPropagation on pointerdown if they need to
          be clickable without initiating drag. Session 3.5 mock
          widget is non-interactive so no conflict. */}
      <div className="h-full w-full overflow-hidden rounded-md">
        {children}
      </div>

      {/* 8 invisible resize zones — 4 corners + 4 edges. Each has a
          distinct cursor style (CSS handles cursor on hover) + its
          own onPointerDown. stopPropagation prevents drag
          initiation. */}
      {RESIZE_ZONES.map(({ zone, className, cursor, ariaLabel }) => (
        <div
          key={zone}
          data-slot="focus-widget-resize-zone"
          data-zone={zone}
          role="button"
          aria-label={ariaLabel}
          tabIndex={-1}
          className={cn(
            "absolute z-20",
            className,
          )}
          style={{ cursor }}
          onPointerDown={resize.bind(zone)}
        />
      ))}
    </div>
  )
}
