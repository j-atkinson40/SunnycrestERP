/**
 * GraphCanvas — Phase B sub-arc B-1 (Graph canvas foundation).
 *
 * Replaces the pre-B-1 `<ol><li>` vertical-list canvas rendering in
 * WorkflowEditorPage with a directed-graph authoring surface. Per
 * Entry 11 (WYSIWYG canvas-layout-model constraint), the authoring
 * canvas matches the runtime DAG layout model:
 *
 *   - nodes render as fixed-size cards positioned at their canvas_state
 *     `position: {x, y}` (top-left corner)
 *   - edges render as SVG cubic-bezier paths between node anchor points
 *     (source bottom-center → target top-center), replacing the old
 *     "→ target_label" text fragments
 *   - branching + parallel split/join read naturally as multi-edge
 *     fan-out / fan-in (a node with N outgoing edges = N paths)
 *
 * Drag-to-reposition mirrors the FF-3 free-form-canvas precedent
 * (`focus-builder/FreeFormPlacedWidget` + `computeDragMoveCommit`):
 *   - per-node `useDraggable`; the node card is the drag handle
 *   - PointerSensor 3px activation (Q-9 click-vs-drag disambiguation):
 *     <3px movement → click → selection; ≥3px → drag
 *   - KeyboardSensor (Q-40 JSDOM-testability): Space grabs, arrows
 *     nudge, Space commits; integration tests drive the keyboard sensor
 *   - drag transform applied as CSS translate during the gesture;
 *     COMMIT (drag-end) clamps to canvas bounds via
 *     `computeNodeDragCommit` then calls `onMoveNode`
 *
 * The canvas owns its OWN DndContext (self-contained — the workflow
 * editor page has no other drag concern), keeping the B-1 refactor
 * localized to the canvas region per §4.A single-commit shape.
 *
 * Node-move commits flow through the page's existing
 * `handleUpdateNode(id, {position})` mutation (reused verbatim via the
 * `onMoveNode` prop), which already routes through the auto-save
 * debounce per Adjudication 2 — no new mutation API.
 *
 * Preserves every pre-B-1 edit affordance + test anchor: node
 * selection (`onSelectNode`), node removal (`onRemoveNode` + per-node
 * trash button), the validation-error banner, the empty-state, and the
 * `data-testid` anchors (`canvas-node-list`, `canvas-node-${id}`,
 * `data-node-type`, `data-selected`, `edge-${id}`,
 * `canvas-node-${id}-remove`).
 */

