/**
 * FocusEditorPage — purpose-specific editor for Focus templates +
 * their accessory-layer compositions (May 2026 reorganization).
 *
 * Replaces the standalone Compositions page + the Focus-template
 * portion of the dismantled generic ComponentEditorPage. Combines:
 *   • Per-template prop configuration (was ComponentEditorPage with
 *     focus-template kind filter)
 *   • Composition authoring (was CompositionEditorPage)
 * into one surface where you author Focus templates comprehensively.
 *
 * Three-pane layout following the redesigned editor pattern:
 *
 *   ┌─ Left (320px) ──┬─ Center (60-65%) ──────┬─ Right (320px) ──┐
 *   │ HierarchicalEditor │ Focus preview        │ Tab selector:    │
 *   │   Browser:         │  - Category: Focus   │   • Configuration│
 *   │   • 5 Focus types  │    type stand-in     │   • Composition  │
 *   │     as categories  │  - Template: real    │   • Preview      │
 *   │   • focus-templates│    Focus shell with  │   Settings       │
 *   │     as children    │    accessory layer   │                  │
 *   └────────────────────┴──────────────────────┴──────────────────┘
 *
 * Categories: 5 canonical Focus types (Decision, Coordination,
 * Execution, Review, Generation). Templates within each: registry
 * entries with `componentKind === "focus-template"` grouped by
 * `extensions.focusType`.
 *
 * Composition tab embeds InteractivePlacementCanvas with full
 * drag-drop / multi-select / undo-redo / keyboard-shortcut layer
 * preserved from the previous phase. The composition editor's
 * canvas state lives within this tab; saving persists to the
 * focus_compositions table via focusCompositionsService.
 *
 * NOTE: when the funeral-scheduling template is selected, the
 * preview shows a simplified shell representing the kanban core
 * (the real SchedulingKanbanCore depends on auth/dnd/scheduling-
 * data providers and is not feasible to embed inside the editor
 * preview). The composition tab still authors the runtime accessory
 * layer; what the editor previews is structural representation.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import {
  AlertCircle,
  ArrowLeft,
  ArrowLeftRight,
  Loader2,
  Moon,
  Save,
  Settings as SettingsIcon,
  Sun,
  Sliders,
  Grid3x3,
  Plus,
  Trash2,
  Undo2,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import {
  HierarchicalEditorBrowser,
  type HierarchicalCategory,
  type HierarchicalTemplate,
} from "@/bridgeable-admin/components/visual-editor/HierarchicalEditorBrowser"
import { useStudioRail } from "@/bridgeable-admin/components/studio/StudioRailContext"
import {
  focusCompositionsService,
} from "@/bridgeable-admin/services/focus-compositions-service"
import {
  componentConfigurationsService,
  type ComponentConfigurationRecord,
} from "@/bridgeable-admin/services/component-configurations-service"
import type {
  CompositionRecord,
  CompositionRow,
  Placement,
  ResolvedComposition,
} from "@/lib/visual-editor/compositions/types"
import {
  composeEffectiveProps,
  emptyConfigStack,
  resolvePropSource,
  type ConfigStack,
  type PropOverrideMap,
} from "@/lib/visual-editor/components/config-resolver"
import {
  getAllRegistered,
  getByName,
  getCanvasMetadata,
  getCanvasPlaceableComponents,
  type ComponentKind,
  type ConfigPropSchema,
  type RegistryEntry,
} from "@/lib/visual-editor/registry"
import { CompactPropControl } from "@/bridgeable-admin/components/visual-editor/CompactPropControl"
import { ComponentThumbnail } from "@/bridgeable-admin/components/visual-editor/ComponentThumbnail"
import { FocusContextFrame } from "@/bridgeable-admin/components/visual-editor/context-frames/FocusContextFrame"
import {
  InteractivePlacementCanvas,
  type Selection,
} from "@/bridgeable-admin/components/visual-editor/composition-canvas/InteractivePlacementCanvas"
import {
  TenantPicker,
  type TenantSummary,
} from "@/bridgeable-admin/components/TenantPicker"
import {
  FuneralSchedulingPreviewHarness,
  SampleScenarioPicker,
  compositionDraftAsResolved,
} from "./focus-editor/FuneralSchedulingPreviewHarness"
import type { SampleScenario } from "./focus-editor/mock-data/funeralSchedulingMockData"


type FocusType = "decision" | "coordination" | "execution" | "review" | "generation"
const FOCUS_TYPES: ReadonlyArray<{ id: FocusType; label: string; description: string }> = [
  { id: "decision", label: "Decision Focus", description: "Bounded decision flow — triage, approve/reject queues." },
  { id: "coordination", label: "Coordination Focus", description: "Multi-step coordination — workflow orchestration." },
  { id: "execution", label: "Execution Focus", description: "Operational execution — task completion, action review." },
  { id: "review", label: "Review Focus", description: "Audit + review — read-only inspection of historical state." },
  { id: "generation", label: "Generation Focus", description: "Content generation — scribe panels, AI-assisted authoring." },
]

type RightTab = "configuration" | "composition" | "preview-settings"
type Scope = "platform_default" | "vertical_default" | "tenant_override"
type PreviewMode = "light" | "dark"
const VERTICALS = ["funeral_home", "manufacturing", "cemetery", "crematory"] as const


function defaultCanvasConfig(): CompositionRecord["canvas_config"] {
  return {
    gap_size: 12,
    background_treatment: "surface-base",
  }
}


function newRowId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID()
  }
  return `row-${Math.random().toString(36).slice(2, 10)}-${Date.now()}`
}


function nextPlacementId(rows: CompositionRow[]): string {
  let i = rows.flatMap((r) => r.placements).length + 1
  const existing = new Set(
    rows.flatMap((r) => r.placements.map((p) => p.placement_id)),
  )
  while (existing.has(`p${i}`)) i += 1
  return `p${i}`
}


function findAvailableStartingColumn(
  row: CompositionRow,
  span: number,
): number {
  const sorted = [...row.placements].sort(
    (a, b) => a.starting_column - b.starting_column,
  )
  let cursor = 0
  for (const p of sorted) {
    if (p.starting_column - cursor >= span) return cursor
    cursor = Math.max(cursor, p.starting_column + p.column_span)
  }
  if (row.column_count - cursor >= span) return cursor
  return -1
}


function makeRow(columnCount = 12): CompositionRow {
  return {
    row_id: newRowId(),
    column_count: columnCount,
    row_height: "auto",
    column_widths: null,
    nested_rows: null,
    placements: [],
  }
}


// ─── Composition draft state (lifted from CompositionTab) ─────
// Lifted to FocusEditorPage so the preview pane can read the
// in-progress draft directly. CompositionTab unmounts on tab
// switch, so its state can't live inside that component if the
// preview needs to track it across tab changes.

interface CompositionDraftState {
  draftRows: CompositionRow[]
  setDraftRows: React.Dispatch<React.SetStateAction<CompositionRow[]>>
  draftCanvasConfig: CompositionRecord["canvas_config"]
  setDraftCanvasConfig: React.Dispatch<
    React.SetStateAction<CompositionRecord["canvas_config"]>
  >
  activeRow: CompositionRecord | null
  setActiveRow: React.Dispatch<React.SetStateAction<CompositionRecord | null>>
  resolved: ResolvedComposition | null
  isLoading: boolean
  loadError: string | null
  isSaving: boolean
  setIsSaving: React.Dispatch<React.SetStateAction<boolean>>
  saveError: string | null
  setSaveError: React.Dispatch<React.SetStateAction<string | null>>
  hasUnsaved: boolean
}


function useCompositionDraft(
  compositionFocusType: string | null,
  scope: Scope,
  vertical: string,
  tenantId: string,
): CompositionDraftState {
  const [resolved, setResolved] = useState<ResolvedComposition | null>(null)
  const [activeRow, setActiveRow] = useState<CompositionRecord | null>(null)
  const [draftRows, setDraftRows] = useState<CompositionRow[]>([])
  const [draftCanvasConfig, setDraftCanvasConfig] = useState<
    CompositionRecord["canvas_config"]
  >(defaultCanvasConfig())
  const [isLoading, setIsLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    if (!compositionFocusType) {
      setResolved(null)
      setActiveRow(null)
      setDraftRows([])
      setDraftCanvasConfig(defaultCanvasConfig())
      return
    }
    let cancelled = false
    setIsLoading(true)
    setLoadError(null)
    const resolveParams: Parameters<typeof focusCompositionsService.resolve>[0] = {
      focus_type: compositionFocusType,
    }
    if (scope === "vertical_default") resolveParams.vertical = vertical
    if (scope === "tenant_override") resolveParams.tenant_id = tenantId

    Promise.all([
      focusCompositionsService.resolve(resolveParams),
      focusCompositionsService.list({
        scope,
        focus_type: compositionFocusType,
        ...(scope === "vertical_default" ? { vertical } : {}),
        ...(scope === "tenant_override" ? { tenant_id: tenantId } : {}),
      }),
    ])
      .then(([res, rows]) => {
        if (cancelled) return
        setResolved(res)
        const active = rows.find((r) => r.is_active) ?? null
        setActiveRow(active)
        // R-3.1: API returns rows-shape and the editor authors rows
        // directly. No translation needed.
        if (active) {
          setDraftRows(active.rows ?? [])
          setDraftCanvasConfig({ ...(active.canvas_config ?? {}) })
        } else {
          setDraftRows([])
          setDraftCanvasConfig(defaultCanvasConfig())
        }
      })
      .catch((err) => {
        if (cancelled) return
        // eslint-disable-next-line no-console
        console.error("[focus-editor] composition load failed", err)
        setLoadError(err instanceof Error ? err.message : "Failed to load")
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [compositionFocusType, scope, vertical, tenantId])

  const persistedSnapshot = useMemo(() => {
    if (!activeRow) return JSON.stringify([[], defaultCanvasConfig()])
    return JSON.stringify([activeRow.rows ?? [], activeRow.canvas_config ?? {}])
  }, [activeRow])
  const draftSnapshot = useMemo(
    () => JSON.stringify([draftRows, draftCanvasConfig]),
    [draftRows, draftCanvasConfig],
  )
  const hasUnsaved = persistedSnapshot !== draftSnapshot

  return {
    draftRows,
    setDraftRows,
    draftCanvasConfig,
    setDraftCanvasConfig,
    activeRow,
    setActiveRow,
    resolved,
    isLoading,
    loadError,
    isSaving,
    setIsSaving,
    saveError,
    setSaveError,
    hasUnsaved,
  }
}


export default function FocusEditorPage() {
  // Studio 1a-i.B — hide editor's own left pane when mounted inside the
  // Studio shell with the rail expanded. Standalone-mount callers keep
  // the left pane visible (context defaults to railExpanded=false,
  // inStudioContext=false).
  const { railExpanded, inStudioContext } = useStudioRail()
  const hideLeftPane = railExpanded && inStudioContext

  // ── Arc 3a: Bidirectional deep-link via return_to URL param ──
  //
  // When opened from the runtime editor inspector's Focus tab via the
  // "Open in full editor" deep-link, the URL carries `return_to` and
  // optionally `focus_type` + `composition_id`. We render a "Back to
  // runtime editor" affordance that navigates the operator back with
  // their inspector state preserved (return_to encoded the full
  // pathname + search). When launched directly (no return_to), the
  // affordance is hidden and behavior is identical to pre-Arc-3a.
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const returnTo = searchParams.get("return_to")
  const initialFocusType = searchParams.get("focus_type")
  void searchParams.get("composition_id") // reserved: per-composition pre-select is forward-compat scaffolding

  // ── Selection ────────────────────────────────────────────
  const [search, setSearch] = useState("")
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(
    "decision",
  )
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(
    null,
  )

  // Arc 3a: when launched via deep-link with focus_type, pre-select
  // the focus-template registry entry whose compositionFocusType
  // matches. Runs once on mount per URL param shape; legacy
  // navigation (no focus_type) leaves default selection intact.
  useEffect(() => {
    if (!initialFocusType) return
    const all = getAllRegistered()
    const match = all.find((entry) => {
      if (entry.metadata.type !== "focus-template") return false
      const ext = entry.metadata.extensions as
        | Record<string, unknown>
        | undefined
      return ext?.compositionFocusType === initialFocusType
    })
    if (match) {
      setSelectedTemplateId(match.metadata.name)
      const ext = match.metadata.extensions as
        | Record<string, unknown>
        | undefined
      const cat = (ext?.focusType as string | undefined) ?? null
      if (cat) setSelectedCategoryId(cat)
    }
    // initialFocusType is a URL-param-derived stable string; we
    // deliberately omit it from deps after the initial pass to avoid
    // re-running on every renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Right rail tab ───────────────────────────────────────
  const [tab, setTab] = useState<RightTab>("configuration")

  // ── Scope ────────────────────────────────────────────────
  const [scope, setScope] = useState<Scope>("vertical_default")
  const [vertical, setVertical] = useState<string>("funeral_home")
  const [tenantId, setTenantId] = useState<string>("")
  const [selectedTenant, setSelectedTenant] = useState<TenantSummary | null>(null)

  // ── Preview state ────────────────────────────────────────
  const [previewMode, setPreviewMode] = useState<PreviewMode>("light")
  const [scenario, setScenario] = useState<SampleScenario>("default")

  // Browser data — hierarchical categories (Focus types) + templates
  // (focus-template registry entries with extensions.focusType).
  const { categories, templates } = useMemo(() => {
    const cats: HierarchicalCategory[] = FOCUS_TYPES.map((ft) => ({
      id: ft.id,
      label: ft.label,
      description: ft.description,
    }))
    const all = getAllRegistered()
    const tmpls: HierarchicalTemplate[] = all
      .filter((entry) => entry.metadata.type === "focus-template")
      .map((entry) => {
        const focusType = String(
          (entry.metadata.extensions as Record<string, unknown> | undefined)
            ?.focusType ?? "",
        ) as FocusType
        return {
          id: entry.metadata.name,
          label: entry.metadata.displayName,
          description: entry.metadata.description,
          categoryId: focusType,
        }
      })
      .filter((t) => FOCUS_TYPES.some((ft) => ft.id === t.categoryId))
    return { categories: cats, templates: tmpls }
  }, [])

  const handleSelectCategory = useCallback((id: string) => {
    setSelectedCategoryId(id)
    setSelectedTemplateId(null)
    setTab("configuration")
  }, [])

  const handleSelectTemplate = useCallback((id: string) => {
    setSelectedTemplateId(id)
    // Find the template's category and set it as well so the
    // category context is visible in the browser.
    const tmpl = templates.find((t) => t.id === id)
    if (tmpl) setSelectedCategoryId(tmpl.categoryId)
    setTab("configuration")
  }, [templates])

  const selectedTemplateEntry = useMemo<RegistryEntry | null>(() => {
    if (!selectedTemplateId) return null
    return getByName("focus-template", selectedTemplateId) ?? null
  }, [selectedTemplateId])

  const compositionFocusType = useMemo<string | null>(() => {
    if (!selectedTemplateEntry) return null
    const ext = selectedTemplateEntry.metadata.extensions as
      | Record<string, unknown>
      | undefined
    return (ext?.compositionFocusType as string | undefined) ?? null
  }, [selectedTemplateEntry])

  // ── Composition draft state (lifted; preview reads it directly) ──
  const compositionDraft = useCompositionDraft(
    compositionFocusType,
    scope,
    vertical,
    tenantId,
  )

  return (
    <div
      className="flex h-[calc(100vh-3rem)] w-full flex-col"
      data-testid="focus-editor"
    >
      {/* Arc 3a: return-to banner — visible only when launched via
          inspector deep-link. Decoded URL navigates back; inspector
          state is preserved because the runtime editor route stayed
          mounted in the originating tab. */}
      {returnTo && (
        <div
          className="flex items-center justify-between border-b border-border-subtle bg-accent-subtle/30 px-4 py-2"
          data-testid="focus-editor-return-to-banner"
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
            data-testid="focus-editor-return-to-back"
          >
            <ArrowLeft size={12} />
            Back to runtime editor
          </button>
          <span className="text-caption text-content-muted">
            Inspector state preserved on return
          </span>
        </div>
      )}
      <div className="flex flex-1 overflow-hidden">
        {/* ── LEFT: Hierarchical browser ─────────────────── */}
        {!hideLeftPane && (
          <aside
            className="flex w-[320px] flex-shrink-0 flex-col border-r border-border-subtle bg-surface-elevated"
            data-testid="focus-editor-browser"
          >
            <div className="border-b border-border-subtle px-3 py-2">
              <div className="text-h4 font-plex-serif text-content-strong">
                Focus templates
              </div>
              <div className="text-caption text-content-muted">
                5 Focus types · {templates.length} templates
              </div>
            </div>
            <div className="flex-1 overflow-hidden">
              <HierarchicalEditorBrowser
                categories={categories}
                templates={templates}
                selectedCategoryId={selectedCategoryId}
                selectedTemplateId={selectedTemplateId}
                search={search}
                onSearchChange={setSearch}
                onSelectCategory={handleSelectCategory}
                onSelectTemplate={handleSelectTemplate}
                searchPlaceholder="Filter Focus types + templates"
              />
            </div>
          </aside>
        )}

        {/* ── CENTER: Preview ─────────────────────────── */}
        <main
          className="relative flex flex-1 flex-col overflow-hidden bg-surface-sunken"
          data-testid="focus-editor-preview-pane"
        >
          <div className="flex items-center justify-between border-b border-border-subtle bg-surface-elevated px-4 py-2">
            <div className="flex items-center gap-3">
              {selectedTemplateEntry ? (
                <span
                  className="text-body-sm font-medium text-content-strong"
                  data-testid="focus-preview-template-label"
                >
                  {selectedTemplateEntry.metadata.displayName}
                </span>
              ) : selectedCategoryId ? (
                <span
                  className="text-body-sm font-medium text-content-strong"
                  data-testid="focus-preview-category-label"
                >
                  {FOCUS_TYPES.find((ft) => ft.id === selectedCategoryId)?.label}
                </span>
              ) : (
                <span className="text-body-sm text-content-muted">
                  Select a Focus type or template
                </span>
              )}
              <Badge variant="outline">{scope.replace("_", " ")}</Badge>
              {scope === "vertical_default" && (
                <Badge variant="outline">{vertical}</Badge>
              )}
            </div>
            <button
              type="button"
              onClick={() =>
                setPreviewMode((m) => (m === "light" ? "dark" : "light"))
              }
              className="flex items-center gap-1 rounded-sm border border-border-base px-2 py-1 text-caption text-content-strong hover:bg-accent-subtle/40"
              data-testid="focus-preview-mode-toggle"
            >
              {previewMode === "light" ? <Sun size={12} /> : <Moon size={12} />}
              {previewMode}
            </button>
          </div>
          <div
            className="flex-1 overflow-auto p-4"
            data-mode={previewMode}
            data-testid="focus-preview-area"
          >
            {selectedTemplateEntry ? (
              <FocusTemplatePreview
                template={selectedTemplateEntry}
                compositionFocusType={compositionFocusType}
                vertical={
                  scope === "vertical_default" ? vertical : null
                }
                draftRows={compositionDraft.draftRows}
                draftCanvasConfig={compositionDraft.draftCanvasConfig}
                scenario={scenario}
              />
            ) : (
              <CategoryPreview
                focusType={selectedCategoryId as FocusType | null}
              />
            )}
          </div>
        </main>

        {/* ── RIGHT: Editor controls ─────────────────── */}
        <aside
          className="flex w-[360px] flex-shrink-0 flex-col border-l border-border-subtle bg-surface-elevated"
          data-testid="focus-editor-controls"
        >
          {/* Top scope bar */}
          <div className="border-b border-border-subtle px-3 py-2">
            <label className="mb-1 block text-micro uppercase tracking-wider text-content-muted">
              Scope
            </label>
            <select
              value={scope}
              onChange={(e) => setScope(e.target.value as Scope)}
              className="w-full rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-strong"
              data-testid="focus-scope-selector"
            >
              <option value="platform_default">Platform default</option>
              <option value="vertical_default">Vertical default</option>
              <option value="tenant_override">Tenant override</option>
            </select>
            {scope === "vertical_default" && (
              <select
                value={vertical}
                onChange={(e) => setVertical(e.target.value)}
                className="mt-1.5 w-full rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-strong"
              >
                {VERTICALS.map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            )}
            {scope === "tenant_override" && (
              <div className="mt-1.5">
                <TenantPicker
                  selected={selectedTenant}
                  onSelect={(t) => {
                    setSelectedTenant(t)
                    setTenantId(t?.id ?? "")
                  }}
                />
              </div>
            )}
          </div>

          {/* Tab selector — only when a template is selected */}
          {selectedTemplateEntry && (
            <div
              className="flex items-center gap-0.5 border-b border-border-subtle px-2 py-1"
              data-testid="focus-editor-tabs"
            >
              {(
                [
                  ["configuration", "Configuration", SettingsIcon],
                  ["composition", "Composition", Grid3x3],
                  ["preview-settings", "Preview", Sliders],
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
                  data-testid={`focus-tab-${id}`}
                  data-active={tab === id ? "true" : "false"}
                >
                  <Icon size={11} />
                  {label}
                </button>
              ))}
            </div>
          )}

          {/* Pane content */}
          <div className="flex-1 overflow-y-auto" data-testid="focus-editor-content">
            {selectedTemplateEntry ? (
              tab === "configuration" ? (
                <ConfigurationTab
                  template={selectedTemplateEntry}
                  scope={scope}
                  vertical={vertical}
                  tenantId={tenantId}
                />
              ) : tab === "composition" ? (
                <CompositionTab
                  compositionFocusType={compositionFocusType}
                  scope={scope}
                  vertical={vertical}
                  tenantId={tenantId}
                  state={compositionDraft}
                />
              ) : (
                <PreviewSettingsTab
                  previewMode={previewMode}
                  setPreviewMode={setPreviewMode}
                  vertical={vertical}
                  setVertical={setVertical}
                  scenario={scenario}
                  setScenario={setScenario}
                  templateName={selectedTemplateEntry.metadata.name}
                />
              )
            ) : selectedCategoryId ? (
              <CategoryConfigPlaceholder
                focusType={selectedCategoryId as FocusType}
              />
            ) : (
              <div className="px-3 py-6 text-center text-caption text-content-muted">
                Select a Focus type or template to begin editing.
              </div>
            )}
          </div>

          <div className="border-t border-border-subtle px-3 py-2">
            <Link
              to={adminPath("/visual-editor/widgets")}
              className="flex items-center justify-center gap-1 rounded-sm py-1.5 text-caption text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong"
            >
              <ArrowLeftRight size={11} />
              Edit widgets used in compositions
            </Link>
          </div>
        </aside>
      </div>
    </div>
  )
}


