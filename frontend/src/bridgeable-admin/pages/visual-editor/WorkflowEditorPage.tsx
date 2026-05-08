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
  ArrowLeftRight,
  GitBranch,
  History,
  Loader2,
  Plus,
  Save,
  Trash2,
  Undo2,
} from "lucide-react"
import { Link } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
// Phase R-6.0b — per-node-type inspector configs for the headless
// Generation Focus + Review Focus workflow primitives. Dispatched from
// NodeConfigForm based on selectedNode.type; the JSON textarea remains
// the canonical fallback for every other node type.
import { InvokeGenerationFocusConfig } from "@/bridgeable-admin/components/visual-editor/workflow-canvas/InvokeGenerationFocusConfig"
import { InvokeReviewFocusConfig } from "@/bridgeable-admin/components/visual-editor/workflow-canvas/InvokeReviewFocusConfig"
import {
  HierarchicalEditorBrowser,
  type HierarchicalCategory,
  type HierarchicalTemplate,
} from "@/bridgeable-admin/components/visual-editor/HierarchicalEditorBrowser"
import {
  EMPTY_CANVAS,
  workflowTemplatesService,
  type CanvasNode,
  type CanvasState,
  type TenantWorkflowFork,
  type WorkflowScope,
  type WorkflowTemplateFull,
  type WorkflowTemplateMetadata,
} from "@/bridgeable-admin/services/workflow-templates-service"
import {
  CanvasValidationError,
  VALID_NODE_TYPES,
  summarizeCanvas,
  validateCanvasState,
} from "@/lib/visual-editor/workflows/canvas-validator"


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
  // ── Template selection ───────────────────────────────
  const [scope, setScope] = useState<WorkflowScope>("vertical_default")
  const [vertical, setVertical] = useState<string>("funeral_home")
  const [workflowType, setWorkflowType] = useState<string>("")

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
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

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
    setSelectedNodeId(null)
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

  const handleAddEdge = useCallback(
    (source: string, target: string) => {
      setDraftCanvas((prev) => {
        const id = generateEdgeId(prev, source, target)
        return {
          version: prev.version,
          trigger: prev.trigger,
          nodes: prev.nodes,
          edges: [...prev.edges, { id, source, target }],
        }
      })
    },
    [],
  )

  const handleRemoveEdge = useCallback((edgeId: string) => {
    setDraftCanvas((prev) => ({
      version: prev.version,
      trigger: prev.trigger,
      nodes: prev.nodes,
      edges: prev.edges.filter((e) => e.id !== edgeId),
    }))
  }, [])

  const selectedNode = useMemo(
    () =>
      selectedNodeId
        ? draftCanvas.nodes.find((n) => n.id === selectedNodeId) ?? null
        : null,
    [draftCanvas, selectedNodeId],
  )

  // ── Render ───────────────────────────────────────────
  return (
    <div
      className="flex h-[calc(100vh-3rem)] flex-col"
      data-testid="workflow-editor-page"
    >
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
      <div className="grid flex-1 grid-cols-[280px_minmax(0,1fr)_320px] overflow-hidden">
        {/* ── Left pane — selector + metadata + forks ── */}
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

        {/* ── Center pane — node-list canvas ───────────── */}
        <div
          className="flex flex-col overflow-hidden"
          data-testid="workflow-editor-canvas-pane"
        >
          {/* Node palette across the top of the canvas */}
          <div className="flex flex-wrap items-center gap-1 border-b border-border-subtle bg-surface-elevated px-4 py-2">
            <span className="mr-2 text-caption text-content-muted">
              Add:
            </span>
            {(["start", "action", "decision", "branch", "parallel_split", "parallel_join", "schedule", "send-communication", "generation-focus-invocation", "invoke_generation_focus", "invoke_review_focus", "cross_tenant_order", "cross_tenant_request", "playwright_action", "log_vault_item", "end"] as const).map(
              (t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => handleAddNode(t)}
                  data-testid={`palette-${t}`}
                  className="rounded-sm border border-border-base bg-surface-raised px-2 py-0.5 text-micro text-content-base hover:bg-accent-subtle"
                >
                  {t}
                </button>
              ),
            )}
          </div>
          <div
            className="flex-1 overflow-y-auto px-4 py-3"
            data-testid="canvas-node-list"
          >
            {validationError && (
              <p
                className="mb-2 rounded-sm border border-status-error bg-status-error-muted px-2 py-1 text-caption text-status-error"
                data-testid="canvas-validation-message"
              >
                {validationError}
              </p>
            )}
            {draftCanvas.nodes.length === 0 ? (
              <p className="text-body-sm text-content-muted">
                No nodes yet. Add one from the palette above to start.
              </p>
            ) : (
              <ol className="flex flex-col gap-2">
                {draftCanvas.nodes.map((node, idx) => {
                  const isSelected = selectedNodeId === node.id
                  const outgoingEdges = draftCanvas.edges.filter(
                    (e) => e.source === node.id,
                  )
                  return (
                    <li
                      key={node.id}
                      data-testid={`canvas-node-${node.id}`}
                      data-node-type={node.type}
                      data-selected={isSelected}
                    >
                      <button
                        type="button"
                        onClick={() => setSelectedNodeId(node.id)}
                        className={`flex w-full items-start justify-between gap-3 rounded-md border p-3 text-left ${
                          isSelected
                            ? "border-accent bg-accent-subtle"
                            : "border-border-subtle bg-surface-elevated hover:bg-accent-subtle/40"
                        }`}
                      >
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline">{node.type}</Badge>
                            <code className="font-plex-mono text-caption text-content-muted">
                              {node.id}
                            </code>
                            <span className="text-caption text-content-base">
                              #{idx + 1}
                            </span>
                          </div>
                          {node.label && (
                            <p className="mt-1 text-body-sm text-content-strong">
                              {node.label}
                            </p>
                          )}
                          {outgoingEdges.length > 0 && (
                            <div className="mt-1 flex flex-wrap gap-1">
                              {outgoingEdges.map((e) => {
                                const target = draftCanvas.nodes.find(
                                  (n) => n.id === e.target,
                                )
                                return (
                                  <span
                                    key={e.id}
                                    className="text-caption text-content-muted"
                                    data-testid={`edge-${e.id}`}
                                  >
                                    →{" "}
                                    <code className="font-plex-mono">
                                      {target?.label ?? e.target}
                                    </code>
                                    {e.condition && (
                                      <span className="ml-1 italic">
                                        ({e.condition})
                                      </span>
                                    )}
                                  </span>
                                )
                              })}
                            </div>
                          )}
                        </div>
                        <button
                          type="button"
                          onClick={(ev) => {
                            ev.stopPropagation()
                            handleRemoveNode(node.id)
                          }}
                          data-testid={`canvas-node-${node.id}-remove`}
                          aria-label="Remove node"
                          className="rounded-sm border border-border-base bg-surface-raised p-1 text-content-muted hover:bg-status-error-muted hover:text-status-error"
                        >
                          <Trash2 size={12} />
                        </button>
                      </button>
                    </li>
                  )
                })}
              </ol>
            )}
          </div>
        </div>

        {/* ── Right pane — node configuration ─────────── */}
        <aside
          className="flex flex-col overflow-y-auto border-l border-border-subtle bg-surface-sunken p-4"
          data-testid="workflow-editor-node-config-pane"
        >
          {!selectedNode ? (
            <p className="text-body-sm text-content-muted">
              Select a node to configure it.
            </p>
          ) : (
            <NodeConfigForm
              node={selectedNode}
              allNodes={draftCanvas.nodes}
              outgoingEdges={draftCanvas.edges.filter(
                (e) => e.source === selectedNode.id,
              )}
              onPatch={(patch) => handleUpdateNode(selectedNode.id, patch)}
              onAddEdge={(target) => handleAddEdge(selectedNode.id, target)}
              onRemoveEdge={(edgeId) => handleRemoveEdge(edgeId)}
            />
          )}
        </aside>
      </div>
    </div>
  )
}


