/**
 * Phase 7 — Shared EmptyState component.
 *
 * One canonical pattern for every "nothing here yet" surface across the
 * arc. Surfaces that previously rolled their own (8 different variants
 * audited) now compose this.
 *
 * Pattern: icon + title + optional description + optional primary action
 * + optional secondary action.
 *
 * Sizes:
 *   - default — for full-page empties (saved views index, briefing page)
 *   - sm     — for list sub-surface empties (renderers, widgets)
 *   - xs     — for dropdown / inline empties (command bar no-results)
 *
 * Tone:
 *   - neutral  — default; no data yet, no problem
 *   - positive — celebrate completion (triage caught-up)
 *   - filtered — "no results match" (different from "nothing exists")
 */

import * as React from "react";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

export type EmptyStateTone = "neutral" | "positive" | "filtered";
export type EmptyStateSize = "default" | "sm" | "xs";

export interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: React.ReactNode;
  /** Primary CTA — typically a Button or Link rendered as button. */
  action?: React.ReactNode;
  /** Optional secondary action (e.g., "Clear filters"). */
  secondaryAction?: React.ReactNode;
  tone?: EmptyStateTone;
  size?: EmptyStateSize;
  className?: string;
  /** Test hook for Playwright. */
  "data-testid"?: string;
}

const SIZE_STYLES: Record<EmptyStateSize, string> = {
  default: "p-8 gap-3",
  sm: "p-6 gap-2",
  xs: "py-6 px-3 gap-1",
};

const ICON_SIZE: Record<EmptyStateSize, string> = {
  default: "h-10 w-10",
  sm: "h-8 w-8",
  xs: "h-6 w-6",
};

const TITLE_SIZE: Record<EmptyStateSize, string> = {
  default: "text-body font-medium",
  sm: "text-body-sm font-medium",
  xs: "text-caption font-medium",
};

const TONE_STYLES: Record<EmptyStateTone, string> = {
  neutral: "text-content-muted",
  positive: "text-status-success",
  filtered: "text-content-muted",
};

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  secondaryAction,
  tone = "neutral",
  size = "default",
  className,
  ...props
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-md border border-dashed border-border-subtle font-plex-sans text-center",
        SIZE_STYLES[size],
        TONE_STYLES[tone],
        className,
      )}
      data-testid={props["data-testid"] ?? "empty-state"}
      data-tone={tone}
      data-size={size}
    >
      {Icon ? (
        <Icon className={cn(ICON_SIZE[size], "opacity-70")} aria-hidden="true" />
      ) : null}
      <div className={cn(TITLE_SIZE[size], "text-content-strong")}>{title}</div>
      {description ? (
        <div
          className={cn(
            "max-w-md",
            size === "xs" ? "text-caption" : "text-body-sm",
          )}
        >
          {description}
        </div>
      ) : null}
      {action || secondaryAction ? (
        <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
          {action}
          {secondaryAction}
        </div>
      ) : null}
    </div>
  );
}
