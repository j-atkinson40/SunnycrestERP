/**
 * FocusBuilderBreadcrumb — subject hierarchy in the top bar (sub-arc F-5).
 *
 * Renders the operator's current subject path inside the Focus Builder
 * top bar after the `BRIDGEABLE STUDIO · FOCUS BUILDER` segment. Same
 * hierarchy as the left tree: vertical → focus-type → core → template.
 *
 * Locked decision (F-5 #1):
 *   - TEMPLATE subject: 4 segments (vertical / focus-type / core /
 *     template).
 *   - CORE subject: 3 segments (vertical / focus-type / core).
 *   - EMPTY subject: render null (top-bar header keeps the static
 *     "BRIDGEABLE STUDIO · FOCUS BUILDER" prefix alone).
 *
 * Brass-accent separator `›`, prose weight. Current (deepest) segment
 * weighted slightly heavier than preceding segments. NOT clickable.
 * Pure presentational component — caller derives the segments array.
 */
import * as React from "react"

import { cn } from "@/lib/utils"


export interface FocusBuilderBreadcrumbProps {
  /** Hierarchy segments in deepest-last order. Empty → renders null. */
  segments: string[]
}


export function FocusBuilderBreadcrumb({ segments }: FocusBuilderBreadcrumbProps) {
  if (segments.length === 0) return null
  return (
    <div
      data-testid="focus-builder-breadcrumb"
      className="flex items-center gap-1.5 text-[11px] text-content-muted"
      aria-label="Focus subject breadcrumb"
    >
      {segments.map((segment, idx) => {
        const isCurrent = idx === segments.length - 1
        return (
          <React.Fragment key={`${idx}-${segment}`}>
            {idx > 0 && (
              <span
                aria-hidden
                data-testid="focus-builder-breadcrumb-separator"
                className="text-[color:var(--accent)]"
              >
                ›
              </span>
            )}
            <span
              data-testid={
                isCurrent
                  ? "focus-builder-breadcrumb-current"
                  : `focus-builder-breadcrumb-segment-${idx}`
              }
              className={cn(
                "whitespace-nowrap",
                isCurrent
                  ? "font-medium text-[color:var(--content-base)]"
                  : "text-content-muted",
              )}
            >
              {segment}
            </span>
          </React.Fragment>
        )
      })}
    </div>
  )
}

export default FocusBuilderBreadcrumb
