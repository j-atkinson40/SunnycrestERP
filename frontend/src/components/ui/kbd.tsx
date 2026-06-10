/**
 * Kbd — the DESIGN_LANGUAGE §18.3 key-cap treatment.
 *
 * Shortcuts render in key caps: font-mono, text-micro, content-muted,
 * surface-sunken background, border-subtle 1px, radius-sm, 2px 4px padding
 * (py-0.5 px-1 — on the §5 grid). Modifier symbols use the platform's
 * symbols (⌘ ⇧ ⌥ ⌃) on macOS and text (Ctrl, Shift, Alt) elsewhere —
 * the CALLER passes the resolved string; this primitive is presentation.
 *
 * TooltipShortcut (ui/tooltip) conforms to the same spec per §18.3.
 */
import * as React from "react"

import { cn } from "@/lib/utils"

export function Kbd({
  className,
  ...props
}: React.HTMLAttributes<HTMLElement>) {
  return (
    <kbd
      data-slot="kbd"
      className={cn(
        "rounded-sm border border-border-subtle bg-surface-sunken px-1 py-0.5 font-mono text-micro text-content-muted",
        className,
      )}
      {...props}
    />
  )
}
