/**
 * AnomalyIntelligenceStream V1 — Phase W-4a Commit 5.
 *
 * Renders the synthesized anomaly-watch-list intelligence stream
 * from the backend (`anomaly_intelligence_v1.synthesize`). Per
 * DESIGN_LANGUAGE.md §13.4.2:
 *   • Pattern 2 chrome (solid-fill, rounded-[2px])
 *   • Slightly more prose vs structured data
 *   • Reasoning-context chrome ("Today's watch list:" header)
 *   • Brass-thread accent at top edge (1px aged-brass divider
 *     signaling "composed by intelligence")
 *   • Synthesized text in reading-friendly typography
 *   • Referenced items as inline chips beneath the synthesis copy
 *
 * V2 (Haiku-cached, richer synthesis) deferred per D6. V1's
 * rule-based template is what ships in W-4a.
 *
 * Empty state: backend returns no `anomaly_intelligence` stream
 * when no anomalies exist. The Anomaly Layer's "All clear"
 * advisory carries that UX. This component never renders an empty
 * state itself — if it's mounted, there's content.
 */

import { Sparkles } from "lucide-react"

import { cn } from "@/lib/utils"
import type { IntelligenceStream } from "@/types/pulse"


export interface AnomalyIntelligenceStreamProps {
  stream: IntelligenceStream
  /** Click-through handler. PulsePiece wires this to fire a
   *  navigation signal + actually navigate; the component itself
   *  stays presentational. */
  onReferencedItemClick?: (entityId: string, kind: string) => void
}


export function AnomalyIntelligenceStream({
  stream,
  onReferencedItemClick,
}: AnomalyIntelligenceStreamProps) {
  return (
    <div
      data-slot="anomaly-intelligence-stream"
      data-stream-id={stream.stream_id}
      className={cn(
        // Phase W-4a Step 5 (May 2026): Pattern 2 chrome moved to
        // PulsePiece outer div per the chrome-is-surface-responsibility
        // convention (DESIGN_LANGUAGE §13.4.1 amendment). This stream
        // component now provides only content + the brass-thread
        // top-edge accent that's unique to intelligence streams per
        // §13.4.2. PulsePiece's outer div carries rounded-[2px] +
        // bg-surface-elevated + border + shadow.
        "relative h-full w-full",
        // Brass-thread top-edge accent per §13.4.2 — 1px line in
        // accent (aged-terracotta) signals composed-by-intelligence.
        // The pseudo lives on the PulsePiece's child div (this one)
        // so it sits inside the surface chrome the parent applies.
        "before:content-['']",
        "before:absolute before:left-0 before:right-0 before:top-0",
        "before:h-px before:bg-accent",
        "before:rounded-[2px_2px_0_0]",
        "p-3",
        "flex flex-col gap-2",
        "overflow-hidden",
      )}
    >
      {/* Reasoning-context chrome: title with icon, slightly more
          prose-shaped than structured-data widgets. */}
      <div className="flex items-center gap-1.5">
        <Sparkles
          className="h-3 w-3 text-accent"
          aria-hidden
        />
        <h3
          className="text-caption font-medium text-content-muted font-sans uppercase tracking-wide"
          data-slot="anomaly-intelligence-title"
        >
          {stream.title}
        </h3>
      </div>

      {/* Synthesized text — reading-friendly typography per §13.4.2.
          Slightly larger than `caption`, more prose-like leading. */}
      <p
        className="text-body-sm text-content-base font-sans leading-relaxed"
        data-slot="anomaly-intelligence-text"
      >
        {stream.synthesized_text}
      </p>

      {/* Referenced items as inline chips. Per §13.4.2: clickable
          to investigate. */}
      {stream.referenced_items.length > 0 ? (
        <ul
          className="flex flex-wrap gap-1 mt-auto pt-1"
          data-slot="anomaly-intelligence-references"
        >
          {stream.referenced_items.slice(0, 5).map((ref) => (
            <li key={ref.entity_id}>
              <button
                type="button"
                onClick={() =>
                  onReferencedItemClick?.(ref.entity_id, ref.kind)
                }
                className={cn(
                  "inline-flex items-center px-2 py-0.5",
                  "text-caption font-sans text-content-muted",
                  "rounded-sm border border-border-subtle bg-surface-base",
                  "hover:bg-accent-subtle hover:text-content-base hover:border-accent/30",
                  "focus-ring-accent outline-none",
                  "transition-colors duration-quick ease-settle",
                  "max-w-[200px] truncate",
                )}
                data-slot="anomaly-intelligence-reference-chip"
                title={ref.label}
              >
                {ref.label}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}


export default AnomalyIntelligenceStream
