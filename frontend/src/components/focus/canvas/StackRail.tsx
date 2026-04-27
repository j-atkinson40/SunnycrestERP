/**
 * StackRail — right-rail vertical Smart Stack. Phase A Session 3.7.
 *
 * Renders widgets in a scroll-snap column at the right of the
 * viewport. ONE widget visible at a time; scroll cycles through —
 * each tile fills the rail's full height so scroll-snap settles
 * on exactly one widget at a time, matching iOS Home Screen Smart
 * Stack behavior. Tap a widget to expand into a floating overlay.
 *
 * Session 3.7.1 fix: tiles originally used `state.position.height`
 * (200-320px canvas heights), so three widgets fit in the 70vh rail
 * simultaneously and scroll-snap never engaged — widgets rendered
 * as a plain stacked list, not Smart Stack. Each tile now uses
 * `height: 100%` + `flexShrink: 0` so it fills the rail exactly,
 * forcing scroll to cycle one-by-one.
 *
 * Native CSS `scroll-snap-type: y mandatory` + `scroll-snap-align:
 * start` on each widget provides the snapping behavior. Native
 * scroll momentum on Safari/iOS gives close-to-Smart-Stack feel
 * without a spring-physics library (deferred per
 * PLATFORM_QUALITY_BAR.md 'Almost But Not Quite' for 3.7).
 *
 * Dots indicator column to the left of the rail — one dot per
 * widget; active dot filled accent, inactive outlined subtle.
 * IntersectionObserver on each widget tile reports visibility so
 * the active-dot state tracks the scroll position. The observer's
 * `root` is the rail scroll container (not the viewport) so
 * intersection ratio is computed against the rail's visible area.
 *
 * Chrome (drag/resize/dismiss affordances) is disabled in stack
 * mode — widgets scroll in place, not drag. The mock widget content
 * renders directly without WidgetChrome.
 */

import { useEffect, useRef, useState } from "react"

import type { WidgetId, WidgetState } from "@/contexts/focus-registry"
import { cn } from "@/lib/utils"

import { getWidgetRenderer } from "./widget-renderers"
import { STACK_RAIL_WIDTH } from "./geometry"


interface StackRailProps {
  widgets: Record<WidgetId, WidgetState>
  onExpandWidget: (widgetId: WidgetId) => void
}


export function StackRail({ widgets, onExpandWidget }: StackRailProps) {
  const entries = Object.entries(widgets)
  const [activeIndex, setActiveIndex] = useState(0)
  const tileRefs = useRef<Array<HTMLDivElement | null>>([])
  const railRef = useRef<HTMLDivElement | null>(null)

  // Intersection observer wiring — updates activeIndex when the
  // majority-visible tile changes. Threshold 0.55 so we don't flicker
  // between tiles during mid-scroll. Root is the rail container so
  // intersection is computed relative to the scrollable viewport of
  // the rail, not the browser viewport — critical when the rail is
  // vertically centered and smaller than the viewport. Guarded for
  // environments (jsdom, very old browsers) that don't provide
  // IntersectionObserver — activeIndex stays at 0 in that case.
  useEffect(() => {
    if (entries.length === 0) return
    if (typeof IntersectionObserver === "undefined") return
    if (!railRef.current) return
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
      { root: railRef.current, threshold: [0.55] },
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
                  ? "bg-accent"
                  : "bg-border-subtle hover:bg-content-muted",
                "focus-ring-accent",
              )}
            />
          ))}
        </div>
      )}

      {/* Scroll-snap rail — actual widget tiles. */}
      <div
        ref={railRef}
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
        {entries.map(([id, state], i) => {
          // Phase 4.3b.3 — dispatch by widgetType (registered renderers
          // OR MockSavedViewWidget fallback for back-compat).
          //
          // Widget Library Phase W-1 — Section 12.5 stack tier composition:
          // surface = "focus_stack". Variant defaults to Brief at this
          // tier per Section 12.2 compatibility matrix. Per Decision 5,
          // widgets switch internally on variant_id; the renderer
          // receives the same widget instance + variant_id selection
          // as canvas tier (one widget per layout slot, multiple tiers
          // render the same instance differently).
          const Renderer = getWidgetRenderer(state.widgetType, state.variant_id)
          return (
            <div
              key={id}
              ref={(el) => {
                tileRefs.current[i] = el
              }}
              data-slot="focus-stack-tile"
              data-stack-index={i}
              data-widget-id={id}
              className={cn(
                // Each tile fills the full rail height so scroll-snap
                // settles on exactly one tile at a time. `flexShrink:
                // 0` + explicit `minHeight: 100%` defeats the flex
                // default `min-height: auto` which would otherwise
                // collapse the tile to content height and let multiple
                // tiles fit simultaneously (the 3.7 → 3.7.1 bug).
                "snap-start cursor-pointer",
                "border-b border-border-subtle/60 last:border-b-0",
                "transition-transform duration-quick ease-settle",
                "hover:bg-accent-subtle/20 active:scale-[0.98]",
              )}
              style={{
                height: "100%",
                minHeight: "100%",
                flexShrink: 0,
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
              <Renderer
                widgetId={id}
                variant_id={state.variant_id}
                surface="focus_stack"
              />
            </div>
          )
        })}
      </div>
    </div>
  )
}
