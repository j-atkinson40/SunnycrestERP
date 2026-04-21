import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Bridgeable Textarea — Aesthetic Arc Session 2 refresh.
 *
 * Same shell as Input (surface-raised + border-border-base + radius-base
 * + brass focus border). Min-height scales up to ~80px to match
 * DESIGN_LANGUAGE.md §5 generous-default bias for multiline input.
 * `field-sizing-content` retains auto-expand behavior.
 */
function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-20 w-full rounded border border-border-base bg-surface-raised px-4 py-2.5 font-plex-sans text-body text-content-strong outline-none transition-colors duration-quick ease-settle placeholder:text-content-subtle hover:border-border-strong focus-visible:border-brass focus-visible:ring-2 focus-visible:ring-brass/30 disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-content-subtle aria-invalid:border-status-error aria-invalid:ring-2 aria-invalid:ring-status-error/20 md:text-body-sm",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
