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
import { CheckSquare, ChevronDown, ChevronUp, Maximize2, Minimize2, Route, Square, Trash2, Ungroup } from "lucide-react"

import { Badge } from "@/components/ui/badge"
// Builder Craft 1b — §18.1 designed empty state for the empty canvas.
import { EmptyState } from "@/components/ui/empty-state"
// Builder Craft 1a — shared chrome on the VIEWPORT controls only (Tooltip
// replaces title=; Icon lands the §7 stroke rule). Canvas-internal card
// affordances keep their native title= until the canvas-feel phase.
import { Icon } from "@/components/ui/icon"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type {
  CanvasNode,
  CanvasState,
  WorkflowContainer,
} from "@/bridgeable-admin/services/workflow-templates-service"
import {
  NODE_WIDTH,
  NODE_HEIGHT,
  bbox,
  computeEdgePath,
  computeEdgeMidpoint,
  computeNodeDragCommit,
  // Drag-to-connect P3b-1b — the preview path + the drop decision
  // (consumes the P3b-1a pure helpers; nodeAtPoint is used transitively
  // by dropDecision). Used AS-IS, not reimplemented.
  computeEdgePreviewPath,
  dropDecision,
  // Container-arc Phase 2b — wires the P2a collapse/rerouting pure helpers
  // (consumed AS-IS, not reimplemented). Side-bucketed: crossing-in → box
  // top, crossing-out → box bottom, box↔box → boxA bottom → boxB top.
  buildCollapsedMembership,
  classifyEdge,
  boxAnchor,
  bezierBetween,
  collapsedBoxBounds,
  type BoxBounds,
  // Container-arc Phase 3b — wires the P3a nesting helpers into the container
  // render (first consumer): recursive bounds (outer encloses inner boxes),
  // the parent map + ancestor walk (the container-render hidden-filter +
  // depth-scaled z). The edge-map + node-filter extend for free off the
  // already-nesting-aware buildCollapsedMembership (P3a) — untouched here.
  buildParentMap,
  outermostCollapsedAncestor,
  containerBounds,
} from "@/lib/visual-editor/workflows/canvas-layout"
// Phase B integration-phase — pan + zoom view transform (self-owned).
import {
  type ViewTransform,
  DEFAULT_VIEW,
  PAN_DRAG_THRESHOLD,
  clampPan,
  computeZoomToCursor,
  formatZoomPercent,
  // Drag-to-connect P3b-1b — screen→world inverse (P3b-1a, used as-is).
  screenToWorld,
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
// Inline-params P3a — un-slotted-param expand panel (the inspector-retirement
// precondition). The card surfaces params NOT slotted in its sentence as
// editable PropControlDispatcher rows, reusing the P2a/P2b mutation path. The
// panel's data source is `unslottedParams` (= configurableProps − inspector-
// hidden − slotted), so each param edits in exactly one place (two-tier).
import {
  unslottedParams,
  nodeConfigProps,
  humanizeParam,
  BESPOKE_NAMESPACE_TYPES,
} from "@/lib/visual-editor/workflow-node-templates"
import { PropControlDispatcher } from "@/lib/visual-editor/components/PropControls"
// Focus-invocation reconciliation P3 (E-3, arc close): the 2 bespoke focus
// types edit via their bespoke config hosted IN the card expand panel (not
// the rail) — the dependent op_id + binding-list kwargs need richer editing
// than dispatcher rows. BespokeNodePane is the {node, onChange} router
// (relocated here from the WorkflowEditorPage rail; the rail-pane exception
// is gone). Tokens stay read-only (BESPOKE_NAMESPACE_TYPES still gates them);
// only the editing surface moved rail → card.
import { BespokeNodePane } from "./BespokeNodePane"
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
  /**
   * Container-arc Phase 0 (additive): node selection. `additive` is set
   * when shift/⌘ was held on the click — the page's union-transition handler
   * accumulates instead of replacing. Omitting `additive` (the pre-P0 call
   * shape) is single-select, byte-identical.
   */
  onSelectNode: (id: string | null, additive?: boolean) => void
  /**
   * Container-arc Phase 0 (additive): the multi-node selection set. Each
   * member renders the selected-ring WITHOUT the single-node card-editing
   * affordances (those gate on selectedNodeId, which is null under multi).
   * Omitted/empty → no multi-selection (pre-P0 behavior).
   */
  selectedNodeIds?: string[]
  /** Commit a node's new position (wraps the page's handleUpdateNode). */
  onMoveNode: (id: string, position: { x: number; y: number }) => void
  onRemoveNode: (id: string) => void
  /** Validation message rendered above the canvas; null hides the banner. */
  validationError?: string | null
  /**
   * Builder AI Assistant Phase 1b — "Proposed" preview treatment (additive).
   * When true, the canvas root gains a distinct dashed-accent "proposed" frame
   * so a rendered candidate reads unmistakably as a PROPOSAL awaiting
   * accept/reject, not committed work. Purely visual — the caller wraps the
   * preview in a `pointer-events-none` container to make it read-only (the 1b
   * accept/reject lives in the assistant rail, not on the preview). Omitted /
   * false → the root is byte-identical to the normal authoring canvas.
   */
  proposed?: boolean
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
  /**
   * Inline-params P3a (additive): rename a node from its card title (inline
   * double-click edit). Persists the FULL next label via the page's
   * `handleUpdateNode(id, {label})`. Omitted → the card title is read-only.
   */
  onRenameNode?: (id: string, label: string) => void
  /**
   * Drag-to-connect P3b-1b (additive): create an edge by dragging from a
   * node's outgoing handle to a target node. Receives the resolved
   * (source, target) ids; the page generates the edge id + selects the new
   * edge (so EdgeConditionInspector opens to condition it). Omitted → the
   * connection handle is not rendered (edges add via the inspector only).
   */
  onCreateEdge?: (source: string, target: string) => void
  /**
   * Container-arc Phase 1 (additive): update a container (label edit).
   * Omitted → the container label is read-only. Mirrors onRenameNode.
   */
  onUpdateContainer?: (id: string, patch: Partial<WorkflowContainer>) => void
  /**
   * Container-arc Phase 1 (additive): ungroup — remove the container
   * (its member nodes stay; only the grouping is deleted). Omitted → no
   * ungroup affordance. Mirrors onRemoveNode.
   */
  onRemoveContainer?: (id: string) => void
  /**
   * Container-arc Phase 3c (additive): the multi-CONTAINER selection set —
   * each member renders the selection ring (parallels selectedNodeIds for
   * nodes). Omitted/empty → no container selected.
   */
  selectedContainerIds?: string[]
  /**
   * Container-arc Phase 3c (additive): select a container (mirrors
   * onSelectNode). Collapsed card → body click; expanded frame → the chrome
   * select handle. `additive` (shift/⌘) accumulates. Omitted → containers
   * aren't selectable (pre-3c).
   */
  onSelectContainer?: (id: string, additive?: boolean) => void
  /**
   * Canvas edge-delete P3b-2 (additive): remove the SELECTED edge from the
   * canvas via its midpoint-× affordance. The page removes the edge + clears
   * the selection (so EdgeConditionInspector closes). Omitted → no ×
   * (edges delete via the inspector only). Mirrors the node trash-button
   * idiom; intentionally button-only — keyboard-delete is deferred (see the
   * render comment). Same `handleRemoveEdge` path as the inspector.
   */
  onDeleteEdge?: (id: string) => void
}


