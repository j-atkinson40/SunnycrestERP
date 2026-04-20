/**
 * Phase 7 — Shared InlineError component.
 *
 * One canonical presentation for recoverable errors surfaced inline on
 * arc surfaces. Replaces 4 ad-hoc variants audited (destructive-border
 * box, plain text, toast-only, muted text).
 *
 * The pattern: what happened + why (if actionable) + retry affordance.
 *
 * Composition:
 *   <InlineError
 *     message="Couldn't load this view."
 *     hint="Your filters may have expired."
 *     onRetry={() => reload()}
 *   />
 *
 * Use <ErrorBanner /> for top-level (page-level) errors; InlineError is
 * scoped to a panel / section.
 */

import * as React from "react";
import { AlertCircle, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface InlineErrorProps {
  message: string;
  hint?: React.ReactNode;
  onRetry?: () => void | Promise<void>;
  retryLabel?: string;
  isRetrying?: boolean;
  className?: string;
  size?: "default" | "sm";
  severity?: "error" | "warning";
  /** Test hook for Playwright. */
  "data-testid"?: string;
}

const SEVERITY_STYLES = {
  error: "border-destructive/40 bg-destructive/5 text-destructive",
  warning: "border-amber-500/40 bg-amber-500/5 text-amber-700 dark:text-amber-400",
};

export function InlineError({
  message,
  hint,
  onRetry,
  retryLabel = "Try again",
  isRetrying = false,
  className,
  size = "default",
  severity = "error",
  ...props
}: InlineErrorProps) {
  return (
    <div
      role="alert"
      aria-live="polite"
      data-testid={props["data-testid"] ?? "inline-error"}
      data-severity={severity}
      className={cn(
        "flex items-start gap-3 rounded-md border px-3",
        size === "sm" ? "py-2 text-xs" : "py-3 text-sm",
        SEVERITY_STYLES[severity],
        className,
      )}
    >
      <AlertCircle
        className={cn(
          "shrink-0",
          size === "sm" ? "h-3.5 w-3.5 mt-0.5" : "h-4 w-4 mt-0.5",
        )}
        aria-hidden="true"
      />
      <div className="flex-1 space-y-1">
        <div className="font-medium">{message}</div>
        {hint ? <div className="opacity-80">{hint}</div> : null}
      </div>
      {onRetry ? (
        <Button
          size={size === "sm" ? "sm" : "sm"}
          variant="ghost"
          onClick={() => void onRetry()}
          disabled={isRetrying}
          className="shrink-0 -my-1"
        >
          <RotateCw
            className={cn(
              "h-3.5 w-3.5",
              isRetrying && "motion-safe:animate-spin",
            )}
            aria-hidden="true"
          />
          <span className="ml-1.5">{retryLabel}</span>
        </Button>
      ) : null}
    </div>
  );
}
