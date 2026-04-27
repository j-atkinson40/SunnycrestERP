import * as React from "react"
import { Input as InputPrimitive } from "@base-ui/react/input"

import { cn } from "@/lib/utils"

/**
 * Bridgeable Input — Aesthetic Arc Session 2 refresh.
 *
 * Shell composition per DESIGN_LANGUAGE.md §9 canonical form:
 *   - surface-raised background (inputs sit on elevated surfaces)
 *   - border-border-base subtle alpha-composited warm border
 *   - radius-base (6px) per Q1 button/input consistency
 *   - py-2.5 px-4 (~40px height) per §5 generous-default bias
 *
 * Focus treatment (Q9): border flips to accent + subtle ring-accent/30
 * glow. Different form from Button's full 5px outside ring because an
 * input's border IS its affordance — the border IS the focus signal.
 * Matches DESIGN_LANGUAGE §9 canonical input code example.
 *
 * Invalid: border-status-error + ring-status-error-muted. Pair with
 * the existing `aria-invalid` attribute convention.
 *
 * Disabled: bg-surface-sunken + text-content-subtle. Visibly recessed
 * but legible per §3 content-subtle guidance.
 */
function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <InputPrimitive
      type={type}
      data-slot="input"
      className={cn(
        "flex h-10 w-full min-w-0 rounded border border-border-base bg-surface-raised px-4 py-2.5 font-plex-sans text-body text-content-strong outline-none transition-colors duration-quick ease-settle file:inline-flex file:border-0 file:bg-transparent file:text-body-sm file:font-medium file:text-content-base placeholder:text-content-subtle hover:border-border-strong focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/30 disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-content-subtle aria-invalid:border-status-error aria-invalid:ring-2 aria-invalid:ring-status-error/20 md:text-body-sm",
        className
      )}
      {...props}
    />
  )
}

export { Input }
