/**
 * Arc 3b — Inspector Documents tab.
 *
 * 3-level mode-stack matching Phase 2b Workflows tab canon
 * (B-ARC2B-1 + B-ARC2B-3): list → template-edit → block-detail.
 * Each level uses full 380px width. Generic stack pattern; not a
 * shared inspector-level abstraction.
 *
 * ── Architectural patterns locked (Arc 3b) ──
 *
 * - **Inspector authoring path follows substrate location**
 *   (Q-DOCS-1). The Documents block substrate is mounted on the
 *   tenant router at `/api/v1/documents-v2/admin/*` with
 *   `require_admin` gating (NOT `get_current_platform_user`).
 *   `documentBlocksService` consumes via `apiClient` (tenant
 *   axios). During impersonation, the impersonation token IS the
 *   tenant admin JWT — auth resolves correctly. This is the first
 *   inspector tab where the canonical adminApi pattern doesn't
 *   apply because the substrate IS tenant-admin-side. Future
 *   substrate-cleanup arc may consolidate to platform router; out
 *   of scope here.
 *
 * - **Per-block immediate writes** (Q-DOCS-2). Each block mutation
 *   (add / update / remove) fires `documentBlocksService.*`
 *   immediately. Server recomposes Jinja per mutation; body_template
 *   + variable_schema update atomically. NO form-local batching, NO
 *   autosave wrapping. Per-block error UX: inline error at the
 *   failing block, preserve operator input, retry affordance. This
 *   is the third save-semantics canon: staged-override writer
 *   (Arc 1) for field-merged substrates; form-local + autosave
 *   (Phase 2b) for whole-instance atomic; per-block immediate
 *   (Arc 3b) for sub-instance atomic.
 *
 * - **3-level mode-stack canon** (B-ARC2B-3). Tab owns its own
 *   `{stack, push, pop}` state. Conditional_wrapper child
 *   management lives WITHIN level 3 block-detail (parent-block
 *   selection in the block list adapts to show children inline);
 *   no additional mode-push level needed for v1. If concrete
 *   operator signal warrants, a 4th level lands as bounded
 *   follow-on per generic-stack canon.
 *
 * - **Parity-not-exceedance canon** (Q-UX-3). Inspector matches
 *   standalone DocumentsEditorPage at 380px. Versions tab +
 *   Configuration tab deep-link to standalone editor; NOT
 *   embedded. Activate / Rollback / Test Render stay in
 *   standalone editor.
 *
 * - **Hybrid filter falls back to all-templates + document_type
 *   chip filter** (Q-DOCS-4 — c-expensive cost branch).
 *   `document_type → page_context` mapping doesn't exist today; per
 *   settled spec, ship fallback (a) all-templates default with
 *   document_type filter. Hybrid surface-context default is tracked
 *   as Arc-3.x sub-arc when the mapping infrastructure ships.
 *
 * - **Per-tab scope discipline** (Phase 2b B-ARC2-5). Documents
 *   templates ship with three scopes per §4 Documents canon
 *   (platform_default → vertical_default → tenant_override).
 *   Inspector exposes scope filter via the documents-v2 `scope`
 *   query param ("platform" | "tenant" | "both"); default "both".
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  AlertCircle,
  ArrowLeft,
  ChevronDown,
  ExternalLink,
  GripVertical,
  Loader2,
  MoveDown,
  MoveUp,
  Plus,
  Trash2,
} from "lucide-react"
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core"
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import { buildEditorDeepLink } from "./deep-link-state"
import { BlockConfigEditor } from "@/bridgeable-admin/components/visual-editor/documents/BlockConfigEditor"
import { BlockKindPicker } from "@/bridgeable-admin/components/visual-editor/documents/BlockKindPicker"
import {
  documentBlocksService,
  type BlockKindMetadata,
  type DocumentTypeCatalog,
  type TemplateBlock,
} from "@/bridgeable-admin/services/document-blocks-service"
import {
  documentsV2Service,
  type DocumentTemplateDetail,
  type DocumentTemplateListItem,
  type DocumentTemplateVersion,
} from "@/services/documents-v2-service"
import {
  SuggestionDropdown,
  handleSuggestionKeyDown,
} from "@/lib/visual-editor/suggestion-dropdown"
// Arc 4d — chip-variant SourceBadge for per-template scope display.
// Documents transitions Class C (no source metadata) → Class B
// (per-instance source metadata) via list endpoint's `scope` field +
// new backend `resolve_with_sources` for hover-reveal cascade.
import {
  SourceBadge,
  type SourceValue,
} from "@/lib/visual-editor/source-badge"


/**
 * Arc 4d — map documents-v2 scope (`"platform"` | `"tenant"`) to
 * canonical SourceValue. Note: documents-v2's `scope` field today
 * collapses vertical_default into "platform" (vertical_default is
 * `company_id=NULL AND vertical=X` per §4 Documents canon). The
 * full 3-tier chain is available via the new backend
 * `resolve_with_sources` for hover-reveal scope diff (substrate
 * ready; consumer hookup is bounded Arc-4.x follow-on if signal
 * warrants — list-endpoint-level scope field is sufficient for
 * per-row badge at Arc 4d).
 */
function documentScopeToSource(
  scope: DocumentTemplateListItem["scope"],
): SourceValue {
  return scope === "tenant" ? "tenant" : "platform"
}


export interface DocumentsTabProps {
  /** Impersonated tenant's vertical — passed for future hybrid filter
   *  evolution. Currently unused (Q-DOCS-4 c-expensive cost branch). */
  vertical: string | null
}


/** Mode-stack levels for the Documents tab (B-ARC2B-3).
 *  Generic stack pattern matches Phase 2b WorkflowsTab verbatim. */
export type ModeStackLevel =
  | { kind: "list" }
  | { kind: "template-edit"; templateId: string }
  | { kind: "block-detail"; templateId: string; blockId: string }


/** Scope filter for the templates list. Per documents-v2 contract. */
type ScopeFilter = "both" | "platform" | "tenant"


/** Build the documents standalone editor URL.
 *
 *  Arc-3.x-deep-link-retrofit (May 2026): bidirectional deep-link
 *  carrying `return_to` per Arc 3a canon. Optional params:
 *  `template_id` (so standalone pre-selects matching template),
 *  `scope`, `document_type`. State preservation mechanism per Arc 3a:
 *  return_to encodes originating URL; runtime editor stays mounted
 *  in originating tab (target="_blank"); state is preserved via
 *  React state, not URL restoration. */
function buildDocumentsEditorUrl(opts?: {
  templateId?: string
  scope?: ScopeFilter
  documentType?: string | null
}): string {
  // Studio 1a-i.A1: prefer the Studio path when inside Studio shell.
  const inStudio =
    typeof window !== "undefined" &&
    window.location.pathname
      .replace(/^\/bridgeable-admin/, "")
      .startsWith("/studio/")
  const base = inStudio
    ? adminPath("/studio/documents")
    : adminPath("/visual-editor/documents")
  return buildEditorDeepLink(base, {
    template_id: opts?.templateId,
    scope: opts?.scope,
    document_type: opts?.documentType ?? undefined,
  })
}


