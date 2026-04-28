/**
 * PulseLayer — Phase W-4a Commit 5
 * (extended Step 6 Commit 1 with viewport-fit cell sizing).
 *
 * Renders one of the four Pulse layers (Personal / Operational /
 * Anomaly / Activity) per BRIDGEABLE_MASTER §3.26.2.3.
 *
 * Per DESIGN_LANGUAGE.md §13.3.2 visual demarcation:
 *   • Personal layer at top — no chrome divider
 *   • Operational layer — 1px aged-terracotta thread on top edge
 *     (subtle "composed" affordance signaling structural boundary)
 *   • Anomaly layer — no hard divider; demarcation via positioning
 *     + sizing
 *   • Activity layer — no hard divider; ambient at periphery via
 *     lower-priority sizing in the layer service
 *
 * Empty layers either suppress entirely or render the advisory
 * message in a quiet inline note. Personal + Anomaly + Activity
 * surface advisories like "Nothing addressed to you right now",
 * "All clear", "Quiet day so far." Operational layer surfaces a
 * more action-oriented advisory pointing at /onboarding/operator-
 * profile when work_areas not set (D4 fallback).
 *
 * Viewport-fit grid sizing (Phase W-4a Step 6 Commit 1, May 2026)
 * ──────────────────────────────────────────────────────────────
 * Per DESIGN_LANGUAGE §13.3.4. PulseLayer's grid uses
 * `grid-template-rows: repeat(N, var(--pulse-cell-height))` where
 * N = the layer's row count under tetris packing + the cell height
 * is the surface-owner-solved variable PulseSurface puts on its
 * root. Replaces the pre-Step-6 fixed `auto-rows-[80px]` pattern.
 *
 * 300-400 ms ease-out CSS transition on `grid-template-rows` smooths
 * cell-height recomputation when composition shape changes (piece
 * dismiss, viewport resize, late-arriving composition).
 *
 * Tier-based column count + container-query density tiers land in
 * Commit 2; mobile-fallback + tier-three threshold scroll mode in
 * Commit 3.
 */

import { PulsePiece } from "@/components/spaces/PulsePiece"
import type {
  IntelligenceStream,
  LayerContent,
  LayerName,
  TimeOfDaySignal,
} from "@/types/pulse"
import { cn } from "@/lib/utils"


export interface PulseLayerProps {
  layer: LayerContent
  intelligenceStreams: IntelligenceStream[]
  timeOfDay: TimeOfDaySignal
  workAreas: string[]
  pulseLoadedAt: number | null
  onDismissItem?: (itemId: string) => void
  /** Set of dismissed item_ids — parent PulseSurface tracks these
   *  so PulsePiece's animate-out completes before the parent
   *  removes the piece from render. */
  dismissedItemIds: Set<string>
}


/** Whether this layer shows the brass-thread divider above its
 *  content, per §13.3.2. Only Operational. */
function _hasBrassThread(layer: LayerName): boolean {
  return layer === "operational"
}


/** Compute this layer's row count under tetris packing.
 *
 * Mirrors `computeLayerRowCount` in PulseSurface — kept duplicated
 * for now because PulseSurface needs an aggregate measurement to
 * solve cell_height, and PulseLayer needs the same per-layer count
 * to render the right number of grid rows. Future cleanup: hoist to
 * a shared util in `viewport-fit-constants.ts`. For Commit 1 the
 * duplication is bounded (~30 LOC) + keeps both consumers
 * self-contained.
 *
 * Algorithm: dense-flow placement, same as CSS Grid `auto-flow: row
 * dense`. Returns 0 for empty layers.
 */
