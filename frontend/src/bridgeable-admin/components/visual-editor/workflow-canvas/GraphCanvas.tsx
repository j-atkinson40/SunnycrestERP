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

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core"
import { Maximize2, Route, Trash2 } from "lucide-react"

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
// Phase B integration-phase — pan + zoom view transform (self-owned).
import {
  type ViewTransform,
  DEFAULT_VIEW,
  PAN_DRAG_THRESHOLD,
  clampPan,
  computeZoomToCursor,
  formatZoomPercent,
} from "@/lib/visual-editor/workflows/canvas-pan-zoom"
// A3 shape-treatment — uniform cards + per-type icon + per-family warm
// tone (replaces the retired B-3b silhouette system). Family tone is
// mode-aware → read the current theme mode once + thread it to each node.
import {
  resolveTypeIcon,
  resolveNodeFamily,
  resolveFamilyTone,
} from "./node-families"
// Inline-params P1 — natural-language param SENTENCE on the card body
// (read-only token spans). Replaces the raw label render; node.label
// becomes an optional bold title above it.
import { NodeLabelSentence } from "./NodeLabelSentence"
import { useThemeMode, type ThemeMode } from "@/lib/theme-mode"
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
   * B-5 selection-context (additive — node selection via selectedNodeId
   * is unchanged). When an edge is selected its id is passed here for the
   * selected-edge highlight; edge-click + empty-canvas (background) click
   * report via onSelectEdge / onSelectBackground. Omitted → edges aren't
   * selectable + background clicks are inert (B-4/earlier behavior).
   */
  selectedEdgeId?: string | null
  onSelectEdge?: (id: string) => void
  onSelectBackground?: () => void
  /**
   * Inline-params P2a (additive): persist a config edit from a clickable
   * sentence token. Receives the node id + the FULL next config (the
   * per-param merge happens in GraphCanvasNode where node.config is in
   * hand). Omitted → sentence tokens render read-only (P1 behavior).
   */
  onUpdateNodeConfig?: (id: string, nextConfig: Record<string, unknown>) => void
}


