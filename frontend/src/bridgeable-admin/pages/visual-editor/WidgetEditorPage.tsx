/**
 * WidgetEditorPage — purpose-specific editor for widgets (May 2026
 * reorganization).
 *
 * Replaces the widget-focused portion of the dismantled generic
 * ComponentEditorPage. Two modes via a top-of-page toggle:
 *
 *   "Edit Widgets as Class" — class-level configuration affecting
 *     every widget. Same data and editor surface as Class Editor's
 *     widget class section. Single-pane: controls left, multi-widget
 *     preview right.
 *
 *   "Edit Individual Widgets" — three-pane component editor scoped
 *     to widgets. Browser of registered widgets + DashboardContextFrame
 *     preview + per-widget configurable props.
 *
 * The mode toggle is the structural change — same authoring activities
 * that existed before, presented in one place per Widget context with
 * the class-vs-individual distinction made explicit.
 *
 * Class Editor at /visual-editor/classes remains as the cross-class
 * view; Widget Editor's class mode is an additional path into the
 * same data scoped to widgets specifically.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Link } from "react-router-dom"
import {
  AlertCircle,
  ArrowLeftRight,
  Loader2,
  Moon,
  PanelRightClose,
  PanelRightOpen,
  Save,
  Search,
  Sun,
  Undo2,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import {
  componentClassConfigurationsService,
  type ResolvedClassConfiguration,
  type ClassConfigurationRecord,
} from "@/bridgeable-admin/services/component-class-configurations-service"
import {
  componentConfigurationsService,
  type ResolvedConfiguration,
  type ComponentConfigurationRecord,
} from "@/bridgeable-admin/services/component-configurations-service"
import {
  composeEffectiveProps,
  emptyConfigStack,
  resolvePropSource,
  stackFromResolvedConfig,
  type ConfigStack,
  type PropOverrideMap,
} from "@/lib/visual-editor/components/config-resolver"
import {
  getByName,
  getClassRegistration,
  getComponentsInClass,
  type ConfigPropSchema,
  type RegistryEntry,
} from "@/lib/visual-editor/registry"
import { renderComponentPreview } from "@/lib/visual-editor/components/preview-renderers"
import { CompactPropControl } from "@/bridgeable-admin/components/visual-editor/CompactPropControl"
import { ComponentThumbnail } from "@/bridgeable-admin/components/visual-editor/ComponentThumbnail"
import { DashboardContextFrame } from "@/bridgeable-admin/components/visual-editor/context-frames/DashboardContextFrame"
import {
  TenantPicker,
  type TenantSummary,
} from "@/bridgeable-admin/components/TenantPicker"


type EditMode = "class" | "individual"
type PreviewMode = "light" | "dark"
type Scope = "platform_default" | "vertical_default" | "tenant_override"

const VERTICALS = ["funeral_home", "manufacturing", "cemetery", "crematory"] as const


export default function WidgetEditorPage() {
  const [mode, setMode] = useState<EditMode>("individual")

  return (
    <div
      className="flex h-[calc(100vh-3rem)] w-full flex-col"
      data-testid="widget-editor"
    >
      {/* Top-of-page mode toggle */}
      <div
        className="flex items-center gap-3 border-b border-border-subtle bg-surface-elevated px-6 py-2"
        data-testid="widget-editor-mode-toggle"
      >
        <span className="text-caption text-content-muted">Mode:</span>
        <div className="flex rounded-sm border border-border-base bg-surface-raised p-0.5">
          <button
            type="button"
            onClick={() => setMode("individual")}
            data-testid="widget-mode-individual"
            data-active={mode === "individual" ? "true" : "false"}
            className={
              mode === "individual"
                ? "rounded-sm bg-accent px-3 py-1 text-caption font-medium text-content-on-accent"
                : "rounded-sm px-3 py-1 text-caption text-content-muted hover:text-content-strong"
            }
          >
            Edit Individual Widgets
          </button>
          <button
            type="button"
            onClick={() => setMode("class")}
            data-testid="widget-mode-class"
            data-active={mode === "class" ? "true" : "false"}
            className={
              mode === "class"
                ? "rounded-sm bg-accent px-3 py-1 text-caption font-medium text-content-on-accent"
                : "rounded-sm px-3 py-1 text-caption text-content-muted hover:text-content-strong"
            }
          >
            Edit Widgets as Class
          </button>
        </div>
        <div className="flex-1" />
        <Link
          to={adminPath("/visual-editor/classes")}
          className="flex items-center gap-1 text-caption text-content-muted hover:text-content-strong"
        >
          <ArrowLeftRight size={11} />
          Cross-class editor
        </Link>
      </div>

      {mode === "individual" ? (
        <IndividualWidgetEditor />
      ) : (
        <WidgetClassEditor />
      )}
    </div>
  )
}


