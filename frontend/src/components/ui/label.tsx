import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Bridgeable Label — Aesthetic Arc Session 2 refresh.
 *
 * Per DESIGN_LANGUAGE.md §4 size-weight pairings: UI labels are
 * Plex Sans Medium (500) at text-body-sm (14px). Color is
 * content-base — not content-strong; labels live beside inputs
 * as equal-weight context, not as headings.
 */
function Label({ className, ...props }: React.ComponentProps<"label">) {
  return (
    <label
      data-slot="label"
      className={cn(
        "flex items-center gap-2 font-sans text-body-sm font-medium leading-none text-content-base select-none group-data-[disabled=true]:pointer-events-none group-data-[disabled=true]:opacity-50 peer-disabled:cursor-not-allowed peer-disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
}

export { Label }
