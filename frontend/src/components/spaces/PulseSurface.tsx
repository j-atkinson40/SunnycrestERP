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

import { useCallback, useMemo, useState } from "react"

import { InlineError } from "@/components/ui/inline-error"
import { SkeletonLines } from "@/components/ui/skeleton"
import { PulseFirstLoginBanner } from "@/components/spaces/PulseFirstLoginBanner"
import { PulseLayer } from "@/components/spaces/PulseLayer"
import { useOnboardingTouch } from "@/hooks/useOnboardingTouch"
import { usePulseComposition } from "@/hooks/usePulseComposition"
import {
  type LayerMeasurement,
  useViewportFitMath,
} from "@/hooks/useViewportFitMath"
import type { LayerContent, LayerName } from "@/types/pulse"
import { cn } from "@/lib/utils"


// Canonical layer order per §3.26.2.4. Defined as a constant so
// rendering order is unambiguous + the tests can assert against it.
const LAYER_ORDER: LayerName[] = [
  "personal",
  "operational",
  "anomaly",
  "activity",
]


/**
 * Walk a layer's items, return the row count it consumes under
 * tetris packing with the given column count. Per §13.3.4 Step 3.
 *
 * Algorithm: simulate dense-flow placement. Track per-row occupied
 * cell mask; for each piece (in priority order), find the lowest
 * row + leftmost column where its `cols × rows` span fits without
 * overlap. The maximum row index reached + 1 is the layer's row
 * count.
 *
 * Commit 1 simplification: column count from §13.3.1 desktop tier
 * (6 cols). Tier-based dispatch lands in Commit 2 — tablet (4 cols)
 * + mobile (2 cols, but mobile dispatches to scroll mode in
 * Commit 3 anyway).
 *
 * Empty layer → 0 rows (caller skips the layer or renders advisory).
 */
function computeLayerRowCount(
  items: LayerContent["items"],
  filtered_ids: Set<string>,
  column_count: number,
): number {
  const visible = items.filter((it) => !filtered_ids.has(it.item_id))
  if (visible.length === 0) return 0

  // Bitmap of occupied cells, one row at a time. Grows as needed.
  const occupied: boolean[][] = []

  function ensureRow(row: number) {
    while (occupied.length <= row) {
      occupied.push(new Array(column_count).fill(false))
    }
  }

  function fits(start_row: number, start_col: number, cols: number, rows: number): boolean {
    if (start_col + cols > column_count) return false
    for (let r = start_row; r < start_row + rows; r++) {
      ensureRow(r)
      for (let c = start_col; c < start_col + cols; c++) {
        if (occupied[r][c]) return false
      }
    }
    return true
  }

  function place(start_row: number, start_col: number, cols: number, rows: number) {
    for (let r = start_row; r < start_row + rows; r++) {
      ensureRow(r)
      for (let c = start_col; c < start_col + cols; c++) {
        occupied[r][c] = true
      }
    }
  }

  // Dense flow: for each piece, find the first cell (row-major) where
  // its span fits. Same algorithm CSS Grid `auto-flow: row dense`
  // uses.
  for (const item of visible) {
    const cols = Math.min(Math.max(1, item.cols ?? 1), column_count)
    const rows = Math.max(1, item.rows ?? 1)

    let placed = false
    let r = 0
    while (!placed) {
      ensureRow(r)
      for (let c = 0; c <= column_count - cols; c++) {
        if (fits(r, c, cols, rows)) {
          place(r, c, cols, rows)
          placed = true
          break
        }
      }
      if (!placed) r++
    }
  }

  return occupied.length
}


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

  // Compute LayerMeasurement from the active composition. Re-runs
  // when composition or dismissals change. Empty composition (loading
  // / error) produces a zeroed measurement — math hook handles
  // gracefully.
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
    // Commit 1 hard-codes 6 cols (desktop tier per §13.3.1). Commit 2
    // wires tier-based via `viewportFit.tier`.
    const column_count = 6
    for (const lc of composition.layers) {
      const rows = computeLayerRowCount(
        lc.items,
        dismissedItemIds,
        column_count,
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
  }, [composition, dismissedItemIds])

  const viewportFit = useViewportFitMath({
    measurement,
    banner_visible,
  })

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
      data-tier-three-breached={
        viewportFit.tier_three_threshold_breached ? "true" : "false"
      }
      style={
        {
          "--pulse-content-height": `${viewportFit.available_pulse_height}px`,
          "--pulse-cell-height": `${viewportFit.cell_height}px`,
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
