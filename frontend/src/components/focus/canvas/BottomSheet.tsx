/**
 * BottomSheet — iOS-style bottom sheet for icon-mode widget stack.
 * Phase A Session 3.7.
 *
 * Slides up from viewport bottom when the IconButton is tapped.
 * Contains a scrollable vertical stack of widgets; tap a widget to
 * expand to full-screen widget view; swipe down on the drag handle
 * (or anywhere on the sheet) to dismiss back to icon-mode idle.
 *
 * Swipe gesture: useSwipeDismiss hook (PointerEvent-based, same
 * pattern as useResize). Threshold 150px vertical drag → dismiss.
 * No rubber-band physics this session — architecture-first, polish
 * deferred to mobile polish session.
 *
 * Drag handle: small horizontal bar at top, iOS pattern. Provides
 * the explicit gesture target — tapping anywhere else on the sheet
 * does NOT initiate swipe (widget content is interactive).
 */

import { useEffect, useState } from "react"

import type { WidgetId, WidgetState } from "@/contexts/focus-registry"
import { cn } from "@/lib/utils"

import { getWidgetRenderer } from "./widget-renderers"
import { useSwipeDismiss } from "./useSwipeDismiss"


interface BottomSheetProps {
  widgets: Record<WidgetId, WidgetState>
  onDismiss: () => void
}


export function BottomSheet({ widgets, onDismiss }: BottomSheetProps) {
  const entries = Object.entries(widgets)
  const [expandedWidget, setExpandedWidget] = useState<WidgetId | null>(null)

  const swipe = useSwipeDismiss({ onDismiss, threshold: 150 })

  // Esc dismisses sheet (or expanded widget if open).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        if (expandedWidget) {
          e.stopPropagation()
          setExpandedWidget(null)
        } else {
          e.stopPropagation()
          onDismiss()
        }
      }
    }
    window.addEventListener("keydown", onKey, { capture: true })
    return () =>
      window.removeEventListener("keydown", onKey, { capture: true })
  }, [expandedWidget, onDismiss])

  return (
    <>
      {/* Backdrop — full viewport dim. Click dismisses. */}
      <button
        type="button"
        data-slot="focus-bottom-sheet-backdrop"
        aria-label="Dismiss widget sheet"
        onClick={onDismiss}
        className={cn(
          "pointer-events-auto fixed inset-0",
          "bg-black/30",
          "animate-in fade-in-0 duration-arrive ease-settle",
          "cursor-default",
        )}
        style={{ zIndex: "var(--z-focus)" }}
      />

      {/* Sheet — slides up from bottom. transform is driven by
          useSwipeDismiss during drag for visual feedback (translate
          down with finger). Reset to 0 on release if under threshold. */}
      <div
        data-slot="focus-bottom-sheet"
        role="dialog"
        aria-label="Widgets"
        className={cn(
          "pointer-events-auto fixed inset-x-0 bottom-0",
          "rounded-t-xl bg-surface-raised border-t border-border-subtle shadow-level-3",
          "flex flex-col",
          "animate-in slide-in-from-bottom duration-arrive ease-settle",
        )}
        style={{
          zIndex: "var(--z-focus)",
          height: "90vh",
          transform: `translateY(${swipe.offsetY}px)`,
          transition: swipe.isDragging
            ? "none"
            : "transform var(--duration-settle) var(--ease-gentle)",
        }}
      >
        {/* Drag handle — iOS pattern. Horizontal bar at top.
            onPointerDown initiates swipe-down-dismiss gesture. */}
        <div
          data-slot="focus-bottom-sheet-handle"
          role="button"
          aria-label="Drag handle — swipe down to dismiss"
          tabIndex={-1}
          onPointerDown={swipe.onPointerDown}
          className={cn(
            "flex flex-none items-center justify-center py-3",
            "cursor-grab active:cursor-grabbing",
            "touch-none",
          )}
          // touch-action: none prevents native vertical scroll from
          // hijacking the swipe gesture on mobile.
          style={{ touchAction: "none" }}
        >
          <div className="h-1.5 w-10 rounded-full bg-border-base" />
        </div>

        {/* Scrollable widget list — full-width tiles. */}
        <div
          data-slot="focus-bottom-sheet-content"
          className="flex-1 overflow-y-auto px-4 pb-6"
        >
          {entries.map(([id, state]) => {
            // Phase 4.3b.3 — dispatch by widgetType (registered renderers
            // OR MockSavedViewWidget fallback for back-compat).
            const Renderer = getWidgetRenderer(state.widgetType)
            return (
              <div
                key={id}
                data-slot="focus-bottom-sheet-tile"
                data-widget-id={id}
                className={cn(
                  "mb-3 cursor-pointer overflow-hidden",
                  "rounded-md border border-border-subtle bg-surface-elevated",
                  "transition-transform duration-quick ease-settle",
                  "hover:bg-brass-subtle/20 active:scale-[0.98]",
                )}
                style={{ height: state.position.height }}
                role="button"
                tabIndex={0}
                aria-label="Expand widget"
                onClick={() => setExpandedWidget(id as WidgetId)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault()
                    setExpandedWidget(id as WidgetId)
                  }
                }}
              >
                <Renderer widgetId={id} />
              </div>
            )
          })}
        </div>
      </div>

      {/* Full-screen expanded widget view — when user taps a tile,
          the widget expands to fill the viewport above the sheet.
          Tap outside or Esc to collapse back to sheet. */}
      {expandedWidget && (
        <>
          <button
            type="button"
            data-slot="focus-bottom-sheet-expanded-backdrop"
            aria-label="Collapse widget"
            onClick={() => setExpandedWidget(null)}
            className={cn(
              "pointer-events-auto fixed inset-0",
              "bg-black/50 supports-backdrop-filter:backdrop-blur-sm",
              "animate-in fade-in-0 duration-arrive ease-settle",
              "cursor-default",
            )}
            style={{ zIndex: "var(--z-focus)" }}
          />
          <div
            data-slot="focus-bottom-sheet-expanded"
            className={cn(
              "pointer-events-auto fixed inset-2",
              "rounded-lg border border-border-subtle bg-surface-elevated shadow-level-3",
              "animate-in fade-in-0 zoom-in-95 duration-arrive ease-settle",
              "overflow-hidden",
            )}
            style={{ zIndex: "var(--z-focus)" }}
            onClick={() => setExpandedWidget(null)}
          >
            {(() => {
              // Phase 4.3b.3 — render the expanded widget's registered
              // type (or MockSavedViewWidget fallback).
              const Renderer = getWidgetRenderer(
                widgets[expandedWidget]?.widgetType,
              )
              return <Renderer widgetId={expandedWidget} />
            })()}
          </div>
        </>
      )}
    </>
  )
}
