/**
 * PulseSurface — Phase W-4a Commit 5 top-level Pulse renderer
 * (extended Step 6 Commit 1 with viewport-fit math foundation).
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
 *
 * Viewport-fit math (Phase W-4a Step 6 Commit 1, May 2026)
 * ────────────────────────────────────────────────────────
 * Per DESIGN_LANGUAGE §13.3.4: PulseSurface is the surface owner
 * for viewport-fit math. It walks its composition once to compute
 * a `LayerMeasurement`, hands it to `useViewportFitMath`, and
 * writes the result to inline CSS variables on its root:
 *
 *   --pulse-content-height — solved from chrome budget (Step 1)
 *   --pulse-cell-height    — solved from row-count weighting (Step 4)
 *   --pulse-scale          — clamped 0.875–1.25 (Step 6)
 *
 * Children (PulseLayer, PulsePiece, widget renderers) consume the
 * variables via `var(--pulse-cell-height)` etc. — no React context
 * threading needed.
 *
 * Commit 1 establishes the foundation; tier-based column counts
 * (Step 2 of canon) + container queries on opt-in widgets (Step 8)
 * land in Commit 2. Mobile-fallback + tier-three threshold scroll
 * mode (Step 5) lands in Commit 3.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import { InlineError } from "@/components/ui/inline-error"
import { SkeletonLines } from "@/components/ui/skeleton"
import { PulseFirstLoginBanner } from "@/components/spaces/PulseFirstLoginBanner"
import { PulseLayer } from "@/components/spaces/PulseLayer"
import { computeLayerRowCount } from "@/components/spaces/utils/layer-row-count"
import { isItemRenderable } from "@/components/spaces/utils/renderability"
import { useOnboardingTouch } from "@/hooks/useOnboardingTouch"
import { usePulseComposition } from "@/hooks/usePulseComposition"
import {
  type LayerMeasurement,
  useViewportDimensions,
  useViewportFitMath,
} from "@/hooks/useViewportFitMath"
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

  // Banner-visibility state — surfaced to viewport-fit math so
  // chrome budget reflects whether banner is consuming 96 px.
  const onboarding = useOnboardingTouch("pulse_first_login_banner")
  const banner_visible = !!(
    composition?.metadata.vertical_default_applied && onboarding.shouldShow
  )

  // Phase W-4a Step 6 Commit 2: tier detection runs BEFORE the
  // measurement walk so per-layer tetris packing uses the right
  // column count for the current viewport. PulseLayer + the
  // measurement walk + the math hook all see the same column_count
  // on every render via this single call.
  const dimensions = useViewportDimensions()
  const column_count = dimensions.column_count

  // Compute LayerMeasurement from the active composition. Re-runs
  // when composition / dismissals / column_count change. Empty
  // composition (loading / error) produces a zeroed measurement —
  // math hook handles gracefully.
  const measurement = useMemo<LayerMeasurement>(() => {
    if (!composition) {
      return {
        populated_layer_count: 0,
        total_row_count: 0,
        empty_with_advisory_layer_count: 0,
        has_operational_layer: false,
      }
    }
    let populated_layer_count = 0
    let total_row_count = 0
    let empty_with_advisory_layer_count = 0
    let has_operational_layer = false
    for (const lc of composition.layers) {
      // Phase W-4a Step 6 Commit 4 — pass renderability predicate so
      // unrenderable widget pieces (e.g. backend declares widget_id
      // but frontend has no registered renderer) silently filter out
      // of the row-count math per §13.4.3 platform-composed surface
      // canon. The cell-height solver's denominator therefore matches
      // the actually-rendered piece count. PulseLayer applies the
      // same predicate at render time + emits the canonical
      // console.warn — the warn fires there (canon § "PulseLayer
      // filter (Step 6 implementation)"), not here.
      const rows = computeLayerRowCount(
        lc.items,
        dismissedItemIds,
        column_count,
        isItemRenderable,
      )
      if (rows > 0) {
        populated_layer_count++
        total_row_count += rows
        if (lc.layer === "operational") has_operational_layer = true
      } else if (lc.advisory) {
        empty_with_advisory_layer_count++
      }
    }
    return {
      populated_layer_count,
      total_row_count,
      empty_with_advisory_layer_count,
      has_operational_layer,
    }
  }, [composition, dismissedItemIds, column_count])

  const viewportFit = useViewportFitMath({
    measurement,
    banner_visible,
  })

  // Phase W-4a Step 6 Commit 3 — observability `console.warn` per
  // §13.3.4 Step 5 when the tier-three threshold breaches. Fires
  // ONCE per (cell_height, total_row_count, viewport_height,
  // banner_visible) tuple so the warn doesn't spam during continuous
  // resize. Only fires for tier-three breach (tablet+) — mobile
  // fallback is intentional, not an anomaly. The composition shape
  // can be tuned by the operator (fewer pinned anomalies, simpler
  // operational layer) once the warning surfaces in dev/staging
  // logs.
  const lastWarnKeyRef = useRef<string | null>(null)
  useEffect(() => {
    if (!viewportFit.tier_three_threshold_breached) return
    const key = `${viewportFit.cell_height}|${measurement.total_row_count}|${viewportFit.viewport_height}|${banner_visible}`
    if (lastWarnKeyRef.current === key) return
    lastWarnKeyRef.current = key
    // eslint-disable-next-line no-console
    console.warn(
      "[pulse] cell_height < 80px threshold; falling back to scroll mode",
      {
        cell_height: viewportFit.cell_height,
        total_row_count: measurement.total_row_count,
        viewport_height: viewportFit.viewport_height,
        banner_visible,
      },
    )
  }, [
    viewportFit.tier_three_threshold_breached,
    viewportFit.cell_height,
    viewportFit.viewport_height,
    measurement.total_row_count,
    banner_visible,
  ])

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
      // Phase W-4a Step 6 Commit 1 — viewport-fit math output exposed
      // as data attrs (test observability) + CSS variables (child
      // consumption). See §13.3.4.
      data-viewport-tier={viewportFit.tier}
      data-column-count={viewportFit.column_count}
      data-tier-three-breached={
        viewportFit.tier_three_threshold_breached ? "true" : "false"
      }
      // Phase W-4a Step 6 Commit 3 — `data-scroll-mode` is the
      // canonical CSS attribute selector for scroll-mode dispatch.
      // PulseLayer's grid → flex-column override (in pulse-density.css)
      // keys on this attribute. Per §13.3.4 + §13.3.1.
      data-scroll-mode={viewportFit.scroll_mode_active ? "true" : "false"}
      style={
        {
          "--pulse-content-height": `${viewportFit.available_pulse_height}px`,
          // In scroll mode, the canonical Pulse-cell-height variable
          // is unset (`auto` sentinel) — pieces render at natural
          // heights via flex-column overrides in pulse-density.css.
          // The variable still ships so downstream consumers reading
          // `var(--pulse-cell-height, 80px)` get a predictable signal.
          "--pulse-cell-height": viewportFit.scroll_mode_active
            ? "auto"
            : `${viewportFit.cell_height}px`,
          "--pulse-column-count": viewportFit.column_count.toString(),
          "--pulse-scale": viewportFit.pulse_scale.toString(),
        } as React.CSSProperties
      }
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