export function GraphCanvas({
  canvas,
  selectedNodeId,
  onSelectNode,
  onMoveNode,
  onRemoveNode,
  validationError,
  selectedEdgeId,
  onSelectEdge,
  onSelectBackground,
  onUpdateNodeConfig,
}: GraphCanvasProps) {
  // A3: current theme mode selects each node's family tone (light/dark).
  // Read once; thread to every GraphCanvasNode. Reactive via useThemeMode.
  const [mode] = useThemeMode()
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

  // A3 grow-to-fit — per-node MEASURED heights (ResizeObserver in each
  // GraphCanvasNode). Cards are variable-height (label wraps, card grows
  // down), so bbox's bottom bound + each edge's SOURCE bottom-anchor read
  // the real height via this Map. `reportHeight` is equality-guarded:
  // node height is a pure function of (label, fixed width) — independent of
  // edges/bbox/pan/selection — so measure → setState → render settles in
  // ONE cycle (no feedback edge; RO is transform-invariant so zoom doesn't
  // retrigger). In jsdom the RO stub no-ops → Map stays empty → heightOf
  // falls back to NODE_HEIGHT (the fixed-height math the helper tests cover
  // with injected heights).
  const [heights, setHeights] = useState<Map<string, number>>(new Map())
  const reportHeight = useCallback((id: string, h: number) => {
    setHeights((prev) => {
      if (prev.get(id) === h) return prev
      const next = new Map(prev)
      next.set(id, h)
      return next
    })
  }, [])
  const heightOf = useCallback(
    (n: { id: string }) => heights.get(n.id) ?? NODE_HEIGHT,
    [heights],
  )

  const surface = bbox(canvas.nodes, NODE_WIDTH, heightOf)

  // ── Phase B integration-phase — pan + zoom (self-owned view state) ──
  // {panX, panY, zoom} is EPHEMERAL view state, NEVER persisted in
  // canvas_state (view state, not authored state — same category as the
  // B-4 traceOverlay toggle). Applied as `transform: translate scale` on
  // the content surface div (Option A-direct): edges (SVG) + nodes (DOM)
  // transform together; each node's own inline top/left is UNCHANGED.
  const [view, setView] = useState<ViewTransform>(DEFAULT_VIEW)
  // Mirror refs so the dep-free gesture handlers read current values
  // without re-binding (avoids stale-closure drift mid-gesture).
  const viewRef = useRef(view)
  viewRef.current = view
  const boundsRef = useRef({ minX: 0, minY: 0, maxX: 0, maxY: 0 })
  boundsRef.current = {
    minX: surface.minX,
    minY: surface.minY,
    maxX: surface.maxX,
    maxY: surface.maxY,
  }
  const viewportRef = useRef<HTMLDivElement>(null)
  const surfaceRef = useRef<HTMLDivElement>(null)
  // Drag-threshold gesture bookkeeping (idle → pending-bg-select →
  // panning). Held in a ref — the threshold transitions don't need to
  // re-render; only setView (the pan delta) does.
  const gestureRef = useRef<{
    mode: "idle" | "pending" | "panning"
    startX: number
    startY: number
    startPanX: number
    startPanY: number
  }>({ mode: "idle", startX: 0, startY: 0, startPanX: 0, startPanY: 0 })
  // After a pan completes, the trailing native `click` must NOT fire the
  // B-5 background-select (that would select-trigger-inspector on every
  // pan release). A plain click (no pan) leaves this false → the existing
  // onClick bg-select fires unchanged (fireEvent.click test preserved).
  const suppressClickRef = useRef(false)

  const viewportSize = useCallback(
    () => ({
      width: viewportRef.current?.clientWidth ?? 0,
      height: viewportRef.current?.clientHeight ?? 0,
    }),
    [],
  )

  const handleSurfacePointerDown = useCallback(
    (ev: React.PointerEvent<HTMLDivElement>) => {
      // Background only — a node/edge-hit pointer-down targets its own
      // element (target !== the surface) and reaches dnd-kit / the edge
      // hit-stroke unobstructed. Pan never engages on those.
      if (ev.target !== ev.currentTarget) return
      const v = viewRef.current
      gestureRef.current = {
        mode: "pending",
        startX: ev.clientX,
        startY: ev.clientY,
        startPanX: v.panX,
        startPanY: v.panY,
      }
      // Pointer capture keeps move/up flowing if the cursor leaves the
      // surface mid-pan (guarded — JSDOM may not implement it).
      try {
        ev.currentTarget.setPointerCapture(ev.pointerId)
      } catch {
        /* no-op in environments without pointer capture */
      }
    },
    [],
  )

  const handleSurfacePointerMove = useCallback(
    (ev: React.PointerEvent<HTMLDivElement>) => {
      const g = gestureRef.current
      if (g.mode === "idle") return
      const dx = ev.clientX - g.startX
      const dy = ev.clientY - g.startY
      if (g.mode === "pending") {
        // <3px → still a click-in-progress; ≥3px → promote to a pan.
        if (Math.hypot(dx, dy) <= PAN_DRAG_THRESHOLD) return
        g.mode = "panning"
      }
      const clamped = clampPan(
        {
          panX: g.startPanX + dx,
          panY: g.startPanY + dy,
          zoom: viewRef.current.zoom,
        },
        boundsRef.current,
        viewportSize(),
      )
      setView((prev) => ({ ...prev, panX: clamped.panX, panY: clamped.panY }))
    },
    [viewportSize],
  )

  const handleSurfacePointerUp = useCallback(
    (ev: React.PointerEvent<HTMLDivElement>) => {
      const g = gestureRef.current
      // A real pan happened → suppress the trailing click's bg-select.
      // Pending (<3px) → leave suppress false so the click fires
      // onSelectBackground (the B-5 background-select, preserved).
      if (g.mode === "panning") suppressClickRef.current = true
      gestureRef.current = {
        mode: "idle",
        startX: 0,
        startY: 0,
        startPanX: 0,
        startPanY: 0,
      }
      try {
        ev.currentTarget.releasePointerCapture(ev.pointerId)
      } catch {
        /* no-op */
      }
    },
    [],
  )

  const handleResetView = useCallback(() => setView(DEFAULT_VIEW), [])

  // Wheel zoom-to-cursor via a NATIVE non-passive listener — React's
  // synthetic onWheel can be passive (preventDefault no-op + warning), and
  // we must preventDefault so the page doesn't scroll while zooming the
  // canvas. Re-attaches when the surface element appears/disappears
  // (empty ↔ non-empty branch). setView is functional → handler is stable.
  useEffect(() => {
    const el = surfaceRef.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const rect = viewportRef.current?.getBoundingClientRect()
      const cursorX = e.clientX - (rect?.left ?? 0)
      const cursorY = e.clientY - (rect?.top ?? 0)
      setView((prev) => {
        const zoomed = computeZoomToCursor(prev, cursorX, cursorY, e.deltaY)
        const clamped = clampPan(zoomed, boundsRef.current, viewportSize())
        return { panX: clamped.panX, panY: clamped.panY, zoom: zoomed.zoom }
      })
    }
    el.addEventListener("wheel", onWheel, { passive: false })
    return () => el.removeEventListener("wheel", onWheel)
  }, [canvas.nodes.length, viewportSize])

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
        // A3 grow-to-fit: clamp lower-bound against the node's real height.
        nodeHeight: heights.get(nodeId) ?? NODE_HEIGHT,
      })
      // Skip a no-op commit (keyboard cancel / sub-3px residue).
      if (committed.x === node.position.x && committed.y === node.position.y) {
        return
      }
      onMoveNode(nodeId, committed)
    },
    [canvas.nodes, surface.width, surface.height, onMoveNode, heights],
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
          ref={viewportRef}
          className="relative flex-1 overflow-hidden bg-surface-sunken"
          data-testid="canvas-node-list"
        >
          <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
            <div
              ref={surfaceRef}
              className="relative"
              style={{
                width: surface.width,
                height: surface.height,
                // Pan + zoom view transform (Option A-direct). Both the
                // edge SVG (absolute inset-0) and the node DOM (absolute)
                // are children → they transform together, no sync drift.
                // transform-origin 0,0 keeps the zoom-to-cursor math simple.
                transform: `translate(${view.panX}px, ${view.panY}px) scale(${view.zoom})`,
                transformOrigin: "0 0",
                touchAction: "none",
              }}
              data-testid="graph-canvas-surface"
              data-pan-x={view.panX}
              data-pan-y={view.panY}
              data-zoom={view.zoom}
              onPointerDown={handleSurfacePointerDown}
              onPointerMove={handleSurfacePointerMove}
              onPointerUp={handleSurfacePointerUp}
              onClick={(ev) => {
                // B-5: background-click selects the workflow (trigger
                // inspector). Fires ONLY on a direct surface click — node +
                // edge-hit clicks target their own elements (e.target !==
                // the surface), so they don't trigger background. The edge
                // SVG layer is pointer-events:none, so empty-area clicks
                // fall through to this surface div.
                // Integration-phase: a click that TERMINATED A PAN is
                // suppressed (suppressClickRef) so panning never spuriously
                // fires the background-select; a plain click (no pan) falls
                // through unchanged.
                if (suppressClickRef.current) {
                  suppressClickRef.current = false
                  return
                }
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
                  // A3 grow-to-fit: the SOURCE bottom-anchor (sy = source.y
                  // + nodeHeight) must use the source card's REAL height so
                  // an outgoing edge departs the true bottom of a tall card,
                  // not y+72. The target anchor is the card top (height-
                  // independent) — incoming edges were always correct.
                  const sourceHeight = heights.get(source.id) ?? NODE_HEIGHT
                  const d = computeEdgePath({
                    source: source.position,
                    target: target.position,
                    nodeHeight: sourceHeight,
                  })
                  const mid = computeEdgeMidpoint({
                    source: source.position,
                    target: target.position,
                    nodeHeight: sourceHeight,
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
                  mode={mode}
                  onMeasure={reportHeight}
                  onUpdateNodeConfig={onUpdateNodeConfig}
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

          {/* Pan + zoom controls — zoom readout + reset-view. Sibling of
              the B-4 toggle, OUTSIDE the :192 transform target, so the
              controls themselves stay fixed in the viewport corner (they
              don't pan/zoom with the content). Reset handles the "I zoomed
              out and lost the workflow" case. */}
          <div
            className="absolute bottom-3 right-3 z-10 inline-flex items-center gap-1.5 rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption shadow-level-1"
            data-testid="canvas-zoom-controls"
          >
            <span
              className="tabular-nums text-content-muted"
              data-testid="canvas-zoom-indicator"
            >
              {formatZoomPercent(view.zoom)}
            </span>
            <button
              type="button"
              onClick={handleResetView}
              data-testid="canvas-zoom-reset"
              aria-label="Reset view"
              title="Reset view"
              className="inline-flex items-center gap-1 rounded-sm border border-border-base bg-surface-base px-1.5 py-0.5 text-content-muted hover:bg-accent-subtle hover:text-accent"
            >
              <Maximize2 size={12} />
              Reset
            </button>
          </div>
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
  /** A3: current theme mode selects the family tone (light/dark). */
  mode: ThemeMode
  /** A3 grow-to-fit: report this node's measured border-box height up. */
  onMeasure: (id: string, height: number) => void
  /**
   * Inline-params P2a: persist a config edit from a clickable sentence
   * token. Receives the FULL next config (merge done here, where
   * node.config is in hand). Omitted → tokens render read-only.
   */
  onUpdateNodeConfig?: (id: string, nextConfig: Record<string, unknown>) => void
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
  mode,
  onMeasure,
  onUpdateNodeConfig,
  traceState,
  traceTerminal,
}: GraphCanvasNodeProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({ id: node.id })

  // A3 grow-to-fit: observe this card's rendered border-box height and
  // report it up so bbox + the outgoing-edge source-anchor use the REAL
  // height (cards are variable-height — labels wrap, card grows down).
  // Combined callback ref composes dnd-kit's setNodeRef with our observed
  // element (mirror of SelectionOverlay's ResizeObserver pattern). RO
  // reports the layout border-box (transform-invariant → zoom doesn't
  // retrigger); the parent's reportHeight is equality-guarded → settles in
  // one cycle. In jsdom the RO stub no-ops (heights stay default).
  const elRef = useRef<HTMLDivElement | null>(null)
  const composedRef = useCallback(
    (el: HTMLDivElement | null) => {
      setNodeRef(el)
      elRef.current = el
    },
    [setNodeRef],
  )
  const nodeId = node.id
  useEffect(() => {
    const el = elRef.current
    if (!el || typeof ResizeObserver === "undefined") return
    const ro = new ResizeObserver(() => {
      // offsetHeight = LAYOUT border-box (transform-invariant) — NOT
      // getBoundingClientRect (which returns the zoom-scaled visual rect
      // and would make the height vary with pan+zoom, retriggering measure).
      onMeasure(nodeId, el.offsetHeight)
    })
    ro.observe(el)
    // Initial synchronous measure (RO fires async; seed the height now).
    onMeasure(nodeId, el.offsetHeight)
    return () => ro.disconnect()
  }, [nodeId, onMeasure])

  // Position = canvas_state coordinate + live drag transform (cleared on
  // commit when the page re-renders with the new position).
  const left = node.position.x + (transform?.x ?? 0)
  const top = node.position.y + (transform?.y ?? 0)

  // A3 shape-treatment (replaces the B-3b silhouette system): every node
  // is a uniform rounded-rect card. Type is signalled by a per-type Lucide
  // ICON (the primary signal); family by a quiet warm-tonal bg + a left
  // STRIPE (lightness step, no new hue — DESIGN_LANGUAGE warm-restraint).
  //
  // SELECTION is an ORTHOGONAL channel: family owns bg-tone + stripe (always
  // present, even when selected); selection owns the terracotta ring +
  // border + elevation. A selected node reads as selected regardless of its
  // family tone — the channels never collide (no bg fill-swap that would
  // clobber the family tone).
  const family = resolveNodeFamily(node.type)
  const tone = resolveFamilyTone(node.type, mode)
  const Icon = resolveTypeIcon(node.type)

  // B-4 overlay: dim nodes not reachable from start (orphan/unreachable
  // authoring-error signal). OUTER opacity — shape-agnostic, composes over
  // the card. Overlay off (traceState undefined) → no opacity change.
  const traceDimmed = traceState === "unreachable"

  return (
    <div
      ref={composedRef}
      data-testid={`canvas-node-${node.id}`}
      data-node-type={node.type}
      data-node-family={family ?? "none"}
      data-selected={selected}
      data-trace-state={traceState}
      className={isDragging ? "absolute opacity-80" : "absolute"}
      style={{
        left,
        top,
        width: NODE_WIDTH,
        // A3 grow-to-fit: fixed width, AUTO height with a NODE_HEIGHT floor.
        // The card hugs its wrapped-label content + grows down; the measured
        // height feeds bbox + the outgoing-edge source-anchor (see effect).
        minHeight: NODE_HEIGHT,
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
      {/* Uniform card. Family owns bg-tone (always); selection owns the
          terracotta ring + border (orthogonal — family tone persists when
          selected). min-height floor + content-driven growth. */}
      <div
        className="relative flex min-h-full w-full flex-col overflow-hidden rounded-md border"
        style={{
          background: tone.bg,
          borderColor: selected ? "var(--accent)" : "var(--border-base)",
          outline: selected ? "2px solid var(--accent)" : undefined,
          outlineOffset: selected ? "1px" : undefined,
        }}
      >
        {/* Family left-stripe (always present — the quiet family channel). */}
        <span
          aria-hidden
          data-testid={`canvas-node-${node.id}-family-stripe`}
          className="absolute inset-y-0 left-0 w-1"
          style={{ background: tone.stripe }}
        />

        {/* B-4: terminal (end-node) marker when overlay is on. */}
        {traceTerminal && (
          <span
            data-testid={`canvas-node-${node.id}-terminal-marker`}
            aria-hidden
            className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full border-2 border-accent bg-surface-base"
          />
        )}

        {/* Content: per-type icon header-left + type badge + optional
            bold label TITLE + the natural-language param SENTENCE.
            Inline-params P1: the sentence (NodeLabelSentence) is the card
            body — it summarizes the node's params as prose with read-only
            token-styled spans, replacing the raw label render. node.label,
            when set, renders as an optional bold TITLE line above it (the
            operator's human name for the node). Both wrap (whitespace-normal
            break-words) so A3 grow-to-fit measures + grows the card. The
            n_ node-ID stays hidden (Shortcuts-like). */}
        <div className="relative flex flex-1 items-start justify-between gap-2 py-2 pl-3 pr-2">
          <div className="flex min-w-0 flex-1 items-start gap-2">
            <span
              className="mt-0.5 shrink-0 text-content-muted"
              data-testid={`canvas-node-${node.id}-icon`}
              aria-hidden
            >
              <Icon size={15} />
            </span>
            <div className="min-w-0 flex-1">
              <Badge variant="outline">{node.type}</Badge>
              {node.label && (
                <p
                  className="mt-1 whitespace-normal break-words text-caption font-semibold text-content-strong"
                  data-testid={`canvas-node-${node.id}-label`}
                >
                  {node.label}
                </p>
              )}
              <p className="mt-1 whitespace-normal break-words">
                <NodeLabelSentence
                  nodeId={node.id}
                  nodeType={node.type}
                  config={node.config}
                  fallback={node.label}
                  // P2a: simple-type tokens become clickable popover
                  // editors; the merge happens here (node.config in hand),
                  // then flows up as the full next config.
                  onEditParam={
                    onUpdateNodeConfig
                      ? (param, value) =>
                          onUpdateNodeConfig(node.id, {
                            ...node.config,
                            [param]: value,
                          })
                      : undefined
                  }
                />
              </p>
            </div>
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
      </div>
    </div>
  )
}