// ─── Preview helpers ────────────────────────────────────────


function CategoryPreview({ focusType }: { focusType: FocusType | null }) {
  if (!focusType) {
    return (
      <div className="flex h-full items-center justify-center text-content-muted">
        Select a Focus type to see the type-level preview.
      </div>
    )
  }
  return (
    <FocusContextFrame focusType={focusType}>
      <div
        className="flex h-full flex-col items-center justify-center p-8 text-center text-content-muted"
        data-testid={`focus-category-preview-${focusType}`}
      >
        <div className="text-h3 font-plex-serif text-content-strong">
          {FOCUS_TYPES.find((ft) => ft.id === focusType)?.label}
        </div>
        <div className="mt-2 max-w-md text-body-sm">
          Class-level configuration affects every Focus of this type.
          Concrete templates inherit type-level defaults and may
          override per-template via the Configuration tab.
        </div>
      </div>
    </FocusContextFrame>
  )
}


function FocusTemplatePreview({
  template,
  compositionFocusType,
  vertical,
  draftRows,
  draftCanvasConfig,
  scenario,
}: {
  template: RegistryEntry
  compositionFocusType: string | null
  vertical: string | null
  draftRows: CompositionRow[]
  draftCanvasConfig: CompositionRecord["canvas_config"]
  scenario: SampleScenario
}) {
  const focusType = String(
    (template.metadata.extensions as Record<string, unknown> | undefined)
      ?.focusType ?? "decision",
  ) as FocusType

  // Synthesize a ResolvedComposition from the editor's in-progress
  // draft. The preview renders the draft directly — saves don't have
  // to round-trip through the API for the preview to update.
  const draftComposition = useMemo<ResolvedComposition | null>(() => {
    if (!compositionFocusType) return null
    return compositionDraftAsResolved(draftRows, draftCanvasConfig, vertical)
  }, [compositionFocusType, draftRows, draftCanvasConfig, vertical])

  // ── Funeral-scheduling: faithful preview via harness ─────────
  // The funeral-scheduling Focus has a real production core
  // (SchedulingKanbanCore) and an accessory composition layer. The
  // harness renders structurally-faithful kanban using REAL
  // DeliveryCard + DateBox sub-components fed by mock data — same
  // visual fidelity as production at the atomic level, without
  // mounting the 1,714-LOC orchestrator with its provider tree.
  if (template.metadata.name === "funeral-scheduling") {
    return (
      <FocusContextFrame focusType={focusType}>
        <div
          className="h-full p-4"
          data-testid={`focus-template-preview-${template.metadata.name}`}
        >
          <FuneralSchedulingPreviewHarness
            scenario={scenario}
            compositionDraft={draftComposition}
          />
        </div>
      </FocusContextFrame>
    )
  }

  // ── Other templates: generic placeholder ─────────────────────
  // Triage + Arrangement Scribe + future Focus templates stay on
  // the generic placeholder until their cores are built. When a
  // new template ships, replicate the funeral-scheduling pattern:
  // build a per-template harness in `focus-editor/`, dispatch on
  // template.metadata.name above.
  return (
    <FocusContextFrame focusType={focusType}>
      <div
        className="flex h-full gap-3 p-4"
        data-testid={`focus-template-preview-${template.metadata.name}`}
      >
        <div
          className="flex flex-1 items-center justify-center rounded-md border border-dashed border-border-subtle bg-surface-base p-6 text-center"
          data-testid="focus-preview-core-region"
        >
          <div>
            <div className="text-h4 font-plex-serif text-content-strong">
              {template.metadata.displayName}
            </div>
            <div className="mt-2 max-w-sm text-caption text-content-muted">
              Bespoke Focus core (rendered by code at runtime).
              Operational behavior — drag-drop, finalize, scribe input,
              decision commit — lives in the production component, not in
              the composition.
            </div>
            <div className="mt-2 text-caption text-content-subtle">
              Faithful editor preview will land when this Focus core
              ships; until then, the placeholder above represents where
              the bespoke surface renders at runtime.
            </div>
          </div>
        </div>
        {(() => {
          // R-3.0: count placements across all rows in the rows-shape
          // composition; the placeholder rail summarizes accessory
          // widgets without grid coords (rows model is row-implicit).
          const allPlacements =
            draftComposition?.rows.flatMap((r) => r.placements) ?? []
          if (allPlacements.length === 0) return null
          return (
            <aside
              className="w-72 flex-shrink-0 overflow-y-auto rounded-md border border-border-subtle bg-surface-elevated"
              data-testid="focus-preview-accessory-region"
            >
              <div className="border-b border-border-subtle bg-surface-sunken px-3 py-1.5 text-caption font-medium text-content-strong">
                Accessory layer ({allPlacements.length} widgets)
              </div>
              <div className="p-2">
                {draftComposition?.rows.map((row, rowIdx) => (
                  <div
                    key={row.row_id}
                    className="mb-3"
                    data-testid={`focus-preview-row-${row.row_id}`}
                  >
                    <div className="mb-1 text-micro uppercase tracking-wider text-content-subtle">
                      Row {rowIdx + 1} ({row.column_count}-col)
                    </div>
                    {row.placements.map((p) => (
                      <div
                        key={p.placement_id}
                        className="mb-2 rounded-sm border border-border-subtle bg-surface-base p-2 text-caption"
                        data-testid={`focus-preview-placement-${p.placement_id}`}
                      >
                        <div className="font-medium text-content-strong">
                          {p.component_name}
                        </div>
                        <div className="text-content-muted">
                          {p.component_kind} · col{" "}
                          {p.starting_column + 1}–
                          {p.starting_column + p.column_span}
                        </div>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </aside>
          )
        })()}
      </div>
    </FocusContextFrame>
  )
}


// ─── Right-rail tab content ────────────────────────────────


function ConfigurationTab({
  template,
  scope,
  vertical,
  tenantId,
}: {
  template: RegistryEntry
  scope: Scope
  vertical: string
  tenantId: string
}) {
  const [draftOverrides, setDraftOverrides] = useState<PropOverrideMap>({})
  const [activeRow, setActiveRow] = useState<ComponentConfigurationRecord | null>(
    null,
  )
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Reset state when the template/scope changes.
  useEffect(() => {
    setDraftOverrides({})
    setActiveRow(null)
    let cancelled = false
    const listParams: Parameters<typeof componentConfigurationsService.list>[0] = {
      scope,
      component_kind: "focus-template",
      component_name: template.metadata.name,
    }
    if (scope === "vertical_default") listParams.vertical = vertical
    if (scope === "tenant_override") listParams.tenant_id = tenantId
    componentConfigurationsService
      .list(listParams)
      .then((rows) => {
        if (cancelled) return
        const active = rows.find((r) => r.is_active) ?? null
        setActiveRow(active)
        setDraftOverrides({ ...(active?.prop_overrides ?? {}) })
      })
      .catch((err) => {
        // eslint-disable-next-line no-console
        console.warn("[focus-editor] config list failed", err)
      })
    return () => {
      cancelled = true
    }
  }, [template.metadata.name, scope, vertical, tenantId])

  const props = template.metadata.configurableProps ?? {}
  const propEntries = Object.entries(props) as Array<[string, ConfigPropSchema]>

  const persistedOverrides = activeRow?.prop_overrides ?? {}
  const hasUnsaved =
    JSON.stringify(persistedOverrides) !== JSON.stringify(draftOverrides)

  const stack: ConfigStack = useMemo(() => {
    return { ...emptyConfigStack(), draft: draftOverrides }
  }, [draftOverrides])

  const effectiveProps = useMemo(
    () => composeEffectiveProps("focus-template", template.metadata.name, stack),
    [template.metadata.name, stack],
  )

  const handleSave = useCallback(async () => {
    if (!hasUnsaved) return
    setIsSaving(true)
    setSaveError(null)
    try {
      if (activeRow) {
        const updated = await componentConfigurationsService.update(
          activeRow.id,
          draftOverrides,
        )
        setActiveRow(updated)
      } else {
        const created = await componentConfigurationsService.create({
          scope,
          component_kind: "focus-template",
          component_name: template.metadata.name,
          vertical: scope === "vertical_default" ? vertical : null,
          tenant_id: scope === "tenant_override" ? tenantId : null,
          prop_overrides: draftOverrides,
        })
        setActiveRow(created)
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[focus-editor] save failed", err)
      setSaveError(err instanceof Error ? err.message : "Failed to save")
    } finally {
      setIsSaving(false)
    }
  }, [hasUnsaved, activeRow, draftOverrides, scope, vertical, tenantId, template.metadata.name])

  return (
    <div data-testid="focus-config-tab">
      {/* Save bar */}
      <div className="flex items-center justify-between border-b border-border-subtle bg-surface-elevated px-3 py-2">
        <div className="flex items-center gap-1.5">
          {hasUnsaved && (
            <Badge variant="warning" data-testid="focus-config-unsaved">
              unsaved
            </Badge>
          )}
          {isSaving && (
            <Loader2 size={12} className="animate-spin text-content-muted" />
          )}
          {saveError && (
            <span className="text-caption text-status-error">{saveError}</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="ghost"
            onClick={() =>
              setDraftOverrides({ ...(activeRow?.prop_overrides ?? {}) })
            }
            disabled={!hasUnsaved}
            data-testid="focus-config-discard"
          >
            <Undo2 size={12} />
          </Button>
          <Button
            size="sm"
            onClick={() => void handleSave()}
            disabled={!hasUnsaved}
            data-testid="focus-config-save"
          >
            <Save size={12} className="mr-1" />
            Save
          </Button>
        </div>
      </div>

      {propEntries.length === 0 ? (
        <div className="px-3 py-6 text-center text-caption text-content-muted">
          This template declares no configurable props.
        </div>
      ) : (
        propEntries.map(([name, schema]) => {
          const source = resolvePropSource(name, stack)
          const value = effectiveProps[name]
          const isOverridden = name in draftOverrides
          return (
            <div
              key={name}
              className="border-b border-border-subtle px-2 py-1.5"
              data-testid={`focus-prop-${name}`}
            >
              <CompactPropControl
                name={name}
                schema={schema}
                value={value}
                source={source}
                onChange={(next) =>
                  setDraftOverrides((cur) => ({ ...cur, [name]: next }))
                }
                isOverriddenAtCurrentScope={isOverridden}
                onReset={() =>
                  setDraftOverrides((cur) => {
                    const next = { ...cur }
                    delete next[name]
                    return next
                  })
                }
              />
            </div>
          )
        })
      )}
    </div>
  )
}


function CompositionTab({
  compositionFocusType,
  scope,
  vertical,
  tenantId,
  state,
}: {
  compositionFocusType: string | null
  scope: Scope
  vertical: string
  tenantId: string
  state: CompositionDraftState
}) {
  // State lifted to FocusEditorPage; this component is now purely
  // presentational + handles save/palette/canvas interactions.
  const {
    draftRows,
    setDraftRows,
    draftCanvasConfig,
    activeRow,
    setActiveRow,
    resolved,
    isLoading,
    loadError,
    isSaving,
    setIsSaving,
    saveError,
    setSaveError,
    hasUnsaved,
  } = state

  // R-3.1: Selection union ({none|placement|placements-multi|row}).
  const [selection, setSelection] = useState<Selection>({ kind: "none" })

  const selectedPlacementIds = useMemo(
    () => selection.placementIds ?? new Set<string>(),
    [selection],
  )

  // Component palette
  const palette = useMemo(() => getCanvasPlaceableComponents(), [])

  // Delete-row confirmation modal
  const [deleteRowConfirm, setDeleteRowConfirm] = useState<{
    rowId: string
    placementCount: number
  } | null>(null)

  const draftSnapshot = useMemo(
    () => JSON.stringify([draftRows, draftCanvasConfig]),
    [draftRows, draftCanvasConfig],
  )

  const handleSave = useCallback(async () => {
    if (!compositionFocusType || !hasUnsaved) return
    setIsSaving(true)
    setSaveError(null)
    try {
      // R-3.1: editor authors rows directly. No legacy wrap.
      if (activeRow) {
        const updated = await focusCompositionsService.update(activeRow.id, {
          rows: draftRows,
          canvas_config: draftCanvasConfig,
        })
        setActiveRow(updated)
      } else {
        const created = await focusCompositionsService.create({
          scope,
          focus_type: compositionFocusType,
          vertical: scope === "vertical_default" ? vertical : null,
          tenant_id: scope === "tenant_override" ? tenantId : null,
          rows: draftRows,
          canvas_config: draftCanvasConfig,
        })
        setActiveRow(created)
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[focus-editor] composition save failed", err)
      setSaveError(err instanceof Error ? err.message : "Failed to save")
    } finally {
      setIsSaving(false)
    }
  }, [
    compositionFocusType,
    hasUnsaved,
    activeRow,
    draftRows,
    draftCanvasConfig,
    scope,
    vertical,
    tenantId,
    setIsSaving,
    setActiveRow,
    setSaveError,
  ])

  const autosaveTimer = useRef<number | null>(null)
  useEffect(() => {
    if (!hasUnsaved) return
    if (autosaveTimer.current !== null) {
      window.clearTimeout(autosaveTimer.current)
    }
    autosaveTimer.current = window.setTimeout(() => void handleSave(), 2000)
    return () => {
      if (autosaveTimer.current !== null) {
        window.clearTimeout(autosaveTimer.current)
      }
    }
  }, [draftSnapshot, hasUnsaved, handleSave])

  // ── Row + placement handlers ─────────────────────────────
  const handleAddRow = useCallback(
    (insertIndex: number, columnCount = 12) => {
      const newRow = makeRow(columnCount)
      setDraftRows((cur) => {
        const next = [...cur]
        next.splice(insertIndex, 0, newRow)
        return next
      })
      setSelection({ kind: "row", rowId: newRow.row_id })
    },
    [setDraftRows],
  )

  const handleAddRowAbove = useCallback(
    (rowIndex: number) => handleAddRow(rowIndex),
    [handleAddRow],
  )
  const handleAddRowBelow = useCallback(
    (rowIndex: number) => handleAddRow(rowIndex + 1),
    [handleAddRow],
  )

  const handleRequestDeleteRow = useCallback(
    (rowId: string) => {
      const row = draftRows.find((r) => r.row_id === rowId)
      if (!row) return
      if (row.placements.length === 0) {
        setDraftRows((cur) => cur.filter((r) => r.row_id !== rowId))
        setSelection({ kind: "none" })
      } else {
        setDeleteRowConfirm({
          rowId,
          placementCount: row.placements.length,
        })
      }
    },
    [draftRows, setDraftRows],
  )

  const handleConfirmDeleteRow = useCallback(() => {
    if (!deleteRowConfirm) return
    setDraftRows((cur) =>
      cur.filter((r) => r.row_id !== deleteRowConfirm.rowId),
    )
    setSelection({ kind: "none" })
    setDeleteRowConfirm(null)
  }, [deleteRowConfirm, setDraftRows])

  const handleReorderRow = useCallback(
    ({ fromIndex, toIndex }: { fromIndex: number; toIndex: number }) => {
      if (fromIndex === toIndex) return
      setDraftRows((cur) => {
        const next = [...cur]
        const [moved] = next.splice(fromIndex, 1)
        next.splice(toIndex, 0, moved)
        return next
      })
    },
    [setDraftRows],
  )

  const handleChangeRowColumnCount = useCallback(
    (rowId: string, newColumnCount: number) => {
      setDraftRows((cur) =>
        cur.map((r) =>
          r.row_id === rowId ? { ...r, column_count: newColumnCount } : r,
        ),
      )
    },
    [setDraftRows],
  )

  const handleAddPlacement = useCallback(
    (entry: RegistryEntry) => {
      const meta = getCanvasMetadata(entry)
      setDraftRows((cur) => {
        let rows = [...cur]
        let targetRowId: string
        if (selection.kind === "row" && selection.rowId) {
          targetRowId = selection.rowId
        } else if (rows.length > 0) {
          targetRowId = rows[rows.length - 1].row_id
        } else {
          const newRow = makeRow(12)
          rows = [newRow]
          targetRowId = newRow.row_id
        }
        const targetIdx = rows.findIndex((r) => r.row_id === targetRowId)
        const targetRow = rows[targetIdx]
        const span = Math.min(
          meta.defaultDimensions.columns,
          targetRow.column_count,
        )
        let startingColumn = findAvailableStartingColumn(targetRow, span)
        if (startingColumn < 0) {
          const newRow = makeRow(targetRow.column_count)
          rows = [
            ...rows.slice(0, targetIdx + 1),
            newRow,
            ...rows.slice(targetIdx + 1),
          ]
          targetRowId = newRow.row_id
          startingColumn = 0
        }
        const newPlacement: Placement = {
          placement_id: nextPlacementId(rows),
          component_kind: entry.metadata.type as ComponentKind,
          component_name: entry.metadata.name,
          starting_column: startingColumn,
          column_span: span,
          prop_overrides: {},
          display_config: { show_header: true, show_border: true },
          nested_rows: null,
        }
        rows = rows.map((r) =>
          r.row_id === targetRowId
            ? { ...r, placements: [...r.placements, newPlacement] }
            : r,
        )
        setSelection({
          kind: "placement",
          placementIds: new Set([newPlacement.placement_id]),
        })
        return rows
      })
    },
    [selection, setDraftRows],
  )

  const handleDeleteSelected = useCallback(() => {
    const ids = selectedPlacementIds
    if (ids.size === 0) return
    setDraftRows((cur) =>
      cur.map((r) => ({
        ...r,
        placements: r.placements.filter((p) => !ids.has(p.placement_id)),
      })),
    )
    setSelection({ kind: "none" })
  }, [selectedPlacementIds, setDraftRows])

  const handleCommitPlacementMove = useCallback(
    (input: {
      placementId: string
      sourceRowId: string
      targetRowId: string
      newStartingColumn: number
      siblingMoves: Array<{
        placementId: string
        newStartingColumn: number
      }>
    }) => {
      const { placementId, sourceRowId, targetRowId, newStartingColumn, siblingMoves } =
        input
      setDraftRows((cur) => {
        if (sourceRowId === targetRowId) {
          return cur.map((r) => {
            if (r.row_id !== sourceRowId) return r
            return {
              ...r,
              placements: r.placements.map((p) => {
                if (p.placement_id === placementId) {
                  return { ...p, starting_column: newStartingColumn }
                }
                const sib = siblingMoves.find(
                  (m) => m.placementId === p.placement_id,
                )
                if (sib) {
                  return { ...p, starting_column: sib.newStartingColumn }
                }
                return p
              }),
            }
          })
        }
        const moved = cur
          .find((r) => r.row_id === sourceRowId)
          ?.placements.find((p) => p.placement_id === placementId)
        if (!moved) return cur
        return cur.map((r) => {
          if (r.row_id === sourceRowId) {
            return {
              ...r,
              placements: r.placements.filter(
                (p) => p.placement_id !== placementId,
              ),
            }
          }
          if (r.row_id === targetRowId) {
            return {
              ...r,
              placements: [
                ...r.placements,
                { ...moved, starting_column: newStartingColumn },
              ],
            }
          }
          return r
        })
      })
    },
    [setDraftRows],
  )

  const handleCommitPlacementResize = useCallback(
    (input: {
      placementId: string
      rowId: string
      newStartingColumn: number
      newColumnSpan: number
    }) => {
      setDraftRows((cur) =>
        cur.map((r) => {
          if (r.row_id !== input.rowId) return r
          return {
            ...r,
            placements: r.placements.map((p) =>
              p.placement_id === input.placementId
                ? {
                    ...p,
                    starting_column: input.newStartingColumn,
                    column_span: input.newColumnSpan,
                  }
                : p,
            ),
          }
        }),
      )
    },
    [setDraftRows],
  )

  if (!compositionFocusType) {
    return (
      <div className="px-3 py-6 text-caption text-content-muted">
        This template doesn't declare a compositionFocusType in its
        registration extensions. Composition authoring requires the
        template to opt into the composition runtime.
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col" data-testid="focus-composition-tab">
      {/* Save bar */}
      <div className="flex items-center justify-between border-b border-border-subtle bg-surface-elevated px-3 py-2">
        <div className="flex items-center gap-1.5">
          {hasUnsaved && (
            <Badge variant="warning" data-testid="composition-unsaved-badge">
              unsaved
            </Badge>
          )}
          {isLoading && (
            <Loader2 size={12} className="animate-spin text-content-muted" />
          )}
          {isSaving && (
            <Loader2 size={12} className="animate-spin text-content-muted" />
          )}
          {(loadError || saveError) && (
            <span className="flex items-center gap-1 text-caption text-status-error">
              <AlertCircle size={12} />
              {loadError ?? saveError}
            </span>
          )}
          {resolved?.source && (
            <Badge variant="outline">source: {resolved.source}</Badge>
          )}
        </div>
        <Button
          size="sm"
          onClick={() => void handleSave()}
          disabled={!hasUnsaved}
          data-testid="composition-save-button"
        >
          <Save size={12} className="mr-1" />
          Save
        </Button>
      </div>

      {/* Canvas — row-aware placement editor */}
      <div className="flex-1 overflow-hidden bg-surface-sunken" data-testid="composition-canvas-area">
        <InteractivePlacementCanvas
          rows={draftRows}
          gapSize={draftCanvasConfig.gap_size ?? 12}
          backgroundTreatment={draftCanvasConfig.background_treatment}
          selection={selection}
          showGrid={true}
          interactionsEnabled={!isSaving}
          onSelectPlacement={(id, opts) => {
            setSelection((prev) => {
              const prevIds = prev.placementIds ?? new Set<string>()
              if (opts.shift) {
                const next = new Set(prevIds)
                if (next.has(id)) next.delete(id)
                else next.add(id)
                if (next.size === 0) return { kind: "none" }
                if (next.size === 1)
                  return { kind: "placement", placementIds: next }
                return { kind: "placements-multi", placementIds: next }
              }
              return { kind: "placement", placementIds: new Set([id]) }
            })
          }}
          onSelectRow={(rowId) => setSelection({ kind: "row", rowId })}
          onDeselectAll={() => setSelection({ kind: "none" })}
          onCommitPlacementMove={handleCommitPlacementMove}
          onCommitPlacementResize={handleCommitPlacementResize}
          onCommitRowReorder={handleReorderRow}
          onMarqueeSelect={(ids) => {
            if (ids.length === 0) {
              setSelection({ kind: "none" })
            } else if (ids.length === 1) {
              setSelection({ kind: "placement", placementIds: new Set(ids) })
            } else {
              setSelection({
                kind: "placements-multi",
                placementIds: new Set(ids),
              })
            }
          }}
          onAddRowAbove={handleAddRowAbove}
          onAddRowBelow={handleAddRowBelow}
          onDeleteRow={handleRequestDeleteRow}
          onChangeRowColumnCount={handleChangeRowColumnCount}
        />
      </div>

      {/* Bottom palette + actions */}
      <div className="border-t border-border-subtle bg-surface-elevated px-3 py-2">
        <div className="flex items-center justify-between">
          <span className="text-caption text-content-muted">
            {draftRows.length} row{draftRows.length === 1 ? "" : "s"} ·{" "}
            {draftRows.reduce((acc, r) => acc + r.placements.length, 0)}{" "}
            placement
            {draftRows.reduce((acc, r) => acc + r.placements.length, 0) === 1
              ? ""
              : "s"}
            {selectedPlacementIds.size > 0 &&
              ` · ${selectedPlacementIds.size} selected`}
          </span>
          <div className="flex items-center gap-1">
            <Button
              size="sm"
              variant="ghost"
              onClick={() => handleAddRow(draftRows.length, 12)}
              data-testid="composition-add-row-button"
            >
              <Plus size={11} className="mr-1" />
              Add row
            </Button>
            {selectedPlacementIds.size > 0 && (
              <Button
                size="sm"
                variant="ghost"
                onClick={handleDeleteSelected}
                className="text-status-error"
                data-testid="composition-delete-selected"
              >
                <Trash2 size={11} className="mr-1" />
                Delete
              </Button>
            )}
          </div>
        </div>
        <div className="mt-1.5">
          <details>
            <summary className="cursor-pointer text-caption font-medium text-content-strong">
              Add a widget…
            </summary>
            <div className="mt-1.5 max-h-40 overflow-y-auto rounded-sm border border-border-subtle">
              {palette.map((entry) => (
                <button
                  key={`${entry.metadata.type}:${entry.metadata.name}`}
                  type="button"
                  onClick={() => handleAddPlacement(entry)}
                  className="flex w-full items-center gap-2 px-2 py-1 text-left hover:bg-accent-subtle/30"
                  data-testid={`composition-palette-${entry.metadata.name}`}
                >
                  <ComponentThumbnail
                    kind={entry.metadata.type as ComponentKind}
                    componentName={entry.metadata.name}
                  />
                  <span className="flex-1 truncate text-caption text-content-strong">
                    {entry.metadata.displayName}
                  </span>
                  <Plus size={10} className="text-content-muted" />
                </button>
              ))}
            </div>
          </details>
        </div>
      </div>

      {deleteRowConfirm && (
        <div
          className="fixed inset-0 z-[var(--z-modal,80)] flex items-center justify-center bg-black/40 backdrop-blur-sm"
          data-testid="delete-row-confirm-modal"
          onClick={() => setDeleteRowConfirm(null)}
        >
          <div
            className="w-[420px] max-w-[90vw] rounded-lg border border-border-subtle bg-surface-raised p-5 shadow-level-3"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-h4 font-plex-serif font-medium text-content-strong">
              Delete row?
            </div>
            <div className="mt-2 text-caption text-content-muted">
              This row contains {deleteRowConfirm.placementCount} placement
              {deleteRowConfirm.placementCount === 1 ? "" : "s"}. Deleting the
              row will remove{" "}
              {deleteRowConfirm.placementCount === 1 ? "it" : "them"}.
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setDeleteRowConfirm(null)}
                data-testid="delete-row-cancel"
              >
                Cancel
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={handleConfirmDeleteRow}
                data-testid="delete-row-confirm"
              >
                <Trash2 size={11} className="mr-1" />
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}


function PreviewSettingsTab({
  previewMode,
  setPreviewMode,
  vertical,
  setVertical,
  scenario,
  setScenario,
  templateName,
}: {
  previewMode: PreviewMode
  setPreviewMode: (m: PreviewMode) => void
  vertical: string
  setVertical: (v: string) => void
  scenario: SampleScenario
  setScenario: (s: SampleScenario) => void
  templateName: string
}) {
  // Sample scenario picker is currently funeral-scheduling-specific —
  // other Focus templates render the generic placeholder which doesn't
  // consume mock data. Future per-template harnesses extend this gate.
  const supportsScenarios = templateName === "funeral-scheduling"
  return (
    <div className="px-3 py-2" data-testid="focus-preview-settings-tab">
      <div className="text-caption text-content-muted">
        Preview-only settings. Don't persist; only affect how the
        preview renders.
      </div>
      <label className="mt-3 mb-1 block text-micro uppercase tracking-wider text-content-muted">
        Preview mode
      </label>
      <div className="flex gap-1.5">
        {(["light", "dark"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setPreviewMode(m)}
            className={
              previewMode === m
                ? "flex-1 rounded-sm bg-accent-subtle px-2 py-1 text-caption font-medium text-content-strong"
                : "flex-1 rounded-sm border border-border-base px-2 py-1 text-caption text-content-muted hover:text-content-strong"
            }
          >
            {m}
          </button>
        ))}
      </div>
      <label className="mt-3 mb-1 block text-micro uppercase tracking-wider text-content-muted">
        Sample vertical
      </label>
      <select
        value={vertical}
        onChange={(e) => setVertical(e.target.value)}
        className="w-full rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-strong"
      >
        {VERTICALS.map((v) => (
          <option key={v} value={v}>
            {v}
          </option>
        ))}
      </select>
      {supportsScenarios && (
        <>
          <label className="mt-3 mb-1 block text-micro uppercase tracking-wider text-content-muted">
            Sample data scenario
          </label>
          <SampleScenarioPicker scenario={scenario} onChange={setScenario} />
          <p className="mt-1.5 text-[10px] text-content-subtle">
            Mock data feeds the preview only. Edits don't persist.
          </p>
        </>
      )}
    </div>
  )
}


function CategoryConfigPlaceholder({ focusType }: { focusType: FocusType }) {
  return (
    <div className="px-3 py-4" data-testid={`focus-category-config-${focusType}`}>
      <div className="text-body-sm text-content-strong">
        Class-level Focus configuration
      </div>
      <div className="mt-1 text-caption text-content-muted">
        Type-level configurable props (header treatment, transition
        style, dismiss behavior, accent border) live in the Class
        Editor. Action bar buttons for this Focus type are configured
        in the Class Editor as well — open the <code>focus</code> class
        and edit its <code>buttonSlugs</code> array to compose the
        default action bar, or open the <code>focus-template</code>
        class to override per-template (Arc 4a.1).
      </div>
      <Link
        to={adminPath("/visual-editor/classes")}
        className="mt-3 inline-flex items-center gap-1 rounded-sm border border-border-base px-2 py-1 text-caption text-content-strong hover:bg-accent-subtle/40"
        data-testid="focus-link-to-class-editor"
      >
        <ArrowLeftRight size={11} />
        Open in Class Editor
      </Link>
    </div>
  )
}
