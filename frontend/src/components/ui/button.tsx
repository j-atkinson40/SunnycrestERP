import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"
import { Loader2 } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * Bridgeable Button — Aesthetic Arc Session 2 refresh.
 *
 * Tokens map per DESIGN_LANGUAGE.md:
 *   - Primary (default): terracotta — `bg-accent`, `text-content-on-accent`,
 *     shadow-level-1 (substantial pill feel). Accent is the platform's
 *     primary action signal.
 *   - Secondary: elevated surface — reads as a quiet action on warm cream.
 *   - Outline: transparent + subtle border — toolbar actions.
 *   - Ghost: transparent, accent-subtle on hover — dense contexts.
 *   - Destructive: status-error-muted background + status-error text. Accent
 *     focus ring still applies (Q4: destructive communicates via color,
 *     focus communicates via accent per DESIGN_LANGUAGE §6).
 *   - Link: text-accent + hover underline, scale suppressed.
 *
 * Radius: radius-base (6px) per Q1 decision. `rounded-md` in Tailwind v4
 * resolves to our radius-md (8px); we use `rounded` which maps to our
 * --radius DEFAULT (radius-base = 6px).
 *
 * Focus: accent focus ring via `focus-ring-accent` utility (styles/base.css,
 * Session 1). Removes the gray shadcn ring.
 *
 * Motion: `transition-colors duration-quick ease-settle` + `active:scale-[0.97]`
 * per DESIGN_LANGUAGE §6 button-press pattern.
 *
 * Sizes: 4 legacy compact sizes (xs / icon-xs / sm / icon-sm) preserved
 * for backward compat across 295 imports. `default` and `lg` grow to
 * DESIGN_LANGUAGE's "substantial button" per §5 (py-2.5 px-5 = ~40-44px).
 * Use `default` or `sm` for new work; xs sizes are documented legacy.
 */
const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center bg-clip-padding font-plex-sans font-medium whitespace-nowrap transition-colors duration-quick ease-settle outline-none select-none focus-ring-accent active:scale-[0.97] disabled:pointer-events-none disabled:opacity-50 disabled:cursor-not-allowed aria-invalid:border-status-error [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "bg-accent text-content-on-accent font-semibold shadow-level-1 hover:bg-accent-hover active:bg-accent-hover",
        secondary:
          "bg-surface-raised text-content-strong hover:bg-surface-elevated active:bg-accent-subtle aria-expanded:bg-accent-subtle",
        outline:
          "border border-border-base bg-transparent text-content-base hover:bg-accent-subtle hover:text-content-strong active:bg-accent-muted aria-expanded:bg-accent-subtle aria-expanded:text-content-strong",
        ghost:
          "bg-transparent text-content-base hover:bg-accent-subtle hover:text-content-strong active:bg-accent-muted aria-expanded:bg-accent-subtle aria-expanded:text-content-strong",
        destructive:
          "bg-status-error-muted text-status-error hover:brightness-95 active:brightness-90",
        link:
          "text-accent underline-offset-4 hover:underline hover:text-accent-hover active:scale-100",
      },
      size: {
        // Substantial default — DESIGN_LANGUAGE §5 py-2.5 px-5 target (~40px).
        default:
          "h-10 gap-2 rounded px-5 text-body-sm has-data-[icon=inline-end]:pr-4 has-data-[icon=inline-start]:pl-4",
        // Legacy compact sizes — kept for backward compat (295 imports).
        // Prefer `default` or `sm` for new work.
        xs: "h-6 gap-1 rounded-sm px-2 text-caption in-data-[slot=button-group]:rounded has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-8 gap-1.5 rounded px-3 text-body-sm in-data-[slot=button-group]:rounded has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2 [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-11 gap-2 rounded px-6 text-body has-data-[icon=inline-end]:pr-4 has-data-[icon=inline-start]:pl-4",
        // Icon-only buttons — explicit size ensures WCAG 2.2 24x24 target
        // minimum. `icon` at 40px comfortably exceeds 44x44 Apple HIG guideline.
        icon: "size-10 rounded",
        "icon-xs":
          "size-6 rounded-sm in-data-[slot=button-group]:rounded [&_svg:not([class*='size-'])]:size-3",
        "icon-sm":
          "size-8 rounded in-data-[slot=button-group]:rounded",
        "icon-lg": "size-11 rounded",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

interface ButtonProps extends ButtonPrimitive.Props, VariantProps<typeof buttonVariants> {
  loading?: boolean
}

function Button({
  className,
  variant = "default",
  size = "default",
  loading,
  disabled,
  children,
  ...props
}: ButtonProps) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </ButtonPrimitive>
  )
}

export { Button, buttonVariants }
export type { ButtonProps }