function computeLayerRowCount(
  items: LayerContent["items"],
  filtered_ids: Set<string>,
  column_count: number,
): number {
  const visible = items.filter((it) => !filtered_ids.has(it.item_id))
  if (visible.length === 0) return 0

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


/** Column count per §13.3.1 viewport tier. Commit 1 uses desktop
 *  (6 cols) as the canonical assumption for row-count packing.
 *  Tier-based dispatch lands in Commit 2 — at that point this
 *  helper accepts a tier param. */
const COMMIT_1_COLUMN_COUNT = 6


export function PulseLayer({
  layer,
  intelligenceStreams,
  timeOfDay,
  workAreas,
  pulseLoadedAt,
  onDismissItem,
  dismissedItemIds,
}: PulseLayerProps) {
  // Filter out items the user dismissed in this session (parent
  // tracks the set; PulsePiece animates out then parent removes).
  const visibleItems = layer.items.filter(
    (it) => !dismissedItemIds.has(it.item_id),
  )

  // Empty-after-dismiss OR truly empty layer.
  if (visibleItems.length === 0) {
    if (!layer.advisory) {
      // Silent empty — common for personal/activity. Suppress the
      // entire layer block; the brass-thread (if any) doesn't
      // surface either, so the surface stays clean.
      return null
    }
    return (
      <section
        data-slot="pulse-layer"
        data-layer={layer.layer}
        data-empty="true"
        className={cn(
          "w-full",
          _hasBrassThread(layer.layer) &&
            "border-t border-accent/30 pt-4 mt-2",
        )}
      >
        <p
          className="text-caption text-content-muted font-sans italic px-1"
          data-slot="pulse-layer-advisory"
        >
          {layer.advisory}
        </p>
      </section>
    )
  }

  // Phase W-4a Step 6 Commit 1 — compute this layer's row count
  // (visible items only, post-dismissal filter). Drives explicit
  // grid-template-rows below so the grid produces exactly N rows of
  // var(--pulse-cell-height).
  const layerRowCount = computeLayerRowCount(
    layer.items,
    dismissedItemIds,
    COMMIT_1_COLUMN_COUNT,
  )

  return (
    <section
      data-slot="pulse-layer"
      data-layer={layer.layer}
      data-row-count={layerRowCount}
      className={cn(
        "w-full",
        // §13.3.2 — brass-thread above Operational layer. Subtle:
        // border-t at 30% accent alpha is the canonical
        // "composed-by-intelligence" hairline. Cover with hand
        // test: layer reads as logical group without divider ⇒
        // divider correctly subtle.
        _hasBrassThread(layer.layer) &&
          "border-t border-accent/30 pt-4 mt-2",
      )}
    >
      <div
        data-slot="pulse-layer-grid"
        // Per §13.3.4 Step 7: grid-template-rows uses an explicit
        // row count × the surface-owner-solved cell height. Replaces
        // the pre-Step-6 fixed `auto-rows-[80px]`. The transition is
        // applied via inline style (Tailwind doesn't have a built-in
        // utility for transitioning grid-template-rows with a custom
        // cubic-bezier).
        style={{
          gridTemplateRows: `repeat(${layerRowCount}, var(--pulse-cell-height, 80px))`,
          // Per §13.3.2 amendment: 300ms ease-out transition on
          // grid-template-rows when cell-height recomputes. Smooth
          // visual handoff during composition changes / viewport
          // resize / banner dismiss. Falls back to 80px when
          // --pulse-cell-height is unset (initial mount before
          // PulseSurface wires the variable).
          transition:
            "grid-template-rows 350ms cubic-bezier(0.4, 0, 0.2, 1)",
        }}
        className={cn(
          // Tetris layout per §13.3.1 + D2 (custom CSS Grid via
          // WidgetGrid pattern). Auto-fit columns; rows now follow
          // the surface-fit math (§13.3.4 cell_height variable).
          //
          // `grid-flow-row-dense` (Phase W-4a Step 2.C, April 2026):
          // smaller pieces (e.g. today widget Glance 1×1) backfill
          // empty cells left by larger pieces' spans rather than
          // leaving row-2 visual gaps. Pieces still respect their
          // priority-driven render order (composition_engine sorts
          // before emission); dense flow only changes _which empty
          // cell_ each smaller piece lands in, not the order pieces
          // are placed.
          //
          // Tier-based column count (Commit 2) replaces the auto-fit
          // pattern with `grid-cols-{tier}` where tier ∈ 2/4/6.
          // Commit 1 keeps auto-fit + minmax(160px, 1fr) so the page
          // doesn't blow up before tier dispatch lands.
          "grid grid-flow-row-dense",
          "grid-cols-[repeat(auto-fit,minmax(160px,1fr))]",
          "gap-3",
        )}
      >
        {visibleItems.map((item) => (
          <PulsePiece
            key={item.item_id}
            item={item}
            layer={layer.layer}
            timeOfDay={timeOfDay}
            workAreas={workAreas}
            intelligenceStreams={intelligenceStreams}
            pulseLoadedAt={pulseLoadedAt}
            onDismiss={onDismissItem}
          />
        ))}
      </div>
    </section>
  )
}


export default PulseLayer
