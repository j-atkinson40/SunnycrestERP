"use client";

import { Popover as PopoverPrimitive } from "@base-ui/react/popover";

import { cn } from "@/lib/utils";

/**
 * Bridgeable Popover — Aesthetic Arc Session 3.
 *
 * Standalone popover primitive — net-new. Distinct from Dialog
 * (modal, backdrop, focus-trap) and DropdownMenu (item-list with
 * keyboard navigation). Use Popover for anchored content panels
 * that aren't menu items: filter controls, date pickers, quick
 * forms, detail peeks.
 *
 * **Two Base UI Popover sites already exist in the codebase**:
 *   - `components/layout/notification-dropdown.tsx` (Session 2)
 *   - `components/core/LocationSelector.tsx`
 *
 * Per Session 3 scope decision (Q4), both existing sites stay on
 * their direct `@base-ui/react/popover` imports. This primitive
 * exists as the platform-standard shape for future work. As
 * existing sites are touched for unrelated reasons, they migrate.
 *
 * Composition per DESIGN_LANGUAGE.md §6 overlay family (matches
 * Dialog/DropdownMenu/Select popup/Tooltip):
 *   - bg-surface-raised
 *   - border border-border-subtle + rounded-md
 *   - shadow-level-2
 *   - duration-settle ease-settle open / duration-quick ease-gentle close
 *   - accent focus ring on the trigger; content has no outer ring (it's
 *     the triggered surface)
 *
 * Usage:
 *
 *     <Popover>
 *       <PopoverTrigger render={<Button variant="outline">Open</Button>} />
 *       <PopoverContent>
 *         <p>Popover content.</p>
 *       </PopoverContent>
 *     </Popover>
 */

function Popover({ ...props }: PopoverPrimitive.Root.Props) {
  return <PopoverPrimitive.Root data-slot="popover" {...props} />;
}

function PopoverTrigger({ ...props }: PopoverPrimitive.Trigger.Props) {
  return (
    <PopoverPrimitive.Trigger data-slot="popover-trigger" {...props} />
  );
}

function PopoverContent({
  className,
  align = "center",
  alignOffset = 0,
  side = "bottom",
  sideOffset = 6,
  children,
  ...props
}: PopoverPrimitive.Popup.Props &
  Pick<
    PopoverPrimitive.Positioner.Props,
    "align" | "alignOffset" | "side" | "sideOffset"
  >) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Positioner
        className="isolate z-50 outline-none"
        side={side}
        sideOffset={sideOffset}
        align={align}
        alignOffset={alignOffset}
      >
        <PopoverPrimitive.Popup
          data-slot="popover-content"
          className={cn(
            "z-50 min-w-[8rem] max-w-(--available-width) origin-(--transform-origin) rounded-md border border-border-subtle bg-surface-raised p-4 font-sans text-content-base shadow-level-2 outline-none duration-settle ease-settle data-[side=bottom]:slide-in-from-top-2 data-[side=inline-end]:slide-in-from-left-2 data-[side=inline-start]:slide-in-from-right-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95 data-closed:duration-quick data-closed:ease-gentle",
            className,
          )}
          {...props}
        >
          {children}
        </PopoverPrimitive.Popup>
      </PopoverPrimitive.Positioner>
    </PopoverPrimitive.Portal>
  );
}

function PopoverClose({ ...props }: PopoverPrimitive.Close.Props) {
  return <PopoverPrimitive.Close data-slot="popover-close" {...props} />;
}

export { Popover, PopoverTrigger, PopoverContent, PopoverClose };
