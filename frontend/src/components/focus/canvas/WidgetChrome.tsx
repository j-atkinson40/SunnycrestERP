/**
 * WidgetChrome — drag/resize/dismiss chrome primitive for canvas
 * widgets.
 *
 * Phase A Session 3. Wraps a widget's content and renders three
 * chrome affordances that are ghosted by default and appear on hover:
 *   - Drag handle (top-left) — grip icon; drag-initiates only from
 *     here, not from the widget body
 *   - Dismiss X (top-right) — calls onDismiss when clicked
 *   - Resize corner (bottom-right) — pointer-event-driven resize
 *
 * Chrome stays visible during active drag or resize (state-driven
 * `data-chrome-active="true"` — chrome elements use a group CSS
 * selector so hover reveals them during idle + force-reveals during
 * active operations).
 *
 * Drag is provided by @dnd-kit/core via `useDraggable`. The consumer
 * wraps this WidgetChrome in a positioned container; WidgetChrome
 * forwards `style.transform` from @dnd-kit so the widget visually
 * tracks the cursor during drag (position update persists on drop,
 * per PA Session 3 decision: "update on drop, not during drag").
 *
 * Per DESIGN_LANGUAGE §6 restraint principle — affordances visible
 * when needed, invisible when not.
 */

import { useDraggable } from "@dnd-kit/core"
import { CSS } from "@dnd-kit/utilities"
import { GripVertical, X, ArrowDownRight } from "lucide-react"

import { useFocus } from "@/contexts/focus-context"
import type { WidgetId, WidgetPosition } from "@/contexts/focus-registry"
import { cn } from "@/lib/utils"

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


/** Default min size for widgets — 200×100 px. Per PA §5.1 "soft
 *  maximum on visible widgets" — we enforce mins to prevent widgets
 *  shrinking below usefully-readable. */
const DEFAULT_MIN_WIDTH = 200
const DEFAULT_MIN_HEIGHT = 100


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

  // @dnd-kit drag — we apply the translate transform to the widget
  // container so the widget tracks the cursor during drag. Drop
  // position is persisted by the parent Canvas's onDragEnd handler
  // (see Canvas.tsx) — not here, so WidgetChrome can stay stateless
  // about drag bookkeeping.
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: widgetId,
    })

  // Resize — local in-progress size drives visual feedback; on
  // pointer-up, the snapped+clamped final size is persisted via
  // updateSessionLayout.
  const resize = useResize({
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

  const activeWidth = resize.liveSize?.width ?? position.width
  const activeHeight = resize.liveSize?.height ?? position.height
  const chromeActive = isDragging || resize.isResizing

  return (
    <div
      ref={setNodeRef}
      data-slot="focus-widget-chrome"
      data-widget-id={widgetId}
      data-chrome-active={chromeActive ? "true" : "false"}
      className={cn(
        // Positioned absolutely within the Canvas — position.x/y are
        // viewport pixels because Canvas is a fixed-inset overlay.
        "group absolute",
        "rounded-md border border-border-subtle bg-surface-elevated shadow-level-1",
        // During drag/resize, lift subtly + raise z within the
        // canvas stack.
        "transition-shadow duration-quick ease-settle",
        chromeActive && "shadow-level-2",
      )}
      style={{
        left: position.x,
        top: position.y,
        width: activeWidth,
        height: activeHeight,
        transform: CSS.Translate.toString(transform),
        // During drag, a tiny scale lift per PA §5.1 "subtle lift
        // effect". Kept CSS-only so the drop-snap feels instant
        // rather than an animated transform ending.
        ...(isDragging && {
          transform: `${CSS.Translate.toString(transform) ?? ""} scale(1.02)`,
        }),
        zIndex: chromeActive ? 2 : 1,
      }}
    >
      {/* Drag handle — top-left corner. Only this element initiates
          drag; the widget body is not a drag handle. */}
      <button
        type="button"
        data-slot="focus-widget-drag-handle"
        aria-label="Drag widget"
        className={cn(
          "absolute left-1 top-1 z-10 flex h-6 w-6 cursor-grab items-center justify-center rounded",
          "bg-surface-raised/80 text-content-muted",
          "opacity-0 group-hover:opacity-100 transition-opacity duration-arrive ease-settle",
          "group-data-[chrome-active=true]:opacity-100",
          "hover:bg-brass-subtle hover:text-content-strong",
          "focus-ring-brass",
          "active:cursor-grabbing",
        )}
        {...listeners}
        {...attributes}
      >
        <GripVertical className="h-3.5 w-3.5" />
      </button>

      {/* Dismiss X — top-right corner. Clicking removes the widget
          from the canvas via FocusContext.removeWidget (wired by
          onDismiss prop). */}
      {onDismiss && (
        <button
          type="button"
          data-slot="focus-widget-dismiss"
          aria-label="Dismiss widget"
          onClick={onDismiss}
          className={cn(
            "absolute right-1 top-1 z-10 flex h-6 w-6 items-center justify-center rounded",
            "bg-surface-raised/80 text-content-muted",
            "opacity-0 group-hover:opacity-100 transition-opacity duration-arrive ease-settle",
            "group-data-[chrome-active=true]:opacity-100",
            "hover:bg-status-error-muted hover:text-status-error",
            "focus-ring-brass",
          )}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}

      {/* Widget content fills the full chrome bounds. */}
      <div className="h-full w-full overflow-hidden rounded-md">
        {children}
      </div>

      {/* Resize corner — bottom-right. Pointer events handled by
          useResize; real-time size propagates via liveSize so the
          widget visibly grows during resize. */}
      <button
        type="button"
        data-slot="focus-widget-resize"
        aria-label="Resize widget"
        onPointerDown={resize.onPointerDown}
        className={cn(
          "absolute bottom-1 right-1 z-10 flex h-5 w-5 cursor-nwse-resize items-center justify-center rounded",
          "bg-surface-raised/80 text-content-muted",
          "opacity-0 group-hover:opacity-100 transition-opacity duration-arrive ease-settle",
          "group-data-[chrome-active=true]:opacity-100",
          "hover:bg-brass-subtle hover:text-content-strong",
          "focus-ring-brass",
        )}
      >
        <ArrowDownRight className="h-3 w-3" />
      </button>
    </div>
  )
}
