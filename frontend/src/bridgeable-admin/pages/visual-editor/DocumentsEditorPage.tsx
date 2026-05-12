/**
 * DocumentsEditorPage — block-based document template authoring
 * (Phase D-10 + D-11, June 2026).
 *
 * Replaces the May 2026 placeholder. Provides the visual editor's
 * canonical authoring surface for block-based templates. Coexists
 * with `/vault/documents/templates/:id` (textarea-based Jinja
 * editor for legacy templates) — the Phase 2 architectural decision
 * is that block-authored is the new model; legacy Jinja templates
 * stay where they are.
 *
 * Three-pane layout:
 *
 *   ┌─ Left (320px) ──┬─ Center (60-65%) ──────┬─ Right (360px) ──┐
 *   │ Hierarchical    │ Live preview against    │ Tabs:             │
 *   │   browser:      │ sample data — block-by  │ • Blocks          │
 *   │   • categories  │  -block in the canvas.  │ • Configuration   │
 *   │     from        │  Block boundaries shown │ • Versions        │
 *   │     curated     │  during editing.        │                   │
 *   │     catalog     │                         │ When a block is   │
 *   │   • templates   │ Sample data variation   │ selected, its     │
 *   │     filtered by │ via dropdown.           │ config controls   │
 *   │     document_   │                         │ appear below.     │
 *   │     type        │                         │                   │
 *   └─────────────────┴─────────────────────────┴───────────────────┘
 *
 * Save discipline: each block-mutation endpoint persists immediately
 * (recompose runs server-side; body_template + variable_schema
 * update atomically). No "save draft" debounce — the editor writes
 * through. Activate / Discard happen via the existing
 * TemplateActivationDialog + version history.
 */
import { useCallback, useEffect, useMemo, useState } from "react"
import {
  AlertCircle,
  FileText,
  Layers,
  Loader2,
  Plus,
  Settings as SettingsIcon,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  HierarchicalEditorBrowser,
  type HierarchicalCategory,
  type HierarchicalTemplate,
} from "@/bridgeable-admin/components/visual-editor/HierarchicalEditorBrowser"
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
  ConditionalWrapperBlockRenderer,
  UnknownBlockRenderer,
  getBlockRenderer,
} from "@/components/documents/blocks"


type RightTab = "blocks" | "configuration" | "versions"


