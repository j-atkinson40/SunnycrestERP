/**
 * Arc 2 Phase 2a — Inspector Workflows tab (list view).
 * Arc 2 Phase 2b — In-inspector canvas editing (3-level mode-stack:
 * list → workflow-edit → node-config). Form-local state + 1.5s
 * autosave matching standalone editor pattern verbatim (parity-not-
 * exceedance canon). NodeConfigForm + InvokeGenerationFocusConfig +
 * InvokeReviewFocusConfig reused verbatim from standalone.
 *
 * Architectural patterns locked (Phase 2b):
 *
 * - **Tab-level mode-stack canon** (B-ARC2B-1): each tab owns its own
 *   {stack, push, pop} state. Arc 3+ tabs inherit the pattern via
 *   convention, NOT via a shared inspector-level abstraction. Per
 *   §3.26.7.5 architectural restraint: factor a shared helper hook
 *   when a third tab needs the same shape — not preemptively.
 *
 * - **Form-local + 1.5s autosave canon** (B-ARC2B-2): atomic-per-
 *   instance writes (workflow templates, document templates, focus
 *   compositions, etc.) use form-local React `useState` for the
 *   draft + a debounced `service.update()` call. Contrasts with
 *   Arc 1's staged-override writer pattern, which is reserved for
 *   surfaces where a single commit flushes ≥2 different shape types
 *   together (theme + class + prop tokens). Direct-service-call
 *   atomicity from Phase 2a's B-ARC2-3 preserved.
 *
 * - **3-level sub-mode push canon** (B-ARC2B-3): when an inspector
 *   tab needs detail-authoring on top of a list, it pushes through
 *   `list → edit → detail`. Each level uses full 380px width. Arc 3
 *   tabs that need the same shape (Documents template-detail, Focus
 *   composition node-config) inherit verbatim.
 *
 * - **Parity-not-exceedance canon** (Q-UX-3): the inspector ships
 *   everything the standalone editor has at 380px and nothing more.
 *   No drag-reorder (standalone preserves array order). No trigger-
 *   editing UI (standalone preserves read-only). Edges canonical
 *   only at node-config sub-view; canvas edit-view shows them as
 *   read-only `→ target` labels per standalone lines 888-913.
 *
 * - **Mount-gate refactor deferred** (B-ARC2B-4): Phase 2b preserves
 *   the Phase 2a "select any widget, open Workflows tab" entry
 *   pattern. Selection-free panel mount ships as Arc-3.x-mount-gate
 *   when Arc 3 Documents tab forces the discoverability question.
 *
 * - **Workflow scope locked** at `vertical_default` + `platform_
 *   default` (workflow_templates table only). Tenant `workflows` +
 *   `tenant_workflow_forks` deferred post-September.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  ArrowLeft,
  ChevronDown,
  ExternalLink,
  Loader2,
  Plus,
  Trash2,
} from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { NodeConfigForm } from "@/bridgeable-admin/components/visual-editor/workflow-canvas/NodeConfigForm"
import {
  EMPTY_CANVAS,
  workflowTemplatesService,
  type CanvasNode,
  type CanvasState,
  type WorkflowScope,
  type WorkflowTemplateFull,
  type WorkflowTemplateMetadata,
} from "@/bridgeable-admin/services/workflow-templates-service"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import { buildEditorDeepLink } from "./deep-link-state"
import {
  CanvasValidationError,
  VALID_NODE_TYPES,
  validateCanvasState,
} from "@/lib/visual-editor/workflows/canvas-validator"
// Arc 4d — chip-variant SourceBadge for per-workflow scope display.
// Class B per-instance source metadata: workflows expose scope on
// each WorkflowTemplateMetadata row.
import {
  SourceBadge,
  type SourceValue,
} from "@/lib/visual-editor/source-badge"

import { usePageContext } from "../use-page-context"


/**
 * Arc 4d — map workflows-side WorkflowScope (`platform_default` |
 * `vertical_default`) to canonical SourceBadge SourceValue.
 * `tenant_override` is N/A here — tenant customization happens via
 * fork mechanic (TenantWorkflowFork), not tenant_override scope.
 */
function workflowScopeToSource(scope: WorkflowScope): SourceValue {
  return scope === "vertical_default" ? "vertical" : "platform"
}


// ── Autosave timing (verbatim parity with standalone editor) ──
export const AUTOSAVE_DEBOUNCE_MS = 1500


export interface WorkflowsTabProps {
  /** Impersonated tenant's vertical, threaded by RuntimeEditorShell.
   *  Used as default for vertical_default scope. */
  vertical: string | null
}


