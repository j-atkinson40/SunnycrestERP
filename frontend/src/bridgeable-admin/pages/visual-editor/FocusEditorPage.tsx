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
import { Link } from "react-router-dom"
import {
  AlertCircle,
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
import {
  focusCompositionsService,
} from "@/bridgeable-admin/services/focus-compositions-service"
import {
  componentConfigurationsService,
  type ComponentConfigurationRecord,
} from "@/bridgeable-admin/services/component-configurations-service"
import type {
  CompositionRecord,
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
import { InteractivePlacementCanvas } from "@/bridgeable-admin/components/visual-editor/composition-canvas/InteractivePlacementCanvas"
import {
  TenantPicker,
  type TenantSummary,
} from "@/bridgeable-admin/components/TenantPicker"


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
    total_columns: 1,
    row_height: 64,
    gap_size: 12,
    background_treatment: "surface-base",
  }
}


function nextPlacementId(existing: Placement[]): string {
  let i = existing.length + 1
  while (existing.some((p) => p.placement_id === `p${i}`)) i += 1
  return `p${i}`
}


export default function FocusEditorPage() {
  // ── Selection ────────────────────────────────────────────
  const [search, setSearch] = useState("")
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(
    "decision",
  )
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(
    null,
  )

  // ── Right rail tab ───────────────────────────────────────
  const [tab, setTab] = useState<RightTab>("configuration")

  // ── Scope ────────────────────────────────────────────────
  const [scope, setScope] = useState<Scope>("vertical_default")
  const [vertical, setVertical] = useState<string>("funeral_home")
  const [tenantId, setTenantId] = useState<string>("")
  const [selectedTenant, setSelectedTenant] = useState<TenantSummary | null>(null)

  // ── Preview state ────────────────────────────────────────
  const [previewMode, setPreviewMode] = useState<PreviewMode>("light")

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

  return (
    <div
      className="flex h-[calc(100vh-3rem)] w-full flex-col"
      data-testid="focus-editor"
    >
      <div className="flex flex-1 overflow-hidden">
        {/* ── LEFT: Hierarchical browser ─────────────────── */}
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
                tenantId={
                  scope === "tenant_override" ? tenantId : null
                }
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
                />
              ) : (
                <PreviewSettingsTab
                  previewMode={previewMode}
                  setPreviewMode={setPreviewMode}
                  vertical={vertical}
                  setVertical={setVertical}
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
  tenantId,
}: {
  template: RegistryEntry
  compositionFocusType: string | null
  vertical: string | null
  tenantId: string | null
}) {
  const focusType = String(
    (template.metadata.extensions as Record<string, unknown> | undefined)
      ?.focusType ?? "decision",
  ) as FocusType

  const [composition, setComposition] = useState<ResolvedComposition | null>(null)
  useEffect(() => {
    if (!compositionFocusType) {
      setComposition(null)
      return
    }
    let cancelled = false
    const params: Parameters<typeof focusCompositionsService.resolve>[0] = {
      focus_type: compositionFocusType,
    }
    if (vertical) params.vertical = vertical
    if (tenantId) params.tenant_id = tenantId
    focusCompositionsService
      .resolve(params)
      .then((res) => {
        if (!cancelled) setComposition(res)
      })
      .catch((err) => {
        // eslint-disable-next-line no-console
        console.warn("[focus-editor] composition resolve failed", err)
        if (!cancelled) setComposition(null)
      })
    return () => {
      cancelled = true
    }
  }, [compositionFocusType, vertical, tenantId])

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
          </div>
        </div>
        {composition && composition.placements.length > 0 && (
          <aside
            className="w-72 flex-shrink-0 overflow-y-auto rounded-md border border-border-subtle bg-surface-elevated"
            data-testid="focus-preview-accessory-region"
          >
            <div className="border-b border-border-subtle bg-surface-sunken px-3 py-1.5 text-caption font-medium text-content-strong">
              Accessory layer ({composition.placements.length} widgets)
            </div>
            <div className="p-2">
              {composition.placements.map((p) => (
                <div
                  key={p.placement_id}
                  className="mb-2 rounded-sm border border-border-subtle bg-surface-base p-2 text-caption"
                  data-testid={`focus-preview-placement-${p.placement_id}`}
                >
                  <div className="font-medium text-content-strong">
                    {p.component_name}
                  </div>
                  <div className="text-content-muted">
                    {p.component_kind} · row {p.grid.row_start}-
                    {p.grid.row_start + p.grid.row_span}
                  </div>
                </div>
              ))}
            </div>
          </aside>
        )}
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
}: {
  compositionFocusType: string | null
  scope: Scope
  vertical: string
  tenantId: string
}) {
  // Composition state
  const [resolved, setResolved] = useState<ResolvedComposition | null>(null)
  const [activeRow, setActiveRow] = useState<CompositionRecord | null>(null)
  const [draftPlacements, setDraftPlacements] = useState<Placement[]>([])
  const [draftCanvasConfig, setDraftCanvasConfig] = useState<
    CompositionRecord["canvas_config"]
  >(defaultCanvasConfig())
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [isLoading, setIsLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  // Component palette
  const palette = useMemo(() => getCanvasPlaceableComponents(), [])

  // Resolve composition when scope/template changes.
  useEffect(() => {
    if (!compositionFocusType) {
      setResolved(null)
      setActiveRow(null)
      setDraftPlacements([])
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
        if (active) {
          setDraftPlacements([...active.placements])
          setDraftCanvasConfig({ ...active.canvas_config })
        } else {
          setDraftPlacements([])
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

  const persistedSnapshot = useMemo(
    () =>
      activeRow
        ? JSON.stringify([activeRow.placements, activeRow.canvas_config])
        : JSON.stringify([[], defaultCanvasConfig()]),
    [activeRow],
  )
  const draftSnapshot = useMemo(
    () => JSON.stringify([draftPlacements, draftCanvasConfig]),
    [draftPlacements, draftCanvasConfig],
  )
  const hasUnsaved = persistedSnapshot !== draftSnapshot

  const handleSave = useCallback(async () => {
    if (!compositionFocusType || !hasUnsaved) return
    setIsSaving(true)
    setSaveError(null)
    try {
      if (activeRow) {
        const updated = await focusCompositionsService.update(activeRow.id, {
          placements: draftPlacements,
          canvas_config: draftCanvasConfig,
        })
        setActiveRow(updated)
      } else {
        const created = await focusCompositionsService.create({
          scope,
          focus_type: compositionFocusType,
          vertical: scope === "vertical_default" ? vertical : null,
          tenant_id: scope === "tenant_override" ? tenantId : null,
          placements: draftPlacements,
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
    draftPlacements,
    draftCanvasConfig,
    scope,
    vertical,
    tenantId,
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

  const handleAddPlacement = useCallback(
    (entry: RegistryEntry) => {
      const meta = getCanvasMetadata(entry)
      const totalCols = draftCanvasConfig.total_columns ?? 12
      const newPlacement: Placement = {
        placement_id: nextPlacementId(draftPlacements),
        component_kind: entry.metadata.type as ComponentKind,
        component_name: entry.metadata.name,
        grid: {
          column_start: 1,
          column_span: Math.min(meta.defaultDimensions.columns, totalCols),
          row_start: draftPlacements.reduce(
            (m, p) => Math.max(m, p.grid.row_start + p.grid.row_span),
            1,
          ),
          row_span: meta.defaultDimensions.rows,
        },
        prop_overrides: {},
        display_config: { show_header: true, show_border: true },
      }
      setDraftPlacements((cur) => [...cur, newPlacement])
      setSelectedIds(new Set([newPlacement.placement_id]))
    },
    [draftPlacements, draftCanvasConfig.total_columns],
  )

  const handleDeleteSelected = useCallback(() => {
    if (selectedIds.size === 0) return
    setDraftPlacements((cur) =>
      cur.filter((p) => !selectedIds.has(p.placement_id)),
    )
    setSelectedIds(new Set())
  }, [selectedIds])

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

      {/* Canvas — interactive placement editor */}
      <div className="flex-1 overflow-hidden bg-surface-sunken" data-testid="composition-canvas-area">
        <InteractivePlacementCanvas
          placements={draftPlacements}
          totalColumns={draftCanvasConfig.total_columns ?? 12}
          rowHeight={
            typeof draftCanvasConfig.row_height === "number"
              ? draftCanvasConfig.row_height
              : 64
          }
          gapSize={draftCanvasConfig.gap_size ?? 12}
          backgroundTreatment={draftCanvasConfig.background_treatment}
          selectedIds={selectedIds}
          showGrid={true}
          interactionsEnabled={!isSaving}
          onSelect={(id, opts) => {
            setSelectedIds((prev) => {
              if (opts.shift) {
                const next = new Set(prev)
                if (next.has(id)) next.delete(id)
                else next.add(id)
                return next
              }
              return new Set([id])
            })
          }}
          onDeselectAll={() => setSelectedIds(new Set())}
          onPlacementsChange={setDraftPlacements}
        />
      </div>

      {/* Bottom palette + actions */}
      <div className="border-t border-border-subtle bg-surface-elevated px-3 py-2">
        <div className="flex items-center justify-between">
          <span className="text-caption text-content-muted">
            {draftPlacements.length} placement
            {draftPlacements.length === 1 ? "" : "s"}
            {selectedIds.size > 0 && ` · ${selectedIds.size} selected`}
          </span>
          {selectedIds.size > 0 && (
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
    </div>
  )
}


function PreviewSettingsTab({
  previewMode,
  setPreviewMode,
  vertical,
  setVertical,
}: {
  previewMode: PreviewMode
  setPreviewMode: (m: PreviewMode) => void
  vertical: string
  setVertical: (v: string) => void
}) {
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
        Type-level configurable props (header treatment, action bar
        layout, transition style, dismiss behavior, accent border) live
        in the Class Editor.
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
