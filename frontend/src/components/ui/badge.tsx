import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * Bridgeable Badge — Aesthetic Arc Session 3 refresh.
 *
 * General-purpose rounded-sm emphasis element. Adds first-class
 * status variants (info/success/warning/error) and aliases
 * `destructive` to `error` for backward compatibility with 142
 * pre-Session-3 usages.
 *
 * **Distinct from `StatusPill`:**
 *   - **Badge** = rounded-sm pill for general-purpose emphasis with
 *     flexible semantics (counts, labels, arbitrary tags). Use Badge
 *     when the meaning isn't strictly "what state is this record in."
 *   - **StatusPill** = rounded-full pill for inline status markers
 *     in lists/tables/detail panels. Takes a `status` string and
 *     auto-maps to the correct status family. Use StatusPill for
 *     workflow/order/case state rendering.
 *
 * Variants:
 *   - default   — brass-muted background + on-brass text (neutral
 *                 emphasis, e.g., count badge)
 *   - secondary — surface-raised background (quiet emphasis)
 *   - outline   — transparent + border
 *   - ghost     — transparent, brass-subtle on hover
 *   - link      — brass text with hover underline
 *   - info      — status-info muted/saturation pair
 *   - success   — status-success muted/saturation pair
 *   - warning   — status-warning muted/saturation pair
 *   - error     — status-error muted/saturation pair (PREFERRED for
 *                 destructive semantics in new work)
 *   - destructive — ALIAS of error for backward compat. Document as
 *                   legacy; prefer `error`.
 *
 * Radius: rounded-sm (4px per DESIGN_LANGUAGE §6 badges/small-pills).
 * Focus: brass focus ring (when badge is rendered as interactive).
 */
const badgeVariants = cva(
  "group/badge inline-flex h-5 w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-sm border border-transparent bg-clip-padding px-2 py-0.5 font-plex-sans text-micro font-medium whitespace-nowrap transition-colors duration-quick ease-settle focus-ring-brass has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 aria-invalid:border-status-error aria-invalid:ring-status-error/20 [&>svg]:pointer-events-none [&>svg]:size-3!",
  {
    variants: {
      variant: {
        default:
          "bg-brass-muted text-content-on-brass [a]:hover:brightness-95",
        secondary:
          "bg-surface-raised text-content-strong border-border-subtle [a]:hover:bg-surface-elevated",
        outline:
          "border-border-base text-content-base [a]:hover:bg-brass-subtle [a]:hover:text-content-strong",
        ghost:
          "text-content-muted hover:bg-brass-subtle hover:text-content-strong",
        link: "text-brass underline-offset-4 hover:underline hover:text-brass-hover",
        // Status variants (new Session 3)
        info: "bg-status-info-muted text-status-info [a]:hover:brightness-95",
        success:
          "bg-status-success-muted text-status-success [a]:hover:brightness-95",
        warning:
          "bg-status-warning-muted text-status-warning [a]:hover:brightness-95",
        error:
          "bg-status-error-muted text-status-error [a]:hover:brightness-95",
        // `destructive` aliases `error`. Kept for the 142 existing
        // call sites. Prefer `error` for new work.
        destructive:
          "bg-status-error-muted text-status-error [a]:hover:brightness-95",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({
  className,
  variant = "default",
  render,
  ...props
}: useRender.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return useRender({
    defaultTagName: "span",
    props: mergeProps<"span">(
      {
        className: cn(badgeVariants({ variant }), className),
      },
      props
    ),
    render,
    state: {
      slot: "badge",
      variant,
    },
  })
}

export { Badge, badgeVariants }
