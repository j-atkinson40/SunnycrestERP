import type { LucideIcon, LucideProps } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * Bridgeable Icon — Builder Craft Arc Phase 1a.
 *
 * The shared Lucide wrapper that makes DESIGN_LANGUAGE §7's stroke-width
 * rule the DEFAULT instead of a per-site responsibility:
 *
 *   - sizes ≤ 16px → 1.5px stroke (lucide's default 2px reads overweight
 *     at small sizes — "2px stroke at 12px size" is a §7 anti-pattern)
 *   - sizes  > 16px → 2px stroke (lucide default)
 *
 * An explicit `strokeWidth` prop always wins (escape hatch for deliberate
 * weight). Icons are decorative by default (`aria-hidden`) — pass an
 * `aria-label` (which flips aria-hidden off) only when the icon IS the
 * content.
 *
 * Usage:
 *     import { Save } from "lucide-react"
 *     <Icon icon={Save} size={14} />            // strokeWidth 1.5 (auto)
 *     <Icon icon={Save} size={20} />            // strokeWidth 2   (auto)
 *     <Icon icon={Save} size={14} strokeWidth={2} />  // explicit wins
 *
 * This is the one-place landing for the platform-wide "1.5px at small
 * sizes" conformance (filed at pre-arc hygiene): new work uses <Icon>;
 * legacy direct-lucide sites migrate as touched.
 */

export interface IconProps extends Omit<LucideProps, "ref"> {
  /** The lucide icon component to render. */
  icon: LucideIcon
  /** Pixel size (width = height). Default 16. */
  size?: number
}

const SMALL_SIZE_MAX = 16
const SMALL_STROKE = 1.5
const DEFAULT_STROKE = 2

export function Icon({
  icon: IconComponent,
  size = 16,
  strokeWidth,
  className,
  "aria-label": ariaLabel,
  ...props
}: IconProps) {
  return (
    <IconComponent
      size={size}
      strokeWidth={
        strokeWidth ?? (size <= SMALL_SIZE_MAX ? SMALL_STROKE : DEFAULT_STROKE)
      }
      className={cn("shrink-0", className)}
      aria-hidden={ariaLabel ? undefined : true}
      aria-label={ariaLabel}
      data-slot="icon"
      {...props}
    />
  )
}
