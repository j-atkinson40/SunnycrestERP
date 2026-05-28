/**
 * simulate-trace — Phase B sub-arc B-4 (execution-trace reachability).
 *
 * Pure-function design-time reachability simulation over a workflow
 * canvas_state. Powers the GraphCanvas trace overlay (B-4): given the
 * authored graph, which nodes + edges are REACHABLE from the start
 * node(s)?
 *
 * REACHABILITY, not execution (Fork 3, operator-locked): at design time
 * there is no input data, so condition/decision/branch outcomes are
 * undefined — we cannot say "which single path runs". Instead we mark
 * EVERY node/edge reachable from a start node. This is honest about
 * branch ambiguity (all branches are potentially-reachable) and catches
 * the real authoring error this overlay exists for: orphan / unreachable
 * nodes (added but never connected from start).
 *
 * PURE — no workflow_engine, no Jinja/condition evaluation, no network.
 * A plain graph traversal over nodes + edges.
 *
 * CYCLE-SAFE: `is_iteration` edges express legitimate loop-backs (a valid
 * construct, not malformed), and malformed cyclic state is possible too.
 * The DFS carries a visited set so a cycle terminates rather than
 * infinite-looping. Reachability is monotonic — revisiting a node adds
 * nothing — so the visited guard loses no information.
 *
 * Multiple start nodes: all `type === "start"` nodes seed the traversal
 * (a malformed graph may have 0 or >1; reachability handles both — 0
 * starts → nothing reachable → everything is an orphan).
 *
 * parallel_split / parallel_join need no special-casing under
 * reachability: a split is a node with N outgoing edges (all targets
 * reachable); a join is reachable if ANY incoming edge is reachable.
 */

import type {
  CanvasState,
  CanvasNode,
} from "@/bridgeable-admin/services/workflow-templates-service"

export interface ReachabilityTrace {
  /** Node ids reachable from a start node (inclusive of the start). */
  reachableNodeIds: ReadonlySet<string>
  /** Edge ids whose source is reachable AND target exists (traversed). */
  reachableEdgeIds: ReadonlySet<string>
}

/**
 * Compute reachability from all `start` nodes. Pure DFS with a visited
 * guard. An edge is "reachable" (traversed) when its source node is
 * reachable and its target node exists — i.e. the edge participates in
 * the reachable subgraph.
 */
export function simulateReachability(canvas: CanvasState): ReachabilityTrace {
  const reachableNodeIds = new Set<string>()
  const reachableEdgeIds = new Set<string>()

  const nodeIds = new Set(canvas.nodes.map((n) => n.id))
  // Adjacency: source id → [{ edgeId, target }]
  const outgoing = new Map<string, Array<{ edgeId: string; target: string }>>()
  for (const edge of canvas.edges) {
    if (!outgoing.has(edge.source)) outgoing.set(edge.source, [])
    outgoing.get(edge.source)!.push({ edgeId: edge.id, target: edge.target })
  }

  const startIds = canvas.nodes
    .filter((n) => n.type === "start")
    .map((n) => n.id)

  // DFS from each start node; visited guard makes cycles terminate.
  const stack: string[] = [...startIds]
  for (const id of startIds) reachableNodeIds.add(id)

  while (stack.length > 0) {
    const current = stack.pop()!
    for (const { edgeId, target } of outgoing.get(current) ?? []) {
      // The edge is traversed iff its target node actually exists
      // (defensive: dangling edges to deleted nodes are not "reachable").
      if (!nodeIds.has(target)) continue
      reachableEdgeIds.add(edgeId)
      if (!reachableNodeIds.has(target)) {
        reachableNodeIds.add(target)
        stack.push(target)
      }
    }
  }

  return { reachableNodeIds, reachableEdgeIds }
}

/** Is a node reachable from a start node? */
export function isNodeReachable(
  trace: ReachabilityTrace,
  nodeId: string,
): boolean {
  return trace.reachableNodeIds.has(nodeId)
}

/** Is an edge traversed within the reachable subgraph? */
export function isEdgeReachable(
  trace: ReachabilityTrace,
  edgeId: string,
): boolean {
  return trace.reachableEdgeIds.has(edgeId)
}

/** Terminal node — an `end` node (workflow completes here). */
export function isTerminalNode(node: CanvasNode): boolean {
  return node.type === "end"
}

/**
 * Orphan node ids — nodes NOT reachable from any start node. This is the
 * primary authoring-error signal the overlay surfaces (a node added but
 * never connected). `start` nodes themselves are always reachable (they
 * seed the traversal), so they are never orphans.
 */
export function orphanNodeIds(
  canvas: CanvasState,
  trace: ReachabilityTrace,
): string[] {
  return canvas.nodes
    .filter((n) => !trace.reachableNodeIds.has(n.id))
    .map((n) => n.id)
}
