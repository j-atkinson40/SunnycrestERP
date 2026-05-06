/**
 * ComponentEditorPage — preview-dominant layout (May 2026 redesign).
 *
 * Three panes:
 *   ┌─ Left (320px) ──┬─ Center (dominant) ────────┬─ Right (320px) ──┐
 *   │ Component       │ Live preview in context    │ Property controls │
 *   │  browser        │ (DashboardContextFrame /   │ (compact)         │
 *   │  + tabs         │  FocusContextFrame /       │                   │
 *   │  + search       │  DocumentContextFrame /    │                   │
 *   │  + thumbnails   │  WorkflowCanvasContextFrame)│                  │
 *   └─────────────────┴────────────────────────────┴───────────────────┘
 *
 * The right pane collapses to a thin strip so the preview can fill
 * available width for inspection-focused work.
 *
 * Replaces the original Phase 3 layout where the property controls
 * dominated the viewport. The capability is identical; only the
 * visual hierarchy + contextual preview rendering change.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import {
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Loader2,
  Moon,
  PanelRightClose,
  PanelRightOpen,
  RotateCcw,
  Save,
  Search,
  Sun,
  Undo2,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  componentConfigurationsService,
  type ComponentConfigurationRecord,
  type ComponentKind,
  type ConfigScope,
  type ResolvedConfiguration,
} from "@/bridgeable-admin/services/component-configurations-service"
import {
  composeEffectiveProps,
  emptyConfigStack,
  resolvePropSource,
  stackFromResolvedConfig,
  type ConfigStack,
  type PropOverrideMap,
  type PropSource,
} from "@/lib/visual-editor/components/config-resolver"
import { renderComponentPreview } from "@/lib/visual-editor/components/preview-renderers"
import {
  getAllRegistered,
  type ConfigPropSchema,
  type RegistryEntry,
} from "@/lib/visual-editor/registry"
import {
  TenantPicker,
  type TenantSummary,
} from "@/bridgeable-admin/components/TenantPicker"
import { ComponentThumbnail } from "@/bridgeable-admin/components/visual-editor/ComponentThumbnail"
import { DashboardContextFrame } from "@/bridgeable-admin/components/visual-editor/context-frames/DashboardContextFrame"
import { FocusContextFrame } from "@/bridgeable-admin/components/visual-editor/context-frames/FocusContextFrame"
import { DocumentContextFrame } from "@/bridgeable-admin/components/visual-editor/context-frames/DocumentContextFrame"
import { WorkflowCanvasContextFrame } from "@/bridgeable-admin/components/visual-editor/context-frames/WorkflowCanvasContextFrame"
import {
  CompactPropControl,
  inferPropGroup,
} from "@/bridgeable-admin/components/visual-editor/CompactPropControl"


const VERTICALS = ["funeral_home", "manufacturing", "cemetery", "crematory"] as const


type CategoryTab = "all" | ComponentKind


const CATEGORY_TABS: ReadonlyArray<{ id: CategoryTab; label: string }> = [
  { id: "all", label: "All" },
  { id: "widget", label: "Widgets" },
  { id: "focus", label: "Focus" },
  { id: "focus-template", label: "Templates" },
  { id: "document-block", label: "Doc Blocks" },
  { id: "workflow-node", label: "Workflow Nodes" },
]


type PreviewMode = "light" | "dark"


function inferFocusType(
  componentName: string,
): "decision" | "coordination" | "execution" | "review" | "generation" | "unknown" {
  const n = componentName.toLowerCase()
  if (n.includes("decision")) return "decision"
  if (n.includes("coordination")) return "coordination"
  if (n.includes("execution")) return "execution"
  if (n.includes("review")) return "review"
  if (n.includes("generation") || n.includes("scribe")) return "generation"
  return "unknown"
}


function inferDocBlockPosition(
  componentName: string,
): "top" | "inline" | "bottom" {
  const n = componentName.toLowerCase()
  if (n.includes("header")) return "top"
  if (n.includes("signature") || n.includes("footer")) return "bottom"
  return "inline"
}


export default function ComponentEditorPage() {
  // ── Component selection ──────────────────────────────────
  const [selectedKind, setSelectedKind] = useState<ComponentKind | null>(null)
  const [selectedName, setSelectedName] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<CategoryTab>("all")
  const [browserSearch, setBrowserSearch] = useState("")
  const [browserVertical, setBrowserVertical] = useState<string>("all")

  // ── Editing scope ────────────────────────────────────────
  const [scope, setScope] = useState<ConfigScope>("platform_default")
  const [vertical, setVertical] = useState<string>("funeral_home")
  const [tenantIdInput, setTenantIdInput] = useState<string>("")
  const [selectedTenant, setSelectedTenant] = useState<TenantSummary | null>(null)

  // ── Preview state ────────────────────────────────────────
  const [previewMode, setPreviewMode] = useState<PreviewMode>("light")
  const [showAllInstances, setShowAllInstances] = useState(false)
  const [rightRailCollapsed, setRightRailCollapsed] = useState(false)

  // ── Backend data state ───────────────────────────────────
  const [resolved, setResolved] = useState<ResolvedConfiguration | null>(null)
  const [activeRow, setActiveRow] = useState<ComponentConfigurationRecord | null>(null)
  const [draft, setDraft] = useState<PropOverrideMap>({})
  const [isLoading, setIsLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  // ── Right-pane local state ───────────────────────────────
  const [propSearch, setPropSearch] = useState("")
  const [showOnlyOverridden, setShowOnlyOverridden] = useState(false)
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set())

  // ── Browser data ─────────────────────────────────────────
  const allComponents = useMemo(() => getAllRegistered(), [])

  const filteredComponents = useMemo(() => {
    const term = browserSearch.trim().toLowerCase()
    return allComponents.filter((entry) => {
      // Tab filter
      if (activeTab !== "all" && entry.metadata.type !== activeTab) return false

      // Vertical filter
      if (browserVertical !== "all") {
        const vs = entry.metadata.verticals
        const matches =
          vs.includes("all") ||
          vs.includes(browserVertical as Parameters<typeof vs.includes>[0])
        if (!matches) return false
      }

      // Search filter
      if (term) {
        const haystack = `${entry.metadata.name} ${entry.metadata.displayName} ${entry.metadata.description ?? ""}`.toLowerCase()
        if (!haystack.includes(term)) return false
      }
      return true
    })
  }, [allComponents, activeTab, browserSearch, browserVertical])

  const selectedEntry = useMemo<RegistryEntry | null>(() => {
    if (!selectedKind || !selectedName) return null
    return (
      allComponents.find(
        (e) =>
          e.metadata.type === selectedKind && e.metadata.name === selectedName,
      ) ?? null
    )
  }, [allComponents, selectedKind, selectedName])

  // Auto-select the first component on first render so the editor
  // isn't blank.
  useEffect(() => {
    if (!selectedKind && !selectedName && allComponents.length > 0) {
      const first = allComponents[0]
      setSelectedKind(first.metadata.type as ComponentKind)
      setSelectedName(first.metadata.name)
    }
  }, [allComponents, selectedKind, selectedName])

  // ── Resolve from backend whenever scope / component changes ──
  const resolveAndLoadActive = useCallback(async () => {
    if (!selectedKind || !selectedName) return
    setIsLoading(true)
    setLoadError(null)
    try {
      const resolveParams: {
        component_kind: ComponentKind
        component_name: string
        vertical?: string | null
        tenant_id?: string | null
      } = { component_kind: selectedKind, component_name: selectedName }
      if (scope === "vertical_default" || scope === "tenant_override") {
        resolveParams.vertical = vertical || undefined
      }
      if (scope === "tenant_override") {
        resolveParams.tenant_id = tenantIdInput || undefined
      }

      const resolveResult = await componentConfigurationsService.resolve(
        resolveParams,
      )
      setResolved(resolveResult)

      const listParams: Parameters<typeof componentConfigurationsService.list>[0] =
        {
          scope,
          component_kind: selectedKind,
          component_name: selectedName,
        }
      if (scope === "vertical_default") listParams.vertical = vertical
      if (scope === "tenant_override") listParams.tenant_id = tenantIdInput

      const rows = await componentConfigurationsService.list(listParams)
      const active = rows.find((r) => r.is_active) ?? null
      setActiveRow(active)
      setDraft(
        active
          ? Object.fromEntries(
              Object.entries(active.prop_overrides).map(([k, v]) => [k, v]),
            )
          : {},
      )
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[component-editor] resolve failed", err)
      setLoadError(err instanceof Error ? err.message : "Failed to load")
    } finally {
      setIsLoading(false)
    }
  }, [scope, selectedKind, selectedName, tenantIdInput, vertical])

  useEffect(() => {
    void resolveAndLoadActive()
  }, [resolveAndLoadActive])

  // Reset draft when component changes (no warning — selection
  // change discards local edits intentionally).
  useEffect(() => {
    setDraft({})
  }, [selectedKind, selectedName])

  // ── Effective props (registration default + scope chain + draft) ──
  const stack: ConfigStack = useMemo(() => {
    const base = resolved
      ? stackFromResolvedConfig(resolved, draft)
      : emptyConfigStack()
    return { ...base, draft }
  }, [resolved, draft])

  const effectiveProps = useMemo(() => {
    if (!selectedEntry) return {}
    return composeEffectiveProps(
      selectedEntry.metadata.type as ComponentKind,
      selectedEntry.metadata.name,
      stack,
    )
  }, [selectedEntry, stack])

  // ── Save / discard / autosave ────────────────────────────
  const persistedOverrides = useMemo(() => {
    if (!activeRow) return {}
    return { ...activeRow.prop_overrides }
  }, [activeRow])

  const unsavedChanges = useMemo(() => {
    const keys = new Set([
      ...Object.keys(draft),
      ...Object.keys(persistedOverrides),
    ])
    let count = 0
    for (const k of keys) {
      const before = JSON.stringify(persistedOverrides[k])
      const after = JSON.stringify(draft[k])
      if (before !== after) count++
    }
    return count
  }, [draft, persistedOverrides])
  const hasUnsaved = unsavedChanges > 0

  const handleSave = useCallback(async () => {
    if (!selectedKind || !selectedName) return
    if (!hasUnsaved && activeRow) return
    setIsSaving(true)
    setSaveError(null)
    try {
      if (activeRow) {
        const updated = await componentConfigurationsService.update(
          activeRow.id,
          draft,
        )
        setActiveRow(updated)
      } else {
        const created = await componentConfigurationsService.create({
          scope,
          vertical: scope === "vertical_default" ? vertical : null,
          tenant_id: scope === "tenant_override" ? tenantIdInput : null,
          component_kind: selectedKind,
          component_name: selectedName,
          prop_overrides: draft,
        })
        setActiveRow(created)
      }
      await resolveAndLoadActive()
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[component-editor] save failed", err)
      setSaveError(err instanceof Error ? err.message : "Failed to save")
    } finally {
      setIsSaving(false)
    }
  }, [
    activeRow,
    draft,
    hasUnsaved,
    resolveAndLoadActive,
    scope,
    selectedKind,
    selectedName,
    tenantIdInput,
    vertical,
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
        autosaveTimer.current = null
      }
    }
  }, [draft, hasUnsaved, handleSave])

  const handleDiscard = useCallback(() => {
    setDraft({ ...persistedOverrides })
  }, [persistedOverrides])

  const handleResetAll = useCallback(() => {
    if (!window.confirm("Reset all overrides on this scope to inherited?")) return
    setDraft({})
  }, [])

  // ── Per-prop edit handler ────────────────────────────────
  const handlePropChange = useCallback(
    (propName: string, next: unknown) => {
      setDraft((d) => {
        const out = { ...d }
        const schemaDefault =
          selectedEntry?.metadata.configurableProps?.[propName]?.default
        // If next matches the registration default, remove the key
        // (clean draft) so the prop falls back through the stack.
        if (JSON.stringify(next) === JSON.stringify(schemaDefault)) {
          delete out[propName]
        } else {
          out[propName] = next
        }
        return out
      })
    },
    [selectedEntry],
  )

  const handlePropReset = useCallback((propName: string) => {
    setDraft((d) => {
      const out = { ...d }
      delete out[propName]
      return out
    })
  }, [])

  // ── Filtered + grouped props for the right rail ─────────
  // configurableProps is Record<string, ConfigPropSchema> — iterate
  // via Object.entries so we have both the prop name AND schema.
  const groupedProps = useMemo(() => {
    if (!selectedEntry) return new Map<string, Array<[string, ConfigPropSchema]>>()
    const term = propSearch.trim().toLowerCase()
    const props = selectedEntry.metadata.configurableProps ?? {}
    const filtered: Array<[string, ConfigPropSchema]> = Object.entries(props).filter(
      ([name, p]) => {
        if (term) {
          const hay = `${name} ${p.displayLabel ?? ""} ${p.description ?? ""}`.toLowerCase()
          if (!hay.includes(term)) return false
        }
        if (showOnlyOverridden) {
          const src = resolvePropSource(name, stack)
          if (src === "registration-default") return false
        }
        return true
      },
    )
    const grouped = new Map<string, Array<[string, ConfigPropSchema]>>()
    for (const entry of filtered) {
      const [name] = entry
      const group = inferPropGroup(name)
      const list = grouped.get(group) ?? []
      list.push(entry)
      grouped.set(group, list)
    }
    return grouped
  }, [propSearch, selectedEntry, showOnlyOverridden, stack])

  const overriddenCount = useMemo(() => {
    if (!selectedEntry) return 0
    let n = 0
    const props = selectedEntry.metadata.configurableProps ?? {}
    for (const name of Object.keys(props)) {
      const src = resolvePropSource(name, stack)
      if (src !== "registration-default") n++
    }
    return n
  }, [selectedEntry, stack])

  // ── Preview render ──────────────────────────────────────
  const previewNode = useMemo(() => {
    if (!selectedEntry) return null
    const registryKey = `${selectedEntry.metadata.type}:${selectedEntry.metadata.name}`
    return renderComponentPreview(
      registryKey,
      effectiveProps,
      selectedEntry.metadata.displayName,
    )
  }, [selectedEntry, effectiveProps])

  function renderInPreviewContext(): React.ReactNode {
    if (!selectedEntry) {
      return (
        <div className="flex h-full items-center justify-center">
          <div className="text-center">
            <div className="text-h3 font-plex-serif text-content-strong">
              Select a component to begin editing
            </div>
            <div className="mt-2 text-body-sm text-content-muted">
              Choose from the browser on the left.
            </div>
          </div>
        </div>
      )
    }

    const kind = selectedEntry.metadata.type as ComponentKind
    const name = selectedEntry.metadata.name
    const renderInstance = (variant: string) => {
      // For "show all instances" we just render the same preview
      // multiple times (the variant label is provided to the frame
      // for chrome differentiation; the renderer itself is config-
      // driven so different instances would require config variants
      // — out of scope for the redesign).
      void variant
      return previewNode
    }

    if (kind === "widget") {
      return (
        <DashboardContextFrame
          showAllInstances={showAllInstances}
          renderInstance={renderInstance}
        >
          {previewNode}
        </DashboardContextFrame>
      )
    }
    if (kind === "focus" || kind === "focus-template") {
      return (
        <FocusContextFrame
          focusType={inferFocusType(name)}
          title={selectedEntry.metadata.displayName}
          showAllInstances={showAllInstances}
          renderInstance={renderInstance}
        >
          {previewNode}
        </FocusContextFrame>
      )
    }
    if (kind === "document-block") {
      return (
        <DocumentContextFrame
          position={inferDocBlockPosition(name)}
          showAllInstances={showAllInstances}
          renderInstance={renderInstance}
        >
          {previewNode}
        </DocumentContextFrame>
      )
    }
    if (kind === "workflow-node") {
      return (
        <WorkflowCanvasContextFrame
          nodeType={name}
          showAllInstances={showAllInstances}
          renderInstance={renderInstance}
        >
          {previewNode}
        </WorkflowCanvasContextFrame>
      )
    }
    // Fallback for layout / composite / pulse-widget kinds.
    return (
      <div className="flex h-full items-center justify-center bg-surface-base p-6">
        <div className="rounded-md border border-border-subtle bg-surface-elevated p-6">
          {previewNode}
        </div>
      </div>
    )
  }

  // ── Render ───────────────────────────────────────────────
  return (
    <div
      className="flex h-[calc(100vh-3rem)] w-full flex-col"
      data-testid="component-editor-redesign"
    >
      <div className="flex flex-1 overflow-hidden">
        {/* ── LEFT: Component browser ─────────────────────── */}
        <aside
          className="flex w-[320px] flex-shrink-0 flex-col border-r border-border-subtle bg-surface-elevated"
          data-testid="component-browser"
        >
          {/* Header: title + counts */}
          <div className="border-b border-border-subtle px-4 py-3">
            <div className="text-h4 font-plex-serif text-content-strong">
              Components
            </div>
            <div className="text-caption text-content-muted">
              {filteredComponents.length} of {allComponents.length} registered
            </div>
          </div>

          {/* Search */}
          <div className="border-b border-border-subtle px-3 py-2">
            <div className="relative">
              <Search
                size={12}
                className="absolute left-2 top-1/2 -translate-y-1/2 text-content-muted"
              />
              <Input
                value={browserSearch}
                onChange={(e) => setBrowserSearch(e.target.value)}
                placeholder="Search components"
                className="h-8 pl-7 text-body-sm"
                data-testid="component-browser-search"
              />
            </div>
            <div className="mt-2">
              <select
                value={browserVertical}
                onChange={(e) => setBrowserVertical(e.target.value)}
                className="w-full rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-strong"
                data-testid="component-browser-vertical"
              >
                <option value="all">All verticals</option>
                {VERTICALS.map((v) => (
                  <option key={v} value={v}>
                    {v.replace("_", " ")}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Category tabs */}
          <div
            className="flex flex-wrap gap-0.5 border-b border-border-subtle px-2 py-1.5"
            data-testid="component-browser-tabs"
          >
            {CATEGORY_TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={
                  activeTab === tab.id
                    ? "rounded-sm bg-accent-subtle px-2 py-1 text-caption font-medium text-accent"
                    : "rounded-sm px-2 py-1 text-caption text-content-muted hover:bg-accent-subtle/40"
                }
                data-testid={`tab-${tab.id}`}
                data-active={activeTab === tab.id ? "true" : "false"}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Component list */}
          <div className="flex-1 overflow-y-auto px-1 py-1" data-testid="component-list">
            {filteredComponents.map((entry) => {
              const isSelected =
                selectedKind === entry.metadata.type &&
                selectedName === entry.metadata.name
              return (
                <button
                  key={`${entry.metadata.type}:${entry.metadata.name}`}
                  type="button"
                  onClick={() => {
                    setSelectedKind(entry.metadata.type as ComponentKind)
                    setSelectedName(entry.metadata.name)
                  }}
                  className={
                    isSelected
                      ? "flex w-full items-center gap-2 rounded-sm bg-accent-subtle px-2 py-1.5 text-left"
                      : "flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left hover:bg-accent-subtle/30"
                  }
                  data-testid={`component-${entry.metadata.type}-${entry.metadata.name}`}
                  data-selected={isSelected ? "true" : "false"}
                >
                  <ComponentThumbnail
                    kind={entry.metadata.type as ComponentKind}
                    componentName={entry.metadata.name}
                  />
                  <div className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate text-body-sm font-medium text-content-strong">
                      {entry.metadata.displayName}
                    </span>
                    <span className="truncate font-plex-mono text-caption text-content-muted">
                      {entry.metadata.name}
                    </span>
                  </div>
                </button>
              )
            })}
            {filteredComponents.length === 0 && (
              <div className="px-2 py-6 text-center text-caption text-content-muted">
                No components match your filter.
              </div>
            )}
          </div>
        </aside>

        {/* ── CENTER: Live preview ────────────────────────── */}
        <main
          className="relative flex flex-1 flex-col overflow-hidden bg-surface-sunken"
          data-testid="preview-pane"
        >
          {/* Preview controls */}
          <div className="flex items-center justify-between border-b border-border-subtle bg-surface-elevated px-4 py-2">
            <div className="flex items-center gap-3">
              {selectedEntry && (
                <>
                  <span className="text-body-sm font-medium text-content-strong">
                    {selectedEntry.metadata.displayName}
                  </span>
                  <Badge variant="outline" data-testid="preview-kind-badge">
                    {selectedEntry.metadata.type}
                  </Badge>
                </>
              )}
              {isLoading && (
                <Loader2
                  size={12}
                  className="animate-spin text-content-muted"
                />
              )}
              {loadError && (
                <span className="flex items-center gap-1 text-caption text-status-error">
                  <AlertCircle size={12} /> {loadError}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setShowAllInstances((s) => !s)}
                className={
                  showAllInstances
                    ? "rounded-sm bg-accent-subtle px-2 py-1 text-caption font-medium text-accent"
                    : "rounded-sm px-2 py-1 text-caption text-content-muted hover:bg-accent-subtle/40"
                }
                data-testid="show-all-instances-toggle"
                data-active={showAllInstances ? "true" : "false"}
              >
                Show all instances
              </button>
              <button
                type="button"
                onClick={() => setPreviewMode((m) => (m === "light" ? "dark" : "light"))}
                className="flex items-center gap-1 rounded-sm border border-border-base px-2 py-1 text-caption text-content-strong hover:bg-accent-subtle/40"
                aria-label={`Preview mode: ${previewMode}`}
                data-testid="preview-mode-toggle"
              >
                {previewMode === "light" ? <Sun size={12} /> : <Moon size={12} />}
                {previewMode}
              </button>
              <button
                type="button"
                onClick={() => setRightRailCollapsed((c) => !c)}
                className="rounded-sm border border-border-base p-1 text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong"
                aria-label={rightRailCollapsed ? "Expand controls" : "Collapse controls"}
                data-testid="right-rail-toggle"
              >
                {rightRailCollapsed ? (
                  <PanelRightOpen size={14} />
                ) : (
                  <PanelRightClose size={14} />
                )}
              </button>
            </div>
          </div>

          {/* Preview canvas — sandboxed mode toggle via data-mode */}
          <div
            className="flex-1 overflow-hidden"
            data-mode={previewMode}
            data-testid="preview-canvas"
          >
            <div className="h-full w-full">{renderInPreviewContext()}</div>
          </div>
        </main>

        {/* ── RIGHT: Property controls ─────────────────────── */}
        <aside
          className={
            rightRailCollapsed
              ? "flex w-12 flex-shrink-0 flex-col border-l border-border-subtle bg-surface-elevated"
              : "flex w-[320px] flex-shrink-0 flex-col border-l border-border-subtle bg-surface-elevated"
          }
          data-testid="properties-pane"
          data-collapsed={rightRailCollapsed ? "true" : "false"}
        >
          {rightRailCollapsed ? (
            <div className="flex flex-1 flex-col items-center gap-2 py-3">
              <button
                type="button"
                onClick={() => setRightRailCollapsed(false)}
                className="rounded-sm p-1 text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong"
                aria-label="Expand controls"
              >
                <PanelRightOpen size={14} />
              </button>
              <span
                className="rotate-180 text-caption text-content-muted"
                style={{ writingMode: "vertical-rl" }}
              >
                Properties
              </span>
            </div>
          ) : (
            <>
              {/* Sticky save bar */}
              <div className="flex items-center justify-between gap-2 border-b border-border-subtle bg-surface-elevated px-3 py-2">
                <div className="flex items-center gap-1.5">
                  {hasUnsaved && (
                    <Badge variant="warning" data-testid="unsaved-badge">
                      {unsavedChanges} unsaved
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
                    data-testid="discard-button"
                  >
                    <Undo2 size={12} />
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => void handleSave()}
                    disabled={!hasUnsaved}
                    data-testid="save-button"
                  >
                    <Save size={12} className="mr-1" />
                    Save
                  </Button>
                </div>
              </div>

              {/* Selected component identity */}
              {selectedEntry ? (
                <div className="border-b border-border-subtle px-3 py-2">
                  <div className="text-body-sm font-medium text-content-strong">
                    {selectedEntry.metadata.displayName}
                  </div>
                  <div className="mt-0.5 font-plex-mono text-caption text-content-muted">
                    {selectedEntry.metadata.name}
                  </div>
                  <div className="mt-1 flex items-center gap-1.5 text-caption text-content-muted">
                    <span>{selectedEntry.metadata.type}</span>
                    <span>·</span>
                    <span>v{selectedEntry.metadata.componentVersion}</span>
                    <span>·</span>
                    <span>{overriddenCount} overridden</span>
                  </div>
                  {/* Class membership + link to class editor */}
                  {(() => {
                    const declared = selectedEntry.metadata.componentClasses
                    const classes =
                      declared && declared.length > 0
                        ? declared
                        : [selectedEntry.metadata.type]
                    return (
                      <div
                        className="mt-2 flex items-center gap-1.5 rounded-sm bg-surface-sunken px-2 py-1 text-caption"
                        data-testid="component-class-membership"
                      >
                        <span className="text-content-muted">Class:</span>
                        <span className="font-medium text-content-strong">
                          {classes.join(" · ")}
                        </span>
                        <Link
                          to={adminPath("/visual-editor/classes")}
                          className="ml-auto text-accent hover:underline"
                          data-testid="link-to-class-editor"
                        >
                          Edit class defaults →
                        </Link>
                      </div>
                    )
                  })()}
                </div>
              ) : (
                <div className="px-3 py-6 text-center text-caption text-content-muted">
                  No component selected.
                </div>
              )}

              {/* Scope selector */}
              <div className="border-b border-border-subtle px-3 py-2">
                <label className="mb-1 block text-micro uppercase tracking-wider text-content-muted">
                  Scope
                </label>
                <select
                  value={scope}
                  onChange={(e) => setScope(e.target.value as ConfigScope)}
                  className="w-full rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-strong"
                  data-testid="scope-selector"
                >
                  <option value="platform_default">Platform Default</option>
                  <option value="vertical_default">Vertical Default</option>
                  <option value="tenant_override">Tenant Override</option>
                </select>
                {scope === "vertical_default" && (
                  <select
                    value={vertical}
                    onChange={(e) => setVertical(e.target.value)}
                    className="mt-1.5 w-full rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-strong"
                    data-testid="vertical-selector"
                  >
                    {VERTICALS.map((v) => (
                      <option key={v} value={v}>
                        {v.replace("_", " ")}
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
                        setTenantIdInput(t?.id ?? "")
                      }}
                    />
                  </div>
                )}
              </div>

              {/* Prop list */}
              {selectedEntry && (
                <>
                  <div className="border-b border-border-subtle px-3 py-2">
                    <div className="relative">
                      <Search
                        size={11}
                        className="absolute left-2 top-1/2 -translate-y-1/2 text-content-muted"
                      />
                      <Input
                        value={propSearch}
                        onChange={(e) => setPropSearch(e.target.value)}
                        placeholder="Filter props"
                        className="h-7 pl-7 text-caption"
                        data-testid="prop-search"
                      />
                    </div>
                    <label className="mt-1.5 flex items-center gap-1.5 text-caption text-content-muted">
                      <input
                        type="checkbox"
                        checked={showOnlyOverridden}
                        onChange={(e) => setShowOnlyOverridden(e.target.checked)}
                        data-testid="show-only-overridden"
                      />
                      Only overridden
                    </label>
                  </div>
                  <div className="flex-1 overflow-y-auto" data-testid="prop-list">
                    {Array.from(groupedProps.entries()).map(([groupName, props]) => {
                      const collapsed = collapsedGroups.has(groupName)
                      return (
                        <div key={groupName}>
                          <button
                            type="button"
                            onClick={() => {
                              setCollapsedGroups((s) => {
                                const next = new Set(s)
                                if (next.has(groupName)) next.delete(groupName)
                                else next.add(groupName)
                                return next
                              })
                            }}
                            className="flex w-full items-center gap-1 px-3 py-1 text-micro uppercase tracking-wider text-content-muted hover:bg-accent-subtle/30"
                            data-testid={`prop-group-${groupName}`}
                          >
                            {collapsed ? (
                              <ChevronRight size={10} />
                            ) : (
                              <ChevronDown size={10} />
                            )}
                            {groupName}
                            <span className="ml-auto text-caption normal-case text-content-subtle">
                              {props.length}
                            </span>
                          </button>
                          {!collapsed &&
                            props.map(([propName, propSchema]) => {
                              const source = resolvePropSource(propName, stack) as PropSource
                              const isOverriddenAtScope =
                                (scope === "platform_default" && source !== "registration-default") ||
                                (scope === "vertical_default" && (source === "vertical-default" || source === "draft")) ||
                                (scope === "tenant_override" && (source === "tenant-override" || source === "draft"))
                              return (
                                <CompactPropControl
                                  key={propName}
                                  name={propName}
                                  schema={propSchema}
                                  value={effectiveProps[propName]}
                                  onChange={(v) => handlePropChange(propName, v)}
                                  source={source}
                                  isOverriddenAtCurrentScope={isOverriddenAtScope}
                                  onReset={() => handlePropReset(propName)}
                                />
                              )
                            })}
                        </div>
                      )
                    })}
                  </div>
                  <div className="border-t border-border-subtle px-3 py-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={handleResetAll}
                      disabled={Object.keys(draft).length === 0}
                      className="w-full text-caption"
                      data-testid="reset-all"
                    >
                      <RotateCcw size={11} className="mr-1" />
                      Reset all to inherited
                    </Button>
                  </div>
                </>
              )}
            </>
          )}
        </aside>
      </div>
    </div>
  )
}
