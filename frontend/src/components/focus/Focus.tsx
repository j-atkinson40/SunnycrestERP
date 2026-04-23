/**
 * Focus — the Decide primitive's render surface.
 *
 * Session 1 scaffolding. Implemented atop `@base-ui/react/dialog` per
 * PLATFORM_ARCHITECTURE.md §5.X (Implementation Foundation). The
 * Dialog primitive provides focus trap, ESC handling, aria-modal,
 * backdrop-click dismiss, and portal rendering for free; Focus layers
 * the specialized chrome (full-screen backdrop with heavier blur,
 * anchored core container, later sessions: push-back scale on the
 * underlying app, free-form canvas, pins, chat) on top.
 *
 * Session 1 render surface:
 *   - Full-viewport backdrop: bg-black/40 + backdrop-blur-md (matches
 *     overlay-family canonical scrim from Dialog.tsx, but heavier
 *     blur — 12px vs Dialog's 4px — per push-back signal requirement
 *     PA §5.2).
 *   - Anchored core: centered, bg-surface-raised, border-border-subtle,
 *     rounded-lg (12px, matches Dialog overlay-family radius), shadow-
 *     level-3 (heavier than Dialog's level-2 — Focus is floating
 *     further above the page).
 *   - Placeholder content: Session 2 dispatches into core modes (Kanban,
 *     single-record, edit canvas, triage queue, matrix).
 *
 * Animation:
 *   - Enter: duration-arrive + ease-settle + animate-in + fade-in-0 +
 *     zoom-in-95 (matches Dialog overlay-family pattern).
 *   - Exit:  duration-settle + ease-gentle + animate-out + fade-out-0 +
 *     zoom-out-95 (same).
 *
 * Push-back scale on underlying app (PA §5.2 signal):
 *   Deferred from Session 1 — CSS `transform: scale` creates a new
 *   containing block for fixed descendants on Safari and some
 *   Chromium builds, which would break DotNav + ModeToggle (both are
 *   fixed-positioned in the sidebar/header). Backdrop blur alone
 *   provides the push-back feeling for Session 1. Revisit Session 2
 *   with a scoped wrapper element that does not contain the fixed UI.
 *
 * Z-index:
 *   Uses `--z-focus` (100) via Tailwind arbitrary-value utility. See
 *   DESIGN_LANGUAGE.md §9 Layering tokens + styles/tokens.css.
 *
 * Accessibility inherited from base-ui Dialog:
 *   - role="dialog" + aria-modal="true" on Popup
 *   - Focus trap: Tab cycles within Popup
 *   - ESC dismisses
 *   - Focus returned to triggering element on close
 */

"use client"

import { Dialog as DialogPrimitive } from "@base-ui/react/dialog"

import { useFocus } from "@/contexts/focus-context"
import { cn } from "@/lib/utils"
import { Canvas } from "./canvas/Canvas"
import { computeCoreRect } from "./canvas/geometry"
import { useViewportTier } from "./canvas/useViewportTier"
import { ModeDispatcher } from "./mode-dispatcher"


