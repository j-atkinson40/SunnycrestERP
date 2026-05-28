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

import { useCallback } from "react"
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core"
import { Trash2 } from "lucide-react"

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
import { NodeShapeBackdrop, toNodeShape } from "./node-shapes"


export interface GraphCanvasProps {
  canvas: CanvasState
  selectedNodeId: string | null
  onSelectNode: (id: string | null) => void
  /** Commit a node's new position (wraps the page's handleUpdateNode). */
  onMoveNode: (id: string, position: { x: number; y: number }) => void
  onRemoveNode: (id: string) => void
  /** Validation message rendered above the canvas; null hides the banner. */
  validationError?: string | null
}


export function GraphCanvas({
  canvas,
  selectedNodeId,
  onSelectNode,
  onMoveNode,
  onRemoveNode,
  validationError,
}: GraphCanvasProps) {
  // Sensor stack mirrors FocusBuilderPage FF-3: 3px PointerSensor for
  // click-vs-drag disambiguation + KeyboardSensor for accessibility +
  // JSDOM-testable drag per Q-40.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 3 } }),
    useSensor(KeyboardSensor),
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
                  return (
                    <g key={edge.id} data-testid={`edge-${edge.id}`}>
                      <path
                        d={d}
                        fill="none"
                        className={
                          edge.is_iteration
                            ? "stroke-accent"
                            : "stroke-border-strong"
                        }
                        strokeWidth={1.5}
                        strokeDasharray={edge.is_iteration ? "4 3" : undefined}
                        markerEnd="url(#wf-edge-arrow)"
                      />
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
                />
              ))}
            </div>
          </DndContext>
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
}

function GraphCanvasNode({
  node,
  selected,
  onSelect,
  onRemove,
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
  const shape = toNodeShape(node.config?.nodeShape)
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

  return (
    <div
      ref={setNodeRef}
      data-testid={`canvas-node-${node.id}`}
      data-node-type={node.type}
      data-node-shape={shape}
      data-label-position={labelPosition}
      data-selected={selected}
      className={isDragging ? "absolute opacity-80" : "absolute"}
      style={{
        left,
        top,
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        cursor: isDragging ? "grabbing" : "grab",
        zIndex: selected || isDragging ? 2 : 1,
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
