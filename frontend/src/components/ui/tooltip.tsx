"use client";

import * as React from "react";
import { Tooltip as TooltipPrimitive } from "@base-ui/react/tooltip";

import { cn } from "@/lib/utils";

/**
 * Bridgeable Tooltip — Aesthetic Arc Session 3.
 *
 * Platform tooltip primitive — net-new. Prior to Session 3 the
 * platform used **266 native `title=` attributes** for tooltips.
 * Native browser tooltips have no timing control, inconsistent
 * appearance across OS, and accessibility gaps (no keyboard focus
 * trigger, no live-region announcement). This primitive replaces
 * that pattern; migration is long-tail (new work uses this; 266
 * legacy sites migrate as touched).
 *
 * Composition per DESIGN_LANGUAGE.md §6 overlay family:
 *   - bg-surface-raised (level-2 raised — tooltip sits above content)
 *   - border border-border-subtle + rounded-md
 *   - shadow-level-2 (shared with Dialog/DropdownMenu/Select popup)
 *   - duration-settle (300ms) + ease-settle open / duration-quick
 *     (200ms) + ease-gentle close
 *   - 150ms delay before opening — prevents drive-by tooltips on
 *     cursor transit (§6 tooltip-delay rule)
 *   - text-caption (12px) in default size; md size uses text-body-sm
 *     for richer tooltips with more content.
 *
 * Usage:
 *
 *     <TooltipProvider>           {/* Mount once at app root *\/}
 *       <Tooltip>
 *         <TooltipTrigger render={<button>Hover me</button>} />
 *         <TooltipContent>Keyboard shortcut: Cmd+K</TooltipContent>
 *       </Tooltip>
 *     </TooltipProvider>
 *
 * Sizes:
 *   - default (text-caption, p-2) — small labels, keybinds, brief hints
 *   - md (text-body-sm, p-3) — richer explanations
 *
 * For tooltips with a keyboard shortcut:
 *
 *     <TooltipContent>
 *       Approve
 *       <TooltipShortcut>Enter</TooltipShortcut>
 *     </TooltipContent>
 */

/**
 * TooltipProvider wraps the app root (or any subtree) and applies
 * a shared delay before tooltips open. DESIGN_LANGUAGE.md §6 specifies
 * a 150ms delay to prevent drive-by tooltips on cursor transit.
 *
 * Base UI lets an explicit TooltipProvider override the delay for a
 * subtree. Default usage: mount once at app root with delay={150};
 * individual Tooltips inherit.
 */
function TooltipProvider({
  delay = 150,
  ...props
}: React.ComponentProps<typeof TooltipPrimitive.Provider>) {
  return <TooltipPrimitive.Provider delay={delay} {...props} />;
}

function Tooltip({ ...props }: TooltipPrimitive.Root.Props) {
  return <TooltipPrimitive.Root {...props} />;
}

function TooltipTrigger({ ...props }: TooltipPrimitive.Trigger.Props) {
  return (
    <TooltipPrimitive.Trigger
      data-slot="tooltip-trigger"
      {...props}
    />
  );
}

function TooltipContent({
  className,
  side = "top",
  sideOffset = 6,
  align = "center",
  alignOffset = 0,
  size = "default",
  children,
  ...props
}: TooltipPrimitive.Popup.Props &
  Pick<
    TooltipPrimitive.Positioner.Props,
    "side" | "sideOffset" | "align" | "alignOffset"
  > & {
    size?: "default" | "md";
  }) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Positioner
        className="isolate z-50 outline-none"
        side={side}
        sideOffset={sideOffset}
        align={align}
        alignOffset={alignOffset}
      >
        <TooltipPrimitive.Popup
          data-slot="tooltip-content"
          data-size={size}
          className={cn(
            "z-50 max-w-xs origin-(--transform-origin) rounded-md border border-border-subtle bg-surface-raised font-plex-sans text-content-base shadow-level-2 duration-settle ease-settle data-[side=bottom]:slide-in-from-top-1 data-[side=inline-end]:slide-in-from-left-1 data-[side=inline-start]:slide-in-from-right-1 data-[side=left]:slide-in-from-right-1 data-[side=right]:slide-in-from-left-1 data-[side=top]:slide-in-from-bottom-1 data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95 data-closed:duration-quick data-closed:ease-gentle",
            size === "default" && "px-2 py-1 text-caption",
            size === "md" && "px-3 py-2 text-body-sm",
            className,
          )}
          {...props}
        >
          {children}
        </TooltipPrimitive.Popup>
      </TooltipPrimitive.Positioner>
    </TooltipPrimitive.Portal>
  );
}

function TooltipShortcut({
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      data-slot="tooltip-shortcut"
      className={cn(
        "ml-2 rounded-sm border border-border-subtle bg-surface-base px-1 py-0.5 font-plex-mono text-[10px] text-content-muted",
        className,
      )}
      {...props}
    />
  );
}

export {
  Tooltip,
  TooltipProvider,
  TooltipTrigger,
  TooltipContent,
  TooltipShortcut,
};