export function Focus() {
  const { currentFocus, close } = useFocus()
  const isOpen = currentFocus !== null

  // Session 3.7 — tier-aware core sizing. Must match geometry.ts
  // `computeCoreRect` exactly, since findOpenZone + drag-end use it
  // to determine forbidden zones. Canvas tier reserves 100px on each
  // side for widgets; stack tier reserves right-rail; icon tier
  // fills viewport minus small padding.
  //
  // Session 3.7 post-verification fix: pass widgets to useViewportTier
  // so content-aware tier detection runs here too. Canvas + Focus
  // must agree on tier — otherwise Popup would size as canvas while
  // Canvas renders StackRail (mismatched chrome vs content).
  const widgets = currentFocus?.layoutState?.widgets ?? {}
  const viewport = useViewportTier(widgets)
  const coreRect = computeCoreRect(
    viewport.tier,
    viewport.width,
    viewport.height,
  )

  return (
    <DialogPrimitive.Root
      open={isOpen}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) close()
      }}
    >
      <DialogPrimitive.Portal>
        <DialogPrimitive.Backdrop
          data-slot="focus-backdrop"
          className={cn(
            "fixed inset-0 isolate",
            "bg-black/40 supports-backdrop-filter:backdrop-blur-md",
            // Enter animation — matches overlay-family Dialog.tsx
            "transition-opacity duration-arrive ease-settle",
            "data-open:animate-in data-open:fade-in-0",
            "data-closed:animate-out data-closed:fade-out-0",
            "data-closed:duration-settle data-closed:ease-gentle",
          )}
          style={{ zIndex: "var(--z-focus)" }}
        />
        <DialogPrimitive.Popup
          data-slot="focus-core"
          data-focus-tier={viewport.tier}
          aria-modal="true"
          aria-label={
            currentFocus ? `Focus: ${currentFocus.id}` : "Focus"
          }
          className={cn(
            // Positioning — anchored from coreRect (tier-aware).
            "fixed",
            // Chrome — anchored core above backdrop
            "bg-surface-raised rounded-lg shadow-level-3",
            // Content — inner padding generous per DESIGN_LANGUAGE §5
            "p-6 overflow-auto",
            // Typography + focus reset
            "font-plex-sans text-body text-content-base outline-none",
            // Enter / exit KEYFRAME animation — matches overlay-family
            // Dialog. `animate-in`/`animate-out` use CSS animation,
            // not transition, so `transition-none` below doesn't
            // affect them.
            "duration-arrive ease-settle",
            "data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95",
            "data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
            "data-closed:duration-settle data-closed:ease-gentle",
            // Session 3.8.2 — explicit transition-none on layout props.
            // Without this, `duration-arrive` sets transition-duration
            // to 0.4s and the default transition-property is `all`, so
            // left/top/width/height would still transition over 400ms
            // on every viewport change — the transition-lag problem
            // that made resize feel choppy. Setting transition-property
            // to none disables CSS transitions entirely on this element
            // while leaving the keyframe animate-in/animate-out
            // animations untouched (they're `animation`, not
            // `transition`). Core follows viewport synchronously per-
            // frame, macOS-Finder-style. Tier-boundary visual
            // continuity is carried by the tier-renderer opacity
            // crossfade in Canvas.tsx.
            "transition-none",
          )}
          style={{
            zIndex: "var(--z-focus)",
            left: coreRect.x,
            top: coreRect.y,
            width: coreRect.width,
            height: coreRect.height,
          }}
        >
          {currentFocus && <ModeDispatcher focusId={currentFocus.id} />}
        </DialogPrimitive.Popup>
        {/* Phase A Session 3 — Canvas hosts widgets, stack rail, and
            icon around the anchored core. Canvas has pointer-events:
            none on its wrapper so backdrop clicks still reach the
            Backdrop; active subtrees re-enable pointer-events via the
            Session 3.8 crossfade wrapper's data-active gating.

            Session 3.8.1 fix — Canvas renders AFTER Popup in DOM so
            it paints ON TOP of the core. This fixes:

              • Issue 3 — icon button hidden behind core in icon tier
                (core fills viewport; icon sat behind at same z-index).
              • Issue 2 — stack rail appearing "under" core during
                stack↔canvas transitions (fading stack was rendered in
                stale position; growing core covered it at same z-index,
                making the fade look like the rail was dropping behind
                the core instead of fading out cleanly).

            Both were expressions of the same stacking-context bug:
            Popup was later in DOM than Canvas, so at equal z-index it
            won paint order. Swapping the DOM order puts accessories
            (widgets / stack / icon) in front of core — correct for
            every tier (icon floats over core by design; stack and
            canvas widgets don't geometrically overlap core in final
            state but need to paint above during transition).

            Canvas still a SIBLING of Dialog.Popup (not parent) —
            Popup needs its own pointer-events to remain interactive,
            and @dnd-kit's DndContext reaches useDraggable consumers
            via React context regardless of DOM position. */}
        <Canvas />
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
