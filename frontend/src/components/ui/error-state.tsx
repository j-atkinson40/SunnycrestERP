/**
 * ErrorState — DESIGN_LANGUAGE §18.1 error triad.
 *
 * A pane-level error answers three questions, in the user's language:
 *   1. WHAT HAPPENED — plain language, specific ("Couldn't load the
 *      workflows"), never a raw API string or a status code as headline.
 *   2. WHAT SURVIVED — the reassurance line ("Your draft is intact.").
 *      State preservation is the platform's promise; say it.
 *   3. WHAT TO DO — a Retry affordance or the path forward.
 *
 * Raw API strings never reach the pane as primary copy — they go behind
 * the collapsed "Details" disclosure (`details` prop) for support.
 *
 * Tone: calm, unblaming, no exclamation, no theatrical apology.
 *
 * Builds on the InlineError visual recipe (status-error-muted surface,
 * AlertCircle, ghost Retry) extended with the triad slots + disclosure.
 * InlineError remains the narrow field/panel-scoped primitive; ErrorState
 * is the §18.1 pane-level composition.
 */
import * as React from "react"
import { AlertCircle, ChevronDown, RotateCw } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

export interface ErrorStateProps {
  /** WHAT HAPPENED — plain language, specific. Never a raw API string. */
  what: string
  /** WHAT SURVIVED — the reassurance line (e.g. "Your draft is intact."). */
  survived?: string
  /** WHAT TO DO — the retry affordance. Omit for non-retryable errors. */
  onRetry?: () => void | Promise<void>
  retryLabel?: string
  isRetrying?: boolean
  /** The raw API/string detail — rendered ONLY behind the collapsed
      "Details" disclosure, never as primary copy. */
  details?: string | null
  className?: string
  "data-testid"?: string
}

export function ErrorState({
  what,
  survived,
  onRetry,
  retryLabel = "Try again",
  isRetrying = false,
  details,
  className,
  ...props
}: ErrorStateProps) {
  const [detailsOpen, setDetailsOpen] = React.useState(false)
  return (
    <div
      role="alert"
      aria-live="polite"
      data-testid={props["data-testid"] ?? "error-state"}
      className={cn(
        "flex flex-col gap-2 rounded-md border border-status-error/40 bg-status-error-muted p-4 font-sans text-body-sm text-status-error",
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <AlertCircle size={16} strokeWidth={1.5} className="mt-0.5 shrink-0" aria-hidden="true" />
        <div className="flex-1 space-y-1">
          <div className="font-medium" data-testid="error-state-what">
            {what}
          </div>
          {survived ? (
            <div className="opacity-80" data-testid="error-state-survived">
              {survived}
            </div>
          ) : null}
        </div>
        {onRetry ? (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => void onRetry()}
            disabled={isRetrying}
            className="-my-1 shrink-0"
            data-testid="error-state-retry"
          >
            <RotateCw
              size={14}
              className={cn(isRetrying && "motion-safe:animate-spin")}
              aria-hidden="true"
            />
            <span className="ml-1.5">{retryLabel}</span>
          </Button>
        ) : null}
      </div>
      {details ? (
        <div>
          <button
            type="button"
            onClick={() => setDetailsOpen((v) => !v)}
            aria-expanded={detailsOpen}
            className="flex items-center gap-1 text-caption opacity-70 hover:opacity-100"
            data-testid="error-state-details-toggle"
          >
            <ChevronDown
              size={12}
              className={cn(
                "transition-transform duration-quick ease-settle",
                detailsOpen && "rotate-180",
              )}
              aria-hidden="true"
            />
            Details
          </button>
          {detailsOpen ? (
            <pre
              className="mt-1 overflow-x-auto rounded-sm bg-surface-sunken p-2 font-plex-mono text-micro text-content-muted"
              data-testid="error-state-details"
            >
              {details}
            </pre>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