export function GraphCanvas({
  canvas,
  selectedNodeId,
  selectedNodeIds,
  onSelectNode,
  onMoveNode,
  onRemoveNode,
  validationError,
  proposed,
  selectedEdgeId,
  onSelectEdge,
  onSelectBackground,
  onUpdateNodeConfig,
  onRenameNode,
  onCreateEdge,
  onUpdateContainer,
  onRemoveContainer,
  selectedContainerIds,
  onSelectContainer,
  onDeleteEdge,
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

  // Surface sizing counts ALL nodes (incl. hidden members of collapsed
  // containers) so collapsing never shrinks the scroll surface / jumps pan
  // (container-arc Phase 2b — investigation §P2.5).
  const surface = bbox(canvas.nodes, NODE_WIDTH, heightOf)
  // Negative-coordinate support — the content origin (≤ 0; 0 for non-negative
  // content → every offset below is a no-op, byte-identical). `dom = content -
  // origin`: node/container `left/top` subtract it; the edge-SVG viewBox starts
  // at it; the pan-clamp bounds + the drag-to-connect hit-test + the node-drag
  // clamp are all corrected by it.
  const originX = surface.originX
  const originY = surface.originY

  // ── Container-arc Phase 2b — collapse lookups (consume P2a helpers) ──
  // `collapsedMembership` = node-id → its collapsed container's id (the node
  // is a HIDDEN member). Drives: the node-map filter (hidden members don't
  // render), the edge classifier (interior/crossing/box↔box), and the
  // drag-to-connect drop exclusion. `containersById` resolves a classified
  // container id → the container row for `collapsedBoxBounds`. Both rebuild
  // reactively when a collapse toggles (canvas.containers changes).
  const collapsedMembership = useMemo(
    () => buildCollapsedMembership(canvas.containers),
    [canvas.containers],
  )
  const containersById = useMemo(
    () =>
      new Map((canvas.containers ?? []).map((c) => [c.id, c] as const)),
    [canvas.containers],
  )
  // Resolve a collapsed container id → its collapsed-box bounds (for edge
  // re-anchoring). Memo-free helper (cheap; reads the reactive maps above).
  const collapsedBoundsFor = useCallback(
    (containerId: string): BoxBounds | null => {
      const container = containersById.get(containerId)
      if (!container) return null
      return collapsedBoxBounds(container, canvas.nodes, heightOf)
    },
    [containersById, canvas.nodes, heightOf],
  )

  // ── Container-arc Phase 3b — nesting render lookups (consume P3a) ──
  // `parentMap` (child id → parent container id) backs the container-render
  // hidden-filter + depth. `containerIsHidden`: a container is hidden iff an
  // ANCESTOR is collapsed (its collapsed card replaces the whole subtree) —
  // outermostCollapsedAncestor walks from the PARENT, so non-null ⟺ a
  // collapsed ancestor exists (mirrors the node-map hidden-member filter).
  // `containerDepth`: ancestor-chain length (0 = top-level) → depth-scaled z.
  const parentMap = useMemo(
    () => buildParentMap(canvas.containers),
    [canvas.containers],
  )
  const containerIsHidden = useCallback(
    (containerId: string): boolean =>
      outermostCollapsedAncestor(containerId, parentMap, containersById) !==
      null,
    [parentMap, containersById],
  )
  const containerDepth = useCallback(
    (containerId: string): number => {
      let depth = 0
      const visited = new Set<string>()
      let current = parentMap.get(containerId)
      while (current !== undefined && !visited.has(current)) {
        visited.add(current)
        depth += 1
        current = parentMap.get(current)
      }
      return depth
    },
    [parentMap],
  )

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
  // Negative-coordinate support — the pan-clamp works in on-surface (DOM)
  // space, so shift the content bounds by -origin. With origin 0 this is the
  // raw bbox (byte-identical).
  boundsRef.current = {
    minX: surface.minX - originX,
    minY: surface.minY - originY,
    maxX: surface.maxX - originX,
    maxY: surface.maxY - originY,
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

  // ── Drag-to-connect P3b-1b — the draw gesture (mirrors pan) ─────────
  // `drawing` is STATE (drives the preview re-render, like pan's setView);
  // `drawRef` is its mirror (the pointer handlers read current values
  // without stale closures, like viewRef). Pointer-capture lives on the
  // HANDLE element (in GraphCanvasNode) so move/up fire on it even when the
  // cursor is over another node — the handle's own move/up ARE the gesture.
  // `cancelFlash` is a transient sourceId set on an INFORMATIVE reject
  // (self/duplicate/cycle) → the handle tints reject for ~200ms then clears.
  const [drawing, setDrawing] = useState<{
    sourceId: string
    cursorScreen: { x: number; y: number }
  } | null>(null)
  const drawRef = useRef(drawing)
  drawRef.current = drawing
  const [cancelFlash, setCancelFlash] = useState<string | null>(null)

  const handleDrawStart = useCallback(
    (sourceId: string, screenPt: { x: number; y: number }) => {
      setDrawing({ sourceId, cursorScreen: screenPt })
    },
    [],
  )
  const handleDrawMove = useCallback(
    (screenPt: { x: number; y: number }) => {
      setDrawing((d) => (d ? { ...d, cursorScreen: screenPt } : d))
    },
    [],
  )
  const handleDrawEnd = useCallback(
    (screenPt: { x: number; y: number }) => {
      const d = drawRef.current
      setDrawing(null)
      if (!d) return
      const rect = viewportRef.current?.getBoundingClientRect()
      const domPt = screenToWorld(viewRef.current, {
        x: screenPt.x - (rect?.left ?? 0),
        y: screenPt.y - (rect?.top ?? 0),
      })
      // Negative-coordinate support — screenToWorld yields the on-surface (DOM)
      // point; nodes are hit-tested in RAW content coords, so add the origin
      // back (dom + origin = content). With origin 0 this is a no-op.
      const cursorWorld = { x: domPt.x + originX, y: domPt.y + originY }
      const decision = dropDecision({
        // Container-arc Phase 2b — exclude HIDDEN members (members of a
        // collapsed container) from the drop hit-test, so a drag-to-connect
        // can't resolve onto an invisible node. (Dropping onto a collapsed
        // BOX is out of scope for P2b — the box isn't a dropDecision target;
        // such a drop falls through to cancel/empty.)
        nodes: canvas.nodes.filter((n) => !collapsedMembership.has(n.id)),
        edges: canvas.edges,
        heights,
        sourceId: d.sourceId,
        cursorWorld,
      })
      if (decision.action === "create" && decision.target && onCreateEdge) {
        onCreateEdge(d.sourceId, decision.target)
      } else if (
        decision.action === "cancel" &&
        (decision.reason === "self" ||
          decision.reason === "duplicate" ||
          decision.reason === "cycle")
      ) {
        // Informative reject → brief handle flash (empty = silent clear).
        setCancelFlash(d.sourceId)
        window.setTimeout(() => setCancelFlash(null), 200)
      }
    },
    [canvas.nodes, canvas.edges, heights, onCreateEdge, collapsedMembership, originX, originY],
  )

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
        // Negative-coordinate support — let a node legitimately at negative
        // coords stay there (don't snap to 0). origin 0 → pre-support [0,…].
        minX: originX,
        minY: originY,
      })
      // Skip a no-op commit (keyboard cancel / sub-3px residue).
      if (committed.x === node.position.x && committed.y === node.position.y) {
        return
      }
      onMoveNode(nodeId, committed)
    },
    [canvas.nodes, surface.width, surface.height, onMoveNode, heights, originX, originY],
  )

  return (
    <div
      className={
        proposed
          ? "flex flex-1 flex-col overflow-hidden rounded-md border-2 border-dashed border-accent bg-accent-subtle/20"
          : "flex flex-1 flex-col overflow-hidden"
      }
      data-proposed={proposed ? "true" : undefined}
    >
      {validationError && (
        <p
          className="mx-4 mt-3 rounded-sm border border-status-error bg-status-error-muted px-2 py-1 text-caption text-status-error"
          data-testid="canvas-validation-message"
        >
          {validationError}
        </p>
      )}
      {canvas.nodes.length === 0 ? (
        // Builder Craft 1b — §18.1 designed empty state (the coaching
        // moment) replaces the bare caption. Headline names the surface;
        // the guidance line keeps "No nodes yet" (and names BOTH paths
        // forward — the palette and the assistant — so the state never
        // dead-ends; no action button needed, the affordances are adjacent).
        <div
          className="flex flex-1 flex-col justify-center"
          data-testid="canvas-node-list"
        >
          <EmptyState
            variant="quiet"
            icon={Route}
            title="Workflow canvas"
            description="No nodes yet — add one from the palette on the right, or ask the AI assistant to draft a workflow."
            data-testid="canvas-empty-state"
          />
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
                // Negative-coordinate support — the viewBox starts at the
                // content origin so geometry at negative coords is in-viewport
                // (no longer clipped at x<0/y<0). With origin 0 this is
                // "0 0 width height", identical to the prior no-viewBox 1:1 map.
                viewBox={`${originX} ${originY} ${surface.width} ${surface.height}`}
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
                  // Container-arc Phase 2b — classify against collapsed
                  // membership (side-bucketed). external → the UNTOUCHED P1
                  // path (byte-identical; when nothing is collapsed every edge
                  // is external → zero change). interior → skip (both endpoints
                  // hidden). crossing/box↔box → re-anchor the hidden endpoint(s)
                  // to the collapsed box (in→top, out→bottom).
                  const klass = classifyEdge(edge, collapsedMembership)
                  if (klass.kind === "interior") return null
                  let d: string
                  let mid: { x: number; y: number }
                  if (klass.kind === "external") {
                    d = computeEdgePath({
                      source: source.position,
                      target: target.position,
                      nodeHeight: sourceHeight,
                    })
                    mid = computeEdgeMidpoint({
                      source: source.position,
                      target: target.position,
                      nodeHeight: sourceHeight,
                    })
                  } else {
                    const srcBounds = klass.sourceContainerId
                      ? collapsedBoundsFor(klass.sourceContainerId)
                      : null
                    const tgtBounds = klass.targetContainerId
                      ? collapsedBoundsFor(klass.targetContainerId)
                      : null
                    // Source anchor: the collapsed box BOTTOM (crossing-out /
                    // box↔box) else the source node's bottom-center. Target
                    // anchor: the collapsed box TOP (crossing-in / box↔box)
                    // else the target node's top-center (height-independent).
                    const sa = srcBounds
                      ? boxAnchor(srcBounds, "bottom")
                      : boxAnchor(
                          {
                            x: source.position.x,
                            y: source.position.y,
                            width: NODE_WIDTH,
                            height: sourceHeight,
                          },
                          "bottom",
                        )
                    const ta = tgtBounds
                      ? boxAnchor(tgtBounds, "top")
                      : boxAnchor(
                          {
                            x: target.position.x,
                            y: target.position.y,
                            width: NODE_WIDTH,
                            height: NODE_HEIGHT,
                          },
                          "top",
                        )
                    d = bezierBetween(sa, ta)
                    mid = { x: (sa.x + ta.x) / 2, y: (sa.y + ta.y) / 2 }
                  }
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
                      {/* Canvas edge-delete (P3b-2): a midpoint-× on the
                          SELECTED edge → handleRemoveEdge + clear selection
                          (the page closes EdgeConditionInspector). Mirrors the
                          node trash-button idiom — BUTTON, not keyboard.
                          Keyboard-delete is a DELIBERATE deferral (not an
                          oversight): nodes are button-only too; if a future arc
                          adds node keyboard-delete, edge keyboard-delete joins
                          it then, with the focus guard designed at that point.
                          pointerEvents:auto re-enables clicks under the
                          pointer-events:none SVG layer (like the hit-stroke);
                          stopPropagation so the click doesn't re-trigger the
                          hit-stroke select. Lives in the edge <g> → transforms
                          + scales WITH the canvas, glued to the midpoint. */}
                      {edgeSelected && onDeleteEdge && (
                        <g
                          role="button"
                          aria-label="Delete edge"
                          data-testid={`edge-${edge.id}-delete`}
                          transform={`translate(${mid.x}, ${mid.y})`}
                          className="group/edgedel"
                          style={{ pointerEvents: "auto", cursor: "pointer" }}
                          onClick={(ev) => {
                            ev.stopPropagation()
                            onDeleteEdge(edge.id)
                          }}
                        >
                          <circle
                            r={8}
                            strokeWidth={1}
                            className="fill-surface-base stroke-border-base group-hover/edgedel:fill-status-error-muted"
                          />
                          <path
                            d="M -3 -3 L 3 3 M 3 -3 L -3 3"
                            strokeWidth={1.5}
                            strokeLinecap="round"
                            className="stroke-status-error"
                          />
                        </g>
                      )}
                    </g>
                  )
                })}

                {/* Drag-to-connect P3b-1b — the in-progress preview edge.
                    Renders only while drawing: from the source node's
                    bottom-center anchor (height-aware) to the live cursor
                    (screen→world via the proven inverse). Dashed accent
                    (reuses the is_iteration edge styling — no new tokens),
                    no arrow-marker, no hit-stroke (purely visual). Reads
                    `view` directly (the SVG is in the render path → it
                    re-renders as `drawing.cursorScreen` updates). */}
                {drawing &&
                  (() => {
                    const src = canvas.nodes.find((n) => n.id === drawing.sourceId)
                    if (!src) return null
                    const rect = viewportRef.current?.getBoundingClientRect()
                    const domPt = screenToWorld(view, {
                      x: drawing.cursorScreen.x - (rect?.left ?? 0),
                      y: drawing.cursorScreen.y - (rect?.top ?? 0),
                    })
                    // Negative-coordinate support — recover raw content coords
                    // (dom + origin) so the preview, drawn in the origin-based
                    // viewBox alongside the raw source anchor, aligns. No-op at
                    // origin 0.
                    const cursorWorld = {
                      x: domPt.x + originX,
                      y: domPt.y + originY,
                    }
                    const d = computeEdgePreviewPath(
                      src.position,
                      heights.get(src.id) ?? NODE_HEIGHT,
                      cursorWorld,
                    )
                    return (
                      <path
                        d={d}
                        fill="none"
                        className="stroke-accent"
                        strokeWidth={2}
                        strokeDasharray="4 3"
                        data-testid="graph-canvas-draw-preview"
                      />
                    )
                  })()}
              </svg>

              {/* Container layer (container-arc Phase 1) — labeled boxes
                  drawn AFTER the SVG edge layer + BEFORE the node layer, so
                  they paint over edges but UNDER the node cards (nodes stay on
                  top + clickable). Each box encloses its member nodes; bounds
                  come from the measured-height bbox corners (recomputed
                  reactively as members move). The box body is
                  pointer-events:none (enclosed nodes stay clickable through
                  it); only its chrome (label + ungroup) is interactive.
                  Phase 1 renders EXPANDED regions only — `collapsed` is not
                  read yet (Phase 2). Containers with no resolvable node-member
                  render nothing (empty container = no box). */}
              {canvas.containers?.map((container) => {
                // Container-arc Phase 3b — skip a container hidden inside a
                // COLLAPSED ancestor (the ancestor's collapsed card replaces
                // the whole subtree). Mirrors the node-map hidden-member
                // filter; non-null ⟺ a collapsed ancestor exists.
                if (containerIsHidden(container.id)) return null
                const memberNodes = container.members
                  .filter((m) => m.kind === "node")
                  .map((m) => canvas.nodes.find((n) => n.id === m.id))
                  .filter((n): n is CanvasNode => n !== undefined)
                // Container-arc Phase 3b — render if there's ≥1 resolvable
                // member of EITHER kind. The P2 guard counted node-members
                // only → it wrongly skipped a pure-nesting outer (whose members
                // are all kind:"container"). A truly-empty container still
                // skips (matches the P1 empty-renders-nothing stance).
                const resolvableContainerMembers = container.members.filter(
                  (m) => m.kind === "container" && containersById.has(m.id),
                ).length
                if (memberNodes.length + resolvableContainerMembers === 0) {
                  return null
                }
                // Container-arc Phase 3b — bounds via the recursive
                // containerBounds (handles BOTH states: collapsed → the fixed
                // card [== P2 collapsedBoxBounds]; expanded → bbox enclosing
                // member nodes AND inner container boxes). Replaces the P2
                // inline bbox; flat-case byte-identical.
                const bounds = containerBounds(
                  container,
                  canvas.nodes,
                  containersById,
                  heightOf,
                )
                return (
                  <GraphCanvasContainer
                    key={container.id}
                    container={container}
                    bounds={bounds}
                    // Negative-coordinate support — render shift (dom = content
                    // - origin); 0 → unchanged.
                    originX={originX}
                    originY={originY}
                    memberCount={memberNodes.length}
                    depth={containerDepth(container.id)}
                    // Container-arc Phase 3c — selection ring + select handler.
                    multiSelected={
                      selectedContainerIds?.includes(container.id) ?? false
                    }
                    onSelect={onSelectContainer}
                    onUpdateContainer={onUpdateContainer}
                    onRemoveContainer={onRemoveContainer}
                  />
                )
              })}

              {/* Node layer — draggable cards above the edge layer.
                  Container-arc Phase 2b — HIDDEN members (nodes that are
                  members of a COLLAPSED container) don't render; the collapsed
                  box replaces them. When nothing is collapsed the membership
                  map is empty → every node renders (P1 behavior). */}
              {canvas.nodes
                .filter((node) => !collapsedMembership.has(node.id))
                .map((node) => (
                <GraphCanvasNode
                  key={node.id}
                  node={node}
                  // Negative-coordinate support — render shift (dom = content
                  // - origin); 0 → unchanged.
                  originX={originX}
                  originY={originY}
                  selected={selectedNodeId === node.id}
                  // Container-arc Phase 0 — ring-only multi-selection state
                  // (distinct from `selected` so card editing stays dormant).
                  multiSelected={selectedNodeIds?.includes(node.id) ?? false}
                  onSelect={onSelectNode}
                  onRemove={onRemoveNode}
                  mode={mode}
                  onMeasure={reportHeight}
                  onUpdateNodeConfig={onUpdateNodeConfig}
                  onRenameNode={onRenameNode}
                  // Drag-to-connect P3b-1b — the outgoing handle + its
                  // pointer gesture (only when the page wired onCreateEdge).
                  canConnect={!!onCreateEdge}
                  onDrawStart={handleDrawStart}
                  onDrawMove={handleDrawMove}
                  onDrawEnd={handleDrawEnd}
                  rejectFlash={cancelFlash === node.id}
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
            {/* Builder Craft 1a — title= → shared Tooltip on the VIEWPORT
                chrome only. The canvas-internal title= affordances (container
                expand/collapse/ungroup on cards) are canvas content under the
                protected-path invariant — they stay for the canvas-feel phase. */}
            <Tooltip>
              <TooltipTrigger
                render={
                  <button
                    type="button"
                    onClick={handleResetView}
                    data-testid="canvas-zoom-reset"
                    aria-label="Reset view"
                    className="inline-flex items-center gap-1 rounded-sm border border-border-base bg-surface-base px-1.5 py-0.5 text-content-muted hover:bg-accent-subtle hover:text-accent"
                  >
                    <Icon icon={Maximize2} size={12} />
                    Reset
                  </button>
                }
              />
              <TooltipContent>Reset view</TooltipContent>
            </Tooltip>
          </div>
        </div>
      )}
    </div>
  )
}


