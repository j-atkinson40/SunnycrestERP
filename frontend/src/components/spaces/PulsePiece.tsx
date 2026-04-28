/**
 * PulsePiece — Phase W-4a Commit 5.
 *
 * Renders a single Pulse content piece. Two render paths per
 * DESIGN_LANGUAGE.md §13.4:
 *
 *   • Widget pieces (`item.kind === "widget"`):
 *       Resolve renderer via `getWidgetRenderer(component_key)`,
 *       pass `surface="pulse_grid"` per §12.5, pass `config`
 *       (W-3b plumbing fix), pass `variant_id`.
 *
 *   • Stream pieces (`item.kind === "stream"`):
 *       Look up the corresponding IntelligenceStream from the
 *       composition's `intelligence_streams` array by
 *       `component_key === stream_id`. For the only V1 stream
 *       shipped this commit (`anomaly_intelligence`), render
 *       `<AnomalyIntelligenceStream>`. Future streams (smart
 *       email, briefing, etc., Phase W-4b) extend the dispatch
 *       table here.
 *
 * Signal collection chrome per §13.5:
 *   • Dismiss X icon top-right, opacity-30 default → opacity-100
 *     hover, brass on hover. On click: animates piece out + fires
 *     `recordDismiss()` signal.
 *   • Navigation tracking: when a piece's interior triggers
 *     navigation (widget click-through, stream chip click), this
 *     component fires `recordNavigation()` with computed dwell
 *     time. The widget renderers themselves don't know about
 *     Pulse — they navigate via React Router; PulsePiece wraps
 *     the click with a navigation-tracker that also fires the
 *     signal.
 *
 * Pattern 2 chrome (Phase W-4a Step 5, May 2026):
 * PulsePiece applies Pattern 2 chrome at its own root; widget
 * renderers provide content only. This keeps surface chrome
 * decisions with the surface, not duplicated across every widget.
 *
 * The dashboard surface applies the equivalent chrome via
 * `WidgetWrapper.tsx:72` (rounded-md + bg-surface-elevated +
 * shadow-level-1). Pulse uses the §11 Pattern 2 / §13.4.1 chrome
 * (rounded-[2px] + bg-surface-elevated + border-border-subtle +
 * shadow-level-1) to match `AnomalyIntelligenceStream` (the V1
 * intelligence stream reference that already applied this chrome
 * at its own root). Result: every Pulse piece is a clearly-bounded
 * card whether it's a widget or an intelligence stream.
 *
 * Convention: widget renderers should NOT apply Pattern 2 chrome at
 * their root. Surface (PulsePiece, WidgetWrapper) applies chrome
 * appropriate to that surface; widgets that double-apply chrome
 * produce nested cards. See DESIGN_LANGUAGE §13.4.1 Step-5
 * convention note.
 *
 * Pre-Step-5 the docstring claimed widget renderers carry their own
 * Pattern 2 chrome — that was an incorrect assumption. The chrome
 * lives on `WidgetWrapper` for dashboard surfaces; widget root
 * elements have only `flex flex-col h-full p-4`. Pulse pieces
 * rendered without any chrome at all, making the surface read as
 * "scattered" rather than as composed cards. Step 5 corrects.
 */

