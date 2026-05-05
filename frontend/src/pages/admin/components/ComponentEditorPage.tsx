/**
 * ComponentEditorPage — Phase 3 of the Admin Visual Editor.
 *
 * Three-pane layout following Phase 2's established pattern:
 *
 *   ┌─ Top bar ─────────────────────────────────────────────┐
 *   │  Title  │  Save · Discard · History · Unsaved badge   │
 *   ├──────────┬────────────────────────┬───────────────────┤
 *   │ Left     │ Center                 │ Right             │
 *   │ Component│ Configurable props     │ Live preview      │
 *   │ browser  │ (per-prop editors)     │ (single component │
 *   │ + scope  │                        │  + show all flag) │
 *   └──────────┴────────────────────────┴───────────────────┘
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  AlertCircle,
  ArrowLeftRight,
  ChevronDown,
  ChevronRight,
  History,
  Layers,
  Loader2,
  Moon,
  RotateCcw,
  Save,
  Search,
  Sun,
  Undo2,
} from "lucide-react"
import { Link } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  componentConfigurationsService,
  type ComponentConfigurationRecord,
  type ComponentKind,
  type ConfigScope,
  type ResolvedConfiguration,
} from "@/services/component-configurations-service"
import {
  composeEffectiveProps,
  emptyConfigStack,
  resolvePropSource,
  stackFromResolvedConfig,
  type ConfigStack,
  type PropOverrideMap,
} from "@/admin/components/config-resolver"
import { PropControlDispatcher } from "@/admin/components/PropControls"
import { renderComponentPreview } from "@/admin/components/preview-renderers"
import {
  getAllRegistered,
  type ConfigPropSchema,
  type RegistryEntry,
} from "@/admin/registry"


const VERTICALS = ["funeral_home", "manufacturing", "cemetery", "crematory"] as const
const KIND_ORDER: ComponentKind[] = [
  "widget",
  "focus",
  "focus-template",
  "document-block",
  "workflow-node",
]


type PreviewMode = "light" | "dark"


export default function ComponentEditorPage() {
  // ── Component selection ───────────────────────────────
  const [selectedKind, setSelectedKind] = useState<ComponentKind | null>(null)
  const [selectedName, setSelectedName] = useState<string | null>(null)
  const [browserSearch, setBrowserSearch] = useState("")
  const [browserVertical, setBrowserVertical] = useState<string>("all")
  const [collapsedKinds, setCollapsedKinds] = useState<Set<ComponentKind>>(new Set())

  // ── Editing scope ─────────────────────────────────────
  const [scope, setScope] = useState<ConfigScope>("platform_default")
  const [vertical, setVertical] = useState<string>("funeral_home")
  const [tenantIdInput, setTenantIdInput] = useState<string>("")

  // ── Preview state ─────────────────────────────────────
  const [previewMode, setPreviewMode] = useState<PreviewMode>("light")
  const [showAllInstances, setShowAllInstances] = useState(false)

  // ── Data state ────────────────────────────────────────
  const [resolved, setResolved] = useState<ResolvedConfiguration | null>(null)
  const [activeRow, setActiveRow] = useState<ComponentConfigurationRecord | null>(null)
  const [draft, setDraft] = useState<PropOverrideMap>({})
  const [isLoading, setIsLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  // ── Center-pane filter state ──────────────────────────
  const [propSearch, setPropSearch] = useState("")
  const [showOnlyOverridden, setShowOnlyOverridden] = useState(false)

  // ── Browser data ──────────────────────────────────────
  const allComponents = useMemo(() => getAllRegistered(), [])

  const filteredComponents = useMemo(() => {
    const term = browserSearch.trim().toLowerCase()
    return allComponents.filter((entry) => {
      if (browserVertical !== "all") {
        const vs = entry.metadata.verticals
        const matches =
          vs.includes("all") ||
          vs.includes(browserVertical as Parameters<typeof vs.includes>[0])
        if (!matches) return false
      }
      if (term) {
        const haystack = `${entry.metadata.name} ${entry.metadata.displayName} ${entry.metadata.description ?? ""}`.toLowerCase()
        if (!haystack.includes(term)) return false
      }
      return true
    })
  }, [allComponents, browserSearch, browserVertical])

  const groupedComponents = useMemo(() => {
    const map = new Map<ComponentKind, RegistryEntry[]>()
    for (const e of filteredComponents) {
      const list = map.get(e.metadata.type as ComponentKind) ?? []
      list.push(e)
      map.set(e.metadata.type as ComponentKind, list)
    }
    return map
  }, [filteredComponents])

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

  // ── Effective stack ────────────────────────────────────
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

  // ── Prop change handler ────────────────────────────────
  const handlePropChange = useCallback(
    (propName: string, value: unknown) => {
      setDraft((prev) => {
        const next = { ...prev }
        if (value === undefined) {
          delete next[propName]
        } else {
          next[propName] = value
        }
        return next
      })
    },
    [],
  )

  // ── Save ────────────────────────────────────────────────
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
      if (before !== after) count += 1
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

  // ── Center-pane filtered prop list ────────────────────
  const props = selectedEntry?.metadata.configurableProps ?? {}
  const filteredPropNames = useMemo(() => {
    const term = propSearch.trim().toLowerCase()
    return Object.keys(props).filter((key) => {
      const schema = props[key]
      if (showOnlyOverridden) {
        const source = resolvePropSource(key, stack)
        if (
          source === "registration-default" ||
          source === "platform-default"
        ) {
          return false
        }
      }
      if (term) {
        const hay = `${key} ${schema.displayLabel ?? ""} ${schema.description ?? ""}`.toLowerCase()
        if (!hay.includes(term)) return false
      }
      return true
    })
  }, [props, propSearch, showOnlyOverridden, stack])

  // ── Render ──────────────────────────────────────────────
  return (
    <div
      className="flex h-[calc(100vh-3rem)] flex-col"
      data-testid="component-editor-page"
    >
      {/* ── Top bar ─────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-4 border-b border-border-subtle bg-surface-elevated px-6 py-3">
        <div>
          <h1 className="text-h3 font-plex-serif font-medium text-content-strong">
            Component editor
          </h1>
          <p className="text-caption text-content-muted">
            Phase 3 of the Admin Visual Editor — configure registered components.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/admin/themes"
            className="flex items-center gap-1 text-caption text-content-muted hover:text-content-strong"
            data-testid="nav-to-themes"
          >
            <ArrowLeftRight size={12} />
            Edit theme
          </Link>
          {hasUnsaved && (
            <Badge
              variant="warning"
              data-testid="component-editor-unsaved-badge"
            >
              {unsavedChanges} unsaved
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
              data-testid="component-editor-save-error"
            >
              <AlertCircle size={12} />
              {saveError}
            </span>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDiscard}
            disabled={!hasUnsaved}
            data-testid="component-editor-discard"
          >
            <Undo2 size={14} className="mr-1" />
            Discard
          </Button>
          <Button
            size="sm"
            onClick={() => void handleSave()}
            disabled={!hasUnsaved || isSaving}
            data-testid="component-editor-save"
          >
            <Save size={14} className="mr-1" />
            Save
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled
            data-testid="component-editor-history"
          >
            <History size={14} className="mr-1" />
            History
          </Button>
        </div>
      </div>

      {/* ── Three-pane body ─────────────────────────────── */}
      <div className="grid flex-1 grid-cols-[300px_minmax(0,1fr)_minmax(0,1.1fr)] overflow-hidden">
        {/* ── Left pane — component browser + scope ───── */}
        <aside
          className="flex flex-col gap-3 overflow-y-auto border-r border-border-subtle bg-surface-sunken p-4"
          data-testid="component-editor-browser-pane"
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
                  ["tenant_override", "Tenant override"],
                ] as Array<[ConfigScope, string]>
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

          {scope === "tenant_override" && (
            <div>
              <label
                htmlFor="tenant-id-input"
                className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted"
              >
                Tenant ID
              </label>
              <input
                id="tenant-id-input"
                value={tenantIdInput}
                onChange={(e) => setTenantIdInput(e.target.value)}
                placeholder="tenant UUID"
                data-testid="tenant-id-input"
                className="w-full rounded-md border border-border-base bg-surface-raised px-2 py-1.5 font-plex-mono text-caption text-content-strong"
              />
            </div>
          )}

          <div>
            <label
              htmlFor="browser-vertical"
              className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted"
            >
              Browser vertical filter
            </label>
            <select
              id="browser-vertical"
              value={browserVertical}
              onChange={(e) => setBrowserVertical(e.target.value)}
              data-testid="browser-vertical-select"
              className="w-full rounded-md border border-border-base bg-surface-raised px-2 py-1.5 text-body-sm text-content-strong"
            >
              <option value="all">All verticals</option>
              {VERTICALS.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted">
              Components
            </label>
            <div className="flex items-center gap-1 mb-2">
              <Search size={12} className="text-content-muted" />
              <Input
                value={browserSearch}
                onChange={(e) => setBrowserSearch(e.target.value)}
                placeholder="Search components…"
                data-testid="browser-search"
                className="h-8 text-caption"
              />
            </div>
            <div data-testid="component-browser-list">
              {KIND_ORDER.map((kind) => {
                const list = groupedComponents.get(kind)
                if (!list || list.length === 0) return null
                const isCollapsed = collapsedKinds.has(kind)
                return (
                  <section
                    key={kind}
                    className="mb-2"
                    data-testid={`browser-kind-${kind}`}
                  >
                    <button
                      type="button"
                      onClick={() =>
                        setCollapsedKinds((prev) => {
                          const next = new Set(prev)
                          if (next.has(kind)) next.delete(kind)
                          else next.add(kind)
                          return next
                        })
                      }
                      className="flex w-full items-center gap-1 text-micro uppercase tracking-wider text-content-muted"
                    >
                      {isCollapsed ? (
                        <ChevronRight size={10} />
                      ) : (
                        <ChevronDown size={10} />
                      )}
                      {kind} ({list.length})
                    </button>
                    {!isCollapsed && (
                      <ul className="mt-1 flex flex-col">
                        {list.map((entry) => {
                          const isSelected =
                            entry.metadata.type === selectedKind &&
                            entry.metadata.name === selectedName
                          return (
                            <li key={`${entry.metadata.type}:${entry.metadata.name}`}>
                              <button
                                type="button"
                                data-testid={`browser-item-${entry.metadata.type}-${entry.metadata.name}`}
                                onClick={() => {
                                  setSelectedKind(entry.metadata.type as ComponentKind)
                                  setSelectedName(entry.metadata.name)
                                }}
                                className={`flex w-full items-center justify-between rounded-sm px-2 py-1 text-left text-body-sm ${
                                  isSelected
                                    ? "bg-accent-subtle text-content-strong"
                                    : "text-content-base hover:bg-accent-subtle/40"
                                }`}
                              >
                                <span>{entry.metadata.displayName}</span>
                              </button>
                            </li>
                          )
                        })}
                      </ul>
                    )}
                  </section>
                )
              })}
            </div>
          </div>
        </aside>

        {/* ── Center pane — config editor ─────────────── */}
        <div
          className="flex flex-col overflow-hidden"
          data-testid="component-editor-config-pane"
        >
          <div className="flex flex-col gap-2 border-b border-border-subtle bg-surface-elevated px-4 py-3">
            {selectedEntry ? (
              <>
                <div className="flex items-baseline justify-between">
                  <h2
                    className="text-h4 font-plex-serif font-medium text-content-strong"
                    data-testid="config-pane-title"
                  >
                    {selectedEntry.metadata.displayName}
                  </h2>
                  <code
                    className="font-plex-mono text-caption text-content-muted"
                    data-testid="config-pane-id"
                  >
                    {selectedEntry.metadata.type} · {selectedEntry.metadata.name}
                  </code>
                </div>
                {selectedEntry.metadata.description && (
                  <p className="text-caption text-content-muted">
                    {selectedEntry.metadata.description}
                  </p>
                )}
                <div className="flex items-center gap-2">
                  <Search size={14} className="text-content-muted" />
                  <Input
                    value={propSearch}
                    onChange={(e) => setPropSearch(e.target.value)}
                    placeholder="Search props…"
                    data-testid="prop-search-input"
                    className="flex-1"
                  />
                </div>
                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-2 text-caption text-content-muted">
                    <input
                      type="checkbox"
                      checked={showOnlyOverridden}
                      onChange={(e) => setShowOnlyOverridden(e.target.checked)}
                      data-testid="show-only-overridden-toggle"
                    />
                    Show only overridden props
                  </label>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleResetAll}
                    disabled={Object.keys(draft).length === 0}
                    data-testid="reset-all-overrides"
                  >
                    Reset all
                  </Button>
                </div>
              </>
            ) : (
              <div className="text-body-sm text-content-muted">
                Select a component from the browser.
              </div>
            )}
          </div>

          <div
            className="flex-1 overflow-y-auto px-4 py-3"
            data-testid="props-list"
          >
            {selectedEntry &&
              filteredPropNames.length === 0 && (
                <p className="text-body-sm text-content-muted">
                  No configurable props match the current filters.
                </p>
              )}
            {selectedEntry &&
              filteredPropNames.map((propName) => {
                const schema = props[propName] as ConfigPropSchema
                const value = effectiveProps[propName]
                const source = resolvePropSource(propName, stack)
                const isOverridden = propName in draft
                return (
                  <div
                    key={propName}
                    data-testid={`prop-row-${propName}`}
                    className="mb-3 rounded-md border border-border-subtle bg-surface-elevated p-3"
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <div>
                        <div className="text-body-sm font-medium text-content-strong">
                          {schema.displayLabel ?? propName}
                          {schema.required && (
                            <Badge variant="warning" className="ml-1.5">
                              required
                            </Badge>
                          )}
                        </div>
                        <code
                          className="font-plex-mono text-caption text-content-muted"
                          data-testid={`prop-row-${propName}-name`}
                        >
                          {propName}
                        </code>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge
                          variant="outline"
                          data-testid={`prop-row-${propName}-source`}
                        >
                          {source}
                        </Badge>
                        {isOverridden && (
                          <button
                            type="button"
                            onClick={() => handlePropChange(propName, undefined)}
                            data-testid={`prop-row-${propName}-reset`}
                            className="flex items-center gap-1 rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-muted hover:bg-accent-subtle"
                            aria-label={`Reset ${propName} to inherited`}
                          >
                            <RotateCcw size={11} />
                            Reset
                          </button>
                        )}
                      </div>
                    </div>
                    {schema.description && (
                      <p className="mt-1 text-caption text-content-muted">
                        {schema.description}
                      </p>
                    )}
                    <div className="mt-2">
                      <PropControlDispatcher
                        schema={schema}
                        value={value}
                        onChange={(next) => handlePropChange(propName, next)}
                        data-testid={`prop-control-${propName}`}
                      />
                    </div>
                  </div>
                )
              })}
            {isLoading && (
              <div className="text-caption text-content-muted">
                <Loader2 size={12} className="mr-1 inline animate-spin" />
                Resolving…
              </div>
            )}
            {loadError && (
              <div className="text-caption text-status-error">{loadError}</div>
            )}
          </div>
        </div>

        {/* ── Right pane — live preview ──────────────── */}
        <div
          className="flex flex-col overflow-hidden"
          data-testid="component-editor-preview-pane"
        >
          <div className="flex items-center justify-between border-b border-border-subtle bg-surface-elevated px-4 py-2">
            <div className="text-body-sm text-content-muted">
              Live preview · single component
            </div>
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-1 text-caption text-content-muted">
                <input
                  type="checkbox"
                  checked={showAllInstances}
                  onChange={(e) => setShowAllInstances(e.target.checked)}
                  data-testid="show-all-instances-toggle"
                />
                Show all instances
              </label>
              <div className="flex items-center gap-1 rounded-md border border-border-subtle bg-surface-raised p-0.5">
                <button
                  type="button"
                  data-testid="preview-mode-light"
                  onClick={() => setPreviewMode("light")}
                  className={`flex items-center gap-1 rounded-sm px-2 py-1 text-caption ${
                    previewMode === "light"
                      ? "bg-accent-subtle text-content-strong"
                      : "text-content-muted hover:bg-accent-subtle/40"
                  }`}
                >
                  <Sun size={12} /> Light
                </button>
                <button
                  type="button"
                  data-testid="preview-mode-dark"
                  onClick={() => setPreviewMode("dark")}
                  className={`flex items-center gap-1 rounded-sm px-2 py-1 text-caption ${
                    previewMode === "dark"
                      ? "bg-accent-subtle text-content-strong"
                      : "text-content-muted hover:bg-accent-subtle/40"
                  }`}
                >
                  <Moon size={12} /> Dark
                </button>
              </div>
            </div>
          </div>
          <div
            data-testid="component-editor-sandbox"
            data-mode={previewMode}
            style={{
              background: "var(--surface-base)",
              color: "var(--content-base)",
              flex: 1,
              overflowY: "auto",
              padding: "1.5rem",
              display: "grid",
              gridTemplateColumns: showAllInstances
                ? "repeat(auto-fit, minmax(280px, 1fr))"
                : "1fr",
              gap: "1rem",
              alignItems: "start",
            }}
          >
            {selectedEntry ? (
              showAllInstances ? (
                // Three slight variations to demonstrate config impact
                // across mock data variants.
                ["instance-1", "instance-2", "instance-3"].map((tag) => (
                  <div
                    key={tag}
                    data-testid={`preview-instance-${tag}`}
                    style={{ minHeight: 0 }}
                  >
                    {renderComponentPreview(
                      `${selectedEntry.metadata.type}:${selectedEntry.metadata.name}`,
                      effectiveProps,
                      selectedEntry.metadata.displayName,
                    )}
                  </div>
                ))
              ) : (
                <div data-testid="preview-instance-single">
                  {renderComponentPreview(
                    `${selectedEntry.metadata.type}:${selectedEntry.metadata.name}`,
                    effectiveProps,
                    selectedEntry.metadata.displayName,
                  )}
                </div>
              )
            ) : (
              <p
                style={{
                  fontFamily: "var(--font-plex-sans)",
                  color: "var(--content-muted)",
                  fontSize: "var(--text-body-sm)",
                }}
              >
                <Layers
                  size={14}
                  style={{ display: "inline", marginRight: "0.375rem" }}
                />
                Select a component to preview.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
