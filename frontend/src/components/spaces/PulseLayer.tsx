/**
 * PulseLayer — Phase W-4a Commit 5.
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

  return (
    <section
      data-slot="pulse-layer"
      data-layer={layer.layer}
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
        className={cn(
          // Tetris layout per §13.3.1 + D2 (custom CSS Grid via
          // WidgetGrid pattern). Auto-fit columns + auto-rows
          // give breathing-room composition; pieces flow into
          // available space sized to their cols/rows hints.
          //
          // Min-width 160px on each grid column means a 1×1 piece
          // (Glance) is roughly 160px wide; 2-col pieces span
          // 320px+ etc. Auto-rows 80px gives ~80px row height,
          // matching the canonical Pattern 1 sidebar Glance height
          // (60px) with a touch of internal padding budget. A
          // Detail piece (2×2) is ~320px × ~160px — enough for
          // vault_schedule's kanban-shaped Detail variant content.
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
          "grid-cols-[repeat(auto-fit,minmax(160px,1fr))]",
          "auto-rows-[80px]",
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
