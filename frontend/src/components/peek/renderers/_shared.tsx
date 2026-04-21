/**
 * Shared label/value pair used by all 6 peek renderers.
 *
 * Keeps spacing + typography consistent so peek panels feel like
 * one product across entity types.
 */

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";


export interface PeekFieldProps {
  label: string;
  value: ReactNode;
  className?: string;
}


export function PeekField({ label, value, className }: PeekFieldProps) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className={cn("flex justify-between gap-3 py-0.5", className)}>
      <span className="text-xs text-muted-foreground shrink-0">{label}</span>
      <span className="text-xs font-medium text-right truncate">{value}</span>
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


export function StatusBadge({ status }: { status: string | null | undefined }) {
  if (!status) return null;
  return (
    <span className="inline-flex items-center rounded-full border bg-muted/50 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
      {status.replace(/_/g, " ")}
    </span>
  );
}
