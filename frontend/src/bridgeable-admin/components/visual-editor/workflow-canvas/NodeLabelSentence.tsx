/**
 * NodeLabelSentence — renders a workflow node's natural-language label
 * sentence (inline-params thread, P1, 2026-05-29). Consumes the pure
 * render model from `workflow-node-templates.interpolate` and renders
 * literals as text + slots as token-styled spans.
 *
 * P1 = READ-ONLY: tokens carry the "this is editable" visual affordance
 * (subtle accent-tinted chip; placeholder tokens dimmed) but are NOT
 * clickable. P2 makes them interactive (click → scoped popover edit).
 * Token styling uses existing DESIGN_LANGUAGE tokens only — no new tokens.
 *
 * Falls back to the plain node label when the type has no template
 * (renderModelFor → null): the raw label text, so untyped/unknown nodes
 * still read sensibly.
 */
import {
  renderModelFor,
  type RenderedSegment,
} from "@/lib/visual-editor/workflow-node-templates"

export interface NodeLabelSentenceProps {
  nodeId: string
  nodeType: string
  config: Record<string, unknown>
  /** Fallback text when the type has no template (raw node label). */
  fallback?: string
}

export function NodeLabelSentence({
  nodeId,
  nodeType,
  config,
  fallback,
}: NodeLabelSentenceProps) {
  const model = renderModelFor(nodeType, config)

  // No template for this type → plain fallback text (raw label / type).
  if (model === null) {
    return (
      <span
        data-testid={`node-sentence-${nodeId}`}
        className="text-caption text-content-strong"
      >
        {fallback ?? nodeType}
      </span>
    )
  }

  return (
    <span
      data-testid={`node-sentence-${nodeId}`}
      className="text-caption leading-relaxed text-content-strong"
    >
      {model.map((seg: RenderedSegment, i) =>
        seg.kind === "literal" ? (
          <span key={i}>{seg.text}</span>
        ) : (
          <span
            key={i}
            data-testid={`node-token-${nodeId}-${seg.param}`}
            data-token-param={seg.param}
            data-token-placeholder={seg.placeholder ? "true" : "false"}
            // Token affordance (read-only in P1): subtle accent-tinted chip
            // for set values; dimmed muted chip for unset placeholders.
            // P2 attaches onClick + a popover; the styling already signals
            // tokenness so the P1→P2 transition is visually continuous.
            className={
              seg.placeholder
                ? "mx-0.5 rounded-sm border border-dashed border-border-base px-1 text-content-muted"
                : "mx-0.5 rounded-sm border border-accent/30 bg-accent-subtle px-1 text-content-strong"
            }
          >
            {seg.text}
          </span>
        ),
      )}
    </span>
  )
}
