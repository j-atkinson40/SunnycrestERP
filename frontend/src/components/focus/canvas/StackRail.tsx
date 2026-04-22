/**
 * StackRail — right-rail vertical Smart Stack. Phase A Session 3.7.
 *
 * Renders widgets in a scroll-snap column at the right of the
 * viewport. One widget visible at a time; scroll cycles through.
 * Tap a widget to expand into a floating overlay.
 *
 * Native CSS `scroll-snap-type: y mandatory` + `scroll-snap-align:
 * start` on each widget provides the snapping behavior. Native
 * scroll momentum on Safari/iOS gives close-to-Smart-Stack feel
 * without a spring-physics library (deferred per
 * PLATFORM_QUALITY_BAR.md 'Almost But Not Quite' for 3.7).
 *
 * Dots indicator column to the left of the rail — one dot per
 * widget; active dot filled brass, inactive outlined subtle.
 * IntersectionObserver on each widget tile reports visibility so
 * the active-dot state tracks the scroll position.
 *
 * Chrome (drag/resize/dismiss affordances) is disabled in stack
 * mode — widgets scroll in place, not drag. The mock widget content
 * renders directly without WidgetChrome.
 */

import { useEffect, useRef, useState } from "react"

import type { WidgetId, WidgetState } from "@/contexts/focus-registry"
import { cn } from "@/lib/utils"

import { MockSavedViewWidget } from "./MockSavedViewWidget"
import { STACK_RAIL_WIDTH } from "./geometry"


interface StackRailProps {
  widgets: Record<WidgetId, WidgetState>
  onExpandWidget: (widgetId: WidgetId) => void
}


export function StackRail({ widgets, onExpandWidget }: StackRailProps) {
  const entries = Object.entries(widgets)
  const [activeIndex, setActiveIndex] = useState(0)
  const tileRefs = useRef<Array<HTMLDivElement | null>>([])

  // Intersection observer wiring — updates activeIndex when the
  // majority-visible tile changes. Threshold 0.55 so we don't flicker
  // between tiles during mid-scroll. Guarded for environments (jsdom,
  // very old browsers) that don't provide IntersectionObserver —
  // activeIndex stays at 0 in that case.
  useEffect(() => {
    if (entries.length === 0) return
    if (typeof IntersectionObserver === "undefined") return
    const observer = new IntersectionObserver(
      (observedEntries) => {
        for (const obs of observedEntries) {
          if (obs.isIntersecting && obs.intersectionRatio > 0.55) {
            const idx = Number(
              (obs.target as HTMLElement).dataset.stackIndex ?? -1,
            )
            if (idx >= 0) setActiveIndex(idx)
          }
        }
      },
      { threshold: [0.55] },
    )
    tileRefs.current.forEach((el) => el && observer.observe(el))
    return () => observer.disconnect()
  }, [entries.length])

  if (entries.length === 0) return null

  return (
    <div
      data-slot="focus-stack-rail-wrapper"
      className="pointer-events-auto fixed right-4 top-1/2 -translate-y-1/2 flex items-center gap-2"
      style={{ width: STACK_RAIL_WIDTH + 16 /* dots column */ }}
    >
      {/* Dots indicator column — left of the rail. */}
      {entries.length > 1 && (
        <div
          data-slot="focus-stack-dots"
          className="flex flex-col items-center gap-1.5"
          role="tablist"
          aria-label="Stack navigation"
        >
          {entries.map(([id], i) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-label={`Scroll to widget ${i + 1}`}
              aria-selected={i === activeIndex}
              onClick={() => {
                const el = tileRefs.current[i]
                if (el) {
                  el.scrollIntoView({ behavior: "smooth", block: "start" })
                }
              }}
              className={cn(
                "h-2 w-2 rounded-full transition-colors duration-quick ease-settle",
                i === activeIndex
                  ? "bg-brass"
                  : "bg-border-subtle hover:bg-content-muted",
                "focus-ring-brass",
              )}
            />
          ))}
        </div>
      )}

      {/* Scroll-snap rail — actual widget tiles. */}
      <div
        data-slot="focus-stack-rail"
        className={cn(
          "flex flex-col overflow-y-auto",
          "rounded-md border border-border-subtle bg-surface-elevated shadow-level-1",
        )}
        style={{
          width: STACK_RAIL_WIDTH,
          // Use 70vh for a sensible rail height; shorter than core
          // so the user sees there's more content outside. Overflow
          // scrolls.
          height: "70vh",
          scrollSnapType: "y mandatory",
        }}
      >
        {entries.map(([id, state], i) => (
          <div
            key={id}
            ref={(el) => {
              tileRefs.current[i] = el
            }}
            data-slot="focus-stack-tile"
            data-stack-index={i}
            data-widget-id={id}
            className={cn(
              // Each tile is the full rail height minus a small
              // offset so the "next tile" peeks in at the bottom,
              // matching Smart Stack visual affordance.
              "flex-none snap-start cursor-pointer",
              "border-b border-border-subtle/60 last:border-b-0",
              "transition-transform duration-quick ease-settle",
              "hover:bg-brass-subtle/20 active:scale-[0.98]",
            )}
            style={{
              height: state.position.height,
              scrollSnapAlign: "start",
            }}
            onClick={() => onExpandWidget(id as WidgetId)}
            role="button"
            tabIndex={0}
            aria-label={`Expand widget ${i + 1}`}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault()
                onExpandWidget(id as WidgetId)
              }
            }}
          >
            <MockSavedViewWidget />
          </div>
        ))}
      </div>
    </div>
  )
}
