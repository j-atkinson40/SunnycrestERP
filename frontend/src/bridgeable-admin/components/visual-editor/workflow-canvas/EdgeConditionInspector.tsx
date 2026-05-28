/**
 * EdgeConditionInspector — Phase B sub-arc B-5 (selection-driven chrome).
 *
 * Right-rail inspector shown when an EDGE is selected (selection.kind ===
 * "edge"). Edits the edge's branching condition + display label; the id
 * is read-only (identity).
 *
 * `condition` is a Jinja expression authored as a PLAIN STRING — the
 * workflow engine evaluates it at runtime. B-5 does NOT validate Jinja
 * server-side (out of scope per §2.E.6); the field is a free-text editor.
 *
 * Mirrors the B-3 inspector contract: `{ edge, onChange }` where onChange
 * emits the full next edge object; the page proxies it into the
 * canvas-state edges array via the existing mutation + auto-save path.
 */

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { CanvasEdge } from "@/bridgeable-admin/services/workflow-templates-service"

export interface EdgeConditionInspectorProps {
  edge: CanvasEdge
  onChange: (next: CanvasEdge) => void
}

export function EdgeConditionInspector({
  edge,
  onChange,
}: EdgeConditionInspectorProps) {
  return (
    <div className="flex flex-col gap-3" data-testid="edge-condition-inspector">
      <div>
        <Label className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted">
          Edge id
        </Label>
        <div
          className="rounded-md border border-border-subtle bg-surface-sunken px-2 py-1.5 font-plex-mono text-caption text-content-muted"
          data-testid="edge-inspector-id"
        >
          {edge.id}
        </div>
      </div>

      <div>
        <Label
          htmlFor="edge-condition-input"
          className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted"
        >
          Condition (Jinja)
        </Label>
        <Input
          id="edge-condition-input"
          value={edge.condition ?? ""}
          placeholder="e.g. {{ disposition == 'burial' }}"
          onChange={(e) => onChange({ ...edge, condition: e.target.value })}
          data-testid="edge-inspector-condition"
          className="font-plex-mono text-caption"
        />
        <p className="mt-0.5 text-caption text-content-muted">
          Branching expression evaluated by the workflow engine at runtime.
        </p>
      </div>

      <div>
        <Label
          htmlFor="edge-label-input"
          className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted"
        >
          Label
        </Label>
        <Input
          id="edge-label-input"
          value={edge.label ?? ""}
          onChange={(e) => onChange({ ...edge, label: e.target.value })}
          data-testid="edge-inspector-label"
          className="text-caption"
        />
      </div>
    </div>
  )
}