/** Mode-stack levels for the Workflows tab (B-ARC2B-3).
 *  Generic stack data structure accommodates per-tab depth variation;
 *  Arc 3+ tabs inherit the pattern, not a shared abstraction. */
export type ModeStackLevel =
  | { kind: "list" }
  | { kind: "workflow-edit"; templateId: string }
  | { kind: "node-config"; templateId: string; nodeId: string }


/** Build the workflow standalone editor URL.
 *
 *  Arc-3.x-deep-link-retrofit (May 2026): upgraded from one-way bare
 *  URL to bidirectional deep-link carrying `return_to` per Arc 3a
 *  deep-link-as-navigation-primitive canon. Optional params:
 *  `workflow_type` (so standalone pre-selects the matching template)
 *  + `scope` (preserves inspector's scope pill selection).
 *
 *  Inspector state is preserved on return because `return_to` carries
 *  the originating pathname+search; the runtime editor route stays
 *  mounted in the originating browser tab (link opens via target=
 *  "_blank"). No URL-state-to-inspector-state restoration logic
 *  needed — same mechanism Arc 3a established for FocusCompositionsTab.
 */
function buildEditorUrl(
  template?: WorkflowTemplateMetadata,
  scope?: WorkflowScope,
): string {
  // Studio 1a-i.A1: prefer the Studio path when inside Studio shell.
  const inStudio =
    typeof window !== "undefined" &&
    window.location.pathname
      .replace(/^\/bridgeable-admin/, "")
      .startsWith("/studio/")
  const base = inStudio
    ? adminPath("/studio/workflows")
    : adminPath("/visual-editor/workflows")
  return buildEditorDeepLink(base, {
    workflow_type: template?.workflow_type,
    scope: scope,
  })
}


/** Normalize partial CanvasState into full shape. */
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


function generateEdgeId(
  canvas: CanvasState,
  source: string,
  target: string,
): string {
  const base = `e_${source}_${target}`.replace(/[^a-zA-Z0-9_]/g, "_")
  let candidate = base
  let i = 2
  while (canvas.edges.some((e) => e.id === candidate)) {
    candidate = `${base}_${i}`
    i += 1
  }
  return candidate
}


/** Client-side filter heuristic for "this surface" toggle. */
export function workflowMatchesPageContext(
  workflow: WorkflowTemplateMetadata,
  pageContextId: string,
  pageContextLabel: string,
): boolean {
  const tokens = `${pageContextId} ${pageContextLabel}`
    .toLowerCase()
    .split(/[\s_/.-]+/)
    .filter((t) => t.length >= 3)
  if (tokens.length === 0) return false
  const haystack = [
    workflow.workflow_type,
    workflow.display_name,
    workflow.description ?? "",
  ]
    .join(" ")
    .toLowerCase()
  return tokens.some((t) => haystack.includes(t))
}


export function WorkflowsTab({ vertical }: WorkflowsTabProps) {
  // ── Mode-stack state (B-ARC2B-1: tab-level, not inspector-level) ──
  const [modeStack, setModeStack] = useState<ModeStackLevel[]>([
    { kind: "list" },
  ])
  const currentLevel = modeStack[modeStack.length - 1]

  const push = useCallback((level: ModeStackLevel) => {
    setModeStack((prev) => [...prev, level])
  }, [])

  const pop = useCallback(() => {
    setModeStack((prev) => (prev.length > 1 ? prev.slice(0, -1) : prev))
  }, [])

  if (currentLevel.kind === "list") {
    return (
      <ListView
        vertical={vertical}
        onSelectWorkflow={(templateId) =>
          push({ kind: "workflow-edit", templateId })
        }
      />
    )
  }

  if (currentLevel.kind === "workflow-edit") {
    return (
      <WorkflowEditView
        templateId={currentLevel.templateId}
        onBack={pop}
        onSelectNode={(nodeId) =>
          push({
            kind: "node-config",
            templateId: currentLevel.templateId,
            nodeId,
          })
        }
      />
    )
  }

  // node-config
  return (
    <NodeConfigView
      templateId={currentLevel.templateId}
      nodeId={currentLevel.nodeId}
      onBack={pop}
    />
  )
}


// ─────────────────────────────────────────────────────────────────
// Level 1 — List view (Phase 2a, preserved + onSelectWorkflow wired)
// ─────────────────────────────────────────────────────────────────


