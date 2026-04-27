import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Bridgeable Card — Aesthetic Arc Session 2 refresh + Tier-4
 * measurement-based correction (April 2026).
 *
 * Foundational surface composition per DESIGN_LANGUAGE.md §6:
 *   - bg-surface-elevated   (warm cream lifted from page in light mode /
 *                            warmer-amber charcoal in dark mode — reference
 *                            dark card measures oklch(0.20 0.011 81))
 *   - rounded-md            (Q2: radius-md = 8px default; radius-lg for
 *                            signature/large variants via className override)
 *   - shadow-level-1        (dark mode: three-layer composition of tight
 *                            grounding shadow + soft halo + 3px inset
 *                            top-edge highlight. Light mode: single-layer
 *                            shadow without inset highlight — morning
 *                            light is ambient, not focused.)
 *   - p-6                   (§5 generous-default — 24px padding)
 *   - p-4 for size=sm       (dense variant per §5)
 *
 * NO perimeter border. Tier-2 (April 2026) added `border border-border-
 * subtle` based on inferred anchor-4 prose. Tier-4 reference-measurement
 * showed the canonical design has NO discrete perimeter border — the card
 * edge emerges from the shadow-halo + top-edge highlight + surface-lift
 * stack. Added border was removed in Tier 4.
 *
 * Title: text-h3 font-medium text-content-strong (card titles are h3 level
 * per §4 size-weight pairings).
 * Description: text-body-sm text-content-muted.
 * Footer: bg-surface-base + border-t border-border-subtle sinks the footer
 * below the card body. The border-t is explicit (was removed in Tier 2
 * when the parent perimeter border carried footer-separator duty; with
 * Tier 4 removing the perimeter border, the footer separator returns so
 * the footer zone still reads distinct from the card body).
 *
 * Interactive card:
 *   <Card className="hover:shadow-level-2 focus-ring-accent ..." tabIndex={0}>
 *
 * No `ring-1` anywhere — elevation communicates via surface-lift + shadow
 * composition + (dark mode) 3px top-edge highlight.
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
        "group/card flex flex-col gap-4 overflow-hidden rounded-md bg-surface-elevated font-plex-sans text-body-sm text-content-base shadow-level-1 data-[size=default]:p-6 data-[size=sm]:gap-3 data-[size=sm]:p-4 has-data-[slot=card-footer]:pb-0 data-[size=sm]:has-data-[slot=card-footer]:pb-0 has-[>img:first-child]:pt-0 *:[img:first-child]:rounded-t-md *:[img:last-child]:rounded-b-md",
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
        // Tier-4 restores the explicit `border-t border-border-subtle`.
        // Tier-2 had removed it when the parent Card gained a perimeter
        // border (to avoid doubled-border look); Tier-4 removed that
        // perimeter border per reference measurement, so the footer needs
        // its separator back. Without it the footer's bg-surface-base
        // transition from the card body's bg-surface-elevated is too
        // subtle in dark mode (delta ~0.04 OKLCH) to reliably mark the
        // footer as a distinct sunken region.
        "-mx-6 -mb-6 flex items-center border-t border-border-subtle bg-surface-base p-4 rounded-b-md group-data-[size=sm]/card:-mx-4 group-data-[size=sm]/card:-mb-4 group-data-[size=sm]/card:p-3",
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