interface GraphCanvasNodeProps {
  node: CanvasNode
  /** Negative-coordinate support — the content origin (≤ 0) subtracted from
   *  the node's content position to get its on-surface left/top. 0 → unchanged. */
  originX: number
  originY: number
  selected: boolean
  /**
   * Container-arc Phase 0 — this node is in the multi-node selection.
   * Drives ONLY the selected-ring (border/outline/z-raise); the single-node
   * card-editing affordances (connect-handle full-visibility, label
   * placeholder) stay keyed on `selected` so they remain dormant here.
   */
  multiSelected?: boolean
  /**
   * Container-arc Phase 0 — `additive` reports shift/⌘ on the click so the
   * page accumulates instead of replacing. Single-click omits it.
   */
  onSelect: (id: string | null, additive?: boolean) => void
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
  /**
   * Inline-params P3a: rename this node from its card title (double-click →
   * input → Enter/blur commits {label}). Omitted → title read-only.
   */
  onRenameNode?: (id: string, label: string) => void
  /**
   * Drag-to-connect P3b-1b: when true, render the outgoing connection
   * handle (bottom-center) + wire its pointer gesture. The handle captures
   * the pointer on down (so move/up retarget to it) + calls the draw
   * callbacks up to the canvas, which owns the preview + drop decision.
   */
  canConnect?: boolean
  onDrawStart?: (sourceId: string, screenPt: { x: number; y: number }) => void
  onDrawMove?: (screenPt: { x: number; y: number }) => void
  onDrawEnd?: (screenPt: { x: number; y: number }) => void
  /** Drag-to-connect: brief reject tint after an informative cancel. */
  rejectFlash?: boolean
  /** B-4 trace overlay state for this node (undefined = overlay off). */
  traceState?: NodeTraceState
  /** B-4: node is a terminal (`end`) node + overlay is on. */
  traceTerminal?: boolean
}

