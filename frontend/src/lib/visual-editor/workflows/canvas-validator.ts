/**
 * Frontend canvas validator — mirror of the backend's
 * `app/services/workflow_templates/canvas_validator.py`.
 *
 * The two validators MUST agree on schema rules. Tests verify
 * cross-reference — every CanvasState valid on one side is valid
 * on the other. Used by the admin canvas editor to short-circuit
 * write requests that would 400 at the backend; UI shows the
 * validation message inline before the round-trip.
 */

import type { CanvasState } from "@/bridgeable-admin/services/workflow-templates-service"


export class CanvasValidationError extends Error {}


export const VALID_NODE_TYPES: ReadonlyArray<string> = [
  "start",
  "end",
  "input",
  "action",
  "ai_prompt",
  "send_document",
  "playwright_action",
  "condition",
  "output",
  "notification",
  "create_record",
  "update_record",
  "open_slide_over",
  "show_confirmation",
  "send_notification",
  "send_email",
  "log_vault_item",
  "generate_document",
  "call_service_method",
  "generation-focus-invocation",
  // Phase R-6.0a — headless Generation Focus + Review Focus invocations.
  // Mirrors backend `app/services/workflow_templates/canvas_validator.py`
  // VALID_NODE_TYPES additions. Frontend authoring surfaces (the new
  // InvokeGenerationFocusConfig + InvokeReviewFocusConfig inspector
  // panes) consume these node types directly.
  "invoke_generation_focus",
  "invoke_review_focus",
  "send-communication",
  "cross_tenant_order",
  "cross_tenant_request",
  "cross_tenant_acknowledgment",
  "decision",
  "branch",
  "parallel_split",
  "parallel_join",
  "wait",
  "schedule",
] as const


/** Validate a canvas_state payload. Throws `CanvasValidationError`
 * on shape violations; no-op on valid input. Empty `{}` is
 * permitted (represents an unauthored draft). */
export function validateCanvasState(
  canvas: Partial<CanvasState> | undefined | null,
): asserts canvas is CanvasState | Record<string, never> {
  if (canvas === undefined || canvas === null) {
    throw new CanvasValidationError(
      "canvas_state must be a defined object",
    )
  }
  if (typeof canvas !== "object" || Array.isArray(canvas)) {
    throw new CanvasValidationError("canvas_state must be a mapping")
  }
  // Empty {} is valid (unauthored draft).
  const keys = Object.keys(canvas)
  if (keys.length === 0) return

  const required = ["nodes", "edges", "version"]
  const missing = required.filter((k) => !(k in canvas))
  if (missing.length > 0) {
    throw new CanvasValidationError(
      `canvas_state missing required keys: ${missing.join(", ")}`,
    )
  }

  const c = canvas as CanvasState

  if (!Number.isInteger(c.version) || c.version < 1) {
    throw new CanvasValidationError(
      `canvas_state.version must be a positive integer, got ${String(c.version)}`,
    )
  }

  if (!Array.isArray(c.nodes)) {
    throw new CanvasValidationError("canvas_state.nodes must be an array")
  }
  if (!Array.isArray(c.edges)) {
    throw new CanvasValidationError("canvas_state.edges must be an array")
  }

  const validTypes = new Set(VALID_NODE_TYPES)

  // Per-node validation + id uniqueness
  const seenNodeIds = new Set<string>()
  c.nodes.forEach((node, idx) => {
    if (typeof node !== "object" || node === null) {
      throw new CanvasValidationError(`nodes[${idx}] must be a mapping`)
    }
    if (typeof node.id !== "string" || node.id.length === 0) {
      throw new CanvasValidationError(
        `nodes[${idx}].id must be a non-empty string`,
      )
    }
    if (seenNodeIds.has(node.id)) {
      throw new CanvasValidationError(
        `nodes[${idx}].id duplicates an earlier node: ${node.id}`,
      )
    }
    seenNodeIds.add(node.id)
    if (typeof node.type !== "string" || node.type.length === 0) {
      throw new CanvasValidationError(
        `nodes[${idx}].type must be a non-empty string`,
      )
    }
    if (!validTypes.has(node.type)) {
      throw new CanvasValidationError(
        `nodes[${idx}].type "${node.type}" not in VALID_NODE_TYPES`,
      )
    }
    if (typeof node.position !== "object" || node.position === null) {
      throw new CanvasValidationError(
        `nodes[${idx}].position must be a mapping`,
      )
    }
    if (typeof node.config !== "object" || Array.isArray(node.config)) {
      throw new CanvasValidationError(
        `nodes[${idx}].config must be a mapping`,
      )
    }
  })

  // Per-edge validation + id uniqueness + reference integrity
  const seenEdgeIds = new Set<string>()
  c.edges.forEach((edge, idx) => {
    if (typeof edge !== "object" || edge === null) {
      throw new CanvasValidationError(`edges[${idx}] must be a mapping`)
    }
    if (typeof edge.id !== "string" || edge.id.length === 0) {
      throw new CanvasValidationError(
        `edges[${idx}].id must be a non-empty string`,
      )
    }
    if (seenEdgeIds.has(edge.id)) {
      throw new CanvasValidationError(
        `edges[${idx}].id duplicates an earlier edge: ${edge.id}`,
      )
    }
    seenEdgeIds.add(edge.id)
    if (typeof edge.source !== "string" || !seenNodeIds.has(edge.source)) {
      throw new CanvasValidationError(
        `edges[${idx}].source "${edge.source}" doesn't reference a declared node id`,
      )
    }
    if (typeof edge.target !== "string" || !seenNodeIds.has(edge.target)) {
      throw new CanvasValidationError(
        `edges[${idx}].target "${edge.target}" doesn't reference a declared node id`,
      )
    }
  })

  // Cycle check (excluding edges with is_iteration=true)
  detectCycles(c.nodes, c.edges)
}