import { useCallback, useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { X } from "lucide-react"

import { AnomalyIntelligenceStream } from "@/components/spaces/intelligence-streams/AnomalyIntelligenceStream"
import { getWidgetRenderer } from "@/components/focus/canvas/widget-renderers"
import {
  recordDismiss,
  recordNavigation,
} from "@/services/pulse-service"
import type {
  IntelligenceStream,
  LayerItem,
  LayerName,
  TimeOfDaySignal,
} from "@/types/pulse"
import { cn } from "@/lib/utils"


export interface PulsePieceProps {
  item: LayerItem
  /** The parent layer name — fired into signal payloads so
   *  Tier 2 algorithms can reason about which layer a dismissed
   *  piece belonged to. */
  layer: LayerName
  /** Time-of-day from composition metadata — fired into dismiss
   *  signal payload per the standardized JSONB shape. */
  timeOfDay: TimeOfDaySignal
  /** User's current work_areas (snapshot — fired into dismiss
   *  signal so Tier 2 can correlate "user dismissed X while in
   *  [areas]" patterns). */
  workAreas: string[]
  /** Composition's `intelligence_streams` — looked up by
   *  `component_key === stream_id` for stream pieces. */
  intelligenceStreams: IntelligenceStream[]
  /** Wall-clock millis when the composition currently rendered
   *  was first received. PulsePiece reads this to compute dwell
   *  time on navigation. */
  pulseLoadedAt: number | null
  /** Called when the user dismisses this piece. Parent
   *  PulseSurface handles the animation by removing the piece
   *  from its rendered set. */
  onDismiss?: (itemId: string) => void
}


export function PulsePiece({
  item,
  layer,
  timeOfDay,
  workAreas,
  intelligenceStreams,
  pulseLoadedAt,
  onDismiss,
}: PulsePieceProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const [animatingOut, setAnimatingOut] = useState(false)

  // ── Dismiss handling ────────────────────────────────────────────

  const handleDismiss = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      e.preventDefault()
      setAnimatingOut(true)
      void recordDismiss(item.component_key, layer, timeOfDay, workAreas)
      // Wait for fade-out before unmounting via parent.
      window.setTimeout(() => {
        onDismiss?.(item.item_id)
      }, 200)
    },
    [item.component_key, item.item_id, layer, timeOfDay, workAreas, onDismiss],
  )

  // ── Navigation tracking ─────────────────────────────────────────

  const fireNavigationSignal = useCallback(
    (toRoute: string) => {
      const dwellMs = pulseLoadedAt
        ? Date.now() - pulseLoadedAt
        : 0
      const dwellSec = Math.max(0, Math.floor(dwellMs / 1000))
      void recordNavigation(
        item.component_key,
        toRoute,
        dwellSec,
        layer,
      )
    },
    [item.component_key, layer, pulseLoadedAt],
  )

  // Capture-phase listener catches click-throughs from widget
  // interiors. Widget renderers navigate via <Link> or
  // useNavigate; we intercept at the wrapper boundary, fire the
  // signal, then let the navigation proceed.
  const handlePieceClickCapture = useCallback(
    (e: React.MouseEvent) => {
      // Find the nearest <a> ancestor inside our piece — that's
      // the actual navigation target.
      const target = e.target as HTMLElement
      const anchor = target.closest("a[href]") as HTMLAnchorElement | null
      if (anchor && !anchor.target) {
        fireNavigationSignal(anchor.getAttribute("href") || "")
      }
      // Don't preventDefault — let the navigation continue.
    },
    [fireNavigationSignal],
  )

  // Stream chip click — the stream component invokes this with
  // (entityId, kind); we map kind → route and fire signal +
  // navigate.
  const handleStreamReferenceClick = useCallback(
    (_entityId: string, kind: string) => {
      // V1 anomaly intelligence has no canonical entity-detail
      // route yet (anomalies surface via /agents); Tier 2 routing
      // is post-W-4a. For now, treat all anomaly references as
      // /agents click-throughs.
      const toRoute = kind === "anomaly" ? "/agents" : "/agents"
      fireNavigationSignal(toRoute)
      navigate(toRoute, { state: { from: location.pathname } })
    },
    [fireNavigationSignal, navigate, location.pathname],
  )

  // ── Render dispatch ─────────────────────────────────────────────

  const inner = (() => {
    if (item.kind === "stream") {
      const stream = intelligenceStreams.find(
        (s) => s.stream_id === item.component_key,
      )
      if (!stream) {
        // Defensive: stream missing from composition (shouldn't
        // happen for V1; backend always includes it when the
        // LayerItem exists). Render nothing — empty piece.
        return null
      }
      // Currently only one stream type ships in V1.
      if (stream.stream_id === "anomaly_intelligence") {
        return (
          <AnomalyIntelligenceStream
            stream={stream}
            onReferencedItemClick={handleStreamReferenceClick}
          />
        )
      }
      // Future stream IDs dispatch here.
      return null
    }

    // Widget piece — dispatch through the registry.
    const Renderer = getWidgetRenderer(item.component_key, item.variant_id)
    return (
      <Renderer
        widgetId={item.component_key}
        variant_id={item.variant_id}
        surface="pulse_grid"
        config={item.payload}
      />
    )
  })()

  return (
    <div
      data-slot="pulse-piece"
      data-item-id={item.item_id}
      data-kind={item.kind}
      data-component-key={item.component_key}
      data-variant-id={item.variant_id}
      data-layer={layer}
      style={{
        gridColumn: `span ${item.cols}`,
        gridRow: `span ${item.rows}`,
      }}
      className={cn(
        "group relative",
        // Pattern 2 chrome per DESIGN_LANGUAGE §11 + §13.4.1
        // (Phase W-4a Step 5, May 2026). PulsePiece is the surface
        // chrome owner; widget renderers + AnomalyIntelligenceStream
        // provide content only. Matches the dashboard surface's
        // WidgetWrapper chrome shape (rounded-md+bg-surface-elevated+
        // shadow-level-1) but uses §11-Pattern-2-locked rounded-[2px]
        // for tighter Pulse-grid feel + adds the canonical hairline
        // border so cards demarcate cleanly against the warm-cream
        // / warm-charcoal substrate.
        "rounded-[2px]",
        "bg-surface-elevated",
        "border border-border-subtle",
        "shadow-level-1",
        "overflow-hidden",
        "transition-all duration-settle ease-settle",
        animatingOut ? "opacity-0 scale-95" : "opacity-100 scale-100",
      )}
      onClickCapture={handlePieceClickCapture}
    >
      {/* Dismiss X chrome per §13.5.1 — visible on hover, low-
          contrast at rest. Brass on hover. Sits absolute top-right
          inside the piece. */}
      <button
        type="button"
        onClick={handleDismiss}
        aria-label="Dismiss this piece"
        data-slot="pulse-piece-dismiss"
        className={cn(
          "absolute top-1.5 right-1.5 z-10",
          "flex h-5 w-5 items-center justify-center rounded-sm",
          "opacity-0 group-hover:opacity-100",
          "text-content-subtle hover:text-accent",
          "hover:bg-accent-subtle",
          "focus-ring-accent outline-none focus:opacity-100",
          "transition-opacity duration-quick ease-settle",
        )}
      >
        <X className="h-3 w-3" />
      </button>

      {inner}
    </div>
  )
}


export default PulsePiece