function ListView({
  vertical,
  onSelectWorkflow,
}: {
  vertical: string | null
  onSelectWorkflow: (templateId: string) => void
}) {
  // Per-tab scope state (B-ARC2-5: scope pill is per-tab; does NOT
  // share with theme/class/props tabs).
  const [scope, setScope] = useState<WorkflowScope>("vertical_default")
  const [scopePillOpen, setScopePillOpen] = useState(false)

  // B-ARC2-4: filter toggle. Default off (all workflows in scope).
  const [filterToSurface, setFilterToSurface] = useState(false)

  // Workflow list state
  const [workflows, setWorkflows] = useState<WorkflowTemplateMetadata[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  const pageContext = usePageContext()

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setLoadError(null)
    const params: { scope: WorkflowScope; vertical?: string } = { scope }
    if (scope === "vertical_default" && vertical) {
      params.vertical = vertical
    }
    workflowTemplatesService
      .list(params)
      .then((list) => {
        if (cancelled) return
        setWorkflows(list)
      })
      .catch((err) => {
        if (cancelled) return
        // eslint-disable-next-line no-console
        console.warn("[runtime-editor] workflow list failed", err)
        setLoadError(
          err instanceof Error ? err.message : "Failed to load workflows",
        )
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [scope, vertical])

  const filteredWorkflows = useMemo(() => {
    if (!filterToSurface) return workflows
    return workflows.filter((w) =>
      workflowMatchesPageContext(
        w,
        pageContext.pageContext,
        pageContext.label,
      ),
    )
  }, [workflows, filterToSurface, pageContext])

  const scopeLabel: Record<WorkflowScope, string> = {
    vertical_default: vertical
      ? `Vertical (${vertical})`
      : "Vertical default",
    platform_default: "Platform default",
  }

  return (
    <div
      className="flex flex-col gap-3 px-3 py-3"
      data-testid="runtime-inspector-workflows-tab"
    >
      {/* Scope pill + filter toggle */}
      <div className="flex flex-col gap-2">
        <div className="relative">
          <button
            type="button"
            onClick={() => setScopePillOpen((o) => !o)}
            className="flex w-full items-center justify-between rounded-sm border border-border-base bg-surface-elevated px-2 py-1 text-caption text-content-strong hover:bg-accent-subtle/40"
            data-testid="runtime-inspector-workflows-scope-pill"
            data-scope={scope}
            aria-expanded={scopePillOpen}
          >
            <span>
              <span className="text-content-muted">Scope:</span>{" "}
              {scopeLabel[scope]}
            </span>
            <ChevronDown size={14} />
          </button>
          {scopePillOpen && (
            <div
              className="absolute left-0 right-0 z-10 mt-1 rounded-sm border border-border-base bg-surface-raised shadow-level-2"
              data-testid="runtime-inspector-workflows-scope-menu"
            >
              {(["vertical_default", "platform_default"] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => {
                    setScope(s)
                    setScopePillOpen(false)
                  }}
                  className={`block w-full px-2 py-1.5 text-left text-caption hover:bg-accent-subtle/60 ${
                    scope === s
                      ? "bg-accent-subtle text-content-strong"
                      : "text-content-strong"
                  }`}
                  data-testid={`runtime-inspector-workflows-scope-option-${s}`}
                >
                  {scopeLabel[s]}
                </button>
              ))}
            </div>
          )}
        </div>

        <label
          className="flex items-center gap-2 text-caption text-content-strong"
          data-testid="runtime-inspector-workflows-filter-label"
        >
          <input
            type="checkbox"
            checked={filterToSurface}
            onChange={(e) => setFilterToSurface(e.target.checked)}
            className="rounded-sm border-border-base"
            data-testid="runtime-inspector-workflows-filter-toggle"
          />
          <span>
            Filter to this surface{" "}
            <span className="text-content-muted">
              ({pageContext.label})
            </span>
          </span>
        </label>
      </div>

      {/* List */}
      {isLoading && (
        <div
          className="text-caption text-content-muted"
          data-testid="runtime-inspector-workflows-loading"
        >
          Loading workflows…
        </div>
      )}
      {loadError && !isLoading && (
        <div
          className="rounded-sm bg-status-error-muted px-2 py-1 text-caption text-status-error"
          data-testid="runtime-inspector-workflows-error"
        >
          {loadError}
        </div>
      )}
      {!isLoading && !loadError && filteredWorkflows.length === 0 && (
        <EmptyState
          filterToSurface={filterToSurface}
          surfaceLabel={pageContext.label}
        />
      )}
      {!isLoading && !loadError && filteredWorkflows.length > 0 && (
        <ul
          className="flex flex-col gap-1.5"
          data-testid="runtime-inspector-workflows-list"
        >
          {filteredWorkflows.map((w) => (
            <WorkflowRow
              key={w.id}
              workflow={w}
              scope={scope}
              onSelect={() => onSelectWorkflow(w.id)}
            />
          ))}
        </ul>
      )}
    </div>
  )
}