function detectCycles(
  nodes: Array<{ id: string }>,
  edges: Array<{ source: string; target: string; is_iteration?: boolean }>,
): void {
  const adj = new Map<string, string[]>()
  for (const n of nodes) adj.set(n.id, [])
  for (const e of edges) {
    if (e.is_iteration === true) continue
    if (!adj.has(e.source)) adj.set(e.source, [])
    adj.get(e.source)!.push(e.target)
  }

  // Three-color DFS
  const WHITE = 0
  const GRAY = 1
  const BLACK = 2
  const color = new Map<string, number>()
  for (const id of adj.keys()) color.set(id, WHITE)

  function visit(id: string, path: string[]): void {
    if (color.get(id) === GRAY) {
      throw new CanvasValidationError(
        `canvas_state contains a cycle: ${[...path, id].join(" → ")}. ` +
          "To express iteration explicitly, mark the back-edge with is_iteration=true.",
      )
    }
    if (color.get(id) === BLACK) return
    color.set(id, GRAY)
    for (const neighbor of adj.get(id) ?? []) {
      visit(neighbor, [...path, id])
    }
    color.set(id, BLACK)
  }

  for (const id of color.keys()) {
    if (color.get(id) === WHITE) visit(id, [])
  }
}


/** Compute summary stats for the workflow editor's metadata strip
 * — node count, edge count, terminal-node count, branching nodes. */
export function summarizeCanvas(canvas: Partial<CanvasState>): {
  nodes: number
  edges: number
  terminalNodes: number
  branchingNodes: number
} {
  if (!canvas || !canvas.nodes || !canvas.edges) {
    return { nodes: 0, edges: 0, terminalNodes: 0, branchingNodes: 0 }
  }
  const outgoing = new Map<string, number>()
  for (const e of canvas.edges) {
    if (e.is_iteration === true) continue
    outgoing.set(e.source, (outgoing.get(e.source) ?? 0) + 1)
  }
  let terminals = 0
  let branching = 0
  for (const n of canvas.nodes) {
    const o = outgoing.get(n.id) ?? 0
    if (o === 0) terminals += 1
    if (o > 1) branching += 1
  }
  return {
    nodes: canvas.nodes.length,
    edges: canvas.edges.length,
    terminalNodes: terminals,
    branchingNodes: branching,
  }
}
