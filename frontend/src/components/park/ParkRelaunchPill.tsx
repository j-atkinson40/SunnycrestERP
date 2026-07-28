/**
 * ParkRelaunchPill — the grace-window relaunch affordance (S-5).
 *
 * The §5.6 return-pill pattern, pointed at the PARK session instead of a
 * single Focus. On DELIBERATE exit park stashes the working set; this
 * pill offers to relaunch it for a grace window, then it evaporates
 * (client-held — a hard refresh loses it, per the ephemerality spec).
 * The difference from the Focus pill: it relaunches a SESSION OF N
 * tablets, not one Focus. The countdown hook is reused verbatim.
 */

import { RotateCcw } from "lucide-react"

import { useReturnPillCountdown } from "@/components/focus/useReturnPillCountdown"
import { usePark } from "@/contexts/park-context"
import { cn } from "@/lib/utils"

export function ParkRelaunchPill() {
  const { lastClosedSession, relaunchSession, clearLastClosed } = usePark()

  const count = lastClosedSession?.tablets.length ?? 0
  const resetKey =
    lastClosedSession?.tablets.map((t) => t.tabletId).join("|") ?? null

  const { remainingMs, totalMs, onHoverStart, onHoverEnd } =
    useReturnPillCountdown({ onExpire: clearLastClosed, resetKey })

  if (!lastClosedSession) return null

  const pct = Math.max(0, Math.min(100, (remainingMs / totalMs) * 100))

  return (
    <div
      data-slot="park-relaunch-pill"
      className="fixed bottom-4 left-1/2 z-[115] -translate-x-1/2"
      onPointerEnter={onHoverStart}
      onPointerLeave={onHoverEnd}
    >
      <button
        type="button"
        onClick={relaunchSession}
        data-testid="park-relaunch"
        className={cn(
          "relative flex items-center gap-2 overflow-hidden rounded-full border border-border-subtle bg-surface-raised px-4 py-2 shadow-level-2 [background-image:var(--panel-gradient-raised)]",
          "text-body-sm text-content-strong",
          "focus-ring-accent",
        )}
      >
        <RotateCcw className="size-3.5 text-content-muted" />
        <span>
          Working set closed ·{" "}
          <span className="font-medium tabular-nums">{count}</span>{" "}
          {count === 1 ? "tablet" : "tablets"}
        </span>
        <span className="font-medium text-accent">Relaunch</span>
        {/* Countdown bar — accent, bottom edge. */}
        <span
          aria-hidden
          className="absolute bottom-0 left-0 h-0.5 bg-accent"
          style={{
            width: `${pct}%`,
            transition: "width 100ms cubic-bezier(0.32, 0.72, 0, 1)",
          }}
        />
      </button>
    </div>
  )
}
