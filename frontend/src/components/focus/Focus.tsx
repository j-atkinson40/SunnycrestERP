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


export function Focus() {
  const { currentFocus, close } = useFocus()
  const isOpen = currentFocus !== null

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
          aria-modal="true"
          aria-label={
            currentFocus ? `Focus: ${currentFocus.id}` : "Focus"
          }
          className={cn(
            // Positioning — centered in viewport
            "fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2",
            // Size — soft maximum on both axes per PA §5.1
            "w-[90vw] max-w-[1400px] h-[85vh] max-h-[900px]",
            // Chrome — anchored core above backdrop
            "bg-surface-raised rounded-lg shadow-level-3",
            // Content — inner padding generous per DESIGN_LANGUAGE §5
            "p-6 overflow-auto",
            // Typography + focus reset
            "font-plex-sans text-body text-content-base outline-none",
            // Enter / exit animation — matches overlay-family Dialog
            "duration-arrive ease-settle",
            "data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95",
            "data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
            "data-closed:duration-settle data-closed:ease-gentle",
          )}
          style={{ zIndex: "var(--z-focus)" }}
        >
          {currentFocus && <FocusPlaceholder id={currentFocus.id} />}
        </DialogPrimitive.Popup>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}


/**
 * Placeholder content for Session 1. Session 2 replaces this with
 * the anchored-core mode dispatcher (Kanban, single-record, edit
 * canvas, triage queue, matrix).
 */
function FocusPlaceholder({ id }: { id: string }) {
  return (
    <div className="flex h-full flex-col gap-4">
      <header className="flex flex-col gap-1">
        <p className="text-micro uppercase tracking-wider text-content-muted">
          Focus · scaffolding
        </p>
        <h2 className="text-h2 font-plex-serif text-content-strong">
          {id}
        </h2>
      </header>
      <div className="flex-1 rounded-md border border-dashed border-border-base bg-surface-sunken/40 p-6">
        <p className="text-body-sm text-content-muted">
          Anchored core placeholder. Session 2 adds core-mode dispatch
          (Kanban, single-record, edit canvas, triage queue, matrix).
          Session 3 adds the free-form canvas for pins. Session 5–6
          wires saved + context-aware + system-suggested pins. This
          page is intentionally bare in Session 1.
        </p>
      </div>
      <footer className="flex items-center gap-2 text-body-sm text-content-muted">
        <kbd className="rounded border border-border-subtle bg-surface-elevated px-2 py-0.5 font-plex-mono text-micro">
          Esc
        </kbd>
        <span>or click outside to dismiss</span>
      </footer>
    </div>
  )
}
