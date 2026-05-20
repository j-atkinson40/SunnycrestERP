/**
 * FocusBuilderSaveIndicator — four-state polish on the top-bar
 * auto-save readout (sub-arc F-5).
 *
 * Locked decision (F-5 #2). Reads existing hook surface
 * (`isDirty`, `isSaving`, `error`, `lastSavedAt`) — NO hook changes.
 *
 * State precedence (top to bottom):
 *   - error             → "Save failed · Retry"    (brass-accent;
 *                                                    Retry triggers
 *                                                    onRetry)
 *   - isSaving          → "Saving…"
 *   - isDirty           → "Unsaved changes"
 *   - lastSavedAt       → "Saved · Xs ago"
 *   - none (empty)      → render null
 *
 * Behavior pipeline (debounce + save + version-bump + URL recovery)
 * lives in useFocusTemplateDraft + useFocusCoreDraft and is
 * UNCHANGED. This component polishes the SURFACE only.
 */
import * as React from "react"

import { cn } from "@/lib/utils"


export type SaveIndicatorState =
  | { kind: "empty" }
  | { kind: "saved"; lastSavedAt: Date }
  | { kind: "saving" }
  | { kind: "unsaved" }
  | { kind: "failed" }


export interface FocusBuilderSaveIndicatorProps {
  isDirty: boolean
  isSaving: boolean
  error: string | null
  lastSavedAt: Date | null
  /** Re-trigger save on Retry click (failed state). */
  onRetry: () => void
}


function relativeTime(when: Date): string {
  const secs = Math.max(0, Math.round((Date.now() - when.getTime()) / 1000))
  if (secs < 5) return "just now"
  if (secs < 60) return `${secs}s ago`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  return `${hrs}h ago`
}


/**
 * Pure mapping: hook-surface fields → display state. Exported for
 * unit testability.
 */
export function deriveSaveIndicatorState(input: {
  isDirty: boolean
  isSaving: boolean
  error: string | null
  lastSavedAt: Date | null
}): SaveIndicatorState {
  if (input.error) return { kind: "failed" }
  if (input.isSaving) return { kind: "saving" }
  if (input.isDirty) return { kind: "unsaved" }
  if (input.lastSavedAt) return { kind: "saved", lastSavedAt: input.lastSavedAt }
  return { kind: "empty" }
}


export function FocusBuilderSaveIndicator({
  isDirty,
  isSaving,
  error,
  lastSavedAt,
  onRetry,
}: FocusBuilderSaveIndicatorProps) {
  // Force-refresh "saved Xs ago" every 5 seconds so the relative
  // time doesn't go stale between actual saves.
  const [, force] = React.useReducer((n: number) => n + 1, 0)
  React.useEffect(() => {
    if (!lastSavedAt || isDirty || isSaving || error) return
    const id = setInterval(force, 5000)
    return () => clearInterval(id)
  }, [lastSavedAt, isDirty, isSaving, error])

  const state = deriveSaveIndicatorState({ isDirty, isSaving, error, lastSavedAt })

  if (state.kind === "empty") return null

  if (state.kind === "failed") {
    return (
      <span
        data-testid="save-indicator"
        data-state="failed"
        className="flex items-center gap-1.5 text-[11px] text-[color:var(--accent)]"
        aria-live="polite"
      >
        Save failed ·{" "}
        <button
          type="button"
          data-testid="save-indicator-retry"
          onClick={onRetry}
          className={cn(
            "underline underline-offset-2",
            "hover:text-[color:var(--accent-strong,var(--accent))]",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[color:var(--accent)] rounded-sm",
          )}
        >
          Retry
        </button>
      </span>
    )
  }

  if (state.kind === "saving") {
    return (
      <span
        data-testid="save-indicator"
        data-state="saving"
        className="text-[11px] text-[color:var(--content-muted)]"
        aria-live="polite"
      >
        Saving…
      </span>
    )
  }

  if (state.kind === "unsaved") {
    return (
      <span
        data-testid="save-indicator"
        data-state="unsaved"
        className="text-[11px] text-[color:var(--content-muted)]"
        aria-live="polite"
      >
        Unsaved changes
      </span>
    )
  }

  // saved
  return (
    <span
      data-testid="save-indicator"
      data-state="saved"
      className="text-[11px] text-[color:var(--content-muted)]"
    >
      Saved · {relativeTime(state.lastSavedAt)}
    </span>
  )
}

export default FocusBuilderSaveIndicator
