/**
 * Bridgeable Alert — Aesthetic Arc Session 3.
 *
 * Platform-level banner primitive for status-rendering surfaces
 * (dismissible page banners, section-level status messages, feature
 * nudges). Net-new component; no prior shadcn Alert existed.
 *
 * **Distinct from `InlineError`:**
 *   - **Alert** is the general-purpose page/section-level banner
 *     with 5 variants (info/success/warning/error/neutral) and
 *     optional title + description + dismissible + action button.
 *     Examples: accounting reminder banner, KB coaching banner,
 *     feature-nudge banners.
 *   - **InlineError** is panel-scoped recoverable-error UX with a
 *     retry affordance. Examples: "Couldn't load this view — try
 *     again" inside a card or panel. Has a narrower shape and an
 *     onRetry callback contract.
 *
 * Tokens per DESIGN_LANGUAGE.md §3 + §6:
 *   - Status variants pair `bg-status-{X}-muted` (muted tint) with
 *     `text-status-{X}` (saturation) + `border-l-4 border-status-{X}`
 *     left-accent bar. Title uses same saturation; description drops
 *     one notch via opacity.
 *   - Neutral variant uses `bg-surface-elevated` + `text-content-base`
 *     + `border border-border-subtle`.
 *   - Dismiss button is Ghost-ish (transparent + brass-subtle hover)
 *     via inline className to avoid a full Button dependency + fit the
 *     compact Alert header height.
 *
 * Motion: subtle opacity-fade on mount/dismiss via `transition-opacity
 * duration-settle ease-settle`. Per §6 motion patterns.
 *
 * Accessibility: `role="alert"` + `aria-live="polite"` for non-urgent,
 * `aria-live="assertive"` auto-set on `variant="error"`. Dismiss
 * button has `aria-label="Dismiss"`.
 */

import * as React from "react";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Info,
  X,
  type LucideIcon,
} from "lucide-react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

export type AlertVariant =
  | "info"
  | "success"
  | "warning"
  | "error"
  | "neutral";

const alertVariants = cva(
  "group/alert relative flex items-start gap-3 rounded-md border-l-4 p-4 font-plex-sans text-body-sm transition-opacity duration-settle ease-settle",
  {
    variants: {
      variant: {
        info: "border-l-status-info bg-status-info-muted text-status-info",
        success:
          "border-l-status-success bg-status-success-muted text-status-success",
        warning:
          "border-l-status-warning bg-status-warning-muted text-status-warning",
        error:
          "border-l-status-error bg-status-error-muted text-status-error",
        neutral:
          "border-l-border-base bg-surface-elevated text-content-base",
      },
    },
    defaultVariants: {
      variant: "neutral",
    },
  },
);

const DEFAULT_ICONS: Record<AlertVariant, LucideIcon> = {
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  error: AlertCircle,
  neutral: Info,
};

export interface AlertProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof alertVariants> {
  icon?: LucideIcon | null;
  onDismiss?: () => void;
  dismissLabel?: string;
  "data-testid"?: string;
}

function Alert({
  className,
  variant = "neutral",
  icon,
  onDismiss,
  dismissLabel = "Dismiss",
  children,
  ...props
}: AlertProps) {
  // Resolve icon: explicit prop > default per variant > null (suppress).
  const ResolvedIcon =
    icon === null ? null : icon ?? DEFAULT_ICONS[variant ?? "neutral"];

  const live: "polite" | "assertive" =
    variant === "error" ? "assertive" : "polite";

  return (
    <div
      role="alert"
      aria-live={live}
      data-slot="alert"
      data-variant={variant}
      data-testid={props["data-testid"] ?? "alert"}
      className={cn(alertVariants({ variant }), className)}
      {...props}
    >
      {ResolvedIcon ? (
        <ResolvedIcon
          className="mt-0.5 h-4 w-4 shrink-0"
          aria-hidden="true"
        />
      ) : null}
      <div className="flex-1 space-y-1 min-w-0">{children}</div>
      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          aria-label={dismissLabel}
          className="-my-1 -mr-1 rounded-sm p-1 text-current opacity-70 hover:bg-brass-subtle hover:opacity-100 focus-ring-brass transition-opacity duration-quick ease-settle"
        >
          <X className="h-4 w-4" />
        </button>
      ) : null}
    </div>
  );
}

function AlertTitle({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-slot="alert-title"
      className={cn(
        "font-medium leading-none text-current",
        className,
      )}
      {...props}
    />
  );
}

function AlertDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-slot="alert-description"
      className={cn("text-body-sm text-current opacity-90", className)}
      {...props}
    />
  );
}

function AlertAction({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-slot="alert-action"
      className={cn("flex items-center gap-2 mt-2", className)}
      {...props}
    />
  );
}

export { Alert, AlertTitle, AlertDescription, AlertAction, alertVariants };
