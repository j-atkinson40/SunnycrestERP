/**
 * AreaCard — one area of the business on the map home's STABLE SPINE
 * (The Map Home campaign).
 *
 * THE NAVIGATION GUARANTEE: the spine derives from the vocabulary
 * types-with-content and NEVER reorders by personalization — adaptation
 * augments (the rail above), never hides or shuffles. Pinned.
 *
 * Interactions: hover + hold-P → the AREA OVERVIEW PONDER; CLICK → the
 * area page (the sections/cards layout, re-homed per-area). Same material
 * discipline as TaskCard (elevated, no border, lift on hover); the
 * live-fleet glance is the card's one accent detail.
 */
import { useCallback } from "react"
import { ChevronRight, Radio } from "lucide-react"

import {
  HoldRing, useHoldToPonder,
} from "@/bridgeable-admin/components/moc/MoCTaskTable"

export interface AreaSummary {
  area: string
  taskCount: number
  liveCount: number
}

export function AreaCard({
  summary, onPonder, onOpen,
}: {
  summary: AreaSummary
  onPonder: (area: string) => void
  onOpen: (area: string) => void
}) {
  const { area, taskCount, liveCount } = summary
  const complete = useCallback(() => onPonder(area), [onPonder, area])
  const { hovered, holding, reduced, hoverProps } = useHoldToPonder(true, complete)

  return (
    <div
      {...hoverProps}
      role="button"
      tabIndex={0}
      onClick={() => onOpen(area)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          onOpen(area)
        }
      }}
      className="group flex cursor-pointer flex-col rounded-md bg-surface-elevated p-4 shadow-level-1 transition-shadow duration-quick ease-settle hover:shadow-level-2 focus-ring-accent"
      data-testid={`map-area-${area}`}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-body font-medium text-content-strong">{area}</p>
        {hovered ? (
          <span
            className="flex flex-none items-center gap-1.5 whitespace-nowrap text-caption text-content-muted"
            data-testid="map-area-hold-hint"
          >
            <HoldRing holding={holding} reduced={reduced} />
            Hold{" "}
            <kbd className="rounded-sm border border-border-base px-1 font-plex-mono text-micro">
              P
            </kbd>
          </span>
        ) : (
          <ChevronRight
            size={14}
            className="flex-none text-content-subtle transition-transform duration-quick group-hover:translate-x-0.5"
          />
        )}
      </div>
      <div className="mt-2 flex items-center gap-2 text-caption text-content-muted">
        <span data-testid={`map-area-count-${area}`}>
          {taskCount} {taskCount === 1 ? "task" : "tasks"}
        </span>
        {liveCount > 0 ? (
          <span
            className="inline-flex items-center gap-1 rounded-full bg-accent-subtle px-2 py-0.5 text-micro font-medium text-accent"
            data-testid={`map-area-live-${area}`}
          >
            <Radio size={9} /> {liveCount} live
          </span>
        ) : null}
      </div>
    </div>
  )
}
