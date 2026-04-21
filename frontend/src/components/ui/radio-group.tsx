import { Radio as RadioPrimitive } from "@base-ui/react/radio"
import { RadioGroup as RadioGroupPrimitive } from "@base-ui/react/radio-group"

import { cn } from "@/lib/utils"

/**
 * Bridgeable RadioGroup — Aesthetic Arc Session 3 refresh.
 *
 * Unchecked: border-border-base + bg-surface-raised.
 * Checked: bg-brass + border-brass + content-on-brass indicator dot.
 * Focus: brass focus ring.
 * Invalid: border-status-error + ring-status-error/20.
 */

function RadioGroup({ className, ...props }: RadioGroupPrimitive.Props) {
  return (
    <RadioGroupPrimitive
      data-slot="radio-group"
      className={cn("grid w-full gap-2", className)}
      {...props}
    />
  )
}

function RadioGroupItem({ className, ...props }: RadioPrimitive.Root.Props) {
  return (
    <RadioPrimitive.Root
      data-slot="radio-group-item"
      className={cn(
        "group/radio-group-item peer relative flex aspect-square size-4 shrink-0 rounded-full border border-border-base bg-surface-raised outline-none transition-colors duration-quick ease-settle after:absolute after:-inset-x-3 after:-inset-y-2 focus-ring-brass disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-status-error aria-invalid:ring-2 aria-invalid:ring-status-error/20 data-checked:border-brass data-checked:bg-brass data-checked:text-content-on-brass",
        className
      )}
      {...props}
    >
      <RadioPrimitive.Indicator
        data-slot="radio-group-indicator"
        className="flex size-4 items-center justify-center"
      >
        <span className="absolute top-1/2 left-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-content-on-brass" />
      </RadioPrimitive.Indicator>
    </RadioPrimitive.Root>
  )
}

export { RadioGroup, RadioGroupItem }
