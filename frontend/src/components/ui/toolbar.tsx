import * as React from "react"

import { cn } from "@/lib/utils"
import { Separator } from "@/components/ui/separator"

/**
 * Bridgeable Toolbar — Builder Craft Arc Phase 1a.
 *
 * The shared grouped-controls action bar that every Studio builder
 * previously hand-rolled (Phase 0 audit: 7+ bespoke toolbars + the
 * StudioTopBar). Plain composition, no roving-focus machinery —
 * the controls inside are the shared <Button>/<Tooltip>/etc primitives
 * which carry their own focus treatment; the toolbar contributes
 * `role="toolbar"` for AT grouping semantics.
 *
 *   - Toolbar          — role="toolbar", flex row, min-w-0 so it
 *                        shrinks inside flex parents. Overflow behavior:
 *                        contents never wrap by default (a toolbar is a
 *                        single row); pass `wrap` to allow wrapping on
 *                        narrow widths instead of clipping.
 *   - ToolbarGroup     — a related-controls cluster (tighter gap)
 *   - ToolbarSeparator — vertical rule between groups (shared Separator)
 *
 * Spacing per §5: gap-2 between groups' members, gap-3 between groups.
 */

interface ToolbarProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Allow controls to wrap on narrow widths (default: single row). */
  wrap?: boolean
  /** Accessible name for the toolbar (AT users may have several). */
  "aria-label"?: string
}

function Toolbar({ className, wrap, ...props }: ToolbarProps) {
  return (
    <div
      role="toolbar"
      data-slot="toolbar"
      className={cn(
        "flex min-w-0 items-center gap-3",
        wrap ? "flex-wrap" : "flex-nowrap",
        className,
      )}
      {...props}
    />
  )
}

function ToolbarGroup({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="group"
      data-slot="toolbar-group"
      className={cn("flex min-w-0 items-center gap-2", className)}
      {...props}
    />
  )
}

function ToolbarSeparator({
  className,
  ...props
}: React.ComponentProps<typeof Separator>) {
  return (
    <Separator
      orientation="vertical"
      data-slot="toolbar-separator"
      className={cn("h-5 self-center", className)}
      {...props}
    />
  )
}

export { Toolbar, ToolbarGroup, ToolbarSeparator }
