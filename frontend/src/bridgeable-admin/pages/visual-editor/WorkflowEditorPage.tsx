/**
 * WorkflowEditorPage — Phase 4 of the Admin Visual Editor.
 *
 * Two-pane layout (canvas takes the dominant area; configuration
 * in sidebar):
 *
 *   ┌─ Top bar — title, mode indicator, save buttons, cross-links ┐
 *   ├──────────────────────────────────────────────────────────────┤
 *   │ Left pane — template selector + metadata + dependent forks  │
 *   │ Center — node-list canvas (vertical sequence, branching     │
 *   │           expressed via edge labels + parallel split/join   │
 *   │           markers); each node selectable                    │
 *   │ Right pane (collapsible) — node configuration when selected │
 *   └──────────────────────────────────────────────────────────────┘
 *
 * Edits flow: operator selects/modifies a node → setDraft({...}) →
 * canvas re-renders → save persists. Save triggers backend's
 * mark_pending_merge for dependent tenant forks (locked-to-fork
 * semantics: forks see pending_merge_available=true but their
 * canvas_state is unchanged until the tenant accepts).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  AlertCircle,
  ArrowLeft,
  ArrowLeftRight,
  GitBranch,
  History,
  Loader2,
  Plus,
  Save,
  Undo2,
} from "lucide-react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
// Inline-params P3c + focus-invocation reconciliation P3 (E-3, arc close,
// 2026-06-02) — the card editor's rail no longer renders ANY node-config form:
// EVERY node-edit lives on the card/canvas. Through P1→P3b-2 the general types
// moved onto the card (config tokens + P3a expand panel, label inline-edit,
// edges via drag-to-connect + midpoint-×); the 2 bespoke invoke_* types' last
// remnant (the rail BespokeNodePane) relocated into the card expand panel in
// E-3. So node-selection now ALWAYS shows the palette — no rail-pane exception.
// NodeConfigForm + BespokeNodePane are NOT deleted: the runtime-host
// WorkflowsTab (a panel inspector with no card) still uses NodeConfigForm, and
// GraphCanvas's expand panel now hosts BespokeNodePane.
// Phase B sub-arc B-1 — graph-canvas authoring substrate. Replaces the
// pre-B-1 <ol><li> vertical-list rendering with a directed-graph canvas
// matching the runtime DAG layout model per Entry 11 WYSIWYG.
import { GraphCanvas } from "@/bridgeable-admin/components/visual-editor/workflow-canvas/GraphCanvas"
// Phase B sub-arc B-2 — node palette renders from the component registry
// (getByType("workflow-node")) instead of a hardcoded tuple. Registry is
// populated via App.tsx's auto-register side-effect import (BridgeableAdminApp
// mounts under App.tsx). Flat render per Path A — no grouping substrate.
import {
  HierarchicalEditorBrowser,
  type HierarchicalCategory,
  type HierarchicalTemplate,
} from "@/bridgeable-admin/components/visual-editor/HierarchicalEditorBrowser"
import {
  EMPTY_CANVAS,
  workflowTemplatesService,
  type CanvasNode,
  type CanvasEdge,
  type CanvasState,
  type CanvasTrigger,
  type TenantWorkflowFork,
  type WorkflowScope,
  type WorkflowTemplateFull,
  type WorkflowTemplateMetadata,
} from "@/bridgeable-admin/services/workflow-templates-service"
// Phase B sub-arc B-5 — selection-driven right-rail inspectors. Edge
// selection → EdgeConditionInspector; background (empty-canvas) selection
// → TriggerInspector. (P3c+E-3: node selection → palette for ALL types.)
import { EdgeConditionInspector } from "@/bridgeable-admin/components/visual-editor/workflow-canvas/EdgeConditionInspector"
import { TriggerInspector } from "@/bridgeable-admin/components/visual-editor/workflow-canvas/TriggerInspector"
// Right-rail action palette (2026-05-29) — the none-state becomes a
// searchable, family-grouped node-add palette (Apple Shortcuts model);
// replaces the retired center-top "Add:" chip-row as the sole add-surface.
import { WorkflowNodePalette } from "@/bridgeable-admin/components/visual-editor/workflow-canvas/WorkflowNodePalette"
import {
  CanvasValidationError,
  summarizeCanvas,
  validateCanvasState,
} from "@/lib/visual-editor/workflows/canvas-validator"
import { useStudioRail } from "@/bridgeable-admin/components/studio/StudioRailContext"


const VERTICALS = ["funeral_home", "manufacturing", "cemetery", "crematory"] as const


function ensureCanvasState(
  c: Partial<CanvasState> | undefined,
): CanvasState {
  if (!c || !c.nodes || !c.edges) {
    return { ...EMPTY_CANVAS, nodes: [], edges: [] }
  }
  return {
    version: c.version ?? 1,
    trigger: c.trigger,
    nodes: c.nodes,
    edges: c.edges,
  }
}


function generateNodeId(canvas: CanvasState): string {
  let i = canvas.nodes.length + 1
  while (canvas.nodes.some((n) => n.id === `n_node_${i}`)) i += 1
  return `n_node_${i}`
}




// Phase B sub-arc B-5 — selection-context discriminated union.
// Container-arc Phase 0 (2026-06-04) — added a FIFTH kind `nodes` for
// multi-node selection (shift/⌘+click accumulate). The existing single
// `node` kind is UNCHANGED — it keeps its exact card-editing behavior. The
// new `nodes` kind is the selection MECHANISM only; its first consumer
// (group-into-container) arrives in Phase 1. `selectedNodeId` stays
// single-only (null under `nodes`), so every single-select card affordance
// goes dormant under multi-select for free.
type WorkflowSelection =
  | { kind: "none" }
  | { kind: "node"; id: string }
  | { kind: "nodes"; ids: string[] }
  | { kind: "edge"; id: string }
  | { kind: "background" }


function generateEdgeId(canvas: CanvasState, source: string, target: string): string {
  const base = `e_${source}_${target}`.replace(/[^a-zA-Z0-9_]/g, "_")
  let candidate = base
  let i = 2
  while (canvas.edges.some((e) => e.id === candidate)) {
    candidate = `${base}_${i}`
    i += 1
  }
  return candidate
}


export default function WorkflowEditorPage() {
  // Studio 1a-i.B — hide editor's own left pane when inside Studio shell
  // with rail expanded. Standalone callers keep left pane visible.
  // Workflow editor's left pane carries metadata + dependent-forks view
  // alongside the scope/workflow_type selectors; collapsing the Studio
  // rail to the icon strip restores access to those views.
  const { railExpanded, inStudioContext } = useStudioRail()
  const hideLeftPane = railExpanded && inStudioContext

  // ── Arc-3.x-deep-link-retrofit: bidirectional deep-link ──
  //
  // When opened from the runtime editor inspector's Workflows tab via
  // the "Open in full editor" deep-link, the URL carries `return_to`
  // and optionally `workflow_type` + `scope`. We render a "Back to
  // runtime editor" affordance that navigates the operator back with
  // their inspector state preserved (return_to encoded the full
  // pathname + search; the runtime editor stays mounted in the
  // originating tab because the link uses target="_blank"). Launched
  // directly (no return_to), the affordance is hidden and behavior is
  // identical to pre-retrofit. Mirrors Arc 3a FocusEditorPage canon.
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const returnTo = searchParams.get("return_to")
  const initialWorkflowType = searchParams.get("workflow_type")
  const initialScope = searchParams.get("scope")

  // ── Template selection ───────────────────────────────
  const [scope, setScope] = useState<WorkflowScope>(
    initialScope === "platform_default" || initialScope === "vertical_default"
      ? (initialScope as WorkflowScope)
      : "vertical_default",
  )
  const [vertical, setVertical] = useState<string>("funeral_home")
  const [workflowType, setWorkflowType] = useState<string>(
    initialWorkflowType ?? "",
  )

  // ── Available templates at the current scope/vertical ────
  const [availableTemplates, setAvailableTemplates] = useState<
    WorkflowTemplateMetadata[]
  >([])
  const [activeTemplate, setActiveTemplate] =
    useState<WorkflowTemplateFull | null>(null)
  const [dependentForks, setDependentForks] = useState<TenantWorkflowFork[]>([])
  const [showForksList, setShowForksList] = useState(false)

  // ── Draft state ──────────────────────────────────────
  const [draftCanvas, setDraftCanvas] = useState<CanvasState>(EMPTY_CANVAS)
  const [draftDisplayName, setDraftDisplayName] = useState<string>("")
  const [draftDescription, setDraftDescription] = useState<string>("")
  // Phase B sub-arc B-5 — 4-state selection-context (plain union, no
  // reducer). Drives the right-rail inspector dispatch: none → palette;
  // node → palette for ALL types (P3c+E-3 — bespoke configs host in the card
  // expand panel, not the rail); edge → EdgeConditionInspector; background →
  // TriggerInspector. `selectedNodeId` is derived for GraphCanvas.
  const [selection, setSelection] = useState<WorkflowSelection>({
    kind: "none",
  })
  const selectedNodeId = selection.kind === "node" ? selection.id : null
  const selectedEdgeId = selection.kind === "edge" ? selection.id : null
  // Container-arc Phase 0 — the multi-node selection set (drives the
  // per-member ring in GraphCanvas). Empty unless kind === "nodes". Distinct
  // from selectedNodeId (single) so the ring renders WITHOUT reactivating the
  // single-node card-editing affordances.
  const selectedNodeIds = selection.kind === "nodes" ? selection.ids : []

  // ── Loading + save state ─────────────────────────────
  const [, setIsLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  // ── Form state for new template ──────────────────────
  const [creatingNewType, setCreatingNewType] = useState(false)
  const [newTypeInput, setNewTypeInput] = useState<string>("")
  const [browserSearch, setBrowserSearch] = useState("")

  // ── Load available templates for current scope/vertical ──
  const refreshTemplateList = useCallback(async () => {
    setIsLoading(true)
    setLoadError(null)
    try {
      const params: { scope: WorkflowScope; vertical?: string } = { scope }
      if (scope === "vertical_default" && vertical) {
        params.vertical = vertical
      }
      const list = await workflowTemplatesService.list(params)
      setAvailableTemplates(list)
      if (list.length > 0 && !workflowType) {
        setWorkflowType(list[0].workflow_type)
      } else if (list.length === 0) {
        setWorkflowType("")
        setActiveTemplate(null)
        setDraftCanvas(ensureCanvasState(undefined))
        setDraftDisplayName("")
        setDraftDescription("")
        setDependentForks([])
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[workflow-editor] list failed", err)
      setLoadError(
        err instanceof Error ? err.message : "Failed to load workflows",
      )
    } finally {
      setIsLoading(false)
    }
  }, [scope, vertical, workflowType])

  useEffect(() => {
    void refreshTemplateList()
    // refreshTemplateList itself depends on scope + vertical; running
    // when those change is the intent.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, vertical])

  // ── Load active template when workflowType changes ───
  useEffect(() => {
    let cancelled = false
    async function loadActive() {
      if (!workflowType) return
      const matching = availableTemplates.find(
        (t) => t.workflow_type === workflowType && t.is_active,
      )
      if (!matching) {
        setActiveTemplate(null)
        setDraftCanvas(ensureCanvasState(undefined))
        setDraftDisplayName("")
        setDraftDescription("")
        setDependentForks([])
        return
      }
      try {
        const full = await workflowTemplatesService.get(matching.id)
        if (cancelled) return
        setActiveTemplate(full)
        setDraftCanvas(ensureCanvasState(full.canvas_state))
        setDraftDisplayName(full.display_name)
        setDraftDescription(full.description ?? "")
        // Dependent forks (only meaningful for vertical_default)
        if (full.scope === "vertical_default") {
          const forks = await workflowTemplatesService.getDependentForks(
            full.id,
          )
          if (!cancelled) setDependentForks(forks)
        } else {
          if (!cancelled) setDependentForks([])
        }
      } catch (err) {
        if (cancelled) return
        // eslint-disable-next-line no-console
        console.error("[workflow-editor] get failed", err)
        setLoadError(
          err instanceof Error ? err.message : "Failed to load template",
        )
      }
    }
    void loadActive()
    return () => {
      cancelled = true
    }
  }, [workflowType, availableTemplates])

  // ── Compute unsaved + validity ──────────────────────
  const persistedCanvas = useMemo(
    () => ensureCanvasState(activeTemplate?.canvas_state),
    [activeTemplate],
  )
  const isDirty = useMemo(() => {
    if (!activeTemplate) {
      // No active template — dirty if user has typed anything
      return draftDisplayName.length > 0 || draftCanvas.nodes.length > 0
    }
    return (
      JSON.stringify(persistedCanvas) !== JSON.stringify(draftCanvas) ||
      draftDisplayName !== activeTemplate.display_name ||
      draftDescription !== (activeTemplate.description ?? "")
    )
  }, [activeTemplate, persistedCanvas, draftCanvas, draftDisplayName, draftDescription])

  // Run client-side validation pre-emptively so the editor warns
  // before save round-trips.
  useEffect(() => {
    try {
      validateCanvasState(draftCanvas)
      setValidationError(null)
    } catch (err) {
      if (err instanceof CanvasValidationError) {
        setValidationError(err.message)
      }
    }
  }, [draftCanvas])

  const summary = useMemo(() => summarizeCanvas(draftCanvas), [draftCanvas])

  // ── Save / Save-and-notify ──────────────────────────
  const performSave = useCallback(
    async (notifyForks: boolean) => {
      if (validationError) {
        setSaveError(`Cannot save: ${validationError}`)
        return
      }
      setIsSaving(true)
      setSaveError(null)
      try {
        if (activeTemplate) {
          const updated = await workflowTemplatesService.update(
            activeTemplate.id,
            {
              display_name: draftDisplayName,
              description: draftDescription,
              canvas_state: draftCanvas,
              notify_forks: notifyForks,
            },
          )
          setActiveTemplate(updated)
        } else {
          if (!workflowType) {
            setSaveError("Cannot save: workflow type is empty")
            return
          }
          const created = await workflowTemplatesService.create({
            scope,
            vertical: scope === "vertical_default" ? vertical : null,
            workflow_type: workflowType,
            display_name: draftDisplayName || workflowType,
            description: draftDescription,
            canvas_state: draftCanvas,
            notify_forks: notifyForks,
          })
          setActiveTemplate(created)
        }
        await refreshTemplateList()
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error("[workflow-editor] save failed", err)
        setSaveError(
          err instanceof Error ? err.message : "Failed to save",
        )
      } finally {
        setIsSaving(false)
      }
    },
    [
      activeTemplate,
      draftCanvas,
      draftDescription,
      draftDisplayName,
      refreshTemplateList,
      scope,
      validationError,
      vertical,
      workflowType,
    ],
  )

  // Debounced autosave — same 1.5s pattern as Phase 2 + 3
  const autosaveTimer = useRef<number | null>(null)
  useEffect(() => {
    if (!isDirty || validationError !== null) return
    if (autosaveTimer.current !== null) {
      window.clearTimeout(autosaveTimer.current)
    }
    autosaveTimer.current = window.setTimeout(() => {
      // Default Save also notifies forks; "Save and notify forks"
      // is the explicit-button alias.
      void performSave(true)
    }, 1500)
    return () => {
      if (autosaveTimer.current !== null) {
        window.clearTimeout(autosaveTimer.current)
        autosaveTimer.current = null
      }
    }
  }, [draftCanvas, draftDisplayName, draftDescription, isDirty, performSave, validationError])

  const handleDiscard = useCallback(() => {
    if (activeTemplate) {
      setDraftCanvas(ensureCanvasState(activeTemplate.canvas_state))
      setDraftDisplayName(activeTemplate.display_name)
      setDraftDescription(activeTemplate.description ?? "")
    } else {
      setDraftCanvas(ensureCanvasState(undefined))
      setDraftDisplayName("")
      setDraftDescription("")
    }
    setSaveError(null)
  }, [activeTemplate])

  // ── Node operations ─────────────────────────────────
  const handleAddNode = useCallback(
    (nodeType: string) => {
      setDraftCanvas((prev) => {
        const next: CanvasState = {
          version: prev.version || 1,
          trigger: prev.trigger,
          nodes: [...prev.nodes],
          edges: [...prev.edges],
        }
        const id = generateNodeId(next)
        const yPos =
          next.nodes.length === 0
            ? 0
            : Math.max(...next.nodes.map((n) => n.position.y)) + 120
        next.nodes.push({
          id,
          type: nodeType,
          label: "",
          position: { x: 0, y: yPos },
          config: {},
        })
        return next
      })
    },
    [],
  )

  const handleRemoveNode = useCallback((nodeId: string) => {
    setDraftCanvas((prev) => ({
      version: prev.version,
      trigger: prev.trigger,
      nodes: prev.nodes.filter((n) => n.id !== nodeId),
      edges: prev.edges.filter(
        (e) => e.source !== nodeId && e.target !== nodeId,
      ),
    }))
    setSelection({ kind: "none" })
  }, [])

  const handleUpdateNode = useCallback(
    (nodeId: string, patch: Partial<CanvasNode>) => {
      setDraftCanvas((prev) => ({
        version: prev.version,
        trigger: prev.trigger,
        nodes: prev.nodes.map((n) =>
          n.id === nodeId ? { ...n, ...patch } : n,
        ),
        edges: prev.edges,
      }))
    },
    [],
  )

  // P3c: handleAddEdge removed — its only caller was NodeConfigForm's
  // inspector edge-add (now gone from this rail). Edge creation flows through
  // onCreateEdge (drag-to-connect), which inlines its own id-gen + append.
  // handleRemoveEdge stays (onDeleteEdge / the midpoint-×); generateEdgeId
  // stays (onCreateEdge). WorkflowsTab keeps its OWN handleAddEdge.

  const handleRemoveEdge = useCallback((edgeId: string) => {
    setDraftCanvas((prev) => ({
      version: prev.version,
      trigger: prev.trigger,
      nodes: prev.nodes,
      edges: prev.edges.filter((e) => e.id !== edgeId),
    }))
  }, [])

  // Phase B sub-arc B-5 — edge + trigger edits. Both flow through
  // setDraftCanvas → the SAME dirty/auto-save path as node edits (no new
  // mutation API). EdgeConditionInspector emits the full next edge;
  // TriggerInspector emits the full next trigger.
  const handleUpdateEdge = useCallback((next: CanvasEdge) => {
    setDraftCanvas((prev) => ({
      version: prev.version,
      trigger: prev.trigger,
      nodes: prev.nodes,
      edges: prev.edges.map((e) => (e.id === next.id ? next : e)),
    }))
  }, [])

  const handleUpdateTrigger = useCallback((next: CanvasTrigger) => {
    setDraftCanvas((prev) => ({
      version: prev.version,
      trigger: next,
      nodes: prev.nodes,
      edges: prev.edges,
    }))
  }, [])

  // Phase B sub-arc B-1 — graph-canvas node-move commit. Reuses the
  // existing handleUpdateNode mutation (Partial<CanvasNode> patch) so
  // position changes flow through the SAME auto-save debounce path as
  // every other node edit per Adjudication 2 — no new mutation API.
  const handleMoveNode = useCallback(
    (nodeId: string, position: { x: number; y: number }) => {
      handleUpdateNode(nodeId, { position })
    },
    [handleUpdateNode],
  )

  // Container-arc Phase 0 — node-selection transition. The page owns the
  // union logic (the canvas just reports id + whether shift/⌘ was held).
  // Rule: plain click → single { kind:"node" } (byte-identical to pre-P0);
  // shift/⌘+click → ALWAYS a { kind:"nodes" } multi-selection (even at 1
  // member), so curating a set never surprise-reactivates card editing
  // mid-gesture. A subsequent plain click demotes back to single-select.
  //   - prev "nodes" → toggle the id (remove if present; clearing the last
  //     member returns to "none").
  //   - prev "node"  → promote to "nodes" [prev.id, id] (dedup'd — shift on
  //     the already-single node yields a multi-of-1 of that node).
  //   - prev none/edge/background → start a multi-of-1.
  // id === null clears (preserves the pre-P0 null-clears contract).
  const handleSelectNode = useCallback(
    (id: string | null, additive?: boolean) => {
      if (id === null) {
        setSelection({ kind: "none" })
        return
      }
      if (!additive) {
        setSelection({ kind: "node", id })
        return
      }
      setSelection((prev) => {
        if (prev.kind === "nodes") {
          const ids = prev.ids.includes(id)
            ? prev.ids.filter((x) => x !== id)
            : [...prev.ids, id]
          return ids.length === 0 ? { kind: "none" } : { kind: "nodes", ids }
        }
        if (prev.kind === "node") {
          return {
            kind: "nodes",
            ids: prev.id === id ? [id] : [prev.id, id],
          }
        }
        return { kind: "nodes", ids: [id] }
      })
    },
    [],
  )

  const selectedNode = useMemo(
    () =>
      selectedNodeId
        ? draftCanvas.nodes.find((n) => n.id === selectedNodeId) ?? null
        : null,
    [draftCanvas, selectedNodeId],
  )

  // B-5: the selected edge (when selection.kind === "edge").
  const selectedEdge = useMemo(
    () =>
      selectedEdgeId
        ? draftCanvas.edges.find((e) => e.id === selectedEdgeId) ?? null
        : null,
    [draftCanvas, selectedEdgeId],
  )

  // Phase B sub-arc B-2 sourced the flat "Add:" chip-row from the registry
  // (all 32 workflow-node registrations). That chip-row was retired
  // 2026-05-29 — the right-rail WorkflowNodePalette (none-state) now owns
  // the registry read + grouping + the node-add surface.

  // ── Render ───────────────────────────────────────────
  return (
    <div
      className="flex h-[calc(100vh-3rem)] flex-col"
      data-testid="workflow-editor-page"
    >
      {/* Arc-3.x-deep-link-retrofit: return-to banner — visible only
          when launched via inspector deep-link. Mirrors Arc 3a
          FocusEditorPage banner shape verbatim (icon, copy, placement). */}
      {returnTo && (
        <div
          className="flex items-center justify-between border-b border-border-subtle bg-accent-subtle/30 px-4 py-2"
          data-testid="workflow-editor-return-to-banner"
        >
          <button
            type="button"
            onClick={() => {
              try {
                const decoded = decodeURIComponent(returnTo)
                navigate(decoded)
              } catch {
                navigate(returnTo)
              }
            }}
            className="flex items-center gap-1 text-caption font-medium text-content-strong hover:text-accent"
            data-testid="workflow-editor-return-to-back"
          >
            <ArrowLeft size={12} />
            Back to runtime editor
          </button>
          <span className="text-caption text-content-muted">
            Inspector state preserved on return
          </span>
        </div>
      )}
      {/* ── Top bar ───────────────────────────────────── */}
      <div className="flex items-center justify-between gap-4 border-b border-border-subtle bg-surface-elevated px-6 py-3">
        <div>
          <h1 className="text-h3 font-plex-serif font-medium text-content-strong">
            Workflow editor
          </h1>
          <p className="text-caption text-content-muted">
            Phase 4 of the Admin Visual Editor — author vertical default
            workflows.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Cross-link nav */}
          <Link
            to="/admin/themes"
            className="flex items-center gap-1 text-caption text-content-muted hover:text-content-strong"
            data-testid="nav-to-themes"
          >
            <ArrowLeftRight size={12} />
            Theme
          </Link>
          <Link
            to="/admin/components"
            className="flex items-center gap-1 text-caption text-content-muted hover:text-content-strong"
            data-testid="nav-to-components"
          >
            <ArrowLeftRight size={12} />
            Components
          </Link>
          <Link
            to="/admin/registry"
            className="flex items-center gap-1 text-caption text-content-muted hover:text-content-strong"
            data-testid="nav-to-registry"
          >
            <ArrowLeftRight size={12} />
            Registry
          </Link>
          {isDirty && (
            <Badge
              variant="warning"
              data-testid="workflow-editor-unsaved-badge"
            >
              unsaved
            </Badge>
          )}
          {validationError && (
            <Badge
              variant="destructive"
              data-testid="workflow-editor-validation-badge"
            >
              invalid canvas
            </Badge>
          )}
          {isSaving && (
            <span className="flex items-center gap-1 text-caption text-content-muted">
              <Loader2 size={12} className="animate-spin" />
              Saving…
            </span>
          )}
          {saveError && (
            <span
              className="flex items-center gap-1 text-caption text-status-error"
              data-testid="workflow-editor-save-error"
            >
              <AlertCircle size={12} />
              {saveError}
            </span>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDiscard}
            disabled={!isDirty}
            data-testid="workflow-editor-discard"
          >
            <Undo2 size={14} className="mr-1" />
            Discard
          </Button>
          <Button
            size="sm"
            onClick={() => void performSave(false)}
            disabled={!isDirty || isSaving || validationError !== null}
            data-testid="workflow-editor-save"
          >
            <Save size={14} className="mr-1" />
            Save
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void performSave(true)}
            disabled={!isDirty || isSaving || validationError !== null}
            data-testid="workflow-editor-save-notify"
            title="Save and explicitly flag dependent tenant forks for merge review"
          >
            Save and notify forks
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled
            data-testid="workflow-editor-history"
          >
            <History size={14} className="mr-1" />
            History
          </Button>
        </div>
      </div>

      {/* ── Mode indicator strip ─────────────────────── */}
      <div
        className="flex items-center gap-2 border-b border-border-subtle bg-surface-sunken px-6 py-1.5 text-caption"
        data-testid="workflow-editor-mode-indicator"
      >
        <Badge variant="outline">{scope}</Badge>
        {scope === "vertical_default" && (
          <Badge variant="outline">{vertical}</Badge>
        )}
        {workflowType && (
          <code className="font-plex-mono text-content-muted">
            {workflowType}
          </code>
        )}
        {activeTemplate && (
          <span className="ml-auto text-content-muted">
            v{activeTemplate.version} · {summary.nodes} nodes ·{" "}
            {summary.edges} edges · {summary.branchingNodes} branches ·{" "}
            {summary.terminalNodes} terminals
          </span>
        )}
      </div>

      {/* ── Body ───────────────────────────────────────── */}
      <div
        className={
          hideLeftPane
            ? "grid flex-1 grid-cols-[minmax(0,1fr)_320px] overflow-hidden"
            : "grid flex-1 grid-cols-[280px_minmax(0,1fr)_320px] overflow-hidden"
        }
      >
        {/* ── Left pane — selector + metadata + forks ── */}
        {!hideLeftPane && (
        <aside
          className="flex flex-col gap-3 overflow-y-auto border-r border-border-subtle bg-surface-sunken p-4"
          data-testid="workflow-editor-selector-pane"
        >
          <div>
            <label className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted">
              Scope
            </label>
            <div className="flex flex-col gap-1">
              {(
                [
                  ["platform_default", "Platform default"],
                  ["vertical_default", "Vertical default"],
                ] as Array<[WorkflowScope, string]>
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  data-testid={`scope-${key}`}
                  onClick={() => setScope(key)}
                  className={`rounded-sm px-2 py-1.5 text-left text-body-sm ${
                    scope === key
                      ? "bg-accent-subtle text-content-strong"
                      : "text-content-base hover:bg-accent-subtle/40"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {scope === "vertical_default" && (
            <div>
              <label
                htmlFor="vertical-select"
                className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted"
              >
                Vertical
              </label>
              <select
                id="vertical-select"
                value={vertical}
                onChange={(e) => setVertical(e.target.value)}
                data-testid="vertical-select"
                className="w-full rounded-md border border-border-base bg-surface-raised px-2 py-1.5 text-body-sm text-content-strong"
              >
                {VERTICALS.map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted">
              Workflow type
            </label>
            {creatingNewType ? (
              <div className="flex flex-col gap-1">
                <Input
                  value={newTypeInput}
                  onChange={(e) => setNewTypeInput(e.target.value)}
                  placeholder="e.g., funeral_cascade"
                  data-testid="new-workflow-type-input"
                />
                <div className="flex gap-1">
                  <Button
                    size="sm"
                    onClick={() => {
                      if (newTypeInput) {
                        setWorkflowType(newTypeInput.trim())
                        setActiveTemplate(null)
                        setDraftCanvas(ensureCanvasState(undefined))
                        setDraftDisplayName(newTypeInput.trim())
                        setDraftDescription("")
                        setCreatingNewType(false)
                        setNewTypeInput("")
                      }
                    }}
                    data-testid="confirm-new-workflow-type"
                  >
                    Create
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setCreatingNewType(false)
                      setNewTypeInput("")
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <>
                {/* May 2026 reorganization — flat <select workflow-type-select>
                    replaced with HierarchicalEditorBrowser. Categories are
                    workflow types; "templates" mirror the active row per type
                    (the model has at most one active workflow_template per
                    (workflow_type, scope, vertical) tuple). Selecting either
                    sets the active workflowType and loads its template. The
                    canvas behavior in the center pane is preserved exactly. */}
                <div
                  className="-mx-4 mb-1 h-72 overflow-hidden border-y border-border-subtle bg-surface-elevated"
                  data-testid="workflow-hierarchical-browser-container"
                >
                  <HierarchicalEditorBrowser
                    categories={
                      availableTemplates.map((t) => ({
                        id: t.workflow_type,
                        label: t.display_name,
                        description: t.description ?? undefined,
                        badge: `v${t.version}`,
                      })) as HierarchicalCategory[]
                    }
                    templates={[] as HierarchicalTemplate[]}
                    selectedCategoryId={workflowType || null}
                    selectedTemplateId={null}
                    search={browserSearch}
                    onSearchChange={setBrowserSearch}
                    onSelectCategory={setWorkflowType}
                    onSelectTemplate={() => {}}
                    searchPlaceholder="Filter workflow types"
                    emptyStateForCategory={() => (
                      <span className="text-content-muted">
                        Active version on canvas.
                      </span>
                    )}
                  />
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setCreatingNewType(true)}
                  data-testid="new-workflow-type-button"
                  className="mt-1 w-full"
                >
                  <Plus size={12} className="mr-1" />
                  New workflow type
                </Button>
              </>
            )}
          </div>

          <div>
            <label
              htmlFor="display-name-input"
              className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted"
            >
              Display name
            </label>
            <Input
              id="display-name-input"
              value={draftDisplayName}
              onChange={(e) => setDraftDisplayName(e.target.value)}
              data-testid="display-name-input"
            />
          </div>

          <div>
            <label
              htmlFor="description-input"
              className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted"
            >
              Description
            </label>
            <textarea
              id="description-input"
              value={draftDescription}
              onChange={(e) => setDraftDescription(e.target.value)}
              data-testid="description-input"
              rows={3}
              className="w-full rounded-md border border-border-base bg-surface-raised px-2 py-1.5 font-plex-sans text-caption text-content-strong"
            />
          </div>

          {scope === "vertical_default" && activeTemplate && (
            <div className="rounded-md border border-border-subtle bg-surface-elevated p-2">
              <button
                type="button"
                onClick={() => setShowForksList((cur) => !cur)}
                className="flex w-full items-center justify-between text-caption text-content-base"
                data-testid="dependent-forks-toggle"
              >
                <span className="flex items-center gap-1">
                  <GitBranch size={12} />
                  {dependentForks.length} tenant fork
                  {dependentForks.length === 1 ? "" : "s"} based on this
                </span>
              </button>
              {showForksList && (
                <ul
                  className="mt-2 flex flex-col gap-1"
                  data-testid="dependent-forks-list"
                >
                  {dependentForks.length === 0 ? (
                    <li className="text-caption text-content-muted">
                      No tenant forks yet.
                    </li>
                  ) : (
                    dependentForks.map((f) => (
                      <li
                        key={f.id}
                        className="flex items-center justify-between text-caption"
                      >
                        <code className="font-plex-mono text-content-muted">
                          {f.tenant_id.slice(0, 8)}…
                        </code>
                        <span className="text-content-base">
                          v{f.forked_from_version}
                        </span>
                        {f.pending_merge_available && (
                          <Badge variant="warning">pending merge</Badge>
                        )}
                      </li>
                    ))
                  )}
                </ul>
              )}
            </div>
          )}

          {loadError && (
            <p className="text-caption text-status-error">{loadError}</p>
          )}
        </aside>
        )}

        {/* ── Center pane — node-list canvas ───────────── */}
        {/* The center-top "Add:" chip-row was RETIRED (2026-05-29) — the
            right-rail action palette (none-state) is now the sole node-add
            surface (Apple Shortcuts model; deselect-to-add). */}
        <div
          className="flex flex-col overflow-hidden"
          data-testid="workflow-editor-canvas-pane"
        >
          <GraphCanvas
            canvas={draftCanvas}
            selectedNodeId={selectedNodeId}
            // Container-arc Phase 0 — multi-node selection. `selectedNodeIds`
            // drives the per-member ring; `onSelectNode`'s additive flag
            // (shift/⌘) routes through the union-transition handler. The
            // single `selectedNodeId` prop is unchanged (single-select stays
            // byte-identical).
            selectedNodeIds={selectedNodeIds}
            onSelectNode={handleSelectNode}
            onMoveNode={handleMoveNode}
            onRemoveNode={handleRemoveNode}
            validationError={validationError}
            selectedEdgeId={selectedEdgeId}
            onSelectEdge={(id) => setSelection({ kind: "edge", id })}
            onSelectBackground={() => setSelection({ kind: "background" })}
            // Inline-params P2a: clickable sentence tokens persist config
            // edits through the SAME handleUpdateNode({config}) path the
            // inspector uses — one mutation path, one source of truth.
            onRenameNode={(id, label) => handleUpdateNode(id, { label })}
            onUpdateNodeConfig={(id, nextConfig) =>
              handleUpdateNode(id, { config: nextConfig })
            }
            // Drag-to-connect P3b-1b: create the dragged edge + select it so
            // EdgeConditionInspector opens for conditioning. The id is computed
            // in-handler (generateEdgeId is deterministic; handleAddEdge can't
            // return it from its setState updater) → append + select atomically.
            // Same bare {id, source, target} shape the inspector edge-add uses.
            onCreateEdge={(source, target) => {
              const id = generateEdgeId(draftCanvas, source, target)
              setDraftCanvas((prev) => ({
                ...prev,
                edges: [...prev.edges, { id, source, target }],
              }))
              setSelection({ kind: "edge", id })
            }}
            // Canvas edge-delete P3b-2: the midpoint-× removes the selected
            // edge + clears selection so EdgeConditionInspector closes (the
            // edge is gone). Same handleRemoveEdge path the inspector uses;
            // mirrors handleRemoveNode (filter + clear selection).
            onDeleteEdge={(id) => {
              handleRemoveEdge(id)
              setSelection({ kind: "none" })
            }}
          />
        </div>

        {/* ── Right pane — selection-driven inspector (B-5 + P3c + E-3) ──
            Dispatches by selection kind:
              node (ALL types) → palette (edits happen ON THE CARD — tokens +
                               P3a expand panel incl. the bespoke focus config
                               for invoke_*, hosted in the panel per E-3; label
                               inline; edges on the canvas)
              edge             → EdgeConditionInspector (unchanged)
              background       → TriggerInspector (unchanged)
              none             → palette (unchanged)
            The card is the sole node-editing surface — no rail-pane exception.
            (NodeConfigForm lives on for the runtime-host WorkflowsTab, a panel
            inspector with no card.) */}
        <aside
          className="flex flex-col overflow-y-auto border-l border-border-subtle bg-surface-sunken p-4"
          data-testid="workflow-editor-node-config-pane"
        >
          {selectedNode ? (
            <WorkflowNodePalette onAdd={handleAddNode} />
          ) : selectedEdge ? (
            <EdgeConditionInspector
              edge={selectedEdge}
              onChange={handleUpdateEdge}
            />
          ) : selection.kind === "background" ? (
            <TriggerInspector
              trigger={draftCanvas.trigger}
              onChange={handleUpdateTrigger}
            />
          ) : (
            // none-state → the searchable, family-grouped action palette
            // (Shortcuts model). Reuses handleAddNode verbatim. The other
            // three inspector arms above are untouched.
            <WorkflowNodePalette onAdd={handleAddNode} />
          )}
        </aside>
      </div>
    </div>
  )
}

