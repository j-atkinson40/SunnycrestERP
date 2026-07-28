/**
 * FocusPopover — a base-ui Popover that survives being portaled OUT of
 * the Focus surface (S-3b).
 *
 * THE PROBLEM this exists to solve. The Focus core lives inside a
 * `DialogPrimitive.Portal` at `--z-focus` (100), and its sibling Canvas
 * is `pointer-events: none` (so backdrop clicks fall through). base-ui's
 * Popover portals its popup to `document.body` with the primitive's
 * default `z-50` positioner — which lands it UNDER the Focus backdrop
 * (z-100) where it's both invisible and unclickable.
 *
 * FocusPopover fixes both halves of the Focus pointer-events contract
 * (Focus Canvas tier-renderer pointer-events contract, CLAUDE.md §"Focus
 * Canvas tier-renderer pointer-events contract"):
 *   1. Z-ORDER — the positioner is stacked ABOVE `--z-focus` so the
 *      portaled popup paints over the Focus backdrop + core.
 *   2. SELF-ASSERTED POINTER-EVENTS — the popup carries an explicit
 *      `pointer-events: auto` + `data-focus-interactive` marker. Portaled
 *      content is `auto` by default, but the contract is that every
 *      interactive surface escaping the core self-asserts rather than
 *      relying on inheritance — belt-and-suspenders that also documents
 *      intent for the next portaled surface.
 *
 * Any interactive surface the Focus core needs to portal (the S-3b
 * add-line combobox is the first) routes through here. If a future
 * portaled surface CAN'T self-assert this way, that's the NAMED STOP the
 * S-3b dispatch calls out.
 *
 * Visual composition matches the standard Popover primitive (overlay
 * family per DESIGN_LANGUAGE §6) — this only changes stacking + the
 * pointer-events self-assertion.
 */

"use client"

import { Popover as PopoverPrimitive } from "@base-ui/react/popover"

import { cn } from "@/lib/utils"

export const FocusPopover = PopoverPrimitive.Root
export const FocusPopoverTrigger = PopoverPrimitive.Trigger
export const FocusPopoverClose = PopoverPrimitive.Close

export function FocusPopoverContent({
  className,
  align = "start",
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
        // Stack ABOVE --z-focus (100) so the portaled popup clears the
        // Focus backdrop + core. Kept below --z-toast (120) / --z-tooltip
        // (130) so those still win. `isolate` gives it its own stacking
        // context; `pointer-events: auto` re-enables events on the
        // positioner wrapper too (the Focus Canvas contract).
        className="isolate outline-none"
        style={{ zIndex: 115, pointerEvents: "auto" }}
        side={side}
        sideOffset={sideOffset}
        align={align}
        alignOffset={alignOffset}
      >
        <PopoverPrimitive.Popup
          data-slot="focus-popover-content"
          // SELF-ASSERTED pointer-events per the Focus tier contract.
          data-focus-interactive=""
          className={cn(
            "pointer-events-auto z-[115] min-w-[8rem] max-w-(--available-width) origin-(--transform-origin) rounded-md border border-border-subtle bg-surface-raised p-3 font-sans text-content-base shadow-level-2 [background-image:var(--panel-gradient-raised)] outline-none duration-settle ease-settle data-[side=bottom]:slide-in-from-top-2 data-[side=top]:slide-in-from-bottom-2 data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95 data-closed:duration-quick data-closed:ease-gentle",
            className,
          )}
          {...props}
        >
          {children}
        </PopoverPrimitive.Popup>
      </PopoverPrimitive.Positioner>
    </PopoverPrimitive.Portal>
  )
}
