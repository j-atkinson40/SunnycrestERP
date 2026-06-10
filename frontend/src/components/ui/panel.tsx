import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Bridgeable Panel chrome — Builder Craft Arc Phase 1a.
 *
 * The shared header/title/actions/body/footer chrome that every Studio
 * builder previously hand-rolled (the Phase 0 audit found 7+ bespoke
 * panel-chrome implementations). Composition per DESIGN_LANGUAGE §6
 * surface compositions:
 *
 *   - Panel        — the pane container (flex column; bg from the caller —
 *                    builders use bg-surface-sunken for side rails and
 *                    bg-surface-elevated for top bars, so the surface token
 *                    is the CALLER's choice, not baked in)
 *   - PanelHeader  — border-b border-border-subtle separator row
 *   - PanelTitle   — text-body-sm font-medium text-content-strong
 *   - PanelActions — the right-aligned actions cluster inside a header
 *   - PanelBody    — the scrollable content area (flex-1 overflow-y-auto)
 *   - PanelFooter  — border-t border-border-subtle separator row
 *
 * Spacing defaults are the §5 generous-default (px-4 py-3 chrome rows,
 * p-4 body); callers override via className for denser/looser regions —
 * adoption is chrome CONSOLIDATION, not redesign, so visual parity with
 * an adopting surface's existing paddings is always one className away.
 *
 * All elements are plain divs with data-slot markers (no behavior) —
 * byte-cheap, test-targetable, and safe to adopt incrementally.
 */

function Panel({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-slot="panel"
      className={cn("flex min-h-0 flex-col", className)}
      {...props}
    />
  )
}

function PanelHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-slot="panel-header"
      className={cn(
        "flex items-center justify-between gap-2 border-b border-border-subtle px-4 py-3",
        className,
      )}
      {...props}
    />
  )
}

function PanelTitle({
  className,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2
      data-slot="panel-title"
      className={cn(
        "text-body-sm font-medium text-content-strong",
        className,
      )}
      {...props}
    />
  )
}

function PanelActions({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-slot="panel-actions"
      className={cn("flex items-center gap-2", className)}
      {...props}
    />
  )
}

function PanelBody({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-slot="panel-body"
      className={cn("min-h-0 flex-1 overflow-y-auto p-4", className)}
      {...props}
    />
  )
}

function PanelFooter({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-slot="panel-footer"
      className={cn(
        "flex items-center gap-2 border-t border-border-subtle px-4 py-3",
        className,
      )}
      {...props}
    />
  )
}

export { Panel, PanelHeader, PanelTitle, PanelActions, PanelBody, PanelFooter }