function GraphCanvasNode({
  node,
  originX,
  originY,
  selected,
  multiSelected,
  onSelect,
  onRemove,
  mode,
  onMeasure,
  onUpdateNodeConfig,
  onRenameNode,
  canConnect,
  onDrawStart,
  onDrawMove,
  onDrawEnd,
  rejectFlash,
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
  // Negative-coordinate support — on-surface left/top = content - origin
  // (+ the live drag transform). origin 0 → byte-identical to pre-support.
  const left = node.position.x - originX + (transform?.x ?? 0)
  const top = node.position.y - originY + (transform?.y ?? 0)

  // P3a — stopPropagation guard (mirror of the remove button + the
  // NodeLabelSentence token): a card-interaction must neither select the
  // node (card onClick) nor start a dnd-kit drag ({...listeners}).
  const stop = (ev: { stopPropagation: () => void }) => ev.stopPropagation()

  // P3a — un-slotted-param expand panel. `hidden` = the params NOT in this
  // type's sentence (inspector-only today); the panel surfaces them as
  // editable PropControlDispatcher rows so every config param has an inline
  // home. `expanded` is per-node EPHEMERAL (never persisted — same category
  // as the B-4 trace toggle). Two-tier: slotted params edit via tokens, these
  // via the panel — no overlap (unslottedParams excludes the slotted set).
  const [expanded, setExpanded] = useState(false)
  const unslotted = unslottedParams(node.type)
  const configProps = nodeConfigProps(node.type)
  // P3 (E-3): bespoke focus types host their bespoke config in this panel
  // instead of the un-slotted rows (op_id is a dependent enum, kwargs a
  // binding-list — richer than dispatcher rows). The slotted token stays
  // read-only; the panel is the editing surface.
  const isBespoke = BESPOKE_NAMESPACE_TYPES.has(node.type)

  // P3a — inline label edit. Double-click the title → input → Enter/blur
  // commits via onRenameNode ({label}); Escape cancels. The title slot
  // renders when the node HAS a label OR is selected+empty (so an unnamed
  // node can gain a name from the card).
  const [editingLabel, setEditingLabel] = useState(false)
  const [labelDraft, setLabelDraft] = useState(node.label ?? "")
  const beginLabelEdit = () => {
    setLabelDraft(node.label ?? "")
    setEditingLabel(true)
  }
  const commitLabel = () => {
    setEditingLabel(false)
    const next = labelDraft.trim()
    if (next !== (node.label ?? "")) onRenameNode?.(node.id, next)
  }
  const cancelLabel = () => {
    setEditingLabel(false)
    setLabelDraft(node.label ?? "")
  }

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
      // Container-arc Phase 0 — multi-selection membership (ring-only).
      data-multi-selected={multiSelected ?? false}
      data-trace-state={traceState}
      className={isDragging ? "group absolute opacity-80" : "group absolute"}
      style={{
        left,
        top,
        width: NODE_WIDTH,
        // A3 grow-to-fit: fixed width, AUTO height with a NODE_HEIGHT floor.
        // The card hugs its wrapped-label content + grows down; the measured
        // height feeds bbox + the outgoing-edge source-anchor (see effect).
        minHeight: NODE_HEIGHT,
        cursor: isDragging ? "grabbing" : "grab",
        zIndex: selected || multiSelected || isDragging ? 2 : 1,
        opacity: !isDragging && traceDimmed ? 0.35 : undefined,
        filter: isDragging
          ? "drop-shadow(var(--shadow-level-2))"
          : "drop-shadow(var(--shadow-level-1))",
      }}
      {...listeners}
      {...attributes}
      // Container-arc Phase 0 — shift/⌘+click reports `additive`; the page's
      // union-transition handler accumulates. A plain click is single-select
      // (the pre-P0 path). Inner interactive elements (remove, expand toggle,
      // tokens, label) stopPropagation, so they don't reach this onClick.
      onClick={(ev) => onSelect(node.id, ev.shiftKey || ev.metaKey)}
    >
      {/* Drag-to-connect P3b-1b — outgoing connection handle (bottom-center,
          matching the height-aware source anchor). Child of the OUTER card
          div (the inner card is overflow-hidden + would clip it). Visible on
          group-hover OR when selected. onPointerDown stopPropagations (dnd-kit
          body-drag never engages) + captures the pointer (move/up retarget
          here, even over another node) + starts the draw; the canvas owns the
          preview + drop decision. */}
      {canConnect && (
        <div
          role="button"
          aria-label="Drag to connect to another node"
          data-testid={`canvas-node-${node.id}-connect-handle`}
          onPointerDown={(ev) => {
            ev.stopPropagation()
            try {
              ev.currentTarget.setPointerCapture(ev.pointerId)
            } catch {
              /* no-op in environments without pointer capture (jsdom) */
            }
            onDrawStart?.(node.id, { x: ev.clientX, y: ev.clientY })
          }}
          onPointerMove={(ev) => onDrawMove?.({ x: ev.clientX, y: ev.clientY })}
          onPointerUp={(ev) => {
            onDrawEnd?.({ x: ev.clientX, y: ev.clientY })
            try {
              ev.currentTarget.releasePointerCapture(ev.pointerId)
            } catch {
              /* no-op */
            }
          }}
          className={`absolute bottom-[-5px] left-1/2 z-10 h-2.5 w-2.5 -translate-x-1/2 cursor-crosshair rounded-full border-2 transition-opacity ${
            selected ? "opacity-100" : "opacity-0 group-hover:opacity-100"
          } ${
            rejectFlash
              ? "border-status-error bg-status-error"
              : "border-accent bg-surface-base"
          }`}
        />
      )}

      {/* Uniform card. Family owns bg-tone (always); selection owns the
          terracotta ring + border (orthogonal — family tone persists when
          selected). min-height floor + content-driven growth. */}
      <div
        className="relative flex min-h-full w-full flex-col overflow-hidden rounded-md border"
        style={{
          background: tone.bg,
          // Container-arc Phase 0 — the ring is the shared selection channel:
          // single-select (selected) OR multi-select membership (multiSelected)
          // both show the terracotta ring. The connect-handle + label
          // placeholder below stay on `selected` alone, so card EDITING is
          // single-only — multi-members get a ring, not an editor.
          borderColor:
            selected || multiSelected ? "var(--accent)" : "var(--border-base)",
          outline: selected || multiSelected ? "2px solid var(--accent)" : undefined,
          outlineOffset: selected || multiSelected ? "1px" : undefined,
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
              {/* P3a — inline-editable title. Editing → input; else a label
                  (when set) or a faint "name this node" placeholder (when
                  selected+empty). Double-click enters edit; the stopPropagation
                  family keeps it clear of select + dnd-kit drag. */}
              {editingLabel ? (
                <input
                  autoFocus
                  value={labelDraft}
                  onChange={(e) => setLabelDraft(e.target.value)}
                  onClick={stop}
                  onPointerDown={stop}
                  onBlur={commitLabel}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault()
                      commitLabel()
                    } else if (e.key === "Escape") {
                      e.preventDefault()
                      cancelLabel()
                    }
                  }}
                  data-testid={`canvas-node-${node.id}-label-input`}
                  className="mt-1 w-full rounded-sm border border-accent bg-surface-raised px-1 py-0.5 text-caption font-semibold text-content-strong"
                />
              ) : node.label ? (
                <p
                  className={`mt-1 whitespace-normal break-words text-caption font-semibold text-content-strong${
                    onRenameNode ? " cursor-text" : ""
                  }`}
                  data-testid={`canvas-node-${node.id}-label`}
                  onDoubleClick={
                    onRenameNode
                      ? (ev) => {
                          ev.stopPropagation()
                          beginLabelEdit()
                        }
                      : undefined
                  }
                >
                  {node.label}
                </p>
              ) : selected && onRenameNode ? (
                <p
                  className="mt-1 cursor-text text-caption italic text-content-muted/70"
                  data-testid={`canvas-node-${node.id}-label-placeholder`}
                  onDoubleClick={(ev) => {
                    ev.stopPropagation()
                    beginLabelEdit()
                  }}
                >
                  name this node
                </p>
              ) : null}
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

              {/* P3a — un-slotted-param expand panel. Surfaces the params NOT
                  in the sentence (inspector-only today) as editable rows that
                  reuse PropControlDispatcher + the SAME onUpdateNodeConfig
                  whole-key merge as the tokens. Inline-grow: rows are card
                  content, so grow-to-fit measures the taller card + the edge
                  source-anchor settles. Only rendered when there ARE un-slotted
                  params + an editor callback (the 6 fully-slotted types show
                  nothing). The toggle + panel stopPropagation so neither
                  selects the node nor starts a drag. */}
              {(unslotted.length > 0 || isBespoke) && onUpdateNodeConfig && (
                <div className="mt-1.5">
                  <button
                    type="button"
                    onClick={(ev) => {
                      ev.stopPropagation()
                      setExpanded((x) => !x)
                    }}
                    onPointerDown={stop}
                    data-testid={`canvas-node-${node.id}-expand-toggle`}
                    aria-expanded={expanded}
                    className="inline-flex items-center gap-1 rounded-sm border border-border-base bg-surface-raised px-1.5 py-0.5 text-micro text-content-muted hover:bg-accent-subtle hover:text-accent"
                  >
                    {expanded ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                    {isBespoke
                      ? "Configure"
                      : expanded
                        ? "Fewer fields"
                        : `${unslotted.length} more field${
                            unslotted.length === 1 ? "" : "s"
                          }`}
                  </button>
                  {expanded && (
                    <div
                      className="mt-1.5 flex flex-col gap-2 rounded-sm border border-border-subtle bg-surface-base/60 p-2"
                      data-testid={`canvas-node-${node.id}-expand-panel`}
                      onClick={stop}
                      onPointerDown={stop}
                    >
                      {isBespoke ? (
                        // P3 (E-3): host the bespoke config (dependent op_id +
                        // binding-list kwargs) here — replaces the dumb
                        // unslotted rows the panel would otherwise render for
                        // these types. onChange emits the FULL next config →
                        // the same whole-config persist the rail pane used.
                        <BespokeNodePane
                          node={node}
                          onChange={(cfg) => onUpdateNodeConfig(node.id, cfg)}
                        />
                      ) : (
                        unslotted.map((param) => {
                          const schema = configProps[param]
                          if (!schema) return null
                          const current =
                            param in node.config
                              ? node.config[param]
                              : schema.default
                          return (
                            <div
                              key={param}
                              className="flex flex-col gap-1"
                              data-testid={`canvas-node-${node.id}-field-${param}`}
                            >
                              <label className="text-micro uppercase tracking-wider text-content-muted">
                                {humanizeParam(param)}
                              </label>
                              <PropControlDispatcher
                                schema={schema}
                                value={current}
                                onChange={(next) =>
                                  onUpdateNodeConfig(node.id, {
                                    ...node.config,
                                    [param]: next,
                                  })
                                }
                                data-testid={`canvas-node-${node.id}-field-editor-${param}`}
                              />
                            </div>
                          )
                        })
                      )}
                    </div>
                  )}
                </div>
              )}
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


interface GraphCanvasContainerProps {
  container: WorkflowContainer
  /**
   * Computed bounds (canvas px). Expanded: the member bbox + padding.
   * Collapsed: the compact fixed-size box at the members' bbox top-left
   * (`collapsedBoxBounds`). The parent feeds the right bounds per state.
   */
  bounds: { x: number; y: number; width: number; height: number }
  /** Negative-coordinate support — content origin (≤ 0) subtracted from the
   *  box bounds to get on-surface left/top. 0 → unchanged. */
  originX: number
  originY: number
  /** Number of (resolved node) members — shown on the collapsed card. */
  memberCount: number
  /**
   * Container-arc Phase 3b — nesting depth (0 = top-level). Drives depth-scaled
   * z so an inner box paints ABOVE its outer: expanded frames at
   * `min(0.9, depth·0.1)` (all stay BELOW the nodes' z=1 so nodes remain
   * interactive on top); collapsed cards at `1 + depth` (node band). Both
   * reduce to the P2 values at depth 0 (expanded 0, collapsed 1) → non-nested
   * rendering byte-identical.
   */
  depth?: number
  /** Container-arc Phase 3c — this container is in the multi-selection (drives
   *  the selection ring; mirrors the node `multiSelected`). */
  multiSelected?: boolean
  /** Container-arc Phase 3c — select this container (collapsed → body click;
   *  expanded → the chrome select handle). `additive` = shift/⌘. */
  onSelect?: (id: string, additive?: boolean) => void
  onUpdateContainer?: (id: string, patch: Partial<WorkflowContainer>) => void
  onRemoveContainer?: (id: string) => void
}

/**
 * Container-arc Phase 1 + 2b — a container box, in one of two states.
 *
 * EXPANDED (`collapsed:false`, P1): a labeled frame drawn BEHIND the node
 * layer (pointer-events:none body so enclosed nodes stay clickable through
 * it; chrome — label chip + collapse + ungroup — is pointer-events:auto).
 * Label inline-editable on double-click.
 *
 * COLLAPSED (`collapsed:true`, P2b): an OPAQUE card in the node z-band that
 * REPLACES the hidden members (the parent filters them out of the node-map),
 * showing the label + member count + an expand toggle. Crossing edges reroute
 * to this box's top/bottom (see the edge-map). Label-edit is available on the
 * expanded chrome (expand to rename) — kept off the collapsed card for P2b.
 */
function GraphCanvasContainer({
  container,
  bounds,
  originX,
  originY,
  memberCount,
  depth = 0,
  multiSelected,
  onSelect,
  onUpdateContainer,
  onRemoveContainer,
}: GraphCanvasContainerProps) {
  // Negative-coordinate support — on-surface left/top = bounds - origin.
  // origin 0 → byte-identical. Used in both the collapsed + expanded returns.
  const left = bounds.x - originX
  const top = bounds.y - originY
  // Container-arc Phase 3b — z bands. CSS z-index is INTEGER-only, and there's
  // no integer strictly between an expanded frame (must stay < the node band,
  // z=1, so nodes stay interactive on top) and the nodes — so all EXPANDED
  // frames share z=0 (== P2; their translucent backdrops don't need
  // depth-layering, and nesting reads fine via the recursive bounds + DOM
  // order). The OPAQUE COLLAPSED cards — where layering actually matters — get
  // the integer depth-z `1 + depth` (depth 0 → 1 == P2; an inner collapsed
  // card paints above its outer + above the node baseline).
  const expandedZ = 0
  const collapsedZ = 1 + depth
  const [editingLabel, setEditingLabel] = useState(false)
  const [labelDraft, setLabelDraft] = useState(container.label ?? "")
  const stop = (ev: { stopPropagation: () => void }) => ev.stopPropagation()

  const toggleCollapsed = () =>
    onUpdateContainer?.(container.id, { collapsed: !container.collapsed })

  const beginLabelEdit = () => {
    setLabelDraft(container.label ?? "")
    setEditingLabel(true)
  }
  const commitLabel = () => {
    setEditingLabel(false)
    const next = labelDraft.trim()
    if (next !== (container.label ?? "")) {
      onUpdateContainer?.(container.id, { label: next })
    }
  }
  const cancelLabel = () => {
    setEditingLabel(false)
    setLabelDraft(container.label ?? "")
  }

  // ── COLLAPSED — opaque card in the node z-band (replaces the members) ──
  if (container.collapsed) {
    return (
      <div
        data-testid={`canvas-container-${container.id}`}
        data-collapsed="true"
        // Container-arc Phase 3c — multi-selection state (drives the ring).
        data-multi-selected={multiSelected ?? false}
        className="pointer-events-auto absolute flex flex-col justify-center rounded-md border border-accent/60 bg-surface-elevated shadow-level-1"
        style={{
          left,
          top,
          width: bounds.width,
          height: bounds.height,
          // Node z-band — the collapsed box sits among the cards it replaces.
          // Depth-scaled (1 + depth): an inner collapsed card paints above its
          // outer; depth 0 → z=1 (== P2).
          zIndex: collapsedZ,
          // Container-arc Phase 3c — selection ring (mirrors the node ring).
          outline: multiSelected ? "2px solid var(--accent)" : undefined,
          outlineOffset: multiSelected ? "1px" : undefined,
        }}
        // Container-arc Phase 3c — body click selects (the opaque card is
        // pointer-events:auto; chrome buttons stopPropagation so they act, not
        // select). shift/⌘ accumulates into the multi-selection.
        onClick={
          onSelect
            ? (ev) => onSelect(container.id, ev.shiftKey || ev.metaKey)
            : undefined
        }
      >
        <div className="flex items-center justify-between gap-1 px-2">
          <div className="min-w-0">
            <p
              data-testid={`canvas-container-${container.id}-label`}
              className="truncate text-caption font-semibold text-content-strong"
            >
              {container.label || "Group"}
            </p>
            <p className="text-micro text-content-muted">
              {memberCount} node{memberCount === 1 ? "" : "s"} · collapsed
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            {onUpdateContainer && (
              <button
                type="button"
                onClick={(ev) => {
                  ev.stopPropagation()
                  toggleCollapsed()
                }}
                onPointerDown={stop}
                data-testid={`canvas-container-${container.id}-expand`}
                aria-label="Expand container"
                title="Expand"
                className="rounded-sm border border-border-base bg-surface-raised p-0.5 text-content-muted hover:bg-accent-subtle hover:text-accent"
              >
                <Maximize2 size={12} />
              </button>
            )}
            {onRemoveContainer && (
              <button
                type="button"
                onClick={(ev) => {
                  ev.stopPropagation()
                  onRemoveContainer(container.id)
                }}
                onPointerDown={stop}
                data-testid={`canvas-container-${container.id}-ungroup`}
                aria-label="Ungroup container"
                title="Ungroup (keeps the nodes)"
                className="rounded-sm border border-border-base bg-surface-raised p-0.5 text-content-muted hover:bg-status-error-muted hover:text-status-error"
              >
                <Ungroup size={12} />
              </button>
            )}
          </div>
        </div>
      </div>
    )
  }

  // ── EXPANDED — labeled frame behind the nodes (P1) + a collapse button ──
  return (
    <div
      data-testid={`canvas-container-${container.id}`}
      data-collapsed="false"
      // Container-arc Phase 3c — multi-selection state (drives the ring).
      data-multi-selected={multiSelected ?? false}
      className="pointer-events-none absolute rounded-lg border border-dashed border-accent/50 bg-accent-subtle/15"
      style={{
        left,
        top,
        width: bounds.width,
        height: bounds.height,
        // Behind the node cards (z 1/2) but above the surface background.
        // Depth-scaled (min(0.9, depth·0.1)): an inner frame paints above its
        // outer, yet ALL expanded frames stay < 1 so nodes remain interactive
        // on top; depth 0 → z=0 (== P2).
        zIndex: expandedZ,
        // Container-arc Phase 3c — selection ring. The frame body stays
        // pointer-events:none (drag passes through to pan, unchanged — the
        // E1 decision); selection happens via the chrome handle below.
        outline: multiSelected ? "2px solid var(--accent)" : undefined,
        outlineOffset: multiSelected ? "1px" : undefined,
      }}
    >
      {/* Chrome — top-left select handle + label chip + collapse + ungroup.
          pointer-events:auto so it's interactive even though the box body is
          pointer-events:none. */}
      <div
        className="pointer-events-auto absolute left-2 top-1.5 flex items-center gap-1"
        onPointerDown={stop}
        onClick={stop}
      >
        {/* Container-arc Phase 3c — the EXPANDED-container select handle (E1).
            The frame body is pointer-events:none (drag passes through to pan,
            unchanged), so selection lives on this chrome affordance — a
            checkbox-style toggle that doubles as the selection indicator.
            shift/⌘ accumulates into the multi-selection. */}
        {onSelect && (
          <button
            type="button"
            onClick={(ev) => {
              ev.stopPropagation()
              onSelect(container.id, ev.shiftKey || ev.metaKey)
            }}
            onPointerDown={stop}
            data-testid={`canvas-container-${container.id}-select`}
            aria-label={multiSelected ? "Deselect container" : "Select container"}
            aria-pressed={multiSelected ?? false}
            title="Select (for grouping)"
            className="rounded-sm border border-border-base bg-surface-raised p-0.5 text-content-muted hover:bg-accent-subtle hover:text-accent"
          >
            {multiSelected ? <CheckSquare size={12} /> : <Square size={12} />}
          </button>
        )}
        {editingLabel ? (
          <input
            autoFocus
            value={labelDraft}
            onChange={(e) => setLabelDraft(e.target.value)}
            onClick={stop}
            onPointerDown={stop}
            onBlur={commitLabel}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault()
                commitLabel()
              } else if (e.key === "Escape") {
                e.preventDefault()
                cancelLabel()
              }
            }}
            data-testid={`canvas-container-${container.id}-label-input`}
            className="rounded-sm border border-accent bg-surface-raised px-1 py-0.5 text-caption font-semibold text-content-strong"
          />
        ) : container.label ? (
          <span
            data-testid={`canvas-container-${container.id}-label`}
            className={`rounded-sm bg-surface-raised/80 px-1.5 py-0.5 text-caption font-semibold text-content-strong${
              onUpdateContainer ? " cursor-text" : ""
            }`}
            onDoubleClick={
              onUpdateContainer
                ? (ev) => {
                    ev.stopPropagation()
                    beginLabelEdit()
                  }
                : undefined
            }
          >
            {container.label}
          </span>
        ) : onUpdateContainer ? (
          <span
            data-testid={`canvas-container-${container.id}-label-placeholder`}
            className="cursor-text rounded-sm bg-surface-raised/60 px-1.5 py-0.5 text-caption italic text-content-muted/70"
            onDoubleClick={(ev) => {
              ev.stopPropagation()
              beginLabelEdit()
            }}
          >
            name this group
          </span>
        ) : null}
        {onUpdateContainer && (
          <button
            type="button"
            onClick={(ev) => {
              ev.stopPropagation()
              toggleCollapsed()
            }}
            onPointerDown={stop}
            data-testid={`canvas-container-${container.id}-collapse`}
            aria-label="Collapse container"
            title="Collapse"
            className="rounded-sm border border-border-base bg-surface-raised p-0.5 text-content-muted hover:bg-accent-subtle hover:text-accent"
          >
            <Minimize2 size={12} />
          </button>
        )}
        {onRemoveContainer && (
          <button
            type="button"
            onClick={(ev) => {
              ev.stopPropagation()
              onRemoveContainer(container.id)
            }}
            onPointerDown={stop}
            data-testid={`canvas-container-${container.id}-ungroup`}
            aria-label="Ungroup container"
            title="Ungroup (keeps the nodes)"
            className="rounded-sm border border-border-base bg-surface-raised p-0.5 text-content-muted hover:bg-status-error-muted hover:text-status-error"
          >
            <Ungroup size={12} />
          </button>
        )}
      </div>
    </div>
  )
}