export function DocumentsTab({ vertical: _vertical }: DocumentsTabProps) {
  void _vertical // reserved for future hybrid filter (Q-DOCS-4)
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
        onSelectTemplate={(templateId) =>
          push({ kind: "template-edit", templateId })
        }
      />
    )
  }

  if (currentLevel.kind === "template-edit") {
    return (
      <TemplateEditView
        templateId={currentLevel.templateId}
        onBack={pop}
        onSelectBlock={(blockId) =>
          push({
            kind: "block-detail",
            templateId: currentLevel.templateId,
            blockId,
          })
        }
      />
    )
  }

  // block-detail
  return (
    <BlockDetailView
      templateId={currentLevel.templateId}
      blockId={currentLevel.blockId}
      onBack={pop}
    />
  )
}


// ─────────────────────────────────────────────────────────────────
// Level 1 — Template list view
// ─────────────────────────────────────────────────────────────────


function ListView({
  onSelectTemplate,
}: {
  onSelectTemplate: (templateId: string) => void
}) {
  const [scope, setScope] = useState<ScopeFilter>("both")
  const [scopePillOpen, setScopePillOpen] = useState(false)
  const [documentTypeFilter, setDocumentTypeFilter] = useState<string | null>(
    null,
  )
  const [filterMenuOpen, setFilterMenuOpen] = useState(false)

  const [templates, setTemplates] = useState<DocumentTemplateListItem[]>([])
  const [catalog, setCatalog] = useState<DocumentTypeCatalog | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  // Load catalog once (for document_type filter chips)
  useEffect(() => {
    let cancelled = false
    documentBlocksService
      .listDocumentTypes()
      .then((cat) => {
        if (!cancelled) setCatalog(cat)
      })
      .catch((err) => {
        if (cancelled) return
        // eslint-disable-next-line no-console
        console.warn("[runtime-editor] documents catalog load failed", err)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Load templates whenever scope/filter changes
  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setLoadError(null)
    documentsV2Service
      .listTemplates({
        limit: 500,
        scope,
        document_type: documentTypeFilter ?? undefined,
      })
      .then((res) => {
        if (cancelled) return
        setTemplates(res.items)
      })
      .catch((err) => {
        if (cancelled) return
        // eslint-disable-next-line no-console
        console.warn("[runtime-editor] documents list failed", err)
        setLoadError(
          err instanceof Error ? err.message : "Failed to load templates",
        )
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [scope, documentTypeFilter])

  const scopeLabel: Record<ScopeFilter, string> = {
    both: "All scopes",
    platform: "Platform default",
    tenant: "Tenant override",
  }

  return (
    <div
      className="flex flex-col gap-3 px-3 py-3"
      data-testid="runtime-inspector-documents-tab"
    >
      {/* Scope pill + filter dropdown */}
      <div className="flex flex-col gap-2">
        <div className="relative">
          <button
            type="button"
            onClick={() => setScopePillOpen((o) => !o)}
            className="flex w-full items-center justify-between rounded-sm border border-border-base bg-surface-elevated px-2 py-1 text-caption text-content-strong hover:bg-accent-subtle/40"
            data-testid="runtime-inspector-documents-scope-pill"
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
              data-testid="runtime-inspector-documents-scope-menu"
            >
              {(["both", "platform", "tenant"] as const).map((s) => (
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
                  data-testid={`runtime-inspector-documents-scope-option-${s}`}
                >
                  {scopeLabel[s]}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Document type filter — Q-DOCS-4 (c-expensive) fallback */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setFilterMenuOpen((o) => !o)}
            className="flex w-full items-center justify-between rounded-sm border border-border-base bg-surface-elevated px-2 py-1 text-caption text-content-strong hover:bg-accent-subtle/40"
            data-testid="runtime-inspector-documents-type-filter"
            data-document-type={documentTypeFilter ?? "all"}
            aria-expanded={filterMenuOpen}
          >
            <span>
              <span className="text-content-muted">Type:</span>{" "}
              {documentTypeFilter
                ? (catalog?.types.find((t) => t.type_id === documentTypeFilter)
                    ?.display_name ?? documentTypeFilter)
                : "All types"}
            </span>
            <ChevronDown size={14} />
          </button>
          {filterMenuOpen && (
            <div
              className="absolute left-0 right-0 z-10 mt-1 max-h-64 overflow-y-auto rounded-sm border border-border-base bg-surface-raised shadow-level-2"
              data-testid="runtime-inspector-documents-type-menu"
            >
              <button
                type="button"
                onClick={() => {
                  setDocumentTypeFilter(null)
                  setFilterMenuOpen(false)
                }}
                className={`block w-full px-2 py-1.5 text-left text-caption hover:bg-accent-subtle/60 ${
                  documentTypeFilter === null
                    ? "bg-accent-subtle text-content-strong"
                    : "text-content-strong"
                }`}
                data-testid="runtime-inspector-documents-type-option-all"
              >
                All types
              </button>
              {(catalog?.types ?? []).map((t) => (
                <button
                  key={t.type_id}
                  type="button"
                  onClick={() => {
                    setDocumentTypeFilter(t.type_id)
                    setFilterMenuOpen(false)
                  }}
                  className={`block w-full px-2 py-1.5 text-left text-caption hover:bg-accent-subtle/60 ${
                    documentTypeFilter === t.type_id
                      ? "bg-accent-subtle text-content-strong"
                      : "text-content-strong"
                  }`}
                  data-testid={`runtime-inspector-documents-type-option-${t.type_id}`}
                >
                  {t.display_name}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* List */}
      {isLoading && (
        <div
          className="text-caption text-content-muted"
          data-testid="runtime-inspector-documents-loading"
        >
          Loading templates…
        </div>
      )}
      {loadError && !isLoading && (
        <div
          className="rounded-sm bg-status-error-muted px-2 py-1 text-caption text-status-error"
          data-testid="runtime-inspector-documents-error"
        >
          {loadError}
        </div>
      )}
      {!isLoading && !loadError && templates.length === 0 && (
        <EmptyState
          hasFilter={documentTypeFilter !== null}
          scope={scope}
        />
      )}
      {!isLoading && !loadError && templates.length > 0 && (
        <ul
          className="flex flex-col gap-1.5"
          data-testid="runtime-inspector-documents-list"
        >
          {templates.map((t) => (
            <TemplateRow
              key={t.id}
              template={t}
              scope={scope}
              documentType={documentTypeFilter}
              onSelect={() => onSelectTemplate(t.id)}
            />
          ))}
        </ul>
      )}
    </div>
  )
}


function TemplateRow({
  template,
  scope,
  documentType,
  onSelect,
}: {
  template: DocumentTemplateListItem
  scope: ScopeFilter
  documentType: string | null
  onSelect: () => void
}) {
  // Arc-3.x-deep-link-retrofit: bidirectional deep-link carrying
  // return_to + template_id + scope + document_type so standalone
  // pre-selects matching template and returns to inspector with
  // state preserved.
  const editorUrl = buildDocumentsEditorUrl({
    templateId: template.id,
    scope,
    documentType,
  })
  return (
    <li
      data-testid={`runtime-inspector-document-row-${template.id}`}
      data-template-key={template.template_key}
    >
      <div className="flex items-start justify-between gap-2 rounded-sm border border-border-subtle bg-surface-elevated px-2 py-2 hover:bg-accent-subtle/40">
        <button
          type="button"
          onClick={onSelect}
          className="min-w-0 flex-1 text-left"
          data-testid={`runtime-inspector-document-row-${template.id}-edit`}
          title="Edit in inspector"
        >
          <div
            className="text-body-sm font-medium text-content-strong truncate"
            data-testid={`runtime-inspector-document-row-${template.id}-name`}
          >
            {template.template_key}
          </div>
          <div className="flex items-center gap-1.5 text-caption text-content-muted truncate">
            <code className="font-plex-mono">{template.document_type}</code>
            {/* Arc 4d — chip SourceBadge per-template scope tier. */}
            <SourceBadge
              source={documentScopeToSource(template.scope)}
              variant="chip"
              data-testid={`runtime-inspector-document-row-${template.id}-scope`}
            />
            {template.current_version_number !== null && (
              <span>· v{template.current_version_number}</span>
            )}
            {template.has_draft && (
              <span className="text-status-warning">· draft</span>
            )}
          </div>
          {template.description && (
            <div className="mt-1 text-caption text-content-muted line-clamp-2">
              {template.description}
            </div>
          )}
        </button>
        <a
          href={editorUrl}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="flex-shrink-0 rounded-sm border border-border-base px-2 py-1 text-caption text-content-strong hover:bg-accent-subtle/40"
          data-testid={`runtime-inspector-document-row-${template.id}-open`}
          title="Open in full editor"
        >
          <ExternalLink size={12} className="inline-block" />
        </a>
      </div>
    </li>
  )
}


function EmptyState({
  hasFilter,
  scope,
}: {
  hasFilter: boolean
  scope: ScopeFilter
}) {
  if (hasFilter) {
    return (
      <div
        className="rounded-sm border border-dashed border-border-base px-3 py-4 text-caption text-content-muted"
        data-testid="runtime-inspector-documents-empty-filtered"
      >
        No templates match the selected type in this scope. Clear the
        type filter to see all templates.
      </div>
    )
  }
  return (
    <div
      className="rounded-sm border border-dashed border-border-base px-3 py-4 text-caption text-content-muted"
      data-testid="runtime-inspector-documents-empty"
    >
      No templates in <span className="text-content-strong">{scope}</span>{" "}
      scope yet.{" "}
      <a
        href={buildDocumentsEditorUrl({ scope })}
        target="_blank"
        rel="noopener noreferrer"
        className="text-accent hover:underline"
        data-testid="runtime-inspector-documents-empty-create-link"
      >
        Open the documents editor
      </a>{" "}
      to create one.
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────
// Level 2 — Template edit view (block list)
// ─────────────────────────────────────────────────────────────────


/** Internal hook: loads template + draft/active version + blocks.
 *  Per-block immediate writes (Q-DOCS-2). NO form-local state on
 *  the block list itself; mutations refetch via `reloadBlocks`. */
function useTemplateBlocks(templateId: string) {
  const [templateDetail, setTemplateDetail] =
    useState<DocumentTemplateDetail | null>(null)
  const [activeVersion, setActiveVersion] =
    useState<DocumentTemplateVersion | null>(null)
  const [draftVersion, setDraftVersion] =
    useState<DocumentTemplateVersion | null>(null)
  const [blocks, setBlocks] = useState<TemplateBlock[]>([])
  const [blockKinds, setBlockKinds] = useState<BlockKindMetadata[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  // Per-block error map — keyed on block.id (or "__add__" for add-flow).
  const [blockErrors, setBlockErrors] = useState<Record<string, string>>({})
  // Per-block saving map
  const [blockSaving, setBlockSaving] = useState<Record<string, boolean>>({})
  const cancelledRef = useRef(false)

  useEffect(() => {
    cancelledRef.current = false
    return () => {
      cancelledRef.current = true
    }
  }, [])

  // Load template + version + block kinds
  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setLoadError(null)
    Promise.all([
      documentsV2Service.getTemplate(templateId),
      documentBlocksService.listBlockKinds(),
    ])
      .then(async ([detail, kinds]) => {
        if (cancelled) return
        setTemplateDetail(detail)
        setBlockKinds(kinds)
        const draftSummary = detail.version_summaries.find(
          (v) => v.status === "draft",
        )
        const activeSummary = detail.version_summaries.find(
          (v) => v.status === "active",
        )
        const tasks: Promise<unknown>[] = []
        if (draftSummary) {
          tasks.push(
            documentsV2Service
              .getTemplateVersion(detail.id, draftSummary.id)
              .then((v) => {
                if (!cancelled) setDraftVersion(v)
              }),
          )
        }
        if (activeSummary) {
          tasks.push(
            documentsV2Service
              .getTemplateVersion(detail.id, activeSummary.id)
              .then((v) => {
                if (!cancelled) setActiveVersion(v)
              }),
          )
        }
        await Promise.all(tasks)
      })
      .catch((err) => {
        if (cancelled) return
        // eslint-disable-next-line no-console
        console.warn("[runtime-editor] documents template load failed", err)
        setLoadError(
          err instanceof Error ? err.message : "Failed to load template",
        )
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [templateId])

  const editingVersion = draftVersion ?? activeVersion

  // Load blocks whenever editingVersion settles
  useEffect(() => {
    if (!templateDetail || !editingVersion) {
      setBlocks([])
      return
    }
    let cancelled = false
    documentBlocksService
      .list(templateDetail.id, editingVersion.id)
      .then((rows) => {
        if (!cancelled) setBlocks(rows)
      })
      .catch((err) => {
        if (cancelled) return
        // eslint-disable-next-line no-console
        console.warn("[runtime-editor] documents block list failed", err)
        setLoadError(
          err instanceof Error ? err.message : "Failed to load blocks",
        )
      })
    return () => {
      cancelled = true
    }
  }, [templateDetail, editingVersion])

  const reloadBlocks = useCallback(async () => {
    if (!templateDetail || !editingVersion) return
    const rows = await documentBlocksService.list(
      templateDetail.id,
      editingVersion.id,
    )
    if (!cancelledRef.current) setBlocks(rows)
  }, [templateDetail, editingVersion])

  const clearBlockError = useCallback((key: string) => {
    setBlockErrors((prev) => {
      if (!(key in prev)) return prev
      const next = { ...prev }
      delete next[key]
      return next
    })
  }, [])

  const setBlockError = useCallback((key: string, message: string) => {
    setBlockErrors((prev) => ({ ...prev, [key]: message }))
  }, [])

  /** Per-block immediate write: add block. */
  const addBlock = useCallback(
    async (
      kind: string,
      opts: { parent_block_id?: string | null } = {},
    ): Promise<TemplateBlock | null> => {
      if (!templateDetail || !editingVersion) return null
      clearBlockError("__add__")
      setBlockSaving((prev) => ({ ...prev, __add__: true }))
      try {
        const block = await documentBlocksService.add(
          templateDetail.id,
          editingVersion.id,
          {
            block_kind: kind,
            config: {},
            parent_block_id: opts.parent_block_id ?? null,
          },
        )
        await reloadBlocks()
        return block
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error("[runtime-editor] documents add block failed", err)
        setBlockError(
          "__add__",
          err instanceof Error ? err.message : "Failed to add block",
        )
        return null
      } finally {
        setBlockSaving((prev) => {
          const next = { ...prev }
          delete next.__add__
          return next
        })
      }
    },
    [templateDetail, editingVersion, reloadBlocks, clearBlockError, setBlockError],
  )

  /** Per-block immediate write: update block config. */
  const updateBlockConfig = useCallback(
    async (
      blockId: string,
      config: Record<string, unknown>,
    ): Promise<boolean> => {
      if (!templateDetail || !editingVersion) return false
      clearBlockError(blockId)
      setBlockSaving((prev) => ({ ...prev, [blockId]: true }))
      try {
        await documentBlocksService.update(
          templateDetail.id,
          editingVersion.id,
          blockId,
          { config },
        )
        await reloadBlocks()
        return true
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error(
          "[runtime-editor] documents update block failed",
          err,
        )
        setBlockError(
          blockId,
          err instanceof Error ? err.message : "Failed to update block",
        )
        return false
      } finally {
        setBlockSaving((prev) => {
          const next = { ...prev }
          delete next[blockId]
          return next
        })
      }
    },
    [templateDetail, editingVersion, reloadBlocks, clearBlockError, setBlockError],
  )

  /** Arc 4b.1a — Per-block immediate write: update conditional_wrapper
   *  row-column `condition`. Separate from updateBlockConfig because
   *  `condition` lives on the row, not in config JSONB. Per-block
   *  immediate-write semantics preserved (Q-DOCS-2 canon). */
  const updateBlockCondition = useCallback(
    async (
      blockId: string,
      condition: string | null,
    ): Promise<boolean> => {
      if (!templateDetail || !editingVersion) return false
      clearBlockError(blockId)
      setBlockSaving((prev) => ({ ...prev, [blockId]: true }))
      try {
        await documentBlocksService.update(
          templateDetail.id,
          editingVersion.id,
          blockId,
          { condition },
        )
        await reloadBlocks()
        return true
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error(
          "[runtime-editor] documents update block condition failed",
          err,
        )
        setBlockError(
          blockId,
          err instanceof Error ? err.message : "Failed to update condition",
        )
        return false
      } finally {
        setBlockSaving((prev) => {
          const next = { ...prev }
          delete next[blockId]
          return next
        })
      }
    },
    [templateDetail, editingVersion, reloadBlocks, clearBlockError, setBlockError],
  )

  /** Arc 4b.1b — Per-block-immediate-write: reorder top-level OR
   *  child blocks via documentBlocksService.reorder. Optimistic
   *  update + rollback on failure per Arc 4b.1b drag-drop spec.
   *  Operates on the parent_block_id scope: pass null for top-level,
   *  or a parent_block_id for that parent's children. The full
   *  ordered id list at that scope is what the server replays.
   *  Per Q-DOCS-2 per-block-immediate canon: fires the API
   *  immediately; no batching.
   */
  const reorderBlocks = useCallback(
    async (
      orderedIds: string[],
      parentBlockId: string | null,
    ): Promise<boolean> => {
      if (!templateDetail || !editingVersion) return false
      // Snapshot current blocks for rollback on failure
      const snapshot = blocks
      // Optimistic update — reproject `position` per orderedIds
      // within the parent scope, leaving other blocks untouched.
      const idToPosition = new Map<string, number>()
      orderedIds.forEach((id, idx) => {
        idToPosition.set(id, idx)
      })
      const optimistic = blocks.map((b) => {
        const matchesScope =
          (parentBlockId === null && b.parent_block_id === null) ||
          (parentBlockId !== null && b.parent_block_id === parentBlockId)
        if (matchesScope && idToPosition.has(b.id)) {
          return { ...b, position: idToPosition.get(b.id)! }
        }
        return b
      })
      if (!cancelledRef.current) setBlocks(optimistic)
      clearBlockError("__reorder__")
      try {
        const rows = await documentBlocksService.reorder(
          templateDetail.id,
          editingVersion.id,
          { block_id_order: orderedIds, parent_block_id: parentBlockId },
        )
        if (!cancelledRef.current) setBlocks(rows)
        return true
      } catch (err) {
        // Rollback to pre-mutation snapshot
        if (!cancelledRef.current) setBlocks(snapshot)
        // eslint-disable-next-line no-console
        console.error(
          "[runtime-editor] documents reorder blocks failed",
          err,
        )
        setBlockError(
          "__reorder__",
          err instanceof Error ? err.message : "Failed to reorder blocks",
        )
        return false
      }
    },
    [templateDetail, editingVersion, blocks, clearBlockError, setBlockError],
  )

  /** Per-block immediate write: delete block. */
  const deleteBlock = useCallback(
    async (blockId: string): Promise<boolean> => {
      if (!templateDetail || !editingVersion) return false
      clearBlockError(blockId)
      setBlockSaving((prev) => ({ ...prev, [blockId]: true }))
      try {
        await documentBlocksService.remove(
          templateDetail.id,
          editingVersion.id,
          blockId,
        )
        await reloadBlocks()
        return true
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error(
          "[runtime-editor] documents delete block failed",
          err,
        )
        setBlockError(
          blockId,
          err instanceof Error ? err.message : "Failed to delete block",
        )
        return false
      } finally {
        setBlockSaving((prev) => {
          const next = { ...prev }
          delete next[blockId]
          return next
        })
      }
    },
    [templateDetail, editingVersion, reloadBlocks, clearBlockError, setBlockError],
  )

  return {
    templateDetail,
    activeVersion,
    draftVersion,
    editingVersion,
    blocks,
    blockKinds,
    isLoading,
    loadError,
    blockErrors,
    blockSaving,
    addBlock,
    updateBlockConfig,
    updateBlockCondition,
    deleteBlock,
    reorderBlocks,
    clearBlockError,
  }
}


function TemplateEditView({
  templateId,
  onBack,
  onSelectBlock,
}: {
  templateId: string
  onBack: () => void
  onSelectBlock: (blockId: string) => void
}) {
  const draft = useTemplateBlocks(templateId)
  const [showPicker, setShowPicker] = useState(false)

  // Arc 4b.1b — Slash command summoning state. The `/` keystroke in
  // the slash-input opens SuggestionDropdown with block_registry
  // kinds; Enter inserts a new block; Escape cancels. Documents-only
  // (Q-COMMITMENT-4 settled scope).
  const [slashOpen, setSlashOpen] = useState(false)
  const [slashQuery, setSlashQuery] = useState("")
  const [slashActiveId, setSlashActiveId] = useState<string | null>(null)
  const [slashPosition, setSlashPosition] = useState<{
    top: number
    left: number
  }>({ top: 0, left: 0 })
  const slashInputRef = useRef<HTMLInputElement | null>(null)
  // Arc 4b.1b — Track focused block id so Alt+Arrow keyboard
  // shortcuts target the right block. Updated on block hover/focus.
  const focusedBlockIdRef = useRef<string | null>(null)

  const canEdit = !!draft.draftVersion

  if (draft.isLoading) {
    return (
      <div
        className="flex flex-col gap-2 px-3 py-3"
        data-testid="runtime-inspector-documents-template-edit-loading"
      >
        <BackHeader label="Documents" onBack={onBack} />
        <div className="flex items-center gap-2 text-caption text-content-muted">
          <Loader2 size={14} className="animate-spin" /> Loading template…
        </div>
      </div>
    )
  }

  if (draft.loadError || !draft.templateDetail) {
    return (
      <div
        className="flex flex-col gap-2 px-3 py-3"
        data-testid="runtime-inspector-documents-template-edit-error"
      >
        <BackHeader label="Documents" onBack={onBack} />
        <div className="rounded-sm bg-status-error-muted px-2 py-1 text-caption text-status-error">
          {draft.loadError ?? "Template not found"}
        </div>
      </div>
    )
  }

  const topLevel = draft.blocks.filter((b) => !b.parent_block_id)
  // Arc-3.x-deep-link-retrofit: Level 2 deep-link carries template_id
  // so standalone pre-selects the active template; return_to preserves
  // inspector state (still at Level 2 in the originating tab) on return.
  const editorUrl = buildDocumentsEditorUrl({
    templateId: draft.templateDetail.id,
  })

  return (
    <div
      className="flex flex-col gap-2 px-3 py-3"
      data-testid="runtime-inspector-documents-template-edit"
      data-template-id={draft.templateDetail.id}
    >
      {/* Back + breadcrumb */}
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1 text-caption text-content-muted hover:text-content-strong"
          data-testid="runtime-inspector-documents-template-edit-back"
          aria-label="Back to documents list"
        >
          <ArrowLeft size={12} />
          <span>Documents</span>
        </button>
        <a
          href={editorUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 rounded-sm border border-border-base px-2 py-1 text-caption text-content-strong hover:bg-accent-subtle/40"
          data-testid="runtime-inspector-documents-open-full-editor"
          title="Open in full editor (versions, configuration)"
        >
          <ExternalLink size={10} /> Full editor
        </a>
      </div>
      <h2
        className="text-body-sm font-medium text-content-strong truncate"
        data-testid="runtime-inspector-documents-template-edit-title"
        title={draft.templateDetail.template_key}
      >
        {draft.templateDetail.template_key}
      </h2>
      <div className="flex items-center gap-2 text-caption text-content-muted">
        <code className="font-plex-mono">
          {draft.templateDetail.document_type}
        </code>
        <Badge variant="outline" className="text-micro">
          {draft.templateDetail.scope}
        </Badge>
        {draft.editingVersion && (
          <Badge variant="outline" className="text-micro">
            v{draft.editingVersion.version_number} {draft.editingVersion.status}
          </Badge>
        )}
      </div>

      {!canEdit && (
        <div
          className="rounded-sm bg-status-warning-muted/40 px-2 py-1 text-caption text-status-warning"
          data-testid="runtime-inspector-documents-no-draft-banner"
        >
          No active draft — create one in the full editor to edit blocks.
        </div>
      )}

      {/* Arc 4b.1b — Add block: slash command input + fallback picker.
       *  Slash command is the canonical insertion UX (Notion-shape);
       *  the legacy modal picker remains as fallback for users who
       *  prefer browse-first. */}
      <div className="flex items-center justify-between">
        <span className="text-micro uppercase tracking-wider text-content-muted">
          Blocks ({topLevel.length})
        </span>
        <Button
          size="sm"
          variant="outline"
          onClick={() => setShowPicker(true)}
          disabled={!canEdit}
          data-testid="runtime-inspector-documents-add-block"
        >
          <Plus size={11} className="mr-1" /> Add
        </Button>
      </div>

      {/* Slash-command input — Arc 4b.1b. Type `/` to summon
       *  SuggestionDropdown listing block_registry kinds. Enter
       *  inserts a new block; Escape cancels. */}
      {canEdit && (
        <SlashCommandInput
          inputRef={slashInputRef}
          slashOpen={slashOpen}
          slashQuery={slashQuery}
          slashActiveId={slashActiveId}
          slashPosition={slashPosition}
          blockKinds={draft.blockKinds}
          onOpenChange={setSlashOpen}
          onQueryChange={setSlashQuery}
          onActiveChange={setSlashActiveId}
          onPositionChange={setSlashPosition}
          onInsert={(kind) => {
            setSlashOpen(false)
            setSlashQuery("")
            setSlashActiveId(null)
            if (slashInputRef.current) slashInputRef.current.value = ""
            void draft.addBlock(kind)
          }}
        />
      )}

      {/* Add-block error surface */}
      {draft.blockErrors.__add__ && (
        <div
          className="flex items-start gap-1 rounded-sm bg-status-error-muted px-2 py-1 text-caption text-status-error"
          data-testid="runtime-inspector-documents-add-error"
        >
          <AlertCircle size={12} className="mt-0.5 flex-shrink-0" />
          <span className="flex-1">{draft.blockErrors.__add__}</span>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => draft.clearBlockError("__add__")}
            className="ml-1 h-5 px-1 text-caption"
            data-testid="runtime-inspector-documents-add-error-dismiss"
          >
            Dismiss
          </Button>
        </div>
      )}

      {/* Reorder error surface — Arc 4b.1b. Optimistic-update rollback
       *  on reorder failure restores prior block order; this surface
       *  notifies the operator the server rejected the new order. */}
      {draft.blockErrors.__reorder__ && (
        <div
          className="flex items-start gap-1 rounded-sm bg-status-error-muted px-2 py-1 text-caption text-status-error"
          data-testid="runtime-inspector-documents-reorder-error"
        >
          <AlertCircle size={12} className="mt-0.5 flex-shrink-0" />
          <span className="flex-1">{draft.blockErrors.__reorder__}</span>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => draft.clearBlockError("__reorder__")}
            className="ml-1 h-5 px-1 text-caption"
            data-testid="runtime-inspector-documents-reorder-error-dismiss"
          >
            Dismiss
          </Button>
        </div>
      )}

      {/* Block list — Arc 4b.1b drag-drop reorderable. @dnd-kit/sortable
       *  consumer matching WidgetGrid precedent. Grip handle for drag
       *  (hover-revealed); Move-up/Move-down buttons (also hover-
       *  revealed); Alt+ArrowUp/Down keyboard shortcuts (Alt is
       *  canonical per Command Bar digit shortcut precedent). */}
      <SortableBlockList
        blocks={topLevel}
        allBlocks={draft.blocks}
        canEdit={canEdit}
        blockSaving={draft.blockSaving}
        blockErrors={draft.blockErrors}
        clearBlockError={draft.clearBlockError}
        onSelectBlock={onSelectBlock}
        onDelete={(blockId) => void draft.deleteBlock(blockId)}
        onReorder={(orderedIds) =>
          void draft.reorderBlocks(orderedIds, null)
        }
        onFocusBlock={(id) => {
          focusedBlockIdRef.current = id
        }}
        focusedBlockIdRef={focusedBlockIdRef}
      />

      {showPicker && (
        <BlockKindPicker
          blockKinds={draft.blockKinds}
          onPick={(kind) => {
            setShowPicker(false)
            void draft.addBlock(kind)
          }}
          onCancel={() => setShowPicker(false)}
        />
      )}
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────
// Arc 4b.1b — Slash command input
// ─────────────────────────────────────────────────────────────────


/** Slash-command input. Operator types into a single-line input;
 *  hitting `/` summons SuggestionDropdown over the block kinds.
 *  Per-kind preview = kind display_name + description from the
 *  block_registry metadata (canonical source). Enter inserts;
 *  Escape cancels + clears `/` from input. Documents-only per
 *  Q-COMMITMENT-4 settled scope. */
function SlashCommandInput({
  inputRef,
  slashOpen,
  slashQuery,
  slashActiveId,
  slashPosition,
  blockKinds,
  onOpenChange,
  onQueryChange,
  onActiveChange,
  onPositionChange,
  onInsert,
}: {
  inputRef: React.MutableRefObject<HTMLInputElement | null>
  slashOpen: boolean
  slashQuery: string
  slashActiveId: string | null
  slashPosition: { top: number; left: number }
  blockKinds: BlockKindMetadata[]
  onOpenChange: (open: boolean) => void
  onQueryChange: (q: string) => void
  onActiveChange: (id: string | null) => void
  onPositionChange: (pos: { top: number; left: number }) => void
  onInsert: (kind: string) => void
}) {
  // Filter block kinds by query (after the `/`).
  const filteredKinds = useMemo(() => {
    const q = slashQuery.trim().toLowerCase()
    if (q.length === 0) return blockKinds
    return blockKinds.filter(
      (k) =>
        k.kind.toLowerCase().includes(q) ||
        k.display_name.toLowerCase().includes(q),
    )
  }, [slashQuery, blockKinds])

  // Initialize active id to first match when filter changes.
  useEffect(() => {
    if (!slashOpen) return
    if (filteredKinds.length === 0) {
      onActiveChange(null)
      return
    }
    const stillValid = filteredKinds.some((k) => k.kind === slashActiveId)
    if (!stillValid) onActiveChange(filteredKinds[0].kind)
  }, [filteredKinds, slashActiveId, slashOpen, onActiveChange])

  function cancel() {
    onOpenChange(false)
    onQueryChange("")
    onActiveChange(null)
    if (inputRef.current) inputRef.current.value = ""
  }

  function commitSelection(kind: string) {
    onInsert(kind)
  }

  return (
    <div
      className="relative flex flex-col gap-1"
      data-testid="runtime-inspector-documents-slash-input-wrapper"
    >
      <label
        htmlFor="runtime-inspector-documents-slash-input"
        className="text-micro uppercase tracking-wider text-content-muted"
      >
        Quick insert
      </label>
      <input
        ref={inputRef}
        id="runtime-inspector-documents-slash-input"
        type="text"
        placeholder='Type "/" to insert a block…'
        data-testid="runtime-inspector-documents-slash-input"
        data-slash-open={slashOpen ? "true" : "false"}
        className="w-full rounded-sm border border-border-base bg-surface-elevated px-2 py-1.5 text-caption text-content-strong placeholder:text-content-muted focus-ring-accent"
        onChange={(e) => {
          const value = e.target.value
          if (value.startsWith("/")) {
            if (!slashOpen) {
              // Position dropdown below the input
              const rect = e.currentTarget.getBoundingClientRect()
              onPositionChange({
                top: rect.bottom + 4,
                left: rect.left,
              })
              onOpenChange(true)
            }
            onQueryChange(value.slice(1))
          } else if (value === "") {
            // Cleared input — close
            if (slashOpen) cancel()
          } else if (slashOpen) {
            // User typed non-`/` text; drop the dropdown and treat
            // input as free text (no insertion).
            cancel()
          }
        }}
        onKeyDown={(e) => {
          if (!slashOpen) return
          const handled = handleSuggestionKeyDown(e, {
            suggestions: filteredKinds,
            activeId: slashActiveId,
            onActiveChange,
            onSelect: (k) => commitSelection(k.kind),
            onCancel: cancel,
            getKey: (k) => k.kind,
          })
          if (handled) {
            // event already prevented inside handler
          }
        }}
      />
      {slashOpen && (
        <SuggestionDropdown<BlockKindMetadata>
          suggestions={filteredKinds}
          activeId={slashActiveId}
          onActiveChange={onActiveChange}
          onSelect={(k) => commitSelection(k.kind)}
          onCancel={cancel}
          getKey={(k) => k.kind}
          position={slashPosition}
          width={340}
          renderSuggestion={(k, active) => (
            <div data-testid={`runtime-inspector-documents-slash-row-${k.kind}`}>
              <div className="flex items-center gap-1.5">
                <span
                  className={`text-body-sm font-medium ${
                    active ? "text-content-strong" : "text-content-base"
                  }`}
                >
                  {k.display_name}
                </span>
                <code className="font-plex-mono text-micro text-content-muted">
                  {k.kind}
                </code>
                {k.accepts_children && (
                  <Badge variant="outline" className="text-micro">
                    wraps
                  </Badge>
                )}
              </div>
              <div className="mt-0.5 text-caption text-content-muted line-clamp-2">
                {k.description}
              </div>
            </div>
          )}
          renderEmpty={() => (
            <span data-testid="runtime-inspector-documents-slash-empty">
              No block kind matches{slashQuery ? ` “${slashQuery}”` : ""}.
            </span>
          )}
          data-testid="runtime-inspector-documents-slash-dropdown"
        />
      )}
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────
// Arc 4b.1b — Sortable block list (drag-drop reorder)
// ─────────────────────────────────────────────────────────────────


/** Sortable wrapper for the top-level block list. Mirrors WidgetGrid's
 *  @dnd-kit/sortable consumer shape:
 *    - PointerSensor with 8px activation distance (prevents
 *      accidental drag on intended clicks).
 *    - KeyboardSensor for native focus-based reorder (Tab into a
 *      sortable, Space to lift, ArrowDown to move).
 *    - closestCenter collision detection.
 *    - verticalListSortingStrategy (vs WidgetGrid's rectSorting —
 *      blocks are stacked top-to-bottom, not a 2D grid). */
function SortableBlockList({
  blocks,
  allBlocks,
  canEdit,
  blockSaving,
  blockErrors,
  clearBlockError,
  onSelectBlock,
  onDelete,
  onReorder,
  onFocusBlock,
  focusedBlockIdRef,
}: {
  blocks: TemplateBlock[]
  allBlocks: TemplateBlock[]
  canEdit: boolean
  blockSaving: Record<string, boolean>
  blockErrors: Record<string, string>
  clearBlockError: (key: string) => void
  onSelectBlock: (blockId: string) => void
  onDelete: (blockId: string) => void
  onReorder: (orderedIds: string[]) => void
  onFocusBlock: (id: string | null) => void
  focusedBlockIdRef: React.MutableRefObject<string | null>
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  )

  // Alt+ArrowUp / Alt+ArrowDown keyboard shortcuts target the
  // focused block. Alt is canonical platform-wide for inspector
  // shortcuts per Command Bar digit precedent
  // (lib/cmd-digit-shortcuts.ts). Cmd/Ctrl are reserved for global
  // shortcuts; Shift is reserved for selection/Sortable Space-lift.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (!canEdit) return
      // Require Alt without Cmd/Ctrl/Shift to avoid colliding with
      // browser shortcuts (e.g. Alt+Shift+Arrow on macOS).
      if (!e.altKey || e.metaKey || e.ctrlKey || e.shiftKey) return
      if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return
      const focusedId = focusedBlockIdRef.current
      if (focusedId === null) return
      const idx = blocks.findIndex((b) => b.id === focusedId)
      if (idx < 0) return
      // Only ignore if a non-slash input is focused; the slash
      // input doesn't render blocks above, so Alt+Arrow over a
      // block list element is unambiguous.
      const target = e.target
      if (target instanceof HTMLElement) {
        const tag = target.tagName.toLowerCase()
        const isEditable =
          tag === "input" ||
          tag === "textarea" ||
          target.isContentEditable
        if (isEditable) return
      }
      if (e.key === "ArrowUp" && idx > 0) {
        e.preventDefault()
        const next = arrayMove(blocks, idx, idx - 1).map((b) => b.id)
        onReorder(next)
      } else if (e.key === "ArrowDown" && idx < blocks.length - 1) {
        e.preventDefault()
        const next = arrayMove(blocks, idx, idx + 1).map((b) => b.id)
        onReorder(next)
      }
    }
    document.addEventListener("keydown", onKeyDown)
    return () => {
      document.removeEventListener("keydown", onKeyDown)
    }
  }, [blocks, canEdit, focusedBlockIdRef, onReorder])

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = blocks.findIndex((b) => b.id === active.id)
    const newIndex = blocks.findIndex((b) => b.id === over.id)
    if (oldIndex < 0 || newIndex < 0) return
    const next = arrayMove(blocks, oldIndex, newIndex).map((b) => b.id)
    onReorder(next)
  }

  if (blocks.length === 0) {
    return (
      <div data-testid="runtime-inspector-documents-block-list">
        <p
          className="rounded-sm border border-dashed border-border-base px-2 py-3 text-caption text-content-muted"
          data-testid="runtime-inspector-documents-empty-blocks"
        >
          No blocks yet. Type "/" above to insert one.
        </p>
      </div>
    )
  }

  return (
    <div data-testid="runtime-inspector-documents-block-list">
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={blocks.map((b) => b.id)}
          strategy={verticalListSortingStrategy}
        >
          <ol className="flex flex-col gap-1.5">
            {blocks.map((block, idx) => {
              const children = allBlocks
                .filter((b) => b.parent_block_id === block.id)
                .sort((a, b) => a.position - b.position)
              const canMoveUp = idx > 0
              const canMoveDown = idx < blocks.length - 1
              return (
                <SortableBlockRow
                  key={block.id}
                  block={block}
                  idx={idx}
                  children_={children}
                  canEdit={canEdit}
                  canMoveUp={canMoveUp}
                  canMoveDown={canMoveDown}
                  isSaving={!!blockSaving[block.id]}
                  errorMessage={blockErrors[block.id] ?? null}
                  onSelect={() => onSelectBlock(block.id)}
                  onDelete={() => onDelete(block.id)}
                  onMoveUp={() => {
                    const next = arrayMove(blocks, idx, idx - 1).map((b) => b.id)
                    onReorder(next)
                  }}
                  onMoveDown={() => {
                    const next = arrayMove(blocks, idx, idx + 1).map((b) => b.id)
                    onReorder(next)
                  }}
                  onClearError={() => clearBlockError(block.id)}
                  onFocus={() => onFocusBlock(block.id)}
                />
              )
            })}
          </ol>
        </SortableContext>
      </DndContext>
    </div>
  )
}


/** Sortable row for a top-level block. `useSortable` provides
 *  transform + listeners; we apply them via inline CSS Transform
 *  on the row wrapper. Grip handle gets the drag listeners; the
 *  rest of the row is non-draggable so clicks navigate to block
 *  detail. Edit-vs-drag boundary discipline. */
function SortableBlockRow({
  block,
  idx,
  children_,
  canEdit,
  canMoveUp,
  canMoveDown,
  isSaving,
  errorMessage,
  onSelect,
  onDelete,
  onMoveUp,
  onMoveDown,
  onClearError,
  onFocus,
}: {
  block: TemplateBlock
  idx: number
  children_: TemplateBlock[]
  canEdit: boolean
  canMoveUp: boolean
  canMoveDown: boolean
  isSaving: boolean
  errorMessage: string | null
  onSelect: () => void
  onDelete: () => void
  onMoveUp: () => void
  onMoveDown: () => void
  onClearError: () => void
  onFocus: () => void
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: block.id, disabled: !canEdit })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <li
      ref={setNodeRef}
      style={style}
      data-testid={`runtime-inspector-documents-block-${block.id}`}
      data-block-kind={block.block_kind}
      data-dragging={isDragging ? "true" : "false"}
      onMouseEnter={onFocus}
      onFocus={onFocus}
      className="group"
    >
      <div className="flex items-start gap-1 rounded-sm border border-border-subtle bg-surface-elevated hover:bg-accent-subtle/30">
        {/* Grip handle — drag affordance (hover-revealed via group-hover) */}
        <button
          type="button"
          {...attributes}
          {...listeners}
          disabled={!canEdit}
          aria-label={`Drag block ${block.id}`}
          data-testid={`runtime-inspector-documents-block-${block.id}-grip`}
          className="m-1 flex-shrink-0 cursor-grab self-stretch rounded-sm px-0.5 text-content-muted opacity-0 transition-opacity group-hover:opacity-100 hover:text-content-strong disabled:cursor-not-allowed disabled:opacity-0 active:cursor-grabbing"
          title="Drag to reorder"
        >
          <GripVertical size={12} />
        </button>

        {/* Block summary — click-to-edit */}
        <button
          type="button"
          onClick={onSelect}
          className="min-w-0 flex-1 px-1 py-1.5 text-left"
          data-testid={`runtime-inspector-documents-block-${block.id}-select`}
        >
          <div className="flex items-center gap-1.5">
            <span className="text-micro text-content-muted">#{idx + 1}</span>
            <Badge variant="outline" className="text-micro">
              {block.block_kind}
            </Badge>
            <span className="text-caption text-content-muted">
              pos {block.position}
            </span>
            {children_.length > 0 && (
              <span className="text-caption text-content-muted">
                · {children_.length} child{children_.length === 1 ? "" : "ren"}
              </span>
            )}
          </div>
          {children_.length > 0 && (
            <div className="mt-0.5 flex flex-wrap gap-1">
              {children_.map((c) => (
                <code
                  key={c.id}
                  className="text-caption text-content-muted font-plex-mono"
                >
                  ↳ {c.block_kind}
                </code>
              ))}
            </div>
          )}
        </button>

        {/* Move-up / Move-down — hover-revealed reorder affordances.
         *  Alt+ArrowUp/Down keyboard shortcuts target the focused
         *  block (see SortableBlockList useEffect). */}
        <div className="flex flex-shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
          <button
            type="button"
            onClick={onMoveUp}
            disabled={!canEdit || !canMoveUp || isSaving}
            data-testid={`runtime-inspector-documents-block-${block.id}-move-up`}
            aria-label={`Move block ${block.id} up`}
            title="Move up (Alt+↑)"
            className="m-1 rounded-sm border border-border-base bg-surface-raised p-1 text-content-muted hover:bg-accent-subtle/60 hover:text-content-strong disabled:opacity-50"
          >
            <MoveUp size={10} />
          </button>
          <button
            type="button"
            onClick={onMoveDown}
            disabled={!canEdit || !canMoveDown || isSaving}
            data-testid={`runtime-inspector-documents-block-${block.id}-move-down`}
            aria-label={`Move block ${block.id} down`}
            title="Move down (Alt+↓)"
            className="m-1 rounded-sm border border-border-base bg-surface-raised p-1 text-content-muted hover:bg-accent-subtle/60 hover:text-content-strong disabled:opacity-50"
          >
            <MoveDown size={10} />
          </button>
        </div>

        <button
          type="button"
          onClick={onDelete}
          disabled={!canEdit || isSaving}
          data-testid={`runtime-inspector-documents-block-${block.id}-remove`}
          aria-label={`Remove block ${block.id}`}
          className="m-1 rounded-sm border border-border-base bg-surface-raised p-1 text-content-muted hover:bg-status-error-muted hover:text-status-error disabled:opacity-50"
        >
          <Trash2 size={10} />
        </button>
      </div>
      {errorMessage && (
        <div
          className="mt-1 flex items-start gap-1 rounded-sm bg-status-error-muted px-2 py-1 text-caption text-status-error"
          data-testid={`runtime-inspector-documents-block-${block.id}-error`}
        >
          <AlertCircle size={11} className="mt-0.5 flex-shrink-0" />
          <span className="flex-1">{errorMessage}</span>
          <Button
            size="sm"
            variant="ghost"
            onClick={onClearError}
            className="ml-1 h-5 px-1 text-caption"
          >
            Dismiss
          </Button>
        </div>
      )}
    </li>
  )
}


// ─────────────────────────────────────────────────────────────────
// Level 3 — Block detail view
// ─────────────────────────────────────────────────────────────────


function BlockDetailView({
  templateId,
  blockId,
  onBack,
}: {
  templateId: string
  blockId: string
  onBack: () => void
}) {
  const draft = useTemplateBlocks(templateId)
  const [showChildPicker, setShowChildPicker] = useState(false)

  const block = useMemo(
    () => draft.blocks.find((b) => b.id === blockId) ?? null,
    [draft.blocks, blockId],
  )

  const childBlocks = useMemo(
    () =>
      draft.blocks
        .filter((b) => b.parent_block_id === blockId)
        .sort((a, b) => a.position - b.position),
    [draft.blocks, blockId],
  )

  const blockKindMeta = useMemo(
    () => (block ? draft.blockKinds.find((k) => k.kind === block.block_kind) : null),
    [block, draft.blockKinds],
  )

  const acceptsChildren = blockKindMeta?.accepts_children ?? false
  const canEdit = !!draft.draftVersion

  if (draft.isLoading) {
    return (
      <div
        className="flex flex-col gap-2 px-3 py-3"
        data-testid="runtime-inspector-documents-block-detail-loading"
      >
        <BackHeader label="Template" onBack={onBack} />
        <div className="flex items-center gap-2 text-caption text-content-muted">
          <Loader2 size={14} className="animate-spin" /> Loading template…
        </div>
      </div>
    )
  }

  if (draft.loadError || !draft.templateDetail || !block) {
    return (
      <div
        className="flex flex-col gap-2 px-3 py-3"
        data-testid="runtime-inspector-documents-block-detail-error"
      >
        <BackHeader label="Template" onBack={onBack} />
        <div className="rounded-sm bg-status-error-muted px-2 py-1 text-caption text-status-error">
          {draft.loadError ?? "Block not found"}
        </div>
      </div>
    )
  }

  return (
    <div
      className="flex flex-col gap-2 px-3 py-3"
      data-testid="runtime-inspector-documents-block-detail"
      data-block-id={blockId}
    >
      {/* Back + breadcrumb */}
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1 text-caption text-content-muted hover:text-content-strong"
          data-testid="runtime-inspector-documents-block-detail-back"
          aria-label="Back to template"
        >
          <ArrowLeft size={12} />
          <span className="truncate">
            {draft.templateDetail.template_key}
          </span>
        </button>
      </div>
      <div className="text-caption text-content-muted">
        Block:{" "}
        <code className="font-plex-mono text-content-strong">{block.id}</code>
      </div>

      <BlockConfigEditor
        block={block}
        blockKinds={draft.blockKinds}
        onUpdateConfig={(cfg) => {
          void draft.updateBlockConfig(block.id, cfg)
        }}
        onUpdateCondition={(condition) => {
          void draft.updateBlockCondition(block.id, condition)
        }}
        onDelete={() => {
          void draft.deleteBlock(block.id).then((ok) => {
            if (ok) onBack()
          })
        }}
        canEdit={canEdit}
        errorMessage={draft.blockErrors[block.id] ?? null}
        isSaving={!!draft.blockSaving[block.id]}
      />

      {/* Conditional_wrapper child management */}
      {acceptsChildren && (
        <div
          className="mt-2 border-t border-border-subtle pt-2"
          data-testid="runtime-inspector-documents-children-section"
        >
          <div className="flex items-center justify-between px-3">
            <span className="text-micro uppercase tracking-wider text-content-muted">
              Child blocks ({childBlocks.length})
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setShowChildPicker(true)}
              disabled={!canEdit}
              data-testid="runtime-inspector-documents-add-child"
            >
              <Plus size={11} className="mr-1" /> Add child
            </Button>
          </div>
          {draft.blockErrors.__add__ && (
            <div
              className="mx-3 mt-1 flex items-start gap-1 rounded-sm bg-status-error-muted px-2 py-1 text-caption text-status-error"
              data-testid="runtime-inspector-documents-add-child-error"
            >
              <AlertCircle size={11} className="mt-0.5 flex-shrink-0" />
              <span className="flex-1">{draft.blockErrors.__add__}</span>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => draft.clearBlockError("__add__")}
                className="ml-1 h-5 px-1 text-caption"
              >
                Dismiss
              </Button>
            </div>
          )}
          {childBlocks.length === 0 ? (
            <p
              className="mx-3 mt-1 rounded-sm border border-dashed border-border-base px-2 py-3 text-caption text-content-muted"
              data-testid="runtime-inspector-documents-no-children"
            >
              No child blocks. Use “Add child” to start.
            </p>
          ) : (
            <ol className="mt-1 flex flex-col gap-1 px-3">
              {childBlocks.map((c) => (
                <li
                  key={c.id}
                  data-testid={`runtime-inspector-documents-child-${c.id}`}
                >
                  <div className="flex items-center justify-between gap-1 rounded-sm border border-border-subtle bg-surface-elevated px-2 py-1.5">
                    <span className="flex items-center gap-1.5">
                      <Badge variant="outline" className="text-micro">
                        {c.block_kind}
                      </Badge>
                      <span className="text-caption text-content-muted">
                        pos {c.position}
                      </span>
                    </span>
                    <button
                      type="button"
                      onClick={() => void draft.deleteBlock(c.id)}
                      disabled={!canEdit || !!draft.blockSaving[c.id]}
                      data-testid={`runtime-inspector-documents-child-${c.id}-remove`}
                      aria-label={`Remove child ${c.id}`}
                      className="rounded-sm border border-border-base bg-surface-raised p-1 text-content-muted hover:bg-status-error-muted hover:text-status-error disabled:opacity-50"
                    >
                      <Trash2 size={10} />
                    </button>
                  </div>
                  {draft.blockErrors[c.id] && (
                    <div
                      className="mt-1 flex items-start gap-1 rounded-sm bg-status-error-muted px-2 py-1 text-caption text-status-error"
                      data-testid={`runtime-inspector-documents-child-${c.id}-error`}
                    >
                      <AlertCircle size={11} className="mt-0.5 flex-shrink-0" />
                      <span className="flex-1">{draft.blockErrors[c.id]}</span>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => draft.clearBlockError(c.id)}
                        className="ml-1 h-5 px-1 text-caption"
                      >
                        Dismiss
                      </Button>
                    </div>
                  )}
                </li>
              ))}
            </ol>
          )}
        </div>
      )}

      {showChildPicker && (
        <BlockKindPicker
          blockKinds={draft.blockKinds}
          onPick={(kind) => {
            setShowChildPicker(false)
            void draft.addBlock(kind, { parent_block_id: block.id })
          }}
          onCancel={() => setShowChildPicker(false)}
        />
      )}
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
      data-testid="runtime-inspector-documents-back-header"
    >
      <ArrowLeft size={12} />
      <span>{label}</span>
    </button>
  )
}
