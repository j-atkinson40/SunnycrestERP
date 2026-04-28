/**
 * PulseSurface — Phase W-4a Commit 5 top-level Pulse renderer.
 *
 * Per BRIDGEABLE_MASTER §3.26.2 + DESIGN_LANGUAGE §13. Renders the
 * Home Pulse: composition fetched via `usePulseComposition`, layers
 * rendered in canonical order (Personal / Operational / Anomaly /
 * Activity per §3.26.2.4), pieces sized + placed via the tetris
 * layout engine inside each PulseLayer, dismiss + navigation
 * signals collected for Tier 2 algorithms.
 *
 * Layer ordering visual:
 *   • Personal (top, no chrome divider)
 *   • Operational (brass-thread top edge per §13.3.2)
 *   • Anomaly (no divider — demarcation via positioning + sizing)
 *   • Activity (ambient at periphery — no divider)
 *
 * Composition engine determines per-piece sizing (cols × rows) so
 * the tetris layout in PulseLayer respects the backend's sizing
 * decisions. Frontend doesn't second-guess sizing.
 *
 * Loading + error states use Phase 7 polish primitives
 * (`SkeletonLines`, `InlineError`) for cross-platform consistency.
 *
 * The first-login banner sits above all layers when the
 * composition fell back to vertical-default (per D4).
 */

import { useCallback, useState } from "react"

import { InlineError } from "@/components/ui/inline-error"
import { SkeletonLines } from "@/components/ui/skeleton"
import { PulseFirstLoginBanner } from "@/components/spaces/PulseFirstLoginBanner"
import { PulseLayer } from "@/components/spaces/PulseLayer"
import { usePulseComposition } from "@/hooks/usePulseComposition"
import type { LayerName } from "@/types/pulse"
import { cn } from "@/lib/utils"


// Canonical layer order per §3.26.2.4. Defined as a constant so
// rendering order is unambiguous + the tests can assert against it.
const LAYER_ORDER: LayerName[] = [
  "personal",
  "operational",
  "anomaly",
  "activity",
]


export function PulseSurface() {
  const { composition, isLoading, error, refresh, pulseLoadedAt } =
    usePulseComposition()
  const [dismissedItemIds, setDismissedItemIds] = useState<Set<string>>(
    new Set(),
  )

  const handleDismissItem = useCallback((itemId: string) => {
    setDismissedItemIds((prev) => {
      const next = new Set(prev)
      next.add(itemId)
      return next
    })
  }, [])

  // ── Loading state ──────────────────────────────────────────────

  if (isLoading && !composition) {
    return (
      <div
        data-slot="pulse-surface"
        data-state="loading"
        className="mx-auto max-w-6xl px-4 sm:px-6 py-6 space-y-4"
      >
        <div className="h-8 w-48 rounded-sm bg-surface-sunken animate-pulse" />
        <SkeletonLines count={6} />
      </div>
    )
  }

  // ── Error state ────────────────────────────────────────────────

  if (error || !composition) {
    return (
      <div
        data-slot="pulse-surface"
        data-state="error"
        className="mx-auto max-w-6xl px-4 sm:px-6 py-6"
      >
        <InlineError
          message="Couldn't load your Pulse."
          hint={error ?? undefined}
          onRetry={() => void refresh()}
        />
      </div>
    )
  }

  // ── Composed render ────────────────────────────────────────────

  // Sort layers per the canonical order. Backend already returns
  // them in this order, but we sort defensively in case future
  // composition-engine versions reorder.
  const layersByName = new Map(
    composition.layers.map((lc) => [lc.layer, lc]),
  )
  const orderedLayers = LAYER_ORDER.map((name) => layersByName.get(name)).filter(
    (lc): lc is NonNullable<typeof lc> => lc !== undefined,
  )

  return (
    <div
      data-slot="pulse-surface"
      data-state="ready"
      data-time-of-day={composition.metadata.time_of_day_signal}
      className={cn(
        "mx-auto max-w-6xl",
        "px-4 sm:px-6 py-6",
        // Per §13.3.1 breathing-room composition: deliberate vertical
        // rhythm between layers via space-y; pieces inside each layer
        // get their own grid gap.
        "space-y-4",
      )}
    >
      <PulseFirstLoginBanner
        verticalDefaultApplied={
          composition.metadata.vertical_default_applied
        }
      />

      {orderedLayers.map((lc) => (
        <PulseLayer
          key={lc.layer}
          layer={lc}
          intelligenceStreams={composition.intelligence_streams}
          timeOfDay={composition.metadata.time_of_day_signal}
          workAreas={composition.metadata.work_areas_used}
          pulseLoadedAt={pulseLoadedAt}
          onDismissItem={handleDismissItem}
          dismissedItemIds={dismissedItemIds}
        />
      ))}
    </div>
  )
}


export default PulseSurface