export default function DocumentsEditorPage() {
  // ── Catalog + browser state ──────────────────────────────
  const [catalog, setCatalog] = useState<DocumentTypeCatalog | null>(null)
  const [templates, setTemplates] = useState<DocumentTemplateListItem[]>([])
  const [search, setSearch] = useState("")
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(
    null,
  )
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(
    null,
  )

  // ── Selected template state ──────────────────────────────
  const [templateDetail, setTemplateDetail] =
    useState<DocumentTemplateDetail | null>(null)
  const [activeVersion, setActiveVersion] =
    useState<DocumentTemplateVersion | null>(null)
  const [draftVersion, setDraftVersion] =
    useState<DocumentTemplateVersion | null>(null)
  const [blocks, setBlocks] = useState<TemplateBlock[]>([])
  const [blockKinds, setBlockKinds] = useState<BlockKindMetadata[]>([])
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null)
  const [tab, setTab] = useState<RightTab>("blocks")

  // ── UI state ─────────────────────────────────────────────
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showBlockPicker, setShowBlockPicker] = useState(false)

  // ── Load catalog + block kinds on mount ──────────────────
  useEffect(() => {
    let cancelled = false
    Promise.all([
      documentBlocksService.listDocumentTypes(),
      documentBlocksService.listBlockKinds(),
    ])
      .then(([cat, kinds]) => {
        if (cancelled) return
        setCatalog(cat)
        setBlockKinds(kinds)
        if (!selectedCategoryId && cat.categories.length > 0) {
          setSelectedCategoryId(cat.categories[0]?.category_id ?? null)
        }
      })
      .catch((err) => {
        if (cancelled) return
        // eslint-disable-next-line no-console
        console.error("[documents-editor] catalog load failed", err)
        setError(err instanceof Error ? err.message : "Failed to load catalog")
      })
    return () => {
      cancelled = true
    }
  }, [selectedCategoryId])

  // ── Load templates for browser ───────────────────────────
  useEffect(() => {
    let cancelled = false
    documentsV2Service
      .listTemplates({ limit: 500 })
      .then((res) => {
        if (cancelled) return
        setTemplates(res.items)
      })
      .catch((err) => {
        if (cancelled) return
        // eslint-disable-next-line no-console
        console.warn("[documents-editor] template list failed", err)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // ── Browser data ─────────────────────────────────────────
  const { browserCategories, browserTemplates } = useMemo(() => {
    const cats: HierarchicalCategory[] =
      catalog?.categories.map((c) => ({
        id: c.category_id,
        label: c.display_name,
        description: typeCountForCategory(c.category_id, catalog) + " types",
      })) ?? []

    // Map document_type → category for grouping templates.
    const typeToCategory = new Map<string, string>()
    for (const t of catalog?.types ?? []) {
      typeToCategory.set(t.type_id, t.category)
    }

    const tmpls: HierarchicalTemplate[] = templates
      .filter((t) => typeToCategory.has(t.document_type))
      .map((t) => ({
        id: t.id,
        label: t.template_key,
        description: t.description ?? undefined,
        badge: t.scope === "tenant" ? "tenant" : t.scope,
        categoryId: typeToCategory.get(t.document_type) ?? "other",
      }))

    return { browserCategories: cats, browserTemplates: tmpls }
  }, [catalog, templates])

  // ── Load template detail when selected ───────────────────
  useEffect(() => {
    if (!selectedTemplateId) {
      setTemplateDetail(null)
      setActiveVersion(null)
      setDraftVersion(null)
      setBlocks([])
      setSelectedBlockId(null)
      return
    }
    let cancelled = false
    setIsLoading(true)
    setError(null)
    documentsV2Service
      .getTemplate(selectedTemplateId)
      .then((detail) => {
        if (cancelled) return
        setTemplateDetail(detail)
        // Identify draft + active versions
        const versions = detail.version_summaries
        const draftSummary = versions.find((v) => v.status === "draft")
        const activeSummary = versions.find((v) => v.status === "active")

        const tasks: Promise<unknown>[] = []
        if (draftSummary) {
          tasks.push(
            documentsV2Service
              .getTemplateVersion(detail.id, draftSummary.id)
              .then((v) => {
                if (!cancelled) setDraftVersion(v)
              }),
          )
        } else {
          setDraftVersion(null)
        }
        if (activeSummary) {
          tasks.push(
            documentsV2Service
              .getTemplateVersion(detail.id, activeSummary.id)
              .then((v) => {
                if (!cancelled) setActiveVersion(v)
              }),
          )
        } else {
          setActiveVersion(null)
        }
        return Promise.all(tasks)
      })
      .catch((err) => {
        if (cancelled) return
        // eslint-disable-next-line no-console
        console.error("[documents-editor] template detail failed", err)
        setError(err instanceof Error ? err.message : "Failed to load")
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedTemplateId])

  // ── Load blocks when version changes ─────────────────────
  const editingVersion = draftVersion ?? activeVersion
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
        console.warn("[documents-editor] block list failed", err)
      })
    return () => {
      cancelled = true
    }
  }, [templateDetail, editingVersion])

  // ── Block mutation handlers ──────────────────────────────
  const reloadBlocks = useCallback(async () => {
    if (!templateDetail || !editingVersion) return
    const rows = await documentBlocksService.list(
      templateDetail.id,
      editingVersion.id,
    )
    setBlocks(rows)
  }, [templateDetail, editingVersion])

  const handleAddBlock = useCallback(
    async (kind: string) => {
      if (!templateDetail || !editingVersion) return
      try {
        const block = await documentBlocksService.add(
          templateDetail.id,
          editingVersion.id,
          { block_kind: kind, config: {} },
        )
        await reloadBlocks()
        setSelectedBlockId(block.id)
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error("[documents-editor] add block failed", err)
        setError(err instanceof Error ? err.message : "Failed to add block")
      }
    },
    [templateDetail, editingVersion, reloadBlocks],
  )

  const handleDeleteBlock = useCallback(
    async (blockId: string) => {
      if (!templateDetail || !editingVersion) return
      try {
        await documentBlocksService.remove(
          templateDetail.id,
          editingVersion.id,
          blockId,
        )
        await reloadBlocks()
        setSelectedBlockId(null)
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error("[documents-editor] delete block failed", err)
        setError(err instanceof Error ? err.message : "Failed to delete block")
      }
    },
    [templateDetail, editingVersion, reloadBlocks],
  )

  const handleUpdateBlockConfig = useCallback(
    async (blockId: string, config: Record<string, unknown>) => {
      if (!templateDetail || !editingVersion) return
      try {
        await documentBlocksService.update(
          templateDetail.id,
          editingVersion.id,
          blockId,
          { config },
        )
        await reloadBlocks()
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error("[documents-editor] update block failed", err)
        setError(err instanceof Error ? err.message : "Failed to update block")
      }
    },
    [templateDetail, editingVersion, reloadBlocks],
  )

  const selectedBlock = useMemo(
    () => blocks.find((b) => b.id === selectedBlockId) ?? null,
    [blocks, selectedBlockId],
  )

  // Build a sample context for preview rendering. Pulls from version's
  // sample_context if set; falls back to a reasonable default.
  const sampleContext = useMemo(() => {
    const fromVersion =
      (editingVersion?.sample_context as Record<string, unknown> | null) ?? {}
    return {
      company_name: "Acme Co",
      company_logo_url: "",
      document_title: "Document Preview",
      document_date: "2026-06-01",
      customer_name: "Sample Customer",
      customer_address: "123 Sample St",
      invoice_number: "INV-001",
      items: [
        {
          description: "Sample line item",
          quantity: 1,
          unit_price: "$100.00",
          line_total: "$100.00",
        },
      ],
      subtotal: "$100.00",
      tax: "$8.00",
      total: "$108.00",
      ...fromVersion,
    }
  }, [editingVersion])

  return (
    <div
      className="flex h-[calc(100vh-3rem)] w-full flex-col"
      data-testid="documents-editor"
    >
      <div className="flex flex-1 overflow-hidden">
        {/* ── LEFT: Hierarchical browser ──────────────────── */}
        <aside
          className="flex w-[320px] flex-shrink-0 flex-col border-r border-border-subtle bg-surface-elevated"
          data-testid="documents-editor-browser"
        >
          <div className="border-b border-border-subtle px-3 py-2">
            <div className="text-h4 font-plex-serif text-content-strong">
              Document templates
            </div>
            <div className="text-caption text-content-muted">
              {catalog?.types.length ?? 0} types · {templates.length} templates
            </div>
          </div>
          <div className="flex-1 overflow-hidden">
            <HierarchicalEditorBrowser
              categories={browserCategories}
              templates={browserTemplates}
              selectedCategoryId={selectedCategoryId}
              selectedTemplateId={selectedTemplateId}
              search={search}
              onSearchChange={setSearch}
              onSelectCategory={(id) => {
                setSelectedCategoryId(id)
                setSelectedTemplateId(null)
              }}
              onSelectTemplate={(id) => {
                setSelectedTemplateId(id)
                const t = templates.find((x) => x.id === id)
                if (t) {
                  const cat =
                    catalog?.types.find((ty) => ty.type_id === t.document_type)
                      ?.category ?? null
                  if (cat) setSelectedCategoryId(cat)
                }
                setTab("blocks")
              }}
              searchPlaceholder="Filter document types + templates"
              emptyStateForCategory={(cat) =>
                `No templates yet for ${cat.label}.`
              }
            />
          </div>
        </aside>

        {/* ── CENTER: Preview ──────────────────────────────── */}
        <main
          className="relative flex flex-1 flex-col overflow-hidden bg-surface-sunken"
          data-testid="documents-editor-preview-pane"
        >
          <div className="flex items-center justify-between border-b border-border-subtle bg-surface-elevated px-4 py-2">
            <div className="flex items-center gap-3">
              {templateDetail ? (
                <span
                  className="text-body-sm font-medium text-content-strong"
                  data-testid="documents-editor-template-label"
                >
                  {templateDetail.template_key}
                </span>
              ) : selectedCategoryId ? (
                <span
                  className="text-body-sm font-medium text-content-strong"
                  data-testid="documents-editor-category-label"
                >
                  {
                    catalog?.categories.find(
                      (c) => c.category_id === selectedCategoryId,
                    )?.display_name
                  }
                </span>
              ) : (
                <span className="text-body-sm text-content-muted">
                  Select a category or template
                </span>
              )}
              {templateDetail && (
                <Badge variant="outline">
                  {templateDetail.scope}
                </Badge>
              )}
              {editingVersion && (
                <Badge variant="outline">
                  v{editingVersion.version_number} {editingVersion.status}
                </Badge>
              )}
              {isLoading && (
                <Loader2 size={12} className="animate-spin text-content-muted" />
              )}
              {error && (
                <span className="flex items-center gap-1 text-caption text-status-error">
                  <AlertCircle size={12} />
                  {error}
                </span>
              )}
            </div>
          </div>
          <div
            className="flex-1 overflow-auto p-6"
            data-testid="documents-editor-preview-area"
          >
            {templateDetail && editingVersion ? (
              <BlockPreview
                blocks={blocks}
                selectedBlockId={selectedBlockId}
                onSelectBlock={setSelectedBlockId}
                context={sampleContext}
              />
            ) : selectedCategoryId && catalog ? (
              <CategoryOverview
                categoryId={selectedCategoryId}
                catalog={catalog}
              />
            ) : (
              <div className="flex h-full items-center justify-center text-content-muted">
                Select a category or template to begin.
              </div>
            )}
          </div>
        </main>

        {/* ── RIGHT: Editor controls ─────────────────────── */}
        <aside
          className="flex w-[360px] flex-shrink-0 flex-col border-l border-border-subtle bg-surface-elevated"
          data-testid="documents-editor-controls"
        >
          {templateDetail ? (
            <>
              <div
                className="flex items-center gap-0.5 border-b border-border-subtle px-2 py-1"
                data-testid="documents-editor-tabs"
              >
                {(
                  [
                    ["blocks", "Blocks", Layers],
                    ["configuration", "Config", SettingsIcon],
                    ["versions", "Versions", FileText],
                  ] as const
                ).map(([id, label, Icon]) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setTab(id)}
                    className={
                      tab === id
                        ? "flex flex-1 items-center justify-center gap-1 rounded-sm bg-accent-subtle px-2 py-1 text-caption font-medium text-content-strong"
                        : "flex flex-1 items-center justify-center gap-1 rounded-sm px-2 py-1 text-caption text-content-muted hover:text-content-strong"
                    }
                    data-testid={`documents-tab-${id}`}
                    data-active={tab === id ? "true" : "false"}
                  >
                    <Icon size={11} />
                    {label}
                  </button>
                ))}
              </div>
              <div className="flex-1 overflow-y-auto">
                {tab === "blocks" && (
                  <BlocksTab
                    blocks={blocks}
                    selectedBlockId={selectedBlockId}
                    onSelectBlock={setSelectedBlockId}
                    onDeleteBlock={handleDeleteBlock}
                    onAddBlock={() => setShowBlockPicker(true)}
                    blockKinds={blockKinds}
                    onUpdateBlockConfig={handleUpdateBlockConfig}
                    selectedBlock={selectedBlock}
                    canEdit={!!draftVersion}
                  />
                )}
                {tab === "configuration" && editingVersion && (
                  <ConfigurationTab version={editingVersion} />
                )}
                {tab === "versions" && templateDetail && (
                  <VersionsTab template={templateDetail} />
                )}
              </div>
            </>
          ) : (
            <div className="px-3 py-6 text-center text-caption text-content-muted">
              Select a template to edit.
            </div>
          )}
        </aside>
      </div>

      {showBlockPicker && (
        <BlockKindPicker
          blockKinds={blockKinds}
          onPick={(kind) => {
            setShowBlockPicker(false)
            void handleAddBlock(kind)
          }}
          onCancel={() => setShowBlockPicker(false)}
        />
      )}
    </div>
  )
}


