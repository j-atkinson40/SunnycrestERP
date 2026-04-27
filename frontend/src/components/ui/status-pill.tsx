/**
 * Bridgeable StatusPill — Aesthetic Arc Session 3.
 *
 * Pill-shaped inline status marker for lists, tables, detail panels.
 * Net-new primitive; replaces the ad-hoc `bg-muted text-muted-foreground`
 * pattern in `components/peek/renderers/_shared.tsx::StatusBadge` and
 * ~100 ad-hoc inline status renderings across the platform.
 *
 * **Distinct from `Badge` status variants:**
 *   - **StatusPill** = `rounded-full` pill for inline status markers
 *     in lists / tables / detail cards. Compact, recognizable by
 *     shape alone as "status." Takes a `status` string and auto-maps
 *     to the correct status family; unknown statuses render as
 *     neutral. Use this when you're rendering a workflow status, a
 *     case status, an order status, etc.
 *   - **Badge** with status variants = `rounded-sm` pill for
 *     general-purpose emphasis with flexible semantics (counts,
 *     labels, arbitrary tags). Use Badge when the meaning isn't
 *     strictly "what state is this record in."
 *
 * Status → family mapping (case-insensitive, underscore-tolerant):
 *   success  — approved / completed / active / paid / published /
 *              done / delivered / published / won
 *   warning  — pending / pending_review / in_progress / draft /
 *              scheduled / awaiting / on_hold / review
 *   error    — rejected / failed / voided / cancelled / overdue /
 *              error / expired
 *   info     — new / created / received / submitted / sent
 *   neutral  — anything unmapped (archived, inactive, unknown, …)
 *
 * Label rendering: underscores replaced with spaces, uppercased with
 * letter-spacing — reads as "TAG" not "tag_name." Overridable via
 * `label` prop for custom display.
 *
 * Sizes:
 *   - default — text-micro (11px) inline-fitting for dense rows
 *   - sm      — text-[10px] for ultra-dense tables
 *   - md      — text-caption (12px) for prominent status headers
 */

import * as React from "react";
import { cn } from "@/lib/utils";

export type StatusFamily =
  | "success"
  | "warning"
  | "error"
  | "info"
  | "neutral";

export type StatusPillSize = "sm" | "default" | "md";

const STATUS_MAP: Record<string, StatusFamily> = {
  // success family
  success: "success",
  approved: "success",
  completed: "success",
  complete: "success",
  active: "success",
  paid: "success",
  published: "success",
  done: "success",
  delivered: "success",
  signed: "success",
  won: "success",
  enabled: "success",
  healthy: "success",

  // warning family
  warning: "warning",
  pending: "warning",
  pending_review: "warning",
  pending_approval: "warning",
  in_progress: "warning",
  draft: "warning",
  scheduled: "warning",
  awaiting: "warning",
  awaiting_approval: "warning",
  on_hold: "warning",
  hold: "warning",
  review: "warning",
  partial: "warning",
  watch: "warning",

  // error family
  error: "error",
  rejected: "error",
  failed: "error",
  voided: "error",
  void: "error",
  cancelled: "error",
  canceled: "error",
  overdue: "error",
  expired: "error",
  blocked: "error",
  declined: "error",

  // info family
  info: "info",
  new: "info",
  created: "info",
  received: "info",
  submitted: "info",
  sent: "info",
  unread: "info",
};

const FAMILY_STYLES: Record<StatusFamily, string> = {
  success: "bg-status-success-muted text-status-success",
  warning: "bg-status-warning-muted text-status-warning",
  error: "bg-status-error-muted text-status-error",
  info: "bg-status-info-muted text-status-info",
  neutral: "bg-surface-sunken text-content-muted",
};

const SIZE_STYLES: Record<StatusPillSize, string> = {
  sm: "text-[10px] px-1.5 py-0.5 gap-1",
  default: "text-micro px-2 py-0.5 gap-1",
  md: "text-caption px-2.5 py-1 gap-1.5",
};

export interface StatusPillProps
  extends React.HTMLAttributes<HTMLSpanElement> {
  /** Status string — case-insensitive; underscores tolerated.
   * Auto-maps to a family. Unmapped values render as neutral. */
  status?: string | null;
  /** Explicit family override — takes precedence over status lookup. */
  variant?: StatusFamily;
  /** Custom label override — by default, derived from status string
   * (underscores → spaces, uppercased). */
  label?: string;
  size?: StatusPillSize;
  /** Optional leading icon (e.g., a check for "completed"). */
  icon?: React.ReactNode;
}

export function resolveStatusFamily(
  status: string | null | undefined,
): StatusFamily {
  if (!status) return "neutral";
  const key = status.toLowerCase().trim();
  return STATUS_MAP[key] ?? "neutral";
}

function StatusPill({
  status,
  variant,
  label,
  size = "default",
  icon,
  className,
  children,
  ...props
}: StatusPillProps) {
  const family: StatusFamily = variant ?? resolveStatusFamily(status);
  const displayLabel =
    label ??
    (typeof children === "string"
      ? children
      : status
        ? status.replace(/_/g, " ").toUpperCase()
        : "");

  return (
    <span
      data-slot="status-pill"
      data-status={status ?? null}
      data-variant={family}
      className={cn(
        "inline-flex items-center justify-center rounded-full whitespace-nowrap font-sans font-medium uppercase tracking-wider",
        FAMILY_STYLES[family],
        SIZE_STYLES[size],
        className,
      )}
      {...props}
    >
      {icon ? (
        <span className="inline-flex shrink-0" aria-hidden="true">
          {icon}
        </span>
      ) : null}
      {children && typeof children !== "string" ? children : displayLabel}
    </span>
  );
}

export { StatusPill, STATUS_MAP, FAMILY_STYLES };