import { useCallback, useMemo, useState } from "react"
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core"
import { Route, Trash2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type {
  CanvasNode,
  CanvasState,
} from "@/bridgeable-admin/services/workflow-templates-service"
import {
  NODE_WIDTH,
  NODE_HEIGHT,
  bbox,
  computeEdgePath,
  computeEdgeMidpoint,
  computeNodeDragCommit,
} from "@/lib/visual-editor/workflows/canvas-layout"
// Phase B sub-arc B-3 §(b) — render node.config visual props.
import { NodeShapeBackdrop, resolveNodeShape } from "./node-shapes"
// Phase B sub-arc B-4 — execution-trace reachability overlay.
import {
  simulateReachability,
  isNodeReachable,
  isEdgeReachable,
  isTerminalNode,
} from "@/lib/visual-editor/workflows/simulate-trace"

/** Per-node trace overlay state (undefined = overlay off). */
type NodeTraceState = "reachable" | "unreachable" | undefined


export interface GraphCanvasProps {
  canvas: CanvasState
  selectedNodeId: string | null
  onSelectNode: (id: string | null) => void
  /** Commit a node's new position (wraps the page's handleUpdateNode). */
  onMoveNode: (id: string, position: { x: number; y: number }) => void
  onRemoveNode: (id: string) => void
  /** Validation message rendered above the canvas; null hides the banner. */
  validationError?: string | null
  /**
   * B-3 completion: resolve a node type's default shape (the registry
   * `configurableProps.nodeShape.default`) so a node with no
   * `config.nodeShape` renders its genre shape. Injected so GraphCanvas +
   * node-shapes stay registry-free (the single registry consumer is
   * WorkflowEditorPage). Omitted (e.g. in some tests) → every node falls
   * to the rounded-rect hard default, which is harmless.
   */
  resolveTypeDefaultShape?: (nodeType: string) => unknown
  /**
   * B-5 selection-context (additive — node selection via selectedNodeId
   * is unchanged). When an edge is selected its id is passed here for the
   * selected-edge highlight; edge-click + empty-canvas (background) click
   * report via onSelectEdge / onSelectBackground. Omitted → edges aren't
   * selectable + background clicks are inert (B-4/earlier behavior).
   */
  selectedEdgeId?: string | null
  onSelectEdge?: (id: string) => void
  onSelectBackground?: () => void
}


export function GraphCanvas({
  canvas,
  selectedNodeId,
  onSelectNode,
  onMoveNode,
  onRemoveNode,
  validationError,
  resolveTypeDefaultShape,
  selectedEdgeId,
  onSelectEdge,
  onSelectBackground,
}: GraphCanvasProps) {
  // Sensor stack mirrors FocusBuilderPage FF-3: 3px PointerSensor for
  // click-vs-drag disambiguation + KeyboardSensor for accessibility +
  // JSDOM-testable drag per Q-40.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 3 } }),
    useSensor(KeyboardSensor),
  )

  // Phase B sub-arc B-4 — execution-trace reachability overlay.
  // DEFAULT OFF (operator-locked): the authoring canvas renders at full
  // strength by default — overlay-off is byte-identical to the B-1/B-3
  // render. The overlay is a deliberate "check reachability" toggle, one
  // click away. Trace is computed only when the overlay is on.
  const [traceOverlay, setTraceOverlay] = useState(false)
  const trace = useMemo(
    () => (traceOverlay ? simulateReachability(canvas) : null),
    [traceOverlay, canvas],
  )

  const surface = bbox(canvas.nodes)

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const nodeId = String(event.active.id)
      const node = canvas.nodes.find((n) => n.id === nodeId)
      if (!node) return
      const committed = computeNodeDragCommit({
        currentX: node.position.x,
        currentY: node.position.y,
        dx: event.delta.x,
        dy: event.delta.y,
        canvasWidth: surface.width,
        canvasHeight: surface.height,
      })
      // Skip a no-op commit (keyboard cancel / sub-3px residue).
      if (committed.x === node.position.x && committed.y === node.position.y) {
        return
      }
      onMoveNode(nodeId, committed)
    },
    [canvas.nodes, surface.width, surface.height, onMoveNode],
  )

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {validationError && (
        <p
          className="mx-4 mt-3 rounded-sm border border-status-error bg-status-error-muted px-2 py-1 text-caption text-status-error"
          data-testid="canvas-validation-message"
        >
          {validationError}
        </p>
      )}
      {canvas.nodes.length === 0 ? (
        <div className="px-4 py-3" data-testid="canvas-node-list">
          <p className="text-body-sm text-content-muted">
            No nodes yet. Add one from the palette above to start.
          </p>
        </div>
      ) : (
        <div
          className="relative flex-1 overflow-auto bg-surface-sunken"
          data-testid="canvas-node-list"
        >
          <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
            <div
              className="relative"
              style={{ width: surface.width, height: surface.height }}
              data-testid="graph-canvas-surface"
              onClick={(ev) => {
                // B-5: background-click selects the workflow (trigger
                // inspector). Fires ONLY on a direct surface click — node +
                // edge-hit clicks target their own elements (e.target !==
                // the surface), so they don't trigger background. The edge
                // SVG layer is pointer-events:none, so empty-area clicks
                // fall through to this surface div.
                if (ev.target === ev.currentTarget) onSelectBackground?.()
              }}
            >
              {/* Edge layer — SVG paths beneath the node layer. The SVG
                  is pointer-events:none so node drags pass through; the
                  per-edge group re-enables pointer-events for hover
                  affordances on the visible stroke. */}
              <svg
                className="pointer-events-none absolute inset-0"
                width={surface.width}
                height={surface.height}
                data-testid="graph-canvas-edges"
              >
                <defs>
                  <marker
                    id="wf-edge-arrow"
                    viewBox="0 0 10 10"
                    refX="9"
                    refY="5"
                    markerWidth="7"
                    markerHeight="7"
                    orient="auto-start-reverse"
                  >
                    <path
                      d="M 0 0 L 10 5 L 0 10 z"
                      className="fill-border-strong"
                    />
                  </marker>
                </defs>
                {canvas.edges.map((edge) => {
                  const source = canvas.nodes.find((n) => n.id === edge.source)
                  const target = canvas.nodes.find((n) => n.id === edge.target)
                  if (!source || !target) return null
                  const d = computeEdgePath({
                    source: source.position,
                    target: target.position,
                  })
                  const mid = computeEdgeMidpoint({
                    source: source.position,
                    target: target.position,
                  })
                  const edgeLabel = edge.label ?? edge.condition
                  // B-4 overlay: dim edges not traversed in the reachable
                  // subgraph. Overlay off (trace === null) → no change.
                  const edgeUnreachable =
                    trace !== null && !isEdgeReachable(trace, edge.id)
                  // B-5: selected-edge highlight (composes with B-4 dim —
                  // the <g> opacity applies to both paths).
                  const edgeSelected = selectedEdgeId === edge.id
                  return (
                    <g
                      key={edge.id}
                      data-testid={`edge-${edge.id}`}
                      data-trace-state={
                        trace === null
                          ? undefined
                          : edgeUnreachable
                            ? "unreachable"
                            : "reachable"
                      }
                      data-edge-selected={edgeSelected}
                      style={{ opacity: edgeUnreachable ? 0.2 : undefined }}
                    >
                      <path
                        d={d}
                        fill="none"
                        className={
                          edgeSelected
                            ? "stroke-accent"
                            : edge.is_iteration
                              ? "stroke-accent"
                              : "stroke-border-strong"
                        }
                        strokeWidth={edgeSelected ? 2.5 : 1.5}
                        strokeDasharray={edge.is_iteration ? "4 3" : undefined}
                        markerEnd="url(#wf-edge-arrow)"
                      />
                      {/* B-5: transparent wider hit-stroke. pointer-events
                          :stroke makes THIS path a click target even though
                          the parent <svg> is pointer-events:none (per the
                          SVG spec — a descendant may re-enable events). The
                          passthrough SVG + node-drag survive; only the edge
                          stroke itself is clickable. */}
                      {onSelectEdge && (
                        <path
                          d={d}
                          fill="none"
                          stroke="transparent"
                          strokeWidth={12}
                          style={{ pointerEvents: "stroke", cursor: "pointer" }}
                          data-testid={`edge-hit-${edge.id}`}
                          onClick={(ev) => {
                            ev.stopPropagation()
                            onSelectEdge(edge.id)
                          }}
                        />
                      )}
                      {edgeLabel && (
                        <text
                          x={mid.x}
                          y={mid.y}
                          textAnchor="middle"
                          className="fill-content-muted font-plex-mono"
                          style={{ fontSize: 10 }}
                        >
                          {edgeLabel}
                        </text>
                      )}
                    </g>
                  )
                })}
              </svg>

              {/* Node layer — draggable cards above the edge layer. */}
              {canvas.nodes.map((node) => (
                <GraphCanvasNode
                  key={node.id}
                  node={node}
                  selected={selectedNodeId === node.id}
                  onSelect={onSelectNode}
                  onRemove={onRemoveNode}
                  typeDefaultShape={resolveTypeDefaultShape?.(node.type)}
                  traceState={
                    trace === null
                      ? undefined
                      : isNodeReachable(trace, node.id)
                        ? "reachable"
                        : "unreachable"
                  }
                  traceTerminal={trace !== null && isTerminalNode(node)}
                />
              ))}
            </div>
          </DndContext>

          {/* B-4 trace-controls — persistent reachability-overlay toggle.
              Floats top-right of the canvas viewport; default OFF so the
              authoring render is pristine by default. */}
          <button
            type="button"
            onClick={() => setTraceOverlay((on) => !on)}
            data-testid="trace-overlay-toggle"
            data-trace-overlay={traceOverlay ? "on" : "off"}
            aria-pressed={traceOverlay}
            className={`absolute right-3 top-3 z-10 inline-flex items-center gap-1.5 rounded-sm border px-2 py-1 text-caption shadow-level-1 ${
              traceOverlay
                ? "border-accent bg-accent-subtle text-accent"
                : "border-border-base bg-surface-raised text-content-muted hover:bg-accent-subtle/40"
            }`}
          >
            <Route size={12} />
            {traceOverlay ? "Reachability: on" : "Check reachability"}
          </button>
        </div>
      )}
    </div>
  )
}


