/**
 * IconButton — floating button that opens the widget stack in
 * icon-mode (phone-portrait viewports). Phase A Session 3.7.
 *
 * Position: bottom-right, respecting iOS safe-area inset. Size
 * 56×56px (iOS 44pt HIG minimum × comfortable cursor target).
 * Accent accent + shadow-level-2 + widget-count badge top-right.
 *
 * Only renders when there are widgets to stack. Empty stack = no
 * icon (per user spec: don't clutter with empty affordance).
 */

import { Layers } from "lucide-react"

import { cn } from "@/lib/utils"


interface IconButtonProps {
  widgetCount: number
  onOpen: () => void
}


export function IconButton({ widgetCount, onOpen }: IconButtonProps) {
  if (widgetCount === 0) return null

  return (
    <button
      type="button"
      data-slot="focus-icon-button"
      aria-label={`Open widgets (${widgetCount})`}
      onClick={onOpen}
      className={cn(
        "pointer-events-auto fixed",
        "right-4",
        // Safe-area inset on iOS home indicator; fall back to 1rem
        // for non-iOS browsers via max().
        "bottom-[max(1rem,env(safe-area-inset-bottom))]",
        "flex h-14 w-14 items-center justify-center rounded-full",
        "bg-accent text-content-on-accent",
        "shadow-level-2 hover:shadow-level-3",
        "transition-[transform,box-shadow] duration-quick ease-settle",
        "hover:scale-105 active:scale-95",
        "focus-ring-accent",
      )}
      style={{ zIndex: "var(--z-focus)" }}
    >
      <Layers className="h-6 w-6" />
      {/* Widget-count badge — small accent-muted circle top-right
          with number in contrasting color. Shown only when there's
          more than one widget; single widget is self-evident. */}
      {widgetCount > 1 && (
        <span
          data-slot="focus-icon-badge"
          aria-hidden
          className={cn(
            "absolute -top-1 -right-1",
            "flex h-5 min-w-5 items-center justify-center rounded-full px-1",
            "bg-surface-raised text-content-strong",
            "font-plex-mono text-micro font-medium",
            "shadow-level-1 border border-border-subtle",
          )}
        >
          {widgetCount}
        </span>
      )}
    </button>
  )
}
