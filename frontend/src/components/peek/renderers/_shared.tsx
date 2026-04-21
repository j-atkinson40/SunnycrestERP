/**
 * Shared label/value pair used by all 6 peek renderers.
 *
 * Keeps spacing + typography consistent so peek panels feel like
 * one product across entity types.
 *
 * Aesthetic Arc Session 3 refresh:
 *   - PeekField types migrated to DESIGN_LANGUAGE tokens.
 *   - StatusBadge now re-exports the `StatusPill` primitive from
 *     `@/components/ui/status-pill` so peek panels inherit the
 *     platform's status-family color vocabulary instead of the old
 *     neutral-only rendering. Name preserved for backward compat
 *     across the 6 peek renderer imports.
 */

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { StatusPill } from "@/components/ui/status-pill";


export interface PeekFieldProps {
  label: string;
  value: ReactNode;
  className?: string;
}


export function PeekField({ label, value, className }: PeekFieldProps) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className={cn("flex justify-between gap-3 py-0.5 font-plex-sans", className)}>
      <span className="text-caption text-content-muted shrink-0">{label}</span>
      <span className="text-caption font-medium text-content-strong text-right truncate">
        {value}
      </span>
    </div>
  );
}


export function fmtDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}


export function fmtCurrency(value: number | null | undefined): string | null {
  if (value === null || value === undefined) return null;
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return `$${value.toFixed(2)}`;
  }
}


/**
 * Session 3: delegates to the StatusPill primitive. The status string
 * is auto-mapped to the correct DESIGN_LANGUAGE status family
 * (success/warning/error/info) — e.g., "approved" → success muted+
 * saturation treatment. Unmapped statuses render as neutral.
 */
export function StatusBadge({ status }: { status: string | null | undefined }) {
  if (!status) return null;
  return <StatusPill status={status} size="sm" />;
}