interface GraphCanvasNodeProps {
  node: CanvasNode
  selected: boolean
  onSelect: (id: string | null) => void
  onRemove: (id: string) => void
  /** Registry per-type default shape value (injected; see GraphCanvasProps). */
  typeDefaultShape?: unknown
  /** B-4 trace overlay state for this node (undefined = overlay off). */
  traceState?: NodeTraceState
  /** B-4: node is a terminal (`end`) node + overlay is on. */
  traceTerminal?: boolean
}

function GraphCanvasNode({
  node,
  selected,
  onSelect,
  onRemove,
  typeDefaultShape,
  traceState,
  traceTerminal,
}: GraphCanvasNodeProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({ id: node.id })

  // Position = canvas_state coordinate + live drag transform (cleared on
  // commit when the page re-renders with the new position).
  const left = node.position.x + (transform?.x ?? 0)
  const top = node.position.y + (transform?.y ?? 0)

  // Phase B sub-arc B-3 §(b) — render from node.config visual props.
  // nodeShape -> SVG shape backdrop; labelPosition -> label placement;
  // accentToken -> shape stroke (non-selected). Defaults reproduce B-1's
  // fixed rounded-rect / inside-label / border-subtle look.
  // B-3 completion: shape derives from node TYPE by default (the injected
  // registry per-type default) when config.nodeShape is absent; explicit
  // config overrides. node.config is NOT mutated — shape stays derived.
  const shape = resolveNodeShape(node.config?.nodeShape, typeDefaultShape)
  const labelPosition =
    node.config?.labelPosition === "above" ||
    node.config?.labelPosition === "below"
      ? node.config.labelPosition
      : "inside"
  const accentToken =
    typeof node.config?.accentToken === "string"
      ? node.config.accentToken
      : null

  const fill = selected ? "var(--accent-subtle)" : "var(--surface-elevated)"
  const stroke = selected
    ? "var(--accent)"
    : accentToken
      ? `var(--${accentToken})`
      : "var(--border-subtle)"

  // B-4 overlay: dim nodes not reachable from start (the orphan/
  // unreachable authoring-error signal). Composed as OUTER opacity over
  // the shape/selection render — NodeShapeBackdrop + content untouched.
  // Overlay off (traceState undefined) → no opacity change → byte-
  // identical to the B-1/B-3 authoring render.
  const traceDimmed = traceState === "unreachable"

  return (
    <div
      ref={setNodeRef}
      data-testid={`canvas-node-${node.id}`}
      data-node-type={node.type}
      data-node-shape={shape}
      data-label-position={labelPosition}
      data-selected={selected}
      data-trace-state={traceState}
      className={isDragging ? "absolute opacity-80" : "absolute"}
      style={{
        left,
        top,
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        cursor: isDragging ? "grabbing" : "grab",
        zIndex: selected || isDragging ? 2 : 1,
        opacity: !isDragging && traceDimmed ? 0.35 : undefined,
        filter: isDragging
          ? "drop-shadow(var(--shadow-level-2))"
          : "drop-shadow(var(--shadow-level-1))",
      }}
      {...listeners}
      {...attributes}
      onClick={() => onSelect(node.id)}
    >
      {/* Shape backdrop (SVG, pointer-events none) behind the content. */}
      <NodeShapeBackdrop
        shape={shape}
        width={NODE_WIDTH}
        height={NODE_HEIGHT}
        fill={fill}
        stroke={stroke}
      />

      {/* B-4: terminal (end-node) marker when overlay is on. A small
          accent ring at the top-right corner — layered over the shape,
          does not alter it. */}
      {traceTerminal && (
        <span
          data-testid={`canvas-node-${node.id}-terminal-marker`}
          aria-hidden
          className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full border-2 border-accent bg-surface-base"
        />
      )}

      {/* Label above / below the shape (outside the box). */}
      {node.label && labelPosition === "above" && (
        <p
          className="absolute -top-5 left-0 w-full truncate text-center text-caption text-content-strong"
          data-testid={`canvas-node-${node.id}-label`}
        >
          {node.label}
        </p>
      )}

      {/* Content layer on top of the shape. */}
      <div className="relative flex h-full items-start justify-between gap-2 p-3">
        <div className="flex-1 overflow-hidden">
          <div className="flex items-center gap-1.5">
            <Badge variant="outline">{node.type}</Badge>
          </div>
          <code className="mt-1 block truncate font-plex-mono text-micro text-content-muted">
            {node.id}
          </code>
          {node.label && labelPosition === "inside" && (
            <p className="mt-0.5 truncate text-caption text-content-strong">
              {node.label}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={(ev) => {
            ev.stopPropagation()
            onRemove(node.id)
          }}
          onPointerDown={(ev) => ev.stopPropagation()}
          data-testid={`canvas-node-${node.id}-remove`}
          aria-label="Remove node"
          className="rounded-sm border border-border-base bg-surface-raised p-1 text-content-muted hover:bg-status-error-muted hover:text-status-error"
        >
          <Trash2 size={12} />
        </button>
      </div>

      {node.label && labelPosition === "below" && (
        <p
          className="absolute -bottom-5 left-0 w-full truncate text-center text-caption text-content-strong"
          data-testid={`canvas-node-${node.id}-label`}
        >
          {node.label}
        </p>
      )}
    </div>
  )
}
