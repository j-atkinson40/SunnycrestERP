/**
 * ClassEditorPage — class-level configuration editor (May 2026).
 *
 * Three-pane preview-dominant layout, parallel to the redesigned
 * ComponentEditorPage but operates on classes:
 *
 *   ┌─ Left (320px) ──┬─ Center (dominant) ────────┬─ Right (320px) ──┐
 *   │ Class browser   │ Multi-component preview    │ Class config      │
 *   │ (9 v1 classes)  │ in appropriate context     │ controls          │
 *   │                 │ frame for the class        │                   │
 *   └─────────────────┴────────────────────────────┴───────────────────┘
 *
 * The preview renders multiple components from the class so the
 * operator sees "the class effect" — when they tune the widget
 * shadow at class level, all the widgets in the preview update
 * together.
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
  RotateCcw,
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
  type ClassConfigurationRecord,
  type ResolvedClassConfiguration,
} from "@/bridgeable-admin/services/component-class-configurations-service"
import {
  CLASS_REGISTRATIONS,
  getAllClassNames,
  getClassRegistration,
  getComponentsInClass,
  type ClassRegistration,
  type ConfigPropSchema,
  type ComponentKind,
  type RegistryEntry,
} from "@/lib/visual-editor/registry"
import { renderComponentPreview } from "@/lib/visual-editor/components/preview-renderers"
import { CompactPropControl } from "@/bridgeable-admin/components/visual-editor/CompactPropControl"
import { DashboardContextFrame } from "@/bridgeable-admin/components/visual-editor/context-frames/DashboardContextFrame"
import { FocusContextFrame } from "@/bridgeable-admin/components/visual-editor/context-frames/FocusContextFrame"
import { DocumentContextFrame } from "@/bridgeable-admin/components/visual-editor/context-frames/DocumentContextFrame"
import { WorkflowCanvasContextFrame } from "@/bridgeable-admin/components/visual-editor/context-frames/WorkflowCanvasContextFrame"
import { useStudioRail } from "@/bridgeable-admin/components/studio/StudioRailContext"


type PreviewMode = "light" | "dark"


function pickContextFrame(
  className: string,
  components: readonly RegistryEntry[],
): React.ReactNode {
  // Render up to 3 sample components from the class inside the
  // appropriate context frame so the operator sees the class's
  // shared treatment applied across multiple components at once.
  const samples = components.slice(0, 3)
  if (samples.length === 0) {
    return (
      <div className="flex h-full items-center justify-center bg-surface-base p-8 text-center text-content-muted">
        <div className="max-w-md">
          <div className="text-h4 font-plex-serif text-content-strong">
            No components registered in this class
          </div>
          <div className="mt-2 text-body-sm">
            Class-level changes only become visible once components are
            registered in this class. Component registration tracking lives
            in the registry inspector.
          </div>
        </div>
      </div>
    )
  }

  const renderPreview = (entry: RegistryEntry) =>
    renderComponentPreview(
      `${entry.metadata.type}:${entry.metadata.name}`,
      {},
      entry.metadata.displayName,
    )

  if (className === "widget") {
    return (
      <div className="flex h-full flex-col gap-3 p-4 text-content-base">
        <div className="text-caption text-content-muted">
          Sampling {samples.length} widget{samples.length === 1 ? "" : "s"} from
          this class.
        </div>
        <div className="grid flex-1 grid-cols-1 gap-3 lg:grid-cols-3">
          {samples.map((s) => (
            <div
              key={s.metadata.name}
              className="overflow-hidden rounded-md border border-border-subtle bg-surface-elevated"
              data-testid={`class-preview-instance-${s.metadata.name}`}
            >
              <div className="border-b border-border-subtle bg-surface-sunken px-3 py-1.5 text-caption text-content-muted">
                {s.metadata.displayName}
              </div>
              <div className="p-2">{renderPreview(s)}</div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (className === "focus" || className === "focus-template") {
    return (
      <FocusContextFrame
        focusType="unknown"
        title={`${samples[0].metadata.displayName} preview`}
      >
        <div className="grid gap-3 p-4">
          {samples.map((s) => (
            <div
              key={s.metadata.name}
              className="rounded-md border border-border-subtle p-3"
              data-testid={`class-preview-instance-${s.metadata.name}`}
            >
              <div className="text-caption text-content-muted">
                {s.metadata.displayName}
              </div>
              <div>{renderPreview(s)}</div>
            </div>
          ))}
        </div>
      </FocusContextFrame>
    )
  }

  if (className === "document-block") {
    return (
      <DocumentContextFrame position="inline">
        <div className="flex flex-col gap-3 py-3">
          {samples.map((s) => (
            <div
              key={s.metadata.name}
              data-testid={`class-preview-instance-${s.metadata.name}`}
            >
              {renderPreview(s)}
            </div>
          ))}
        </div>
      </DocumentContextFrame>
    )
  }

  if (className === "workflow-node") {
    return (
      <WorkflowCanvasContextFrame nodeType="default">
        <div className="flex flex-col gap-2 p-2">
          {samples.map((s) => (
            <div
              key={s.metadata.name}
              data-testid={`class-preview-instance-${s.metadata.name}`}
            >
              {renderPreview(s)}
            </div>
          ))}
        </div>
      </WorkflowCanvasContextFrame>
    )
  }

  if (className === "entity-card") {
    return (
      <DashboardContextFrame>
        <div className="flex flex-col gap-2">
          {samples.map((s) => (
            <div
              key={s.metadata.name}
              data-testid={`class-preview-instance-${s.metadata.name}`}
              className="rounded-md border border-border-subtle bg-surface-elevated p-3"
            >
              <div className="text-caption text-content-muted">
                {s.metadata.displayName}
              </div>
              {renderPreview(s)}
            </div>
          ))}
        </div>
      </DashboardContextFrame>
    )
  }

  // button / form-input / surface-card — render multiple stand-ins
  return (
    <div className="flex h-full items-center justify-center bg-surface-base p-8">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {samples.map((s) => (
          <div
            key={s.metadata.name}
            data-testid={`class-preview-instance-${s.metadata.name}`}
            className="rounded-md border border-border-subtle bg-surface-elevated p-4"
          >
            <div className="mb-2 text-caption text-content-muted">
              {s.metadata.displayName}
            </div>
            {renderPreview(s)}
          </div>
        ))}
      </div>
    </div>
  )
}


export default function ClassEditorPage() {
  // Studio 1a-i.B — hide editor's own left pane when inside Studio shell
  // with rail expanded. Standalone callers keep left pane visible.
  const { railExpanded, inStudioContext } = useStudioRail()
  const hideLeftPane = railExpanded && inStudioContext

  // ── Selection ────────────────────────────────────────────
  const [selectedClass, setSelectedClass] = useState<string | null>(null)
  const [browserSearch, setBrowserSearch] = useState("")

  // ── Preview state ────────────────────────────────────────
  const [previewMode, setPreviewMode] = useState<PreviewMode>("light")
  const [rightRailCollapsed, setRightRailCollapsed] = useState(false)

  // ── Backend data ─────────────────────────────────────────
  const [resolved, setResolved] = useState<ResolvedClassConfiguration | null>(
    null,
  )
  const [activeRow, setActiveRow] = useState<ClassConfigurationRecord | null>(
    null,
  )
  const [draft, setDraft] = useState<Record<string, unknown>>({})
  const [isLoading, setIsLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  // ── Browser data ─────────────────────────────────────────
  const allClasses = useMemo(() => getAllClassNames(), [])
  const filteredClasses = useMemo(() => {
    const term = browserSearch.trim().toLowerCase()
    return allClasses.filter((cn) => {
      const reg = getClassRegistration(cn)
      if (!reg) return false
      if (term) {
        const hay = `${cn} ${reg.displayName} ${reg.description}`.toLowerCase()
        return hay.includes(term)
      }
      return true
    })
  }, [allClasses, browserSearch])

  // Auto-select the first class on mount.
  useEffect(() => {
    if (!selectedClass && allClasses.length > 0) {
      setSelectedClass(allClasses[0])
    }
  }, [allClasses, selectedClass])

  // Reset draft when class changes.
  useEffect(() => {
    setDraft({})
  }, [selectedClass])

  // ── Resolve from backend whenever class changes ──────────
  const resolveAndLoadActive = useCallback(async () => {
    if (!selectedClass) return
    setIsLoading(true)
    setLoadError(null)
    try {
      const resolveResult =
        await componentClassConfigurationsService.resolve(selectedClass)
      setResolved(resolveResult)

      const rows = await componentClassConfigurationsService.list({
        component_class: selectedClass,
      })
      const active = rows.find((r) => r.is_active) ?? null
      setActiveRow(active)
      setDraft(active ? { ...active.prop_overrides } : {})
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[class-editor] resolve failed", err)
      setLoadError(err instanceof Error ? err.message : "Failed to load")
    } finally {
      setIsLoading(false)
    }
  }, [selectedClass])

  useEffect(() => {
    void resolveAndLoadActive()
  }, [resolveAndLoadActive])

  const selectedRegistration: ClassRegistration | undefined = selectedClass
    ? getClassRegistration(selectedClass)
    : undefined

  const componentsInClass = useMemo<readonly RegistryEntry[]>(
    () => (selectedClass ? getComponentsInClass(selectedClass) : []),
    [selectedClass],
  )

  // ── Effective props (registration default + draft) ───────
  const effectiveProps = useMemo(() => {
    if (!selectedRegistration) return {}
    const defaults: Record<string, unknown> = {}
    for (const [name, prop] of Object.entries(
      selectedRegistration.configurableProps,
    )) {
      defaults[name] = prop.default
    }
    const persisted = resolved?.props ?? {}
    return { ...defaults, ...persisted, ...draft }
  }, [selectedRegistration, resolved, draft])

  // ── Save / discard / autosave ────────────────────────────
  const persistedOverrides = useMemo(
    () => (activeRow ? { ...activeRow.prop_overrides } : {}),
    [activeRow],
  )

  const unsavedChanges = useMemo(() => {
    const keys = new Set([
      ...Object.keys(draft),
      ...Object.keys(persistedOverrides),
    ])
    let n = 0
    for (const k of keys) {
      if (JSON.stringify(draft[k]) !== JSON.stringify(persistedOverrides[k])) n++
    }
    return n
  }, [draft, persistedOverrides])
  const hasUnsaved = unsavedChanges > 0

  const handleSave = useCallback(async () => {
    if (!selectedClass) return
    if (!hasUnsaved && activeRow) return
    setIsSaving(true)
    setSaveError(null)
    try {
      if (activeRow) {
        const updated = await componentClassConfigurationsService.update(
          activeRow.id,
          draft,
        )
        setActiveRow(updated)
      } else {
        const created = await componentClassConfigurationsService.create({
          component_class: selectedClass,
          prop_overrides: draft,
        })
        setActiveRow(created)
      }
      await resolveAndLoadActive()
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[class-editor] save failed", err)
      setSaveError(err instanceof Error ? err.message : "Failed to save")
    } finally {
      setIsSaving(false)
    }
  }, [activeRow, draft, hasUnsaved, resolveAndLoadActive, selectedClass])

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
    if (!window.confirm("Reset all class-level overrides to registration defaults?"))
      return
    setDraft({})
  }, [])

  const handlePropChange = useCallback(
    (propName: string, next: unknown) => {
      if (!selectedRegistration) return
      const schemaDefault =
        selectedRegistration.configurableProps[propName]?.default
      setDraft((d) => {
        const out = { ...d }
        if (JSON.stringify(next) === JSON.stringify(schemaDefault)) {
          delete out[propName]
        } else {
          out[propName] = next
        }
        return out
      })
    },
    [selectedRegistration],
  )

  const handlePropReset = useCallback((propName: string) => {
    setDraft((d) => {
      const out = { ...d }
      delete out[propName]
      return out
    })
  }, [])

  // ── Render ───────────────────────────────────────────────
  return (
    <div
      className="flex h-[calc(100vh-3rem)] w-full flex-col"
      data-testid="class-editor"
    >
      <div className="flex flex-1 overflow-hidden">
        {/* ── LEFT: Class browser ─────────────────────────── */}
        {!hideLeftPane && (
        <aside
          className="flex w-[320px] flex-shrink-0 flex-col border-r border-border-subtle bg-surface-elevated"
          data-testid="class-browser"
        >
          <div className="border-b border-border-subtle px-4 py-3">
            <div className="text-h4 font-plex-serif text-content-strong">
              Classes
            </div>
            <div className="text-caption text-content-muted">
              {filteredClasses.length} of {allClasses.length} classes
            </div>
          </div>
          <div className="border-b border-border-subtle px-3 py-2">
            <div className="relative">
              <Search
                size={12}
                className="absolute left-2 top-1/2 -translate-y-1/2 text-content-muted"
              />
              <Input
                value={browserSearch}
                onChange={(e) => setBrowserSearch(e.target.value)}
                placeholder="Search classes"
                className="h-8 pl-7 text-body-sm"
                data-testid="class-browser-search"
              />
            </div>
          </div>
          <div className="flex-1 overflow-y-auto px-1 py-1" data-testid="class-list">
            {filteredClasses.map((cn) => {
              const reg = CLASS_REGISTRATIONS[cn]
              if (!reg) return null
              const components = getComponentsInClass(cn)
              const isSelected = selectedClass === cn
              return (
                <button
                  key={cn}
                  type="button"
                  onClick={() => setSelectedClass(cn)}
                  className={
                    isSelected
                      ? "flex w-full flex-col items-start gap-0.5 rounded-sm bg-accent-subtle px-3 py-2 text-left"
                      : "flex w-full flex-col items-start gap-0.5 rounded-sm px-3 py-2 text-left hover:bg-accent-subtle/30"
                  }
                  data-testid={`class-${cn}`}
                  data-selected={isSelected ? "true" : "false"}
                >
                  <span className="text-body-sm font-medium text-content-strong">
                    {reg.displayName}
                  </span>
                  <span className="font-plex-mono text-caption text-content-muted">
                    {cn}
                  </span>
                  <span className="text-caption text-content-subtle">
                    {components.length} component
                    {components.length === 1 ? "" : "s"} ·{" "}
                    {Object.keys(reg.configurableProps).length} prop
                    {Object.keys(reg.configurableProps).length === 1 ? "" : "s"}
                  </span>
                </button>
              )
            })}
          </div>
        </aside>
        )}

        {/* ── CENTER: Multi-component preview ─────────────── */}
        <main
          className="relative flex flex-1 flex-col overflow-hidden bg-surface-sunken"
          data-testid="class-preview-pane"
        >
          <div className="flex items-center justify-between border-b border-border-subtle bg-surface-elevated px-4 py-2">
            <div className="flex items-center gap-3">
              {selectedRegistration && (
                <>
                  <span className="text-body-sm font-medium text-content-strong">
                    {selectedRegistration.displayName}
                  </span>
                  <Badge variant="outline">
                    {componentsInClass.length} component
                    {componentsInClass.length === 1 ? "" : "s"}
                  </Badge>
                </>
              )}
              {isLoading && (
                <Loader2 size={12} className="animate-spin text-content-muted" />
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
                onClick={() =>
                  setPreviewMode((m) => (m === "light" ? "dark" : "light"))
                }
                className="flex items-center gap-1 rounded-sm border border-border-base px-2 py-1 text-caption text-content-strong hover:bg-accent-subtle/40"
                aria-label={`Preview mode: ${previewMode}`}
                data-testid="class-preview-mode-toggle"
              >
                {previewMode === "light" ? <Sun size={12} /> : <Moon size={12} />}
                {previewMode}
              </button>
              <button
                type="button"
                onClick={() => setRightRailCollapsed((c) => !c)}
                className="rounded-sm border border-border-base p-1 text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong"
                aria-label={
                  rightRailCollapsed ? "Expand controls" : "Collapse controls"
                }
                data-testid="class-rail-toggle"
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
            className="flex-1 overflow-auto"
            data-mode={previewMode}
            data-testid="class-preview-canvas"
          >
            {selectedClass ? pickContextFrame(selectedClass, componentsInClass) : null}
          </div>
        </main>

        {/* ── RIGHT: Class config controls ────────────────── */}
        <aside
          className={
            rightRailCollapsed
              ? "flex w-12 flex-shrink-0 flex-col border-l border-border-subtle bg-surface-elevated"
              : "flex w-[320px] flex-shrink-0 flex-col border-l border-border-subtle bg-surface-elevated"
          }
          data-testid="class-properties-pane"
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
                Class config
              </span>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between gap-2 border-b border-border-subtle bg-surface-elevated px-3 py-2">
                <div className="flex items-center gap-1.5">
                  {hasUnsaved && (
                    <Badge variant="warning" data-testid="class-unsaved-badge">
                      {unsavedChanges} unsaved
                    </Badge>
                  )}
                  {isSaving && (
                    <Loader2
                      size={12}
                      className="animate-spin text-content-muted"
                    />
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
                    data-testid="class-discard-button"
                  >
                    <Undo2 size={12} />
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => void handleSave()}
                    disabled={!hasUnsaved}
                    data-testid="class-save-button"
                  >
                    <Save size={12} className="mr-1" />
                    Save
                  </Button>
                </div>
              </div>

              {selectedRegistration ? (
                <>
                  <div className="border-b border-border-subtle px-3 py-2">
                    <div className="text-body-sm font-medium text-content-strong">
                      {selectedRegistration.displayName}
                    </div>
                    <div className="mt-0.5 font-plex-mono text-caption text-content-muted">
                      {selectedRegistration.className}
                    </div>
                    <div className="mt-1 text-caption text-content-muted">
                      {selectedRegistration.description}
                    </div>
                  </div>

                  <div
                    className="flex-1 overflow-y-auto py-2"
                    data-testid="class-prop-list"
                  >
                    {Object.entries(selectedRegistration.configurableProps).map(
                      ([propName, propSchema]: [string, ConfigPropSchema]) => {
                        const isOverridden = propName in draft || propName in persistedOverrides
                        const source = propName in draft
                          ? "draft"
                          : propName in persistedOverrides
                            ? "platform-default" // class layer surfaces as "configured" — reuse platform-default badge
                            : "registration-default"
                        return (
                          <CompactPropControl
                            key={propName}
                            name={propName}
                            schema={propSchema}
                            value={effectiveProps[propName]}
                            onChange={(v) => handlePropChange(propName, v)}
                            source={source}
                            isOverriddenAtCurrentScope={isOverridden}
                            onReset={() => handlePropReset(propName)}
                          />
                        )
                      },
                    )}
                  </div>

                  <div className="border-t border-border-subtle px-3 py-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={handleResetAll}
                      disabled={Object.keys(draft).length === 0}
                      className="w-full text-caption"
                      data-testid="class-reset-all"
                    >
                      <RotateCcw size={11} className="mr-1" />
                      Reset all to defaults
                    </Button>
                    <Link
                      to={adminPath("/visual-editor/components")}
                      className="mt-2 flex items-center justify-center gap-1 rounded-sm py-1.5 text-caption text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong"
                      data-testid="class-link-to-components"
                    >
                      <ArrowLeftRight size={11} />
                      Edit individual components
                    </Link>
                  </div>
                </>
              ) : (
                <div className="px-3 py-6 text-center text-caption text-content-muted">
                  No class selected.
                </div>
              )}
            </>
          )}
        </aside>
      </div>
    </div>
  )
}


// Cosmetic: silence the linter about unused ComponentKind import in
// some build configurations.
export type _UnusedComponentKind = ComponentKind
