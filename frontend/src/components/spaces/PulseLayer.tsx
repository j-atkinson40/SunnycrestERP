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
import { computeLayerRowCount } from "@/components/spaces/utils/layer-row-count"
import { isItemRenderable } from "@/components/spaces/utils/renderability"
import { useViewportDimensions } from "@/hooks/useViewportFitMath"
import type {
  IntelligenceStream,
  LayerContent,
  LayerItem,
  LayerName,
  TimeOfDaySignal,
} from "@/types/pulse"
import { cn } from "@/lib/utils"


/**
 * Per-session debounce store for the canonical §13.4.3 console.warn.
 * Module-scoped (one per page session) so the same `${layer}:${
 * component_key}` warns ONCE during the session even though
 * PulseLayer re-renders on every Pulse refresh, viewport resize, or
 * dismiss action. Cleared on full page reload.
 *
 * Per §13.4.3: "console.warn fires for observability. RUM
 * integration captures the warn (post-September). Users never see
 * misconfigurations they didn't author."
 */
const _emittedWarnKeys = new Set<string>()


/** Reset for tests — production callers never use this. */
export function _resetPulseLayerWarnDebounceForTests(): void {
  _emittedWarnKeys.clear()
}


/**
 * Emit canonical Pulse missing-renderer warning, debounced per
 * `${layer}:${component_key}` so a continuously-failing widget
 * doesn't spam the console across renders.
 */
function _warnUnrenderable(
  layer: LayerName,
  item: LayerItem,
): void {
  const key = `${layer}:${item.component_key}`
  if (_emittedWarnKeys.has(key)) return
  _emittedWarnKeys.add(key)
  // eslint-disable-next-line no-console
  console.warn(
    "[pulse] missing widget renderer; skipping piece",
    {
      component_key: item.component_key,
      layer,
      item_id: item.item_id,
      kind: item.kind,
      hint:
        "Per DESIGN_LANGUAGE §13.4.3 agency-dictated error surface, " +
        "Pulse silently filters unrenderable pieces. Check that the " +
        "frontend `registerWidgetRenderer(widget_id, Component)` " +
        "matches the backend `WIDGET_DEFINITIONS` entry. The CI " +
        "parity test (`frontend/src/__tests__/widget-renderer-" +
        "parity.test.ts`) catches drift at build time.",
    },
  )
}


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


export function PulseLayer({
  layer,
  intelligenceStreams,
  timeOfDay,
  workAreas,
  pulseLoadedAt,
  onDismissItem,
  dismissedItemIds,
}: PulseLayerProps) {
  // Filter out (a) items the user dismissed in this session and (b)
  // unrenderable pieces per §13.4.3 platform-composed surface canon.
  // PulseSurface measurement walk applies the same renderability
  // filter so cell-height math + render stay consistent.
  //
  // For each piece filtered for unrenderability, fire the canonical
  // console.warn (debounced via module-scoped Set keyed on
  // `${layer.layer}:${component_key}` so a continuously-failing
  // widget doesn't spam across renders). Per canon:
  //   "console.warn fires for observability. RUM integration captures
  //    the warn (post-September). Users never see misconfigurations
  //    they didn't author."
  const visibleItems = layer.items.filter((it) => {
    if (dismissedItemIds.has(it.item_id)) return false
    if (!isItemRenderable(it)) {
      _warnUnrenderable(layer.layer, it)
      return false
    }
    return true
  })

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

  // Phase W-4a Step 6 Commit 2 + Commit 4 — compute this layer's row
  // count tier-aware + renderability-aware. Both PulseSurface (for
  // the aggregate measurement) and this layer (for grid-template-rows)
  // consume the same `column_count` from `useViewportDimensions()`
  // AND the same `isItemRenderable` predicate so tetris packing
  // matches across both render surfaces (the cell-height solver's
  // denominator equals the actually-rendered piece count).
  const dimensions = useViewportDimensions()
  const layerRowCount = computeLayerRowCount(
    layer.items,
    dismissedItemIds,
    dimensions.column_count,
    isItemRenderable,
  )

  return (
    <section
      data-slot="pulse-layer"
      data-layer={layer.layer}
      data-row-count={layerRowCount}
      data-column-count={dimensions.column_count}
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
        // Per §13.3.4 Step 7: grid-template-rows + grid-template-columns
        // use viewport-fit-solved CSS variables.
        //
        //   --pulse-cell-height: per-row height (Step 4 solver).
        //   --pulse-column-count: tier-resolved cols (Step 2; Commit 2
        //     replaces Commit 1's hardcoded auto-fit + minmax(160px,
        //     1fr) with tier-based 2/4/6 cols).
        //
        // Both transitions land here as inline styles (Tailwind doesn't
        // have built-in utilities for transitioning grid-template-*
        // with a custom cubic-bezier).
        style={{
          gridTemplateRows: `repeat(${layerRowCount}, var(--pulse-cell-height, 80px))`,
          gridTemplateColumns:
            "repeat(var(--pulse-column-count, 6), minmax(0, 1fr))",
          // Per §13.3.2 amendment: 350ms ease-out transition on both
          // grid-template-rows (cell_height changes) AND grid-template-
          // columns (tier-boundary transitions). Browsers handle
          // discrete int → int column count transitions inconsistently
          // (Chrome 127+ smooths via interpolation, others snap); the
          // transition declaration is harmless when not interpolated.
          // Comma-separated transition properties pick up both at the
          // canonical 350ms duration + cubic-bezier curve.
          transition:
            "grid-template-rows 350ms cubic-bezier(0.4, 0, 0.2, 1), grid-template-columns 350ms cubic-bezier(0.4, 0, 0.2, 1)",
        }}
        className={cn(
          // Tetris layout per §13.3.1 + D2 (custom CSS Grid via
          // WidgetGrid pattern). Tier-based columns + viewport-fit
          // rows.
          //
          // `grid-flow-row-dense` (Phase W-4a Step 2.C, April 2026):
          // smaller pieces (e.g. today widget Glance 1×1) backfill
          // empty cells left by larger pieces' spans rather than
          // leaving row-2 visual gaps. Pieces still respect their
          // priority-driven render order (composition_engine sorts
          // before emission); dense flow only changes _which empty
          // cell_ each smaller piece lands in, not the order pieces
          // are placed.
          "grid grid-flow-row-dense",
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
