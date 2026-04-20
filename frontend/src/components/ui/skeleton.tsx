/**
 * Phase 7 — Shared Skeleton primitive + composites.
 *
 * Replaces 6 ad-hoc "Loading..." text variants across the arc with
 * content-shape-matching placeholders. The base `Skeleton` is a thin
 * div with `motion-safe:animate-pulse` — `motion-safe:` honors users
 * who've enabled prefers-reduced-motion (Phase 7 hard requirement).
 *
 * Composites for common arc shapes:
 *   - SkeletonLines({count}) — n rows of varying-width text
 *   - SkeletonCard — card header + 3 body lines
 *   - SkeletonRow — single list row
 *   - SkeletonTable({rows, cols}) — grid placeholder
 */

import * as React from "react";
import { cn } from "@/lib/utils";

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  className?: string;
}

export function Skeleton({ className, ...props }: SkeletonProps) {
  return (
    <div
      data-slot="skeleton"
      aria-hidden="true"
      className={cn(
        "rounded-md bg-muted/60 motion-safe:animate-pulse",
        className,
      )}
      {...props}
    />
  );
}

export function SkeletonLines({
  count = 3,
  className,
}: {
  count?: number;
  className?: string;
}) {
  return (
    <div className={cn("space-y-2", className)} data-testid="skeleton-lines">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton
          key={i}
          className={cn(
            "h-3",
            i === count - 1 ? "w-2/3" : i % 2 === 0 ? "w-full" : "w-5/6",
          )}
        />
      ))}
    </div>
  );
}

export function SkeletonCard({
  lines = 3,
  className,
  showHeader = true,
}: {
  lines?: number;
  className?: string;
  showHeader?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10",
        className,
      )}
      data-testid="skeleton-card"
    >
      {showHeader ? (
        <div className="flex items-center gap-2">
          <Skeleton className="h-5 w-5 rounded" />
          <Skeleton className="h-4 w-1/3" />
        </div>
      ) : null}
      <SkeletonLines count={lines} />
    </div>
  );
}

export function SkeletonRow({ className }: { className?: string }) {
  return (
    <div
      className={cn("flex items-center gap-3 py-3", className)}
      data-testid="skeleton-row"
    >
      <Skeleton className="h-4 w-4 rounded-full" />
      <Skeleton className="h-4 flex-1" />
      <Skeleton className="h-3 w-20" />
    </div>
  );
}

export function SkeletonTable({
  rows = 5,
  className,
}: {
  rows?: number;
  className?: string;
}) {
  return (
    <div
      className={cn("divide-y rounded-md border", className)}
      data-testid="skeleton-table"
    >
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonRow key={i} className="px-3" />
      ))}
    </div>
  );
}
