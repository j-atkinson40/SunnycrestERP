import { Switch as SwitchPrimitive } from "@base-ui/react/switch";

import { cn } from "@/lib/utils";

/**
 * Bridgeable Switch — Aesthetic Arc Session 3 refresh.
 *
 * Checked state = accent (primary affordance). Unchecked state =
 * surface-sunken (recessed). Thumb = surface-raised with
 * shadow-level-1 for pressable material feel. Focus ring = accent.
 */
function Switch({
  className,
  ...props
}: React.ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      className={cn(
        "peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors duration-quick ease-settle",
        "focus-ring-accent",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "data-[checked]:bg-accent data-[unchecked]:bg-surface-sunken data-[unchecked]:ring-1 data-[unchecked]:ring-border-base",
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb
        className={cn(
          "pointer-events-none block h-4 w-4 rounded-full bg-surface-raised shadow-level-1 ring-0 transition-transform duration-quick ease-settle",
          "data-[checked]:translate-x-4 data-[unchecked]:translate-x-0",
        )}
      />
    </SwitchPrimitive.Root>
  );
}

export { Switch };