// ─── Node configuration form ─────────────────────────────────────


interface NodeConfigFormProps {
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

function NodeConfigForm({
  node,
  allNodes,
  outgoingEdges,
  onPatch,
  onAddEdge,
  onRemoveEdge,
}: NodeConfigFormProps) {
  const [edgeTargetSelect, setEdgeTargetSelect] = useState<string>("")
  const [configJson, setConfigJson] = useState<string>(
    JSON.stringify(node.config, null, 2),
  )
  const [configError, setConfigError] = useState<string | null>(null)

  // Sync configJson when node changes
  useEffect(() => {
    setConfigJson(JSON.stringify(node.config, null, 2))
    setConfigError(null)
  }, [node.id])

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
        <div>
          <label className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted">
            Config (JSON)
          </label>
          <textarea
            value={configJson}
            onChange={(e) => {
              setConfigJson(e.target.value)
              try {
                const parsed = JSON.parse(e.target.value || "{}")
                if (
                  typeof parsed === "object" &&
                  parsed !== null &&
                  !Array.isArray(parsed)
                ) {
                  setConfigError(null)
                  onPatch({ config: parsed })
                } else {
                  setConfigError("Must be a JSON object")
                }
              } catch {
                setConfigError("Invalid JSON")
              }
            }}
            rows={6}
            data-testid="node-config-config-textarea"
            className="w-full rounded-md border border-border-base bg-surface-raised p-2 font-plex-mono text-caption text-content-base"
          />
          {configError && (
            <span
              className="text-caption text-status-error"
              data-testid="node-config-config-error"
            >
              {configError}
            </span>
          )}
        </div>
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
