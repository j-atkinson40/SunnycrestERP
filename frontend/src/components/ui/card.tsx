import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Bridgeable Card — chrome/steel machined panel (2026-07-21 pivot).
 *
 * THE machined-panel primitive. DESIGN_LANGUAGE.md §3: every panel =
 * surface fill + a barely-there vertical gradient toward the recessed
 * surface at the bottom + a 1px inset top-edge specular + the panel
 * shadow. Flat fills are banned for panels. The stack is baked HERE,
 * parameterized by the `elevation` prop, so all ~229 importers flip
 * through one primitive (utilities drift; primitives don't):
 *
 *   elevation="panel" (default) — surface-2 fill, standard gradient
 *     toward surface-1, shadow-level-1 (which carries the specular
 *     in dark mode via --edge-specular).
 *   elevation="raised" — surface-3 fill, lighter gradient toward
 *     surface-2, shadow-level-2. For popover-grade cards.
 *   elevation="recessed" — surface-1 (sunken) fill, NO gradient, NO
 *     shadow. For rail/recessed containers that are part of the
 *     substrate, not objects on it.
 *
 * The gradient rides [background-image:var(--panel-gradient)] because
 * Tailwind bg-* utilities emit background-color only — the gradient
 * VALUES stay in the token layer (tokens.css), this file just keys
 * which token off the elevation prop.
 *
 * NO perimeter border — the edge emerges from the specular + shadow
 * + surface-lift stack.
 *
 * Title: text-h3 font-medium text-content-strong.
 * Description: text-body-sm text-content-muted.
 * Footer: bg-surface-base + border-t border-border-subtle sinks the
 * footer below the card body.
 *
 * Interactive card:
 *   <Card className="hover:shadow-level-2 focus-ring-accent ..." tabIndex={0}>
 */

const ELEVATION_CLASSES = {
  recessed: "bg-surface-sunken",
  panel:
    "bg-surface-elevated shadow-level-1 [background-image:var(--panel-gradient)]",
  raised:
    "bg-surface-raised shadow-level-2 [background-image:var(--panel-gradient-raised)]",
} as const

function Card({
  className,
  size = "default",
  elevation = "panel",
  ...props
}: React.ComponentProps<"div"> & {
  size?: "default" | "sm"
  elevation?: "recessed" | "panel" | "raised"
}) {
  return (
    <div
      data-slot="card"
      data-size={size}
      data-elevation={elevation}
      className={cn(
        "group/card flex flex-col gap-4 overflow-hidden rounded-md font-sans text-body-sm text-content-base data-[size=default]:p-6 data-[size=sm]:gap-3 data-[size=sm]:p-4 has-data-[slot=card-footer]:pb-0 data-[size=sm]:has-data-[slot=card-footer]:pb-0 has-[>img:first-child]:pt-0 *:[img:first-child]:rounded-t-md *:[img:last-child]:rounded-b-md",
        ELEVATION_CLASSES[elevation],
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
