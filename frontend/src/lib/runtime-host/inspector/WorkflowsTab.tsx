/**
 * Arc 2 Phase 2a — Inspector Workflows tab.
 *
 * Read-only workflow list filtered by scope (vertical_default +
 * platform_default). Per-tab scope pill (independent of other tabs
 * per B-ARC2-5). Filter toggle: all-workflows default + "filter to
 * this surface" option (per B-ARC2-4). Deep-link to standalone
 * editor for full editing (per B-ARC2-1 mode-stack pattern Phase 2a).
 *
 * Architectural pattern locked (Arc 2 vs Arc 1 contrast):
 *
 * - Arc 1 dashboard_layout writer: staged-override pattern. Edits
 *   stage into draftOverrides map; commit footer flushes via
 *   makeDashboardLayoutWriter. Field-merged per page_context.
 * - Arc 2 Phase 2a workflows: direct-service-call pattern. NO
 *   writer. Phase 2a is read-only (list + deep-link only); Phase 2b
 *   will call workflowTemplatesService.update directly for atomic-
 *   per-template saves.
 *
 * Discrimination criterion: SAVE SEMANTICS, not surface type.
 * Staged-override writers exist where the same draft-state shape
 * (token / prop / class / layout) needs cross-cutting commit
 * semantics. Workflows are atomic-per-template; they don't fit the
 * staged-override abstraction. Adding a writer would force
 * workflows into the wrong abstraction.
 *
 * Workflow scope locked at vertical_default + platform_default
 * (`workflow_templates` table only). Tenant `workflows` + tenant_
 * workflow_forks deferred post-September.
 *
 * Filter-to-this-surface uses page_context keyword match against
 * workflow display_name + description + workflow_type. Genuine
 * page-context-to-workflow metadata doesn't exist on
 * workflow_templates schema today; client-side keyword match is the
 * Phase 2a heuristic (B-ARC2-4 documented). Phase 2b OR Arc 3 may
 * introduce explicit `extensions.affectingPageContexts` metadata
 * when the relation hardens.
 */
import { useEffect, useMemo, useState } from "react"
import { ExternalLink, ChevronDown } from "lucide-react"

import {
  workflowTemplatesService,
  type WorkflowScope,
  type WorkflowTemplateMetadata,
} from "@/bridgeable-admin/services/workflow-templates-service"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import { usePageContext } from "../use-page-context"


export interface WorkflowsTabProps {
  /** Impersonated tenant's vertical, threaded by RuntimeEditorShell.
   *  Used as default for vertical_default scope. */
  vertical: string | null
}


/** Build the workflow standalone editor URL. Phase 2a uses canonical
 *  `/visual-editor/workflows` (the editor picks workflow_type from
 *  its own left rail). Per pre-flight: WorkflowEditorPage doesn't
 *  accept a `?workflow_type=` query param today; using the canonical
 *  bare URL keeps Phase 2a additive (no standalone-editor changes).
 *  Phase 2b OR a separate hygiene patch can teach the standalone
 *  editor to pre-select via `?workflow_type=<x>&scope=<y>`. */
function buildEditorUrl(_template: WorkflowTemplateMetadata): string {
  return adminPath("/visual-editor/workflows")
}


/** Client-side filter heuristic for "this surface" toggle.
 *
 *  Matches workflow_type / display_name / description against page-
 *  context tokens (the canonical page_context plus its human label).
 *  Tokenized + case-insensitive. Splits both sides on
 *  `[\s_/.-]+` so `funeral_scheduling_focus` matches "funeral",
 *  "scheduling", "focus".
 *
 *  Returns true if ANY token in the page_context tokenization
 *  appears as a substring in any of the workflow's searchable
 *  fields. Heuristic; Phase 2b OR Arc 3 may replace with explicit
 *  `extensions.affectingPageContexts` metadata. */
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

  // Load workflows when scope or vertical changes.
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
            <WorkflowRow key={w.id} workflow={w} />
          ))}
        </ul>
      )}
    </div>
  )
}


function WorkflowRow({ workflow }: { workflow: WorkflowTemplateMetadata }) {
  const editorUrl = buildEditorUrl(workflow)

  return (
    <li
      className="rounded-sm border border-border-subtle bg-surface-elevated px-2 py-2"
      data-testid={`runtime-inspector-workflow-row-${workflow.workflow_type}`}
      data-workflow-id={workflow.id}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div
            className="text-body-sm font-medium text-content-strong truncate"
            data-testid="runtime-inspector-workflow-row-name"
          >
            {workflow.display_name || workflow.workflow_type}
          </div>
          <div className="text-caption text-content-muted truncate">
            <code className="font-plex-mono">{workflow.workflow_type}</code>
            {workflow.vertical ? (
              <span className="ml-2">· {workflow.vertical}</span>
            ) : null}
            <span className="ml-2">· v{workflow.version}</span>
          </div>
          {workflow.description && (
            <div className="mt-1 text-caption text-content-muted line-clamp-2">
              {workflow.description}
            </div>
          )}
        </div>
        <a
          href={editorUrl}
          target="_blank"
          rel="noopener noreferrer"
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
        href={adminPath("/visual-editor/workflows")}
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
