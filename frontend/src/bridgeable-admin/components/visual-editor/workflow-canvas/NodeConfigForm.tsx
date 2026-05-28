/**
 * NodeConfigForm — extracted from WorkflowEditorPage in Arc 2 Phase 2b
 * to allow verbatim reuse inside the inspector Workflows tab's
 * 3-level mode-stack (list → workflow-edit → node-config).
 *
 * Behavior is preserved byte-for-byte from the standalone editor's
 * internal NodeConfigForm function (per parity-not-exceedance canon).
 * Dispatches to InvokeGenerationFocusConfig / InvokeReviewFocusConfig
 * for the two workflow-engine-canonical Focus invocation node types;
 * everything else gets a JSON textarea fallback with parse validation.
 *
 * Consumers:
 * - WorkflowEditorPage (standalone, full surface)
 * - WorkflowsTab (inspector, 380px constrained)
 *
 * Both render the same component verbatim. At 380px the form fits
 * cleanly (standalone right pane is ~320px; inspector body is ~380px).
 */
import { useState } from "react"
import { Plus, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { VALID_NODE_TYPES } from "@/lib/visual-editor/workflows/canvas-validator"
import type { CanvasNode } from "@/bridgeable-admin/services/workflow-templates-service"

import { InvokeGenerationFocusConfig } from "./InvokeGenerationFocusConfig"
import { InvokeReviewFocusConfig } from "./InvokeReviewFocusConfig"
// Phase B sub-arc B-3 — schema-driven generic inspector. Replaces the
// JSON-textarea fallback for the 30 node types without a bespoke config
// (Decision §(a) Option Y). Bespoke overrides dispatch ahead of it.
import { RegistryDrivenConfig } from "./RegistryDrivenConfig"


export interface NodeConfigFormProps {
  node: CanvasNode
  allNodes: CanvasNode[]
  outgoingEdges: Array<{
    id: string
    source: string
    target: string
    condition?: string
    label?: string
  }>
  onPatch: (patch: Partial<CanvasNode>) => void
  onAddEdge: (target: string) => void
  onRemoveEdge: (edgeId: string) => void
}


export function NodeConfigForm({
  node,
  allNodes,
  outgoingEdges,
  onPatch,
  onAddEdge,
  onRemoveEdge,
}: NodeConfigFormProps) {
  const [edgeTargetSelect, setEdgeTargetSelect] = useState<string>("")

  const candidateTargets = allNodes.filter(
    (n) =>
      n.id !== node.id &&
      !outgoingEdges.some((e) => e.target === n.id),
  )

  return (
    <div className="flex flex-col gap-3" data-testid="node-config-form">
      <div>
        <label className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted">
          Type
        </label>
        <select
          value={node.type}
          onChange={(e) => onPatch({ type: e.target.value })}
          data-testid="node-config-type-select"
          className="w-full rounded-md border border-border-base bg-surface-raised px-2 py-1.5 font-plex-mono text-caption text-content-strong"
        >
          {VALID_NODE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label
          htmlFor="node-id-input"
          className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted"
        >
          Node id
        </label>
        <Input
          id="node-id-input"
          value={node.id}
          onChange={(e) => onPatch({ id: e.target.value })}
          data-testid="node-config-id-input"
          className="font-plex-mono text-caption"
        />
      </div>

      <div>
        <label
          htmlFor="node-label-input"
          className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted"
        >
          Label
        </label>
        <Input
          id="node-label-input"
          value={node.label ?? ""}
          onChange={(e) => onPatch({ label: e.target.value })}
          data-testid="node-config-label-input"
        />
      </div>

      {/* Per-type config dispatch (B-3): bespoke override if registered,
          else the schema-driven RegistryDrivenConfig. The pre-B-3
          JSON-textarea fallback is removed — every canonical node type
          now has a real inspector. */}
      {node.type === "invoke_generation_focus" ? (
        <InvokeGenerationFocusConfig
          config={node.config}
          onChange={(next) => onPatch({ config: next })}
        />
      ) : node.type === "invoke_review_focus" ? (
        <InvokeReviewFocusConfig
          config={node.config}
          onChange={(next) => onPatch({ config: next })}
        />
      ) : (
        <RegistryDrivenConfig
          nodeName={node.type}
          config={node.config}
          onChange={(next) => onPatch({ config: next })}
        />
      )}

      <div>
        <label className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted">
          Outgoing edges
        </label>
        <ul className="flex flex-col gap-1" data-testid="node-config-edges">
          {outgoingEdges.length === 0 ? (
            <li className="text-caption text-content-muted">
              No outgoing edges.
            </li>
          ) : (
            outgoingEdges.map((e) => {
              const target = allNodes.find((n) => n.id === e.target)
              return (
                <li
                  key={e.id}
                  className="flex items-center justify-between gap-1 rounded-sm bg-surface-raised px-2 py-1"
                >
                  <span className="text-caption">
                    →{" "}
                    <code className="font-plex-mono">
                      {target?.label ?? e.target}
                    </code>
                    {e.condition && (
                      <span className="ml-1 italic text-content-muted">
                        ({e.condition})
                      </span>
                    )}
                  </span>
                  <button
                    type="button"
                    onClick={() => onRemoveEdge(e.id)}
                    data-testid={`node-config-edge-${e.id}-remove`}
                    aria-label="Remove edge"
                    className="rounded-sm border border-border-base bg-surface-raised p-0.5 text-content-muted hover:text-status-error"
                  >
                    <Trash2 size={10} />
                  </button>
                </li>
              )
            })
          )}
        </ul>
        <div className="mt-1 flex items-center gap-1">
          <select
            value={edgeTargetSelect}
            onChange={(e) => setEdgeTargetSelect(e.target.value)}
            data-testid="node-config-edge-target-select"
            className="flex-1 rounded-md border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-strong"
          >
            <option value="">— select target —</option>
            {candidateTargets.map((n) => (
              <option key={n.id} value={n.id}>
                {n.label || n.id}
              </option>
            ))}
          </select>
          <Button
            size="sm"
            disabled={!edgeTargetSelect}
            onClick={() => {
              if (edgeTargetSelect) {
                onAddEdge(edgeTargetSelect)
                setEdgeTargetSelect("")
              }
            }}
            data-testid="node-config-add-edge"
          >
            <Plus size={12} className="mr-1" />
            Edge
          </Button>
        </div>
      </div>
    </div>
  )
}
