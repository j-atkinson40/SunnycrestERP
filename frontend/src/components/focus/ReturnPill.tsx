/**
 * ReturnPill — UI for resuming a just-closed Focus.
 *
 * Session 1 scaffolding: renders while `lastClosedFocus !== null` and
 * no Focus is currently open. Click the pill body to re-enter the
 * just-closed Focus; click the X to dismiss without re-entering.
 *
 * Session 4 adds:
 *   - 15-second countdown (via useReturnPillCountdown)
 *   - Countdown bar (2px tall, accent) at bottom of pill
 *   - Hover pauses countdown; mouse-leave resumes
 *   - Tab visibility return re-arms to full 15s
 *   - onExpire auto-dismisses the pill
 *
 * The width of the countdown bar animates via a CSS transition on
 * `width` with cubic-bezier(0.32, 0.72, 0, 1) easing — approximates
 * spring decay feel without a physics library. Duration matches
 * the hook's tick loop (100ms per update) so the bar moves smoothly.
 *
 * Visual treatment (unchanged from Session 1):
 *   - Fixed, bottom-center of viewport.
 *   - Pill shape — rounded-full, compact, surface-raised chrome.
 *   - z-index: --z-elevated (below --z-focus).
 */

"use client"

import { ArrowLeft, X } from "lucide-react"

import { useFocus } from "@/contexts/focus-context"
import { cn } from "@/lib/utils"

import { useReturnPillCountdown } from "./useReturnPillCountdown"


export function ReturnPill() {
  const { currentFocus, lastClosedFocus, open, dismissReturnPill } = useFocus()

  const shouldRender = currentFocus === null && lastClosedFocus !== null

  // resetKey derived from the identity of the closed Focus + when it
  // closed. Changes when a different Focus closes OR when the same
  // Focus closes again after re-opening; both should re-arm per
  // Session 4 spec.
  const resetKey = shouldRender && lastClosedFocus !== null
    ? `${lastClosedFocus.id}:${lastClosedFocus.openedAt.getTime()}`
    : null

  const { remainingMs, totalMs, onHoverStart, onHoverEnd } =
    useReturnPillCountdown({
      onExpire: dismissReturnPill,
      resetKey,
    })

  if (!shouldRender || lastClosedFocus === null) {
    return null
  }

  const target = lastClosedFocus
  const barWidthPct = Math.max(0, (remainingMs / totalMs) * 100)

  return (
    <div
      data-slot="focus-return-pill"
      data-testid="focus-return-pill"
      role="status"
      aria-live="polite"
      onPointerEnter={onHoverStart}
      onPointerLeave={onHoverEnd}
      className={cn(
        // Positioning — fixed bottom-center with small offset
        "fixed bottom-4 left-1/2 -translate-x-1/2",
        // Layout — horizontal pill
        "flex flex-col",
        // Chrome — overlay-family treatment
        "bg-surface-raised border border-border-subtle rounded-full shadow-level-2",
        // Pill overflow-hidden so the countdown bar rounds with the pill corners.
        "overflow-hidden",
        // Enter animation — slide up + fade in
        "animate-in slide-in-from-bottom-2 fade-in-0 duration-arrive ease-settle",
      )}
      style={{ zIndex: "var(--z-elevated)" }}
    >
      <div className="flex items-center gap-2 pl-3 pr-1 py-1">
        <button
          type="button"
          onClick={() => open(target.id, { params: target.params })}
          className={cn(
            "flex items-center gap-2 rounded-full px-2 py-1",
            "text-body-sm text-content-base",
            "hover:bg-accent-subtle focus-ring-accent",
            "transition-colors duration-quick",
          )}
          aria-label={`Return to ${target.id}`}
        >
          <ArrowLeft className="h-4 w-4 text-accent" />
          <span className="font-plex-sans">
            Return to{" "}
            <span className="font-medium text-content-strong">
              {target.id}
            </span>
          </span>
        </button>
        <button
          type="button"
          onClick={dismissReturnPill}
          className={cn(
            "flex h-6 w-6 items-center justify-center rounded-full",
            "text-content-muted",
            "hover:bg-accent-subtle hover:text-content-strong focus-ring-accent",
            "transition-colors duration-quick",
          )}
          aria-label="Dismiss return pill"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      {/* Countdown bar — 2px tall, accent, animates width over the
          tick interval. cubic-bezier(0.32, 0.72, 0, 1) gives a
          gentle spring-decay feel without a physics library. */}
      <div
        data-slot="focus-return-pill-countdown-track"
        className="h-0.5 bg-border-subtle/40"
        aria-hidden="true"
      >
        <div
          data-slot="focus-return-pill-countdown-bar"
          data-testid="focus-return-pill-countdown-bar"
          className="h-full bg-accent"
          style={{
            width: `${barWidthPct}%`,
            transition: "width 100ms cubic-bezier(0.32, 0.72, 0, 1)",
          }}
        />
      </div>
    </div>
  )
}
