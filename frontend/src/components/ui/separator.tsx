"use client"

import { Separator as SeparatorPrimitive } from "@base-ui/react/separator"

import { cn } from "@/lib/utils"

/**
 * Bridgeable Separator — Aesthetic Arc Session 3 refresh.
 *
 * Thin visual divider. Tokens: bg-border-subtle (alpha-composited
 * warm border, per DESIGN_LANGUAGE.md §3 + §6). Use border-base or
 * border-strong via className override where more visual weight is
 * needed.
 */
function Separator({
  className,
  orientation = "horizontal",
  ...props
}: SeparatorPrimitive.Props) {
  return (
    <SeparatorPrimitive
      data-slot="separator"
      orientation={orientation}
      className={cn(
        "shrink-0 bg-border-subtle data-horizontal:h-px data-horizontal:w-full data-vertical:w-px data-vertical:self-stretch",
        className
      )}
      {...props}
    />
  )
}

export { Separator }
