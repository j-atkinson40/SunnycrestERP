import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Bridgeable Card — Aesthetic Arc Session 2 refresh + Tier-2 spec
 * reconciliation (April 2026).
 *
 * Foundational surface composition per DESIGN_LANGUAGE.md §6:
 *   - bg-surface-elevated   (warm cream lifted from page / cocktail-lounge
 *                            charcoal with top-edge highlight in dark mode)
 *   - border border-border-subtle  (Tier-2 addition: the "warm hairline
 *                            border that reads as metal edge" option from
 *                            §1 dark-mode anchor 4, promoted from optional
 *                            cue to canonical card treatment. Light mode
 *                            renders as atmospheric-weight whisper; dark
 *                            mode renders as warm metal edge.)
 *   - rounded-md            (Q2: radius-md = 8px default; radius-lg for
 *                            signature/large variants via className override)
 *   - shadow-level-1        (Tier-2: dark mode uses three-layer composition
 *                            — tight grounding shadow + soft halo +
 *                            strengthened inset top-edge highlight. Light
 *                            mode uses single-layer composition unchanged.)
 *   - p-6                   (§5 generous-default — 24px padding)
 *   - p-4 for size=sm       (dense variant per §5)
 *
 * Title: text-h3 font-medium text-content-strong (card titles are h3 level
 * per §4 size-weight pairings).
 * Description: text-body-sm text-content-muted.
 * Footer (Tier-2 update): bg-surface-base only. No explicit `border-t` —
 * the parent Card's perimeter border + the footer's bg-surface-base color
 * shift carry the footer separation. Removing the `border-t` avoids a
 * doubled-border visual where the card's perimeter meets the footer top
 * edge. The footer still sinks BELOW the card body via bg-surface-base.
 *
 * Interactive card:
 *   <Card className="hover:shadow-level-2 focus-ring-brass ..." tabIndex={0}>
 * A formal `interactive` prop is deferred to Session 3 — one-off hover +
 * focus-ring via className is fine for Session 2 scope.
 *
 * No `ring-1` anywhere — elevation communicates via the three material
 * cues (surface lift + top-edge highlight + perimeter border) plus shadow.
 */

function Card({
  className,
  size = "default",
  ...props
}: React.ComponentProps<"div"> & { size?: "default" | "sm" }) {
  return (
    <div
      data-slot="card"
      data-size={size}
      className={cn(
        "group/card flex flex-col gap-4 overflow-hidden rounded-md border border-border-subtle bg-surface-elevated font-plex-sans text-body-sm text-content-base shadow-level-1 data-[size=default]:p-6 data-[size=sm]:gap-3 data-[size=sm]:p-4 has-data-[slot=card-footer]:pb-0 data-[size=sm]:has-data-[slot=card-footer]:pb-0 has-[>img:first-child]:pt-0 *:[img:first-child]:rounded-t-md *:[img:last-child]:rounded-b-md",
        className
      )}
      {...props}
    />
  )
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-header"
      className={cn(
        "group/card-header @container/card-header grid auto-rows-min items-start gap-1 has-data-[slot=card-action]:grid-cols-[1fr_auto] has-data-[slot=card-description]:grid-rows-[auto_auto]",
        className
      )}
      {...props}
    />
  )
}

function CardTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-title"
      className={cn(
        "text-h3 font-medium text-content-strong leading-snug group-data-[size=sm]/card:text-body group-data-[size=sm]/card:font-medium",
        className
      )}
      {...props}
    />
  )
}

function CardDescription({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-description"
      className={cn("text-body-sm text-content-muted", className)}
      {...props}
    />
  )
}

function CardAction({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-action"
      className={cn(
        "col-start-2 row-span-2 row-start-1 self-start justify-self-end",
        className
      )}
      {...props}
    />
  )
}

function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-content"
      className={cn("", className)}
      {...props}
    />
  )
}

function CardFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-footer"
      className={cn(
        // Tier-2 spec reconciliation: removed explicit `border-t border-border-subtle`.
        // Parent Card now carries a perimeter `border border-border-subtle`,
        // so the footer top edge reads as the meeting point of the card body
        // (bg-surface-elevated) and the footer (bg-surface-base). The color
        // shift alone carries the sink-below-body separation; adding a
        // border-t would double-line against the perimeter border.
        "-mx-6 -mb-6 flex items-center bg-surface-base p-4 rounded-b-md group-data-[size=sm]/card:-mx-4 group-data-[size=sm]/card:-mb-4 group-data-[size=sm]/card:p-3",
        className
      )}
      {...props}
    />
  )
}

export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardAction,
  CardDescription,
  CardContent,
}