function WorkflowRow({
  workflow,
  scope,
  onSelect,
}: {
  workflow: WorkflowTemplateMetadata
  scope: WorkflowScope
  onSelect: () => void
}) {
  // Arc-3.x-deep-link-retrofit: bidirectional deep-link carrying
  // return_to + workflow_type + scope so standalone pre-selects
  // matching template and returns to inspector with state preserved.
  const editorUrl = buildEditorUrl(workflow, scope)

  return (
    <li
      data-testid={`runtime-inspector-workflow-row-${workflow.workflow_type}`}
      data-workflow-id={workflow.id}
    >
      <div className="flex items-start justify-between gap-2 rounded-sm border border-border-subtle bg-surface-elevated px-2 py-2 hover:bg-accent-subtle/40">
        <button
          type="button"
          onClick={onSelect}
          className="min-w-0 flex-1 text-left"
          data-testid="runtime-inspector-workflow-row-edit"
          title="Edit in inspector"
        >
          <div
            className="text-body-sm font-medium text-content-strong truncate"
            data-testid="runtime-inspector-workflow-row-name"
          >
            {workflow.display_name || workflow.workflow_type}
          </div>
          <div className="flex items-center gap-1.5 text-caption text-content-muted truncate">
            <code className="font-plex-mono">{workflow.workflow_type}</code>
            {workflow.vertical ? (
              <span>· {workflow.vertical}</span>
            ) : null}
            <span>· v{workflow.version}</span>
            {/* Arc 4d — chip SourceBadge per-workflow scope tier. */}
            <SourceBadge
              source={workflowScopeToSource(workflow.scope)}
              variant="chip"
              data-testid={`runtime-inspector-workflow-row-scope-${workflow.workflow_type}`}
            />
          </div>
          {workflow.description && (
            <div className="mt-1 text-caption text-content-muted line-clamp-2">
              {workflow.description}
            </div>
          )}
        </button>
        <a
          href={editorUrl}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="flex-shrink-0 rounded-sm border border-border-base px-2 py-1 text-caption text-content-strong hover:bg-accent-subtle/40"
          data-testid="runtime-inspector-workflow-row-open"
          title="Open in full editor"
        >
          <ExternalLink size={12} className="inline-block" />
        </a>
      </div>
    </li>
  )
}