// ─── Individual mode ────────────────────────────────────────


function IndividualWidgetEditor() {
  // Load all registered widgets (filter out other kinds).
  const widgets = useMemo<readonly RegistryEntry[]>(() => {
    return getComponentsInClass("widget")
  }, [])

  const [search, setSearch] = useState("")
  const [selectedName, setSelectedName] = useState<string | null>(
    widgets[0]?.metadata.name ?? null,
  )
  const [scope, setScope] = useState<Scope>("platform_default")
  const [vertical, setVertical] = useState<string>("funeral_home")
  const [tenantId, setTenantId] = useState<string>("")
  const [selectedTenant, setSelectedTenant] = useState<TenantSummary | null>(null)
  const [previewMode, setPreviewMode] = useState<PreviewMode>("light")
  const [rightRailCollapsed, setRightRailCollapsed] = useState(false)

  const [resolved, setResolved] = useState<ResolvedConfiguration | null>(null)
  const [activeRow, setActiveRow] = useState<ComponentConfigurationRecord | null>(
    null,
  )
  const [draftOverrides, setDraftOverrides] = useState<PropOverrideMap>({})
  const [isLoading, setIsLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase()
    if (!term) return widgets
    return widgets.filter((w) =>
      `${w.metadata.name} ${w.metadata.displayName}`.toLowerCase().includes(term),
    )
  }, [search, widgets])

  const selectedEntry = useMemo(
    () => (selectedName ? getByName("widget", selectedName) ?? null : null),
    [selectedName],
  )

  // Resolve configuration for the selected widget + scope.
  useEffect(() => {
    if (!selectedName) return
    let cancelled = false
    setIsLoading(true)
    setLoadError(null)
    const resolveParams: Parameters<
      typeof componentConfigurationsService.resolve
    >[0] = {
      component_kind: "widget",
      component_name: selectedName,
    }
    if (scope === "vertical_default") resolveParams.vertical = vertical
    if (scope === "tenant_override") resolveParams.tenant_id = tenantId
    componentConfigurationsService
      .resolve(resolveParams)
      .then((res) => {
        if (cancelled) return
        setResolved(res)
        const listParams: Parameters<
          typeof componentConfigurationsService.list
        >[0] = {
          scope,
          component_kind: "widget",
          component_name: selectedName,
        }
        if (scope === "vertical_default") listParams.vertical = vertical
        if (scope === "tenant_override") listParams.tenant_id = tenantId
        return componentConfigurationsService.list(listParams)
      })
      .then((rows) => {
        if (cancelled || !rows) return
        const active = rows.find((r) => r.is_active) ?? null
        setActiveRow(active)
        setDraftOverrides({ ...(active?.prop_overrides ?? {}) })
      })
      .catch((err) => {
        if (cancelled) return
        // eslint-disable-next-line no-console
        console.error("[widget-editor] resolve failed", err)
        setLoadError(err instanceof Error ? err.message : "Failed to load")
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedName, scope, vertical, tenantId])

  const stack: ConfigStack = useMemo(() => {
    const base = resolved
      ? stackFromResolvedConfig(resolved)
      : emptyConfigStack()
    return { ...base, draft: draftOverrides }
  }, [resolved, draftOverrides])

  const effectiveProps = useMemo(() => {
    if (!selectedEntry) return {}
    return composeEffectiveProps(
      "widget",
      selectedEntry.metadata.name,
      stack,
    )
  }, [selectedEntry, stack])

  const persistedOverrides = activeRow?.prop_overrides ?? {}
  const hasUnsaved =
    JSON.stringify(persistedOverrides) !== JSON.stringify(draftOverrides)

  const handleSave = useCallback(async () => {
    if (!selectedName || !hasUnsaved) return
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
          component_kind: "widget",
          component_name: selectedName,
          vertical: scope === "vertical_default" ? vertical : null,
          tenant_id: scope === "tenant_override" ? tenantId : null,
          prop_overrides: draftOverrides,
        })
        setActiveRow(created)
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[widget-editor] save failed", err)
      setSaveError(err instanceof Error ? err.message : "Failed to save")
    } finally {
      setIsSaving(false)
    }
  }, [
    selectedName,
    hasUnsaved,
    activeRow,
    draftOverrides,
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
    autosaveTimer.current = window.setTimeout(() => {
      void handleSave()
    }, 1500)
    return () => {
      if (autosaveTimer.current !== null) {
        window.clearTimeout(autosaveTimer.current)
      }
    }
  }, [draftOverrides, hasUnsaved, handleSave])

  const handleDiscard = useCallback(() => {
    setDraftOverrides({ ...(activeRow?.prop_overrides ?? {}) })
  }, [activeRow])

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Left — widget browser */}
      <aside
        className="flex w-[320px] flex-shrink-0 flex-col border-r border-border-subtle bg-surface-elevated"
        data-testid="widget-editor-browser"
      >
        <div className="border-b border-border-subtle px-3 py-2">
          <div className="text-h4 font-plex-serif text-content-strong">
            Widgets
          </div>
          <div className="text-caption text-content-muted">
            {widgets.length} registered
          </div>
        </div>
        <div className="border-b border-border-subtle px-2 py-1.5">
          <div className="relative">
            <Search
              size={11}
              className="absolute left-2 top-1/2 -translate-y-1/2 text-content-muted"
            />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter widgets"
              className="h-7 pl-7 text-caption"
              data-testid="widget-browser-search"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-1 py-1">
          {filtered.map((entry) => (
            <button
              key={entry.metadata.name}
              type="button"
              onClick={() => setSelectedName(entry.metadata.name)}
              data-testid={`widget-row-${entry.metadata.name}`}
              data-selected={
                selectedName === entry.metadata.name ? "true" : "false"
              }
              className={
                selectedName === entry.metadata.name
                  ? "flex w-full items-center gap-2 rounded-sm bg-accent-subtle/60 px-2 py-1.5 text-left"
                  : "flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left hover:bg-accent-subtle/30"
              }
            >
              <ComponentThumbnail
                kind="widget"
                componentName={entry.metadata.name}
              />
              <div className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-caption font-medium text-content-strong">
                  {entry.metadata.displayName}
                </span>
                <span className="truncate font-plex-mono text-[10px] text-content-muted">
                  {entry.metadata.name}
                </span>
              </div>
            </button>
          ))}
          {filtered.length === 0 && (
            <div className="px-2 py-6 text-center text-caption text-content-muted">
              No widgets match.
            </div>
          )}
        </div>
      </aside>

      {/* Center — preview */}
      <main
        className="relative flex flex-1 flex-col overflow-hidden bg-surface-sunken"
        data-testid="widget-editor-preview-pane"
      >
        <div className="flex items-center justify-between border-b border-border-subtle bg-surface-elevated px-4 py-2">
          <div className="flex items-center gap-3">
            {selectedEntry && (
              <span className="text-body-sm font-medium text-content-strong">
                {selectedEntry.metadata.displayName}
              </span>
            )}
            <Badge variant="outline">{scope.replace("_", " ")}</Badge>
            {scope === "vertical_default" && (
              <Badge variant="outline">{vertical}</Badge>
            )}
            {isLoading && (
              <Loader2 size={12} className="animate-spin text-content-muted" />
            )}
            {loadError && (
              <span className="flex items-center gap-1 text-caption text-status-error">
                <AlertCircle size={12} />
                {loadError}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() =>
                setPreviewMode((m) => (m === "light" ? "dark" : "light"))
              }
              className="flex items-center gap-1 rounded-sm border border-border-base px-2 py-1 text-caption text-content-strong hover:bg-accent-subtle/40"
              data-testid="widget-preview-mode-toggle"
            >
              {previewMode === "light" ? <Sun size={12} /> : <Moon size={12} />}
              {previewMode}
            </button>
            <button
              type="button"
              onClick={() => setRightRailCollapsed((c) => !c)}
              className="rounded-sm border border-border-base p-1 text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong"
              data-testid="widget-rail-toggle"
            >
              {rightRailCollapsed ? (
                <PanelRightOpen size={14} />
              ) : (
                <PanelRightClose size={14} />
              )}
            </button>
          </div>
        </div>
        <div
          className="flex-1 overflow-auto p-4"
          data-mode={previewMode}
          data-testid="widget-preview-area"
        >
          {selectedEntry ? (
            <DashboardContextFrame>
              <div data-testid="widget-preview-rendering">
                {renderComponentPreview(
                  `widget:${selectedEntry.metadata.name}`,
                  effectiveProps,
                  selectedEntry.metadata.displayName,
                )}
              </div>
            </DashboardContextFrame>
          ) : (
            <div className="flex h-full items-center justify-center text-content-muted">
              Select a widget to begin editing
            </div>
          )}
        </div>
      </main>

      {/* Right — config controls */}
      <aside
        className={
          rightRailCollapsed
            ? "flex w-12 flex-shrink-0 flex-col border-l border-border-subtle bg-surface-elevated"
            : "flex w-[320px] flex-shrink-0 flex-col border-l border-border-subtle bg-surface-elevated"
        }
        data-testid="widget-editor-controls"
      >
        {rightRailCollapsed ? (
          <div className="flex flex-1 flex-col items-center gap-2 py-3">
            <button
              type="button"
              onClick={() => setRightRailCollapsed(false)}
              className="rounded-sm p-1 text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong"
            >
              <PanelRightOpen size={14} />
            </button>
          </div>
        ) : (
          <>
            {/* Save bar */}
            <div className="flex items-center justify-between gap-2 border-b border-border-subtle px-3 py-2">
              <div className="flex items-center gap-1.5">
                {hasUnsaved && (
                  <Badge variant="warning" data-testid="widget-unsaved">
                    unsaved
                  </Badge>
                )}
                {isSaving && (
                  <Loader2 size={12} className="animate-spin text-content-muted" />
                )}
                {saveError && (
                  <span className="text-caption text-status-error">
                    {saveError}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1">
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={handleDiscard}
                  disabled={!hasUnsaved}
                  data-testid="widget-discard"
                >
                  <Undo2 size={12} />
                </Button>
                <Button
                  size="sm"
                  onClick={() => void handleSave()}
                  disabled={!hasUnsaved}
                  data-testid="widget-save"
                >
                  <Save size={12} className="mr-1" />
                  Save
                </Button>
              </div>
            </div>

            {/* Scope */}
            <div className="border-b border-border-subtle px-3 py-2">
              <label className="mb-1 block text-micro uppercase tracking-wider text-content-muted">
                Scope
              </label>
              <select
                value={scope}
                onChange={(e) => setScope(e.target.value as Scope)}
                className="w-full rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-strong"
                data-testid="widget-scope-selector"
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

            {/* Configurable props */}
            <div className="flex-1 overflow-y-auto" data-testid="widget-prop-controls">
              {selectedEntry ? (
                <PropControlsList
                  entry={selectedEntry}
                  draftOverrides={draftOverrides}
                  onChangeProp={(name, value) =>
                    setDraftOverrides((cur) => ({ ...cur, [name]: value }))
                  }
                  onResetProp={(name) =>
                    setDraftOverrides((cur) => {
                      const next = { ...cur }
                      delete next[name]
                      return next
                    })
                  }
                  effectiveProps={effectiveProps}
                  stack={stack}
                />
              ) : (
                <div className="px-3 py-6 text-center text-caption text-content-muted">
                  Select a widget to edit its props.
                </div>
              )}
            </div>
          </>
        )}
      </aside>
    </div>
  )
}


function PropControlsList({
  entry,
  draftOverrides,
  onChangeProp,
  onResetProp,
  effectiveProps,
  stack,
}: {
  entry: RegistryEntry
  draftOverrides: PropOverrideMap
  onChangeProp: (name: string, value: unknown) => void
  onResetProp: (name: string) => void
  effectiveProps: Record<string, unknown>
  stack: ConfigStack
}) {
  const props = entry.metadata.configurableProps ?? {}
  const propEntries = Object.entries(props) as Array<[string, ConfigPropSchema]>
  if (propEntries.length === 0) {
    return (
      <div className="px-3 py-6 text-center text-caption text-content-muted">
        This widget declares no configurable props.
      </div>
    )
  }
  return (
    <div className="px-2 py-1">
      {propEntries.map(([name, schema]) => {
        const source = resolvePropSource(name, stack)
        const value = effectiveProps[name]
        const isOverridden = name in draftOverrides
        return (
          <div
            key={name}
            className="border-b border-border-subtle px-2 py-2 last:border-b-0"
            data-testid={`widget-prop-${name}`}
          >
            <CompactPropControl
              name={name}
              schema={schema}
              value={value}
              source={source}
              onChange={(next) => onChangeProp(name, next)}
              isOverriddenAtCurrentScope={isOverridden}
              onReset={() => onResetProp(name)}
            />
          </div>
        )
      })}
    </div>
  )
}


// ─── Class mode ─────────────────────────────────────────────


function WidgetClassEditor() {
  const widgetClass = useMemo(() => getClassRegistration("widget"), [])
  const widgets = useMemo<RegistryEntry[]>(() => {
    return getComponentsInClass("widget").slice(0, 6)
  }, [])

  const [resolved, setResolved] = useState<ResolvedClassConfiguration | null>(
    null,
  )
  const [activeRow, setActiveRow] = useState<ClassConfigurationRecord | null>(
    null,
  )
  const [draftOverrides, setDraftOverrides] = useState<PropOverrideMap>({})
  const [previewMode, setPreviewMode] = useState<PreviewMode>("light")
  const [isLoading, setIsLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setLoadError(null)
    componentClassConfigurationsService
      .resolve("widget")
      .then((res) => {
        if (cancelled) return
        setResolved(res)
        return componentClassConfigurationsService.list({
          component_class: "widget",
        })
      })
      .then((rows) => {
        if (cancelled || !rows) return
        const active = rows.find((r) => r.is_active) ?? null
        setActiveRow(active)
        setDraftOverrides({ ...(active?.prop_overrides ?? {}) })
      })
      .catch((err) => {
        if (cancelled) return
        // eslint-disable-next-line no-console
        console.error("[widget-class-editor] resolve failed", err)
        setLoadError(err instanceof Error ? err.message : "Failed to load")
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const persistedOverrides = activeRow?.prop_overrides ?? {}
  const hasUnsaved =
    JSON.stringify(persistedOverrides) !== JSON.stringify(draftOverrides)

  const handleSave = useCallback(async () => {
    if (!hasUnsaved) return
    setIsSaving(true)
    setSaveError(null)
    try {
      if (activeRow) {
        const updated = await componentClassConfigurationsService.update(
          activeRow.id,
          draftOverrides,
        )
        setActiveRow(updated)
      } else {
        const created = await componentClassConfigurationsService.create({
          component_class: "widget",
          prop_overrides: draftOverrides,
        })
        setActiveRow(created)
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[widget-class-editor] save failed", err)
      setSaveError(err instanceof Error ? err.message : "Failed to save")
    } finally {
      setIsSaving(false)
    }
  }, [hasUnsaved, activeRow, draftOverrides])

  if (!widgetClass) {
    return (
      <div className="flex flex-1 items-center justify-center text-content-muted">
        Widget class not registered.
      </div>
    )
  }

  const props = widgetClass.configurableProps ?? {}
  const propEntries = Object.entries(props) as Array<[string, ConfigPropSchema]>

  return (
    <div className="flex flex-1 overflow-hidden" data-testid="widget-class-editor">
      <aside className="flex w-[400px] flex-shrink-0 flex-col border-r border-border-subtle bg-surface-elevated">
        <div className="border-b border-border-subtle px-4 py-2">
          <div className="text-h4 font-plex-serif text-content-strong">
            Widget class
          </div>
          <div className="text-caption text-content-muted">
            Edits affect every widget across the platform.
          </div>
        </div>

        {/* Save bar */}
        <div className="flex items-center justify-between gap-2 border-b border-border-subtle px-4 py-2">
          <div className="flex items-center gap-1.5">
            {hasUnsaved && (
              <Badge variant="warning" data-testid="widget-class-unsaved">
                unsaved
              </Badge>
            )}
            {isSaving && (
              <Loader2 size={12} className="animate-spin text-content-muted" />
            )}
            {saveError && (
              <span className="text-caption text-status-error">{saveError}</span>
            )}
            {loadError && (
              <span className="text-caption text-status-error">{loadError}</span>
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
            >
              <Undo2 size={12} />
            </Button>
            <Button
              size="sm"
              onClick={() => void handleSave()}
              disabled={!hasUnsaved}
              data-testid="widget-class-save"
            >
              <Save size={12} className="mr-1" />
              Save
            </Button>
          </div>
        </div>

        {/* Class-level prop controls */}
        <div className="flex-1 overflow-y-auto" data-testid="widget-class-controls">
          {isLoading ? (
            <div className="flex items-center justify-center py-8 text-caption text-content-muted">
              <Loader2 size={14} className="mr-2 animate-spin" />
              Loading…
            </div>
          ) : propEntries.length === 0 ? (
            <div className="px-4 py-6 text-center text-caption text-content-muted">
              No class-level props declared.
            </div>
          ) : (
            propEntries.map(([name, schema]) => (
              <div
                key={name}
                className="border-b border-border-subtle px-3 py-2"
                data-testid={`widget-class-prop-${name}`}
              >
                <CompactPropControl
                  name={name}
                  schema={schema}
                  value={
                    name in draftOverrides
                      ? draftOverrides[name]
                      : (resolved?.props?.[name] ?? schema.default)
                  }
                  source={name in draftOverrides ? "draft" : "class-default"}
                  onChange={(next) =>
                    setDraftOverrides((cur) => ({ ...cur, [name]: next }))
                  }
                  isOverriddenAtCurrentScope={name in draftOverrides}
                  onReset={() =>
                    setDraftOverrides((cur) => {
                      const next = { ...cur }
                      delete next[name]
                      return next
                    })
                  }
                />
              </div>
            ))
          )}
        </div>
      </aside>

      <main
        className="relative flex flex-1 flex-col overflow-hidden bg-surface-sunken"
        data-testid="widget-class-preview-pane"
      >
        <div className="flex items-center justify-between border-b border-border-subtle bg-surface-elevated px-4 py-2">
          <div className="text-caption text-content-muted">
            Sampling {widgets.length} registered widget
            {widgets.length === 1 ? "" : "s"} — class changes propagate to all
          </div>
          <button
            type="button"
            onClick={() =>
              setPreviewMode((m) => (m === "light" ? "dark" : "light"))
            }
            className="flex items-center gap-1 rounded-sm border border-border-base px-2 py-1 text-caption text-content-strong hover:bg-accent-subtle/40"
          >
            {previewMode === "light" ? <Sun size={12} /> : <Moon size={12} />}
            {previewMode}
          </button>
        </div>
        <div
          className="flex-1 overflow-auto p-4"
          data-mode={previewMode}
          data-testid="widget-class-preview-area"
        >
          <DashboardContextFrame>
            <div className="grid grid-cols-3 gap-3">
              {widgets.map((entry) => (
                <div
                  key={entry.metadata.name}
                  data-testid={`class-preview-${entry.metadata.name}`}
                >
                  {renderComponentPreview(
                    `widget:${entry.metadata.name}`,
                    {},
                    entry.metadata.displayName,
                  )}
                </div>
              ))}
            </div>
          </DashboardContextFrame>
        </div>
      </main>
    </div>
  )
}
