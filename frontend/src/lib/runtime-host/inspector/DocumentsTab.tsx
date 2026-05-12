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
  Loader2,
  Plus,
  Trash2,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
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
  onSelect,
}: {
  template: DocumentTemplateListItem
  onSelect: () => void
}) {
  const editorUrl = adminPath("/visual-editor/documents")
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
          <div className="text-caption text-content-muted truncate">
            <code className="font-plex-mono">{template.document_type}</code>
            <span className="ml-2">· {template.scope}</span>
            {template.current_version_number !== null && (
              <span className="ml-2">
                · v{template.current_version_number}
              </span>
            )}
            {template.has_draft && (
              <span className="ml-2 text-status-warning">· draft</span>
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
        href={adminPath("/visual-editor/documents")}
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
    deleteBlock,
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
  const editorUrl = adminPath("/visual-editor/documents")

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

      {/* Add block button */}
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

      {/* Block list */}
      <div data-testid="runtime-inspector-documents-block-list">
        {topLevel.length === 0 ? (
          <p
            className="rounded-sm border border-dashed border-border-base px-2 py-3 text-caption text-content-muted"
            data-testid="runtime-inspector-documents-empty-blocks"
          >
            No blocks yet. Use “Add” above to start.
          </p>
        ) : (
          <ol className="flex flex-col gap-1.5">
            {topLevel.map((block, idx) => {
              const children = draft.blocks
                .filter((b) => b.parent_block_id === block.id)
                .sort((a, b) => a.position - b.position)
              return (
                <li
                  key={block.id}
                  data-testid={`runtime-inspector-documents-block-${block.id}`}
                  data-block-kind={block.block_kind}
                >
                  <div className="flex items-start justify-between gap-1 rounded-sm border border-border-subtle bg-surface-elevated hover:bg-accent-subtle/30">
                    <button
                      type="button"
                      onClick={() => onSelectBlock(block.id)}
                      className="min-w-0 flex-1 px-2 py-1.5 text-left"
                      data-testid={`runtime-inspector-documents-block-${block.id}-select`}
                    >
                      <div className="flex items-center gap-1.5">
                        <span className="text-micro text-content-muted">
                          #{idx + 1}
                        </span>
                        <Badge variant="outline" className="text-micro">
                          {block.block_kind}
                        </Badge>
                        <span className="text-caption text-content-muted">
                          pos {block.position}
                        </span>
                        {children.length > 0 && (
                          <span className="text-caption text-content-muted">
                            · {children.length} child{children.length === 1 ? "" : "ren"}
                          </span>
                        )}
                      </div>
                      {children.length > 0 && (
                        <div className="mt-0.5 flex flex-wrap gap-1">
                          {children.map((c) => (
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
                    <button
                      type="button"
                      onClick={() => void draft.deleteBlock(block.id)}
                      disabled={!canEdit || !!draft.blockSaving[block.id]}
                      data-testid={`runtime-inspector-documents-block-${block.id}-remove`}
                      aria-label={`Remove block ${block.id}`}
                      className="m-1 rounded-sm border border-border-base bg-surface-raised p-1 text-content-muted hover:bg-status-error-muted hover:text-status-error disabled:opacity-50"
                    >
                      <Trash2 size={10} />
                    </button>
                  </div>
                  {draft.blockErrors[block.id] && (
                    <div
                      className="mt-1 flex items-start gap-1 rounded-sm bg-status-error-muted px-2 py-1 text-caption text-status-error"
                      data-testid={`runtime-inspector-documents-block-${block.id}-error`}
                    >
                      <AlertCircle size={11} className="mt-0.5 flex-shrink-0" />
                      <span className="flex-1">{draft.blockErrors[block.id]}</span>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => draft.clearBlockError(block.id)}
                        className="ml-1 h-5 px-1 text-caption"
                      >
                        Dismiss
                      </Button>
                    </div>
                  )}
                </li>
              )
            })}
          </ol>
        )}
      </div>

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
