/**
 * BespokeNodePane — Inline-params P3c (inspector retirement, card editor).
 *
 * The narrow retained node-config pane for the 2 bespoke-namespace types
 * (invoke_generation_focus / invoke_review_focus). After P3c the card
 * editor's rail shows the palette for normal node-selection — edits happen
 * ON THE CARD (config tokens + P3a expand panel + inline label) and on the
 * canvas (edges via drag-to-connect + midpoint-×). These 2 types are the
 * exception: they CAN'T edit inline because their authoring namespace
 * (config.focus_id / config.review_focus_id) diverges from the template's
 * {focusTemplateName} slot — the P2b phantom-key finding (see
 * BESPOKE_NAMESPACE_TYPES in workflow-node-templates.ts). So they keep this
 * pane, routing to their existing bespoke configs.
 *
 * TEMPORARY REMNANT: this pane disappears when the filed-forward
 * "Focus-invocation namespace reconciliation + dedupe" arc lands — at which
 * point the 2 invoke_* types edit inline like the other 31 and the rail
 * shows them the palette too.
 *
 * The bespoke configs (InvokeGenerationFocusConfig / InvokeReviewFocusConfig)
 * are shared VERBATIM with WorkflowsTab's NodeConfigForm — unchanged here;
 * this pane is a thin type→config router so the card editor can render them
 * without the full NodeConfigForm (which it retired). onChange receives the
 * full next config; the page persists it via handleUpdateNode(id, {config}).
 */
import type { CanvasNode } from "@/bridgeable-admin/services/workflow-templates-service"

import { InvokeGenerationFocusConfig } from "./InvokeGenerationFocusConfig"
import { InvokeReviewFocusConfig } from "./InvokeReviewFocusConfig"

export interface BespokeNodePaneProps {
  node: CanvasNode
  /** Receives the FULL next config (mirrors the bespoke configs' onChange). */
  onChange: (nextConfig: Record<string, unknown>) => void
}

export function BespokeNodePane({ node, onChange }: BespokeNodePaneProps) {
  return (
    <div className="flex flex-col gap-3" data-testid="bespoke-node-pane">
      {node.type === "invoke_generation_focus" ? (
        <InvokeGenerationFocusConfig config={node.config} onChange={onChange} />
      ) : node.type === "invoke_review_focus" ? (
        <InvokeReviewFocusConfig config={node.config} onChange={onChange} />
      ) : null}
    </div>
  )
}