// ─── Helpers ──────────────────────────────────────────────────


function typeCountForCategory(
  categoryId: string,
  catalog: DocumentTypeCatalog | null,
): number {
  return (
    catalog?.types.filter((t) => t.category === categoryId).length ?? 0
  )
}


// ─── Sub-components ───────────────────────────────────────────


function CategoryOverview({
  categoryId,
  catalog,
}: {
  categoryId: string
  catalog: DocumentTypeCatalog
}) {
  const types = catalog.types.filter((t) => t.category === categoryId)
  const cat = catalog.categories.find((c) => c.category_id === categoryId)
  return (
    <div
      className="mx-auto max-w-2xl"
      data-testid={`documents-category-overview-${categoryId}`}
    >
      <h2 className="text-h2 font-plex-serif text-content-strong">
        {cat?.display_name}
      </h2>
      <p className="mt-2 text-body-sm text-content-muted">
        {types.length} document type{types.length === 1 ? "" : "s"} in this
        category. Templates are filtered to this category in the browser.
      </p>
      <div className="mt-6 grid gap-3">
        {types.map((t) => (
          <div
            key={t.type_id}
            className="rounded-md border border-border-subtle bg-surface-elevated p-4"
            data-testid={`documents-type-card-${t.type_id}`}
          >
            <div className="text-h4 font-plex-serif text-content-strong">
              {t.display_name}
            </div>
            <div className="mt-1 text-caption text-content-muted">
              {t.description}
            </div>
            <div className="mt-2 text-[10px] font-plex-mono text-content-muted">
              type_id: {t.type_id} · {t.starter_blocks.length} starter blocks
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}


function BlockPreview({
  blocks,
  selectedBlockId,
  onSelectBlock,
  context,
}: {
  blocks: TemplateBlock[]
  selectedBlockId: string | null
  onSelectBlock: (id: string) => void
  context: Record<string, unknown>
}) {
  const topLevel = blocks.filter((b) => !b.parent_block_id)
  if (topLevel.length === 0) {
    return (
      <div className="mx-auto max-w-2xl rounded-md border border-dashed border-border-subtle bg-surface-base p-8 text-center text-content-muted">
        <FileText size={32} className="mx-auto mb-2 text-content-subtle" />
        <div className="text-body-sm">
          No blocks yet — add one from the right rail.
        </div>
      </div>
    )
  }
  return (
    <div className="mx-auto max-w-3xl rounded-md border border-border-subtle bg-surface-elevated shadow-level-2">
      {topLevel.map((block) => {
        const Renderer = getBlockRenderer(block.block_kind)
        const isSelected = block.id === selectedBlockId
        // For conditional_wrappers, render their children inside the
        // wrapper renderer's `children` slot.
        let children: React.ReactNode = null
        if (block.block_kind === "conditional_wrapper") {
          const childBlocks = blocks
            .filter((b) => b.parent_block_id === block.id)
            .sort((a, b) => a.position - b.position)
          children = childBlocks.map((c) => {
            const ChildRenderer = getBlockRenderer(c.block_kind)
            if (!ChildRenderer) {
              return <UnknownBlockRenderer key={c.id} block={c} />
            }
            return (
              <div
                key={c.id}
                className={
                  c.id === selectedBlockId
                    ? "ring-2 ring-accent ring-offset-2 ring-offset-surface-elevated"
                    : ""
                }
                onClick={(e) => {
                  e.stopPropagation()
                  onSelectBlock(c.id)
                }}
              >
                <ChildRenderer block={c} context={context} />
              </div>
            )
          })
        }
        return (
          <div
            key={block.id}
            className={
              isSelected
                ? "ring-2 ring-accent ring-offset-2 ring-offset-surface-elevated"
                : ""
            }
            onClick={() => onSelectBlock(block.id)}
            data-testid={`block-preview-wrapper-${block.id}`}
          >
            {Renderer ? (
              block.block_kind === "conditional_wrapper" ? (
                <ConditionalWrapperBlockRenderer
                  block={block}
                  context={context}
                >
                  {children}
                </ConditionalWrapperBlockRenderer>
              ) : (
                <Renderer block={block} context={context} />
              )
            ) : (
              <UnknownBlockRenderer block={block} />
            )}
          </div>
        )
      })}
    </div>
  )
}


function BlocksTab({
  blocks,
  selectedBlockId,
  onSelectBlock,
  onDeleteBlock,
  onAddBlock,
  blockKinds,
  onUpdateBlockConfig,
  selectedBlock,
  canEdit,
}: {
  blocks: TemplateBlock[]
  selectedBlockId: string | null
  onSelectBlock: (id: string) => void
  onDeleteBlock: (id: string) => void
  onAddBlock: () => void
  blockKinds: BlockKindMetadata[]
  onUpdateBlockConfig: (id: string, config: Record<string, unknown>) => void
  selectedBlock: TemplateBlock | null
  canEdit: boolean
}) {
  const topLevel = blocks.filter((b) => !b.parent_block_id)
  return (
    <div data-testid="documents-blocks-tab">
      {!canEdit && (
        <div className="border-b border-border-subtle bg-status-warning-muted/40 px-3 py-2 text-caption text-status-warning">
          No active draft — create one from the Versions tab to edit blocks.
        </div>
      )}
      <div className="border-b border-border-subtle px-3 py-2">
        <div className="mb-1.5 flex items-center justify-between">
          <div className="text-micro uppercase tracking-wider text-content-muted">
            Blocks ({topLevel.length})
          </div>
          <Button
            size="sm"
            onClick={onAddBlock}
            disabled={!canEdit}
            data-testid="documents-add-block"
          >
            <Plus size={11} className="mr-1" />
            Add
          </Button>
        </div>
        {topLevel.length === 0 ? (
          <div className="px-2 py-3 text-center text-caption text-content-muted">
            No blocks yet.
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            {topLevel.map((b) => (
              <button
                key={b.id}
                type="button"
                onClick={() => onSelectBlock(b.id)}
                className={
                  b.id === selectedBlockId
                    ? "flex items-center justify-between rounded-sm bg-accent-subtle/60 px-2 py-1.5 text-left"
                    : "flex items-center justify-between rounded-sm px-2 py-1.5 text-left hover:bg-accent-subtle/30"
                }
                data-testid={`documents-block-row-${b.id}`}
              >
                <span className="text-caption font-medium text-content-strong">
                  {b.block_kind}
                </span>
                <span className="font-plex-mono text-[10px] text-content-muted">
                  pos {b.position}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
      {selectedBlock && (
        <BlockConfigEditor
          block={selectedBlock}
          blockKinds={blockKinds}
          onUpdateConfig={(cfg) => onUpdateBlockConfig(selectedBlock.id, cfg)}
          onDelete={() => onDeleteBlock(selectedBlock.id)}
          canEdit={canEdit}
        />
      )}
    </div>
  )
}


function ConfigurationTab({
  version,
}: {
  version: DocumentTemplateVersion
}) {
  return (
    <div className="px-3 py-3" data-testid="documents-config-tab">
      <div className="mb-3">
        <div className="text-micro uppercase tracking-wider text-content-muted">
          Variable schema
        </div>
        <pre className="mt-1.5 rounded-sm bg-surface-sunken p-2 text-[10px] text-content-base">
          {JSON.stringify(version.variable_schema ?? {}, null, 2)}
        </pre>
      </div>
      <div className="mb-3">
        <div className="text-micro uppercase tracking-wider text-content-muted">
          CSS variables
        </div>
        <pre className="mt-1.5 rounded-sm bg-surface-sunken p-2 text-[10px] text-content-base">
          {JSON.stringify(version.css_variables ?? {}, null, 2)}
        </pre>
      </div>
      <div className="text-caption text-content-muted">
        Variable schema is auto-populated from declared block variables;
        manual annotations stay preserved across recompose. Edit the
        full schema via the existing template editor at{" "}
        <code className="rounded-sm bg-surface-sunken px-1 py-0.5 font-plex-mono text-[10px]">
          /vault/documents/templates/{version.template_id}
        </code>
        .
      </div>
    </div>
  )
}


function VersionsTab({
  template,
}: {
  template: DocumentTemplateDetail
}) {
  return (
    <div className="px-3 py-3" data-testid="documents-versions-tab">
      <div className="mb-2 text-micro uppercase tracking-wider text-content-muted">
        Versions ({template.version_summaries.length})
      </div>
      <div className="flex flex-col gap-1">
        {template.version_summaries.map((v) => (
          <div
            key={v.id}
            className="flex items-center justify-between rounded-sm bg-surface-sunken px-2 py-1.5"
            data-testid={`documents-version-row-${v.id}`}
          >
            <span className="text-caption font-medium text-content-strong">
              v{v.version_number}
            </span>
            <Badge variant="outline">{v.status}</Badge>
          </div>
        ))}
      </div>
      <div className="mt-3 text-caption text-content-muted">
        Activate / Rollback / Test Render via the existing template
        editor's controls.
      </div>
    </div>
  )
}


// BlockKindPicker + BlockConfigEditor moved to shared module at
// @/bridgeable-admin/components/visual-editor/documents/* per Arc 3b
// Q-CROSS-2 canon — both standalone editor + inspector Documents tab
// consume identical components.
