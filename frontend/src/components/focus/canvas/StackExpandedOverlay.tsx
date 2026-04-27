/**
 * StackExpandedOverlay — tap-to-expand floating panel for stack
 * mode widgets. Phase A Session 3.7.
 *
 * Bespoke (not a nested base-ui Dialog) — renders as a sibling of
 * Dialog.Popup inside the Focus portal, positioned center-overlay
 * with a subtle backdrop that dims the stack but preserves
 * visibility (user sees stack context).
 *
 * Dismiss:
 *   - Outside-click on backdrop
 *   - Tap the widget itself (toggle collapse)
 *   - Esc key
 *
 * Transition: CSS scale 0.96 → 1.0 + fade via `--duration-arrive`
 * + `--ease-settle` on enter; reverse on exit. Spring physics
 * deferred per PLATFORM_QUALITY_BAR.md 'Almost But Not Quite'.
 */

import { useEffect } from "react"

import type { WidgetId, WidgetState } from "@/contexts/focus-registry"
import { cn } from "@/lib/utils"

import { getWidgetRenderer } from "./widget-renderers"


interface StackExpandedOverlayProps {
  widgetId: WidgetId
  state: WidgetState
  onDismiss: () => void
}


export function StackExpandedOverlay({
  widgetId,
  state,
  onDismiss,
}: StackExpandedOverlayProps) {
  // Phase 4.3b.3 — dispatch by widgetType. The expanded view renders
  // the same widget the StackRail tile shows, just at a larger size.
  //
  // Widget Library Phase W-1 — Section 12.5: stack-expanded surface
  // is full reveal of the stack tile (canvas-tier register); pass
  // surface="focus_canvas". The widget instance carries the same
  // variant_id as the stack tile (one widget per layout slot;
  // expanded view re-renders with the canvas-tier surface flag).
  const Renderer = getWidgetRenderer(state.widgetType, state.variant_id)
  // Esc dismisses.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation() // don't let Focus handler also fire
        onDismiss()
      }
    }
    window.addEventListener("keydown", onKey, { capture: true })
    return () => window.removeEventListener("keydown", onKey, { capture: true })
  }, [onDismiss])

  return (
    <>
      {/* Subtle backdrop — dims the stack at lower opacity than
          the Focus backdrop, preserving stack context visibility. */}
      <button
        type="button"
        data-slot="focus-stack-expanded-backdrop"
        aria-label="Dismiss expanded widget"
        onClick={onDismiss}
        className={cn(
          "pointer-events-auto fixed inset-0",
          "bg-black/20 supports-backdrop-filter:backdrop-blur-sm",
          "animate-in fade-in-0 duration-arrive ease-settle",
          "cursor-default",
        )}
        style={{ zIndex: "var(--z-focus)" }}
      />

      {/* Floating expanded widget — centered within core area
          (approximated as center of viewport). Capped at sensible
          full-size; tap to toggle collapse. */}
      <div
        data-slot="focus-stack-expanded"
        className={cn(
          "pointer-events-auto fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2",
          "rounded-md border border-border-subtle bg-surface-elevated shadow-level-3",
          "animate-in fade-in-0 zoom-in-95 duration-arrive ease-settle",
          "overflow-hidden",
        )}
        style={{
          zIndex: "var(--z-focus)",
          width: "min(800px, 90vw)",
          height: "min(600px, 85vh)",
        }}
        onClick={onDismiss}
      >
        <Renderer
          widgetId={widgetId}
          variant_id={state.variant_id}
          surface="focus_canvas"
        />
      </div>
    </>
  )
}