function EmptyState({
  filterToSurface,
  surfaceLabel,
}: {
  filterToSurface: boolean
  surfaceLabel: string
}) {
  if (filterToSurface) {
    return (
      <div
        className="rounded-sm border border-dashed border-border-base px-3 py-4 text-caption text-content-muted"
        data-testid="runtime-inspector-workflows-empty-filtered"
      >
        No workflows match{" "}
        <span className="text-content-strong">{surfaceLabel}</span>. Toggle
        the filter off to see all workflows in this scope.
      </div>
    )
  }
  return (
    <div
      className="rounded-sm border border-dashed border-border-base px-3 py-4 text-caption text-content-muted"
      data-testid="runtime-inspector-workflows-empty"
    >
      No workflows in this scope yet.{" "}
      <a
        href={buildEditorUrl()}
        target="_blank"
        rel="noopener noreferrer"
        className="text-accent hover:underline"
        data-testid="runtime-inspector-workflows-empty-create-link"
      >
        Open the workflow editor
      </a>{" "}
      to create one.
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────
// Level 2 — Workflow edit view
// ─────────────────────────────────────────────────────────────────


type SavingState = "idle" | "saving" | "saved" | "error"


/** Internal hook: form-local draft + 1.5s autosave (B-ARC2B-2). */
function useWorkflowDraft(templateId: string) {
  const [template, setTemplate] = useState<WorkflowTemplateFull | null>(null)
  const [draftCanvas, setDraftCanvas] = useState<CanvasState>(EMPTY_CANVAS)
  const [lastSavedCanvas, setLastSavedCanvas] =
    useState<CanvasState>(EMPTY_CANVAS)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [savingState, setSavingState] = useState<SavingState>("idle")
  const autosaveTimerRef = useRef<number | null>(null)
  const pendingSaveRef = useRef<boolean>(false)

  // Load template
  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setLoadError(null)
    workflowTemplatesService
      .get(templateId)
      .then((full) => {
        if (cancelled) return
        setTemplate(full)
        const canvas = ensureCanvasState(full.canvas_state)
        setDraftCanvas(canvas)
        setLastSavedCanvas(canvas)
      })
      .catch((err) => {
        if (cancelled) return
        // eslint-disable-next-line no-console
        console.warn("[runtime-editor] workflow get failed", err)
        setLoadError(
          err instanceof Error ? err.message : "Failed to load workflow",
        )
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [templateId])

  // Client-side validation runs on every mutation
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

  // isDirty derived
  const isDirty = useMemo(() => {
    return JSON.stringify(lastSavedCanvas) !== JSON.stringify(draftCanvas)
  }, [draftCanvas, lastSavedCanvas])

  const performSave = useCallback(async () => {
    if (validationError) {
      // Validation blocks autosave per standalone canon (line 321)
      return
    }
    if (!template) return
    setSavingState("saving")
    pendingSaveRef.current = true
    try {
      const updated = await workflowTemplatesService.update(template.id, {
        canvas_state: draftCanvas,
        notify_forks: true,
      })
      setTemplate(updated)
      setLastSavedCanvas(ensureCanvasState(updated.canvas_state))
      setSavingState("saved")
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[runtime-editor] workflow save failed", err)
      setSavingState("error")
      toast.error("Failed to save workflow", {
        action: {
          label: "Retry",
          onClick: () => {
            void performSave()
          },
        },
      })
    } finally {
      pendingSaveRef.current = false
    }
  }, [draftCanvas, template, validationError])

  // Autosave debounce — 1.5s after last mutation
  useEffect(() => {
    if (!isDirty || validationError !== null) return
    if (autosaveTimerRef.current !== null) {
      window.clearTimeout(autosaveTimerRef.current)
    }
    autosaveTimerRef.current = window.setTimeout(() => {
      void performSave()
    }, AUTOSAVE_DEBOUNCE_MS)
    return () => {
      if (autosaveTimerRef.current !== null) {
        window.clearTimeout(autosaveTimerRef.current)
        autosaveTimerRef.current = null
      }
    }
  }, [draftCanvas, isDirty, performSave, validationError])

  // Flush pending autosave immediately
  const flushPendingSave = useCallback(async () => {
    if (autosaveTimerRef.current !== null) {
      window.clearTimeout(autosaveTimerRef.current)
      autosaveTimerRef.current = null
    }
    if (isDirty && !validationError && template) {
      await performSave()
    }
  }, [isDirty, performSave, template, validationError])

  // Discard draft → revert to last saved
  const discardDraft = useCallback(() => {
    setDraftCanvas(lastSavedCanvas)
    setSavingState("idle")
  }, [lastSavedCanvas])

  return {
    template,
    draftCanvas,
    setDraftCanvas,
    validationError,
    loadError,
    isLoading,
    isDirty,
    savingState,
    flushPendingSave,
    discardDraft,
  }
}


/** Unsaved-changes guard state */
type GuardAction = "save" | "discard" | null


function WorkflowEditView({
  templateId,
  onBack,
  onSelectNode,
}: {
  templateId: string
  onBack: () => void
  onSelectNode: (nodeId: string) => void
}) {
  const draft = useWorkflowDraft(templateId)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [guardOpen, setGuardOpen] = useState(false)
  const [guardAction, setGuardAction] = useState<GuardAction>(null)

  const handleAddNode = useCallback(
    (nodeType: string) => {
      draft.setDraftCanvas((prev) => {
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
      setPaletteOpen(false)
    },
    [draft],
  )

  const handleRemoveNode = useCallback(
    (nodeId: string) => {
      draft.setDraftCanvas((prev) => ({
        version: prev.version,
        trigger: prev.trigger,
        nodes: prev.nodes.filter((n) => n.id !== nodeId),
        edges: prev.edges.filter(
          (e) => e.source !== nodeId && e.target !== nodeId,
        ),
      }))
    },
    [draft],
  )

  const hasPendingWrite =
    draft.savingState === "saving" || draft.isDirty

  const handleBack = useCallback(() => {
    if (hasPendingWrite) {
      setGuardOpen(true)
      return
    }
    onBack()
  }, [hasPendingWrite, onBack])

  const handleGuardSave = useCallback(async () => {
    setGuardAction("save")
    await draft.flushPendingSave()
    setGuardAction(null)
    setGuardOpen(false)
    onBack()
  }, [draft, onBack])

  const handleGuardDiscard = useCallback(() => {
    setGuardAction("discard")
    draft.discardDraft()
    setGuardAction(null)
    setGuardOpen(false)
    onBack()
  }, [draft, onBack])

  if (draft.isLoading) {
    return (
      <div
        className="flex flex-col gap-2 px-3 py-3"
        data-testid="runtime-inspector-workflow-edit-loading"
      >
        <BackHeader label="Workflows" onBack={onBack} />
        <div className="flex items-center gap-2 text-caption text-content-muted">
          <Loader2 size={14} className="animate-spin" /> Loading workflow…
        </div>
      </div>
    )
  }

  if (draft.loadError || !draft.template) {
    return (
      <div
        className="flex flex-col gap-2 px-3 py-3"
        data-testid="runtime-inspector-workflow-edit-error"
      >
        <BackHeader label="Workflows" onBack={onBack} />
        <div className="rounded-sm bg-status-error-muted px-2 py-1 text-caption text-status-error">
          {draft.loadError ?? "Failed to load workflow"}
        </div>
      </div>
    )
  }

  return (
    <div
      className="flex flex-col gap-2 px-3 py-3"
      data-testid="runtime-inspector-workflow-edit"
      data-workflow-id={draft.template.id}
    >
      {/* Back header + breadcrumb */}
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={handleBack}
          className="flex items-center gap-1 text-caption text-content-muted hover:text-content-strong"
          data-testid="runtime-inspector-workflow-edit-back"
          aria-label="Back to workflows list"
        >
          <ArrowLeft size={12} />
          <span>Workflows</span>
        </button>
        <SavingIndicator state={draft.savingState} isDirty={draft.isDirty} />
      </div>
      <h2
        className="text-body-sm font-medium text-content-strong truncate"
        data-testid="runtime-inspector-workflow-edit-title"
        title={draft.template.display_name}
      >
        {draft.template.display_name || draft.template.workflow_type}
      </h2>
      <div className="flex items-center gap-2 text-caption text-content-muted">
        <code className="font-plex-mono">{draft.template.workflow_type}</code>
        {draft.template.vertical && (
          <Badge variant="outline" className="text-micro">
            {draft.template.vertical}
          </Badge>
        )}
      </div>

      {/* Validation banner */}
      {draft.validationError && (
        <div
          className="rounded-sm border border-status-error bg-status-error-muted px-2 py-1 text-caption text-status-error"
          data-testid="runtime-inspector-workflow-validation"
        >
          {draft.validationError}
        </div>
      )}

      {/* Toolbar — Add node */}
      <div className="relative">
        <Button
          size="sm"
          variant="outline"
          onClick={() => setPaletteOpen((o) => !o)}
          data-testid="runtime-inspector-workflow-add-node"
          aria-expanded={paletteOpen}
        >
          <Plus size={12} className="mr-1" />
          Add node
          <ChevronDown size={12} className="ml-1" />
        </Button>
        {paletteOpen && (
          <div
            className="absolute left-0 right-0 z-20 mt-1 max-h-64 overflow-y-auto rounded-sm border border-border-base bg-surface-raised shadow-level-2"
            data-testid="runtime-inspector-workflow-palette"
          >
            {VALID_NODE_TYPES.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => handleAddNode(t)}
                className="block w-full px-2 py-1.5 text-left font-plex-mono text-caption text-content-strong hover:bg-accent-subtle/60"
                data-testid={`runtime-inspector-workflow-palette-${t}`}
              >
                {t}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Node list (read-only edges as labels per parity canon) */}
      <div data-testid="runtime-inspector-workflow-node-list">
        {draft.draftCanvas.nodes.length === 0 ? (
          <p
            className="rounded-sm border border-dashed border-border-base px-2 py-3 text-caption text-content-muted"
            data-testid="runtime-inspector-workflow-empty-nodes"
          >
            No nodes yet. Use “Add node” above to start.
          </p>
        ) : (
          <ol className="flex flex-col gap-1.5">
            {draft.draftCanvas.nodes.map((node, idx) => {
              const outgoingEdges = draft.draftCanvas.edges.filter(
                (e) => e.source === node.id,
              )
              return (
                <li
                  key={node.id}
                  data-testid={`runtime-inspector-workflow-node-${node.id}`}
                  data-node-type={node.type}
                >
                  <div className="flex items-start justify-between gap-1 rounded-sm border border-border-subtle bg-surface-elevated hover:bg-accent-subtle/30">
                    <button
                      type="button"
                      onClick={() => onSelectNode(node.id)}
                      className="min-w-0 flex-1 px-2 py-1.5 text-left"
                      data-testid={`runtime-inspector-workflow-node-${node.id}-select`}
                    >
                      <div className="flex items-center gap-1.5">
                        <span className="text-micro text-content-muted">
                          #{idx + 1}
                        </span>
                        <Badge variant="outline" className="text-micro">
                          {node.type}
                        </Badge>
                        <code className="truncate font-plex-mono text-caption text-content-muted">
                          {node.id}
                        </code>
                      </div>
                      {node.label && (
                        <p className="mt-0.5 truncate text-caption text-content-strong">
                          {node.label}
                        </p>
                      )}
                      {outgoingEdges.length > 0 && (
                        <div className="mt-0.5 flex flex-wrap gap-1">
                          {outgoingEdges.map((e) => {
                            const target = draft.draftCanvas.nodes.find(
                              (n) => n.id === e.target,
                            )
                            return (
                              <span
                                key={e.id}
                                className="text-caption text-content-muted"
                              >
                                →{" "}
                                <code className="font-plex-mono">
                                  {target?.label ?? e.target}
                                </code>
                              </span>
                            )
                          })}
                        </div>
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleRemoveNode(node.id)}
                      data-testid={`runtime-inspector-workflow-node-${node.id}-remove`}
                      aria-label={`Remove node ${node.id}`}
                      className="m-1 rounded-sm border border-border-base bg-surface-raised p-1 text-content-muted hover:bg-status-error-muted hover:text-status-error"
                    >
                      <Trash2 size={10} />
                    </button>
                  </div>
                </li>
              )
            })}
          </ol>
        )}
      </div>

      {/* Unsaved-changes guard */}
      <UnsavedChangesDialog
        open={guardOpen}
        actionPending={guardAction}
        onSave={handleGuardSave}
        onDiscard={handleGuardDiscard}
        onCancel={() => setGuardOpen(false)}
      />
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────
// Level 3 — Node config view
// ─────────────────────────────────────────────────────────────────


function NodeConfigView({
  templateId,
  nodeId,
  onBack,
}: {
  templateId: string
  nodeId: string
  onBack: () => void
}) {
  const draft = useWorkflowDraft(templateId)
  const [guardOpen, setGuardOpen] = useState(false)
  const [guardAction, setGuardAction] = useState<GuardAction>(null)

  const selectedNode = useMemo(
    () => draft.draftCanvas.nodes.find((n) => n.id === nodeId) ?? null,
    [draft.draftCanvas, nodeId],
  )

  const outgoingEdges = useMemo(
    () =>
      draft.draftCanvas.edges.filter((e) => e.source === nodeId),
    [draft.draftCanvas, nodeId],
  )

  const handlePatch = useCallback(
    (patch: Partial<CanvasNode>) => {
      draft.setDraftCanvas((prev) => ({
        version: prev.version,
        trigger: prev.trigger,
        nodes: prev.nodes.map((n) =>
          n.id === nodeId ? { ...n, ...patch } : n,
        ),
        edges: prev.edges,
      }))
    },
    [draft, nodeId],
  )

  const handleAddEdge = useCallback(
    (target: string) => {
      draft.setDraftCanvas((prev) => {
        const id = generateEdgeId(prev, nodeId, target)
        return {
          version: prev.version,
          trigger: prev.trigger,
          nodes: prev.nodes,
          edges: [...prev.edges, { id, source: nodeId, target }],
        }
      })
    },
    [draft, nodeId],
  )

  const handleRemoveEdge = useCallback(
    (edgeId: string) => {
      draft.setDraftCanvas((prev) => ({
        version: prev.version,
        trigger: prev.trigger,
        nodes: prev.nodes,
        edges: prev.edges.filter((e) => e.id !== edgeId),
      }))
    },
    [draft],
  )

  const hasPendingWrite =
    draft.savingState === "saving" || draft.isDirty

  const handleBack = useCallback(() => {
    if (hasPendingWrite) {
      setGuardOpen(true)
      return
    }
    onBack()
  }, [hasPendingWrite, onBack])

  const handleGuardSave = useCallback(async () => {
    setGuardAction("save")
    await draft.flushPendingSave()
    setGuardAction(null)
    setGuardOpen(false)
    onBack()
  }, [draft, onBack])

  const handleGuardDiscard = useCallback(() => {
    setGuardAction("discard")
    draft.discardDraft()
    setGuardAction(null)
    setGuardOpen(false)
    onBack()
  }, [draft, onBack])

  if (draft.isLoading) {
    return (
      <div
        className="flex flex-col gap-2 px-3 py-3"
        data-testid="runtime-inspector-node-config-loading"
      >
        <BackHeader label="Workflow" onBack={onBack} />
        <div className="flex items-center gap-2 text-caption text-content-muted">
          <Loader2 size={14} className="animate-spin" /> Loading workflow…
        </div>
      </div>
    )
  }

  if (draft.loadError || !draft.template || !selectedNode) {
    return (
      <div
        className="flex flex-col gap-2 px-3 py-3"
        data-testid="runtime-inspector-node-config-error"
      >
        <BackHeader label="Workflow" onBack={onBack} />
        <div className="rounded-sm bg-status-error-muted px-2 py-1 text-caption text-status-error">
          {draft.loadError ?? "Node not found"}
        </div>
      </div>
    )
  }

  return (
    <div
      className="flex flex-col gap-2 px-3 py-3"
      data-testid="runtime-inspector-node-config"
      data-node-id={nodeId}
    >
      {/* Back header + breadcrumb */}
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={handleBack}
          className="flex items-center gap-1 text-caption text-content-muted hover:text-content-strong"
          data-testid="runtime-inspector-node-config-back"
          aria-label="Back to workflow"
        >
          <ArrowLeft size={12} />
          <span className="truncate">
            {draft.template.display_name || draft.template.workflow_type}
          </span>
        </button>
        <SavingIndicator state={draft.savingState} isDirty={draft.isDirty} />
      </div>
      <div className="text-caption text-content-muted">
        Node:{" "}
        <code className="font-plex-mono text-content-strong">
          {selectedNode.id}
        </code>
      </div>

      {/* Validation banner */}
      {draft.validationError && (
        <div
          className="rounded-sm border border-status-error bg-status-error-muted px-2 py-1 text-caption text-status-error"
          data-testid="runtime-inspector-node-config-validation"
        >
          {draft.validationError}
        </div>
      )}

      <NodeConfigForm
        node={selectedNode}
        allNodes={draft.draftCanvas.nodes}
        outgoingEdges={outgoingEdges}
        onPatch={handlePatch}
        onAddEdge={handleAddEdge}
        onRemoveEdge={handleRemoveEdge}
      />

      {/* Unsaved-changes guard */}
      <UnsavedChangesDialog
        open={guardOpen}
        actionPending={guardAction}
        onSave={handleGuardSave}
        onDiscard={handleGuardDiscard}
        onCancel={() => setGuardOpen(false)}
      />
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────
// Shared sub-components
// ─────────────────────────────────────────────────────────────────


function BackHeader({
  label,
  onBack,
}: {
  label: string
  onBack: () => void
}) {
  return (
    <button
      type="button"
      onClick={onBack}
      className="flex items-center gap-1 text-caption text-content-muted hover:text-content-strong"
      data-testid="runtime-inspector-back-header"
    >
      <ArrowLeft size={12} />
      <span>{label}</span>
    </button>
  )
}


function SavingIndicator({
  state,
  isDirty,
}: {
  state: SavingState
  isDirty: boolean
}) {
  // Saving-now beats saved beats unsaved beats idle.
  if (state === "saving") {
    return (
      <span
        className="flex items-center gap-1 text-caption text-content-muted"
        data-testid="runtime-inspector-saving-indicator"
        data-state="saving"
      >
        <Loader2 size={10} className="animate-spin" />
        Saving…
      </span>
    )
  }
  if (state === "error") {
    return (
      <span
        className="text-caption text-status-error"
        data-testid="runtime-inspector-saving-indicator"
        data-state="error"
      >
        Save failed
      </span>
    )
  }
  if (isDirty) {
    return (
      <span
        className="text-caption text-content-muted"
        data-testid="runtime-inspector-saving-indicator"
        data-state="unsaved"
      >
        Unsaved
      </span>
    )
  }
  if (state === "saved") {
    return (
      <span
        className="text-caption text-content-muted"
        data-testid="runtime-inspector-saving-indicator"
        data-state="saved"
      >
        Saved
      </span>
    )
  }
  return null
}


function UnsavedChangesDialog({
  open,
  actionPending,
  onSave,
  onDiscard,
  onCancel,
}: {
  open: boolean
  actionPending: GuardAction
  onSave: () => void
  onDiscard: () => void
  onCancel: () => void
}) {
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onCancel()
      }}
    >
      <DialogContent
        showCloseButton={false}
        data-testid="runtime-inspector-unsaved-dialog"
      >
        <DialogHeader>
          <DialogTitle>Unsaved changes</DialogTitle>
          <DialogDescription>
            You have unsaved changes. Save now or discard?
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="ghost"
            onClick={onCancel}
            disabled={actionPending !== null}
            data-testid="runtime-inspector-unsaved-cancel"
          >
            Cancel
          </Button>
          <Button
            variant="outline"
            onClick={onDiscard}
            disabled={actionPending !== null}
            data-testid="runtime-inspector-unsaved-discard"
          >
            Discard
          </Button>
          <Button
            onClick={() => {
              void onSave()
            }}
            disabled={actionPending !== null}
            data-testid="runtime-inspector-unsaved-save"
          >
            {actionPending === "save" ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
