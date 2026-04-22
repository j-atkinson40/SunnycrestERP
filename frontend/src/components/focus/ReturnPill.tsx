/**
 * ReturnPill — UI for resuming a just-closed Focus.
 *
 * Session 1 scaffolding: renders while `lastClosedFocus !== null`
 * and no Focus is currently open. Click the pill body to re-enter
 * the just-closed Focus; click the X to dismiss the pill without
 * re-entering.
 *
 * Session 1 does NOT include:
 *   - 15-second countdown bar (Session 4)
 *   - Hover-to-pause countdown (Session 4)
 *   - Re-arm-on-state-change semantics (Session 4)
 *   - Cmd+K history integration (Session 4+)
 *
 * Visual treatment:
 *   - Fixed, bottom-center of viewport.
 *   - Pill shape — rounded-full, compact height, surface-raised chrome.
 *   - Small brass back-arrow icon + "Return to <id>" label + dismiss X.
 *   - Shadow-level-2 + border-border-subtle — overlay-family chrome.
 *   - z-index: --z-elevated (below --z-focus so a newly-opened Focus
 *     renders above the pill — shouldn't happen in practice because
 *     opening a Focus clears lastClosedFocus, but defensive).
 */

"use client"

import { ArrowLeft, X } from "lucide-react"

import { useFocus } from "@/contexts/focus-context"
import { cn } from "@/lib/utils"


export function ReturnPill() {
  const { currentFocus, lastClosedFocus, open, dismissReturnPill } = useFocus()

  // Render only when there is a recently-closed Focus AND no Focus
  // is currently open.
  if (currentFocus !== null || lastClosedFocus === null) {
    return null
  }

  const target = lastClosedFocus

  return (
    <div
      data-slot="focus-return-pill"
      role="status"
      aria-live="polite"
      className={cn(
        // Positioning — fixed bottom-center with small offset
        "fixed bottom-4 left-1/2 -translate-x-1/2",
        // Layout — horizontal pill
        "flex items-center gap-2",
        "pl-3 pr-1 py-1",
        // Chrome — overlay-family treatment
        "bg-surface-raised border border-border-subtle rounded-full shadow-level-2",
        // Enter animation — slide up + fade in
        "animate-in slide-in-from-bottom-2 fade-in-0 duration-arrive ease-settle",
      )}
      style={{ zIndex: "var(--z-elevated)" }}
    >
      <button
        type="button"
        onClick={() => open(target.id, { params: target.params })}
        className={cn(
          "flex items-center gap-2 rounded-full px-2 py-1",
          "text-body-sm text-content-base",
          "hover:bg-brass-subtle focus-ring-brass",
          "transition-colors duration-quick",
        )}
        aria-label={`Return to ${target.id}`}
      >
        <ArrowLeft className="h-4 w-4 text-brass" />
        <span className="font-plex-sans">
          Return to{" "}
          <span className="font-medium text-content-strong">{target.id}</span>
        </span>
      </button>
      <button
        type="button"
        onClick={dismissReturnPill}
        className={cn(
          "flex h-6 w-6 items-center justify-center rounded-full",
          "text-content-muted",
          "hover:bg-brass-subtle hover:text-content-strong focus-ring-brass",
          "transition-colors duration-quick",
        )}
        aria-label="Dismiss return pill"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  )
}
