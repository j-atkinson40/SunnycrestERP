/**
 * CompositionEditorPage — canvas-based Focus composition editor
 * (May 2026 composition layer).
 *
 * v1 layout: three-pane preview-dominant matching the redesigned
 * component editor:
 *
 *   ┌─ Left (260px) ──┬─ Center (canvas) ──────┬─ Right (320px) ──┐
 *   │ Component       │ CompositionRenderer in │ Placement controls│
 *   │  palette        │ editorMode=true        │ + canvas config   │
 *   │  (canvas-       │ (CSS grid + selection  │ + scope selector  │
 *   │   placeable)    │  affordances)           │                   │
 *   └─────────────────┴─────────────────────────┴───────────────────┘
 *
 * v1 interaction model: form-based placement positioning. Click to
 * select a placement, then edit its grid coords + display config in
 * the right rail. Add new placements via the palette's "+ Add" button
 * (drops the component at the next-available grid cell). Drag-drop
 * positioning + resize handles are deferred to a follow-up — they
 * require non-trivial gesture infrastructure that this phase scopes
 * out per the "ship the foundation" approach. The data model + grid
 * positioning + renderer are all in place; the editor just uses
 * form-based controls for v1.
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
  Plus,
  Save,
  Search,
  Sun,
  Trash2,
  Undo2,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import {
  focusCompositionsService,
} from "@/bridgeable-admin/services/focus-compositions-service"
import type {
  CompositionRecord,
  Placement,
  ResolvedComposition,
} from "@/lib/visual-editor/compositions/types"
import { CompositionRenderer } from "@/lib/visual-editor/compositions/CompositionRenderer"
import {
  getCanvasMetadata,
  getCanvasPlaceableComponents,
  type ComponentKind,
  type RegistryEntry,
} from "@/lib/visual-editor/registry"
import { ComponentThumbnail } from "@/bridgeable-admin/components/visual-editor/ComponentThumbnail"
import {
  TenantPicker,
  type TenantSummary,
} from "@/bridgeable-admin/components/TenantPicker"


type Scope = "platform_default" | "vertical_default" | "tenant_override"
const VERTICALS = ["funeral_home", "manufacturing", "cemetery", "crematory"] as const
const FOCUS_TYPES = [
  "scheduling",
  "arrangement_scribe",
  "triage_decision",
  "coordination",
  "execution",
  "review",
  "generation",
] as const


type PreviewMode = "light" | "dark"


function defaultCanvasConfig() {
  return {
    total_columns: 12,
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


function findEmptyGridSlot(
  existing: Placement[],
  defaultDims: { columns: number; rows: number },
  totalColumns: number,
): { column_start: number; column_span: number; row_start: number; row_span: number } {
  const span = Math.min(defaultDims.columns, totalColumns)
  // Place at the first row where there's room; fall through to a
  // new row past every existing placement's bottom edge if needed.
  let row = 1
  for (let attempt = 0; attempt < 24; attempt++) {
    let col = 1
    while (col + span <= totalColumns + 1) {
      const overlap = existing.some((p) => {
        const pc0 = p.grid.column_start
        const pc1 = pc0 + p.grid.column_span
        const pr0 = p.grid.row_start
        const pr1 = pr0 + p.grid.row_span
        const newR1 = row + defaultDims.rows
        const newC1 = col + span
        return !(newC1 <= pc0 || pc1 <= col || newR1 <= pr0 || pr1 <= row)
      })
      if (!overlap) {
        return {
          column_start: col,
          column_span: span,
          row_start: row,
          row_span: defaultDims.rows,
        }
      }
      col += 1
    }
    row += 1
  }
  // Fallback — place below everything.
  const maxBottom = existing.reduce(
    (m, p) => Math.max(m, p.grid.row_start + p.grid.row_span),
    1,
  )
  return {
    column_start: 1,
    column_span: span,
    row_start: maxBottom,
    row_span: defaultDims.rows,
  }
}


export default function CompositionEditorPage() {
  // ── Selection ────────────────────────────────────────────
  const [scope, setScope] = useState<Scope>("vertical_default")
  const [vertical, setVertical] = useState<string>("funeral_home")
  const [tenantIdInput, setTenantIdInput] = useState<string>("")
  const [selectedTenant, setSelectedTenant] = useState<TenantSummary | null>(null)
  const [focusType, setFocusType] = useState<string>("scheduling")

  // ── Editor state ─────────────────────────────────────────
  const [resolved, setResolved] = useState<ResolvedComposition | null>(null)
  const [activeRow, setActiveRow] = useState<CompositionRecord | null>(null)
  const [draftPlacements, setDraftPlacements] = useState<Placement[]>([])
  const [draftCanvasConfig, setDraftCanvasConfig] = useState<
    CompositionRecord["canvas_config"]
  >(defaultCanvasConfig())
  const [selectedPlacementId, setSelectedPlacementId] = useState<string | null>(
    null,
  )

  const [isLoading, setIsLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  // ── Preview state ────────────────────────────────────────
  const [previewMode, setPreviewMode] = useState<PreviewMode>("light")
  const [rightRailCollapsed, setRightRailCollapsed] = useState(false)
  const [paletteSearch, setPaletteSearch] = useState("")

  // ── Component palette ────────────────────────────────────
  const palette = useMemo(() => getCanvasPlaceableComponents(), [])
  const filteredPalette = useMemo(() => {
    const term = paletteSearch.trim().toLowerCase()
    if (!term) return palette
    return palette.filter((e) => {
      const hay = `${e.metadata.name} ${e.metadata.displayName}`.toLowerCase()
      return hay.includes(term)
    })
  }, [palette, paletteSearch])

  // ── Resolve from backend whenever scope/focus changes ────
  const resolveAndLoadActive = useCallback(async () => {
    setIsLoading(true)
    setLoadError(null)
    try {
      const params: Parameters<typeof focusCompositionsService.resolve>[0] = {
        focus_type: focusType,
      }
      if (scope === "vertical_default") params.vertical = vertical
      if (scope === "tenant_override") params.tenant_id = tenantIdInput
      const result = await focusCompositionsService.resolve(params)
      setResolved(result)

      const listParams: Parameters<typeof focusCompositionsService.list>[0] = {
        scope,
        focus_type: focusType,
      }
      if (scope === "vertical_default") listParams.vertical = vertical
      if (scope === "tenant_override") listParams.tenant_id = tenantIdInput
      const rows = await focusCompositionsService.list(listParams)
      const active = rows.find((r) => r.is_active) ?? null
      setActiveRow(active)
      if (active) {
        setDraftPlacements([...active.placements])
        setDraftCanvasConfig({ ...active.canvas_config })
      } else {
        setDraftPlacements([])
        setDraftCanvasConfig(defaultCanvasConfig())
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[composition-editor] resolve failed", err)
      setLoadError(err instanceof Error ? err.message : "Failed to load")
    } finally {
      setIsLoading(false)
    }
  }, [scope, vertical, tenantIdInput, focusType])

  useEffect(() => {
    void resolveAndLoadActive()
  }, [resolveAndLoadActive])

  // Reset selection when scope / focus changes.
  useEffect(() => {
    setSelectedPlacementId(null)
  }, [scope, focusType])

  // ── Save / discard / autosave ────────────────────────────
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
  const hasUnsaved = draftSnapshot !== persistedSnapshot

  const handleSave = useCallback(async () => {
    if (!hasUnsaved && activeRow) return
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
          focus_type: focusType,
          vertical: scope === "vertical_default" ? vertical : null,
          tenant_id: scope === "tenant_override" ? tenantIdInput : null,
          placements: draftPlacements,
          canvas_config: draftCanvasConfig,
        })
        setActiveRow(created)
      }
      await resolveAndLoadActive()
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[composition-editor] save failed", err)
      setSaveError(err instanceof Error ? err.message : "Failed to save")
    } finally {
      setIsSaving(false)
    }
  }, [
    activeRow,
    draftCanvasConfig,
    draftPlacements,
    focusType,
    hasUnsaved,
    resolveAndLoadActive,
    scope,
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
    }, 2000)
    return () => {
      if (autosaveTimer.current !== null) {
        window.clearTimeout(autosaveTimer.current)
      }
    }
  }, [draftSnapshot, hasUnsaved, handleSave])

  const handleDiscard = useCallback(() => {
    if (activeRow) {
      setDraftPlacements([...activeRow.placements])
      setDraftCanvasConfig({ ...activeRow.canvas_config })
    } else {
      setDraftPlacements([])
      setDraftCanvasConfig(defaultCanvasConfig())
    }
  }, [activeRow])

  // ── Placement operations ────────────────────────────────
  const handleAddPlacement = useCallback(
    (entry: RegistryEntry) => {
      const meta = getCanvasMetadata(entry)
      const grid = findEmptyGridSlot(
        draftPlacements,
        meta.defaultDimensions,
        draftCanvasConfig.total_columns ?? 12,
      )
      const newPlacement: Placement = {
        placement_id: nextPlacementId(draftPlacements),
        component_kind: entry.metadata.type as ComponentKind,
        component_name: entry.metadata.name,
        grid,
        prop_overrides: {},
        display_config: { show_header: true, show_border: true },
      }
      setDraftPlacements((p) => [...p, newPlacement])
      setSelectedPlacementId(newPlacement.placement_id)
    },
    [draftPlacements, draftCanvasConfig.total_columns],
  )

  const handleDeletePlacement = useCallback((placementId: string) => {
    setDraftPlacements((p) =>
      p.filter((x) => x.placement_id !== placementId),
    )
    setSelectedPlacementId(null)
  }, [])

  const handleUpdateGrid = useCallback(
    (
      placementId: string,
      patch: Partial<Placement["grid"]>,
    ) => {
      setDraftPlacements((p) =>
        p.map((x) =>
          x.placement_id === placementId
            ? { ...x, grid: { ...x.grid, ...patch } }
            : x,
        ),
      )
    },
    [],
  )

  const selectedPlacement = useMemo(
    () =>
      selectedPlacementId
        ? draftPlacements.find((p) => p.placement_id === selectedPlacementId) ??
          null
        : null,
    [draftPlacements, selectedPlacementId],
  )

  // ── Synthesize a ResolvedComposition for the renderer ───
  const draftComposition: ResolvedComposition = useMemo(
    () => ({
      focus_type: focusType,
      vertical: scope === "platform_default" ? null : vertical,
      tenant_id: scope === "tenant_override" ? tenantIdInput : null,
      source: resolved?.source ?? null,
      source_id: resolved?.source_id ?? null,
      source_version: resolved?.source_version ?? null,
      placements: draftPlacements,
      canvas_config: draftCanvasConfig,
    }),
    [
      draftCanvasConfig,
      draftPlacements,
      focusType,
      resolved,
      scope,
      tenantIdInput,
      vertical,
    ],
  )

  // ── Render ───────────────────────────────────────────────
  return (
    <div
      className="flex h-[calc(100vh-3rem)] w-full flex-col"
      data-testid="composition-editor"
    >
      <div className="flex flex-1 overflow-hidden">
        {/* ── LEFT: Component palette ─────────────────────── */}
        <aside
          className="flex w-[260px] flex-shrink-0 flex-col border-r border-border-subtle bg-surface-elevated"
          data-testid="composition-palette"
        >
          <div className="border-b border-border-subtle px-3 py-2">
            <div className="text-h4 font-plex-serif text-content-strong">
              Palette
            </div>
            <div className="text-caption text-content-muted">
              {filteredPalette.length} canvas-placeable
            </div>
          </div>
          <div className="border-b border-border-subtle px-2 py-1.5">
            <div className="relative">
              <Search
                size={11}
                className="absolute left-2 top-1/2 -translate-y-1/2 text-content-muted"
              />
              <Input
                value={paletteSearch}
                onChange={(e) => setPaletteSearch(e.target.value)}
                placeholder="Filter palette"
                className="h-7 pl-7 text-caption"
                data-testid="palette-search"
              />
            </div>
          </div>
          <div
            className="flex-1 overflow-y-auto px-1 py-1"
            data-testid="palette-list"
          >
            {filteredPalette.map((entry) => (
              <button
                key={`${entry.metadata.type}:${entry.metadata.name}`}
                type="button"
                onClick={() => handleAddPlacement(entry)}
                className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left hover:bg-accent-subtle/30"
                data-testid={`palette-${entry.metadata.type}-${entry.metadata.name}`}
              >
                <ComponentThumbnail
                  kind={entry.metadata.type as ComponentKind}
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
                <Plus size={11} className="text-content-muted" />
              </button>
            ))}
            {filteredPalette.length === 0 && (
              <div className="px-2 py-6 text-center text-caption text-content-muted">
                No canvas-placeable components match.
              </div>
            )}
          </div>
        </aside>

        {/* ── CENTER: Canvas (composition preview in editor mode) ── */}
        <main
          className="relative flex flex-1 flex-col overflow-hidden bg-surface-sunken"
          data-testid="canvas-pane"
        >
          <div className="flex items-center justify-between border-b border-border-subtle bg-surface-elevated px-4 py-2">
            <div className="flex items-center gap-3">
              <span className="text-body-sm font-medium text-content-strong">
                {focusType}
              </span>
              <Badge variant="outline">
                {scope.replace("_", " ")}
              </Badge>
              {scope === "vertical_default" && (
                <Badge variant="outline">{vertical}</Badge>
              )}
              {resolved?.source && (
                <Badge variant="outline">
                  source: {resolved.source}
                </Badge>
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
                onClick={() => setPreviewMode((m) => (m === "light" ? "dark" : "light"))}
                className="flex items-center gap-1 rounded-sm border border-border-base px-2 py-1 text-caption text-content-strong hover:bg-accent-subtle/40"
                aria-label={`Preview mode: ${previewMode}`}
                data-testid="composition-preview-mode-toggle"
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
                data-testid="composition-rail-toggle"
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
            data-testid="composition-canvas-area"
          >
            <CompositionRenderer
              composition={draftComposition}
              editorMode={true}
              selectedPlacementId={selectedPlacementId}
              onPlacementClick={(id) => setSelectedPlacementId(id)}
            />
          </div>
        </main>

        {/* ── RIGHT: Composition controls ─────────────────── */}
        <aside
          className={
            rightRailCollapsed
              ? "flex w-12 flex-shrink-0 flex-col border-l border-border-subtle bg-surface-elevated"
              : "flex w-[320px] flex-shrink-0 flex-col border-l border-border-subtle bg-surface-elevated"
          }
          data-testid="composition-controls-pane"
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
                Composition
              </span>
            </div>
          ) : (
            <>
              {/* Save bar */}
              <div className="flex items-center justify-between gap-2 border-b border-border-subtle bg-surface-elevated px-3 py-2">
                <div className="flex items-center gap-1.5">
                  {hasUnsaved && (
                    <Badge variant="warning" data-testid="composition-unsaved-badge">
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
                    data-testid="composition-discard-button"
                  >
                    <Undo2 size={12} />
                  </Button>
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
              </div>

              {/* Scope + focus selectors */}
              <div className="border-b border-border-subtle px-3 py-2">
                <label className="mb-1 block text-micro uppercase tracking-wider text-content-muted">
                  Focus type
                </label>
                <select
                  value={focusType}
                  onChange={(e) => setFocusType(e.target.value)}
                  className="w-full rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-strong"
                  data-testid="focus-type-selector"
                >
                  {FOCUS_TYPES.map((ft) => (
                    <option key={ft} value={ft}>
                      {ft}
                    </option>
                  ))}
                </select>
                <label className="mb-1 mt-2 block text-micro uppercase tracking-wider text-content-muted">
                  Scope
                </label>
                <select
                  value={scope}
                  onChange={(e) => setScope(e.target.value as Scope)}
                  className="w-full rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-strong"
                  data-testid="composition-scope-selector"
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

              {/* Canvas config */}
              <div className="border-b border-border-subtle px-3 py-2">
                <div className="text-micro uppercase tracking-wider text-content-muted">
                  Canvas
                </div>
                <div className="mt-1.5 flex items-center gap-2 text-caption">
                  <span className="text-content-muted">Cols:</span>
                  <input
                    type="number"
                    min={1}
                    max={12}
                    value={draftCanvasConfig.total_columns ?? 12}
                    onChange={(e) =>
                      setDraftCanvasConfig({
                        ...draftCanvasConfig,
                        total_columns: Number(e.target.value),
                      })
                    }
                    className="w-14 rounded-sm border border-border-base bg-surface-raised px-1 py-0.5 font-plex-mono"
                    data-testid="canvas-cols-input"
                  />
                  <span className="text-content-muted">Gap:</span>
                  <input
                    type="number"
                    min={0}
                    max={48}
                    value={draftCanvasConfig.gap_size ?? 12}
                    onChange={(e) =>
                      setDraftCanvasConfig({
                        ...draftCanvasConfig,
                        gap_size: Number(e.target.value),
                      })
                    }
                    className="w-14 rounded-sm border border-border-base bg-surface-raised px-1 py-0.5 font-plex-mono"
                  />
                </div>
                <div className="mt-1.5">
                  <label className="block text-caption text-content-muted">
                    Background
                  </label>
                  <select
                    value={draftCanvasConfig.background_treatment ?? "surface-base"}
                    onChange={(e) =>
                      setDraftCanvasConfig({
                        ...draftCanvasConfig,
                        background_treatment: e.target.value,
                      })
                    }
                    className="mt-0.5 w-full rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-strong"
                  >
                    <option value="surface-base">surface-base</option>
                    <option value="surface-elevated">surface-elevated</option>
                    <option value="surface-sunken">surface-sunken</option>
                  </select>
                </div>
              </div>

              {/* Selected placement controls */}
              {selectedPlacement ? (
                <div className="flex-1 overflow-y-auto" data-testid="placement-controls">
                  <div className="border-b border-border-subtle px-3 py-2">
                    <div className="text-body-sm font-medium text-content-strong">
                      {selectedPlacement.component_name}
                    </div>
                    <div className="font-plex-mono text-caption text-content-muted">
                      {selectedPlacement.component_kind} · {selectedPlacement.placement_id}
                    </div>
                  </div>
                  <div className="px-3 py-2">
                    <div className="text-micro uppercase tracking-wider text-content-muted">
                      Grid position
                    </div>
                    <div className="mt-1.5 grid grid-cols-2 gap-2 text-caption">
                      {(["column_start", "column_span", "row_start", "row_span"] as const).map(
                        (k) => (
                          <label key={k} className="flex flex-col">
                            <span className="text-content-muted">{k}</span>
                            <input
                              type="number"
                              min={1}
                              value={selectedPlacement.grid[k]}
                              onChange={(e) =>
                                handleUpdateGrid(selectedPlacement.placement_id, {
                                  [k]: Number(e.target.value),
                                })
                              }
                              className="rounded-sm border border-border-base bg-surface-raised px-1 py-0.5 font-plex-mono text-content-strong"
                              data-testid={`placement-grid-${k}`}
                            />
                          </label>
                        ),
                      )}
                    </div>
                  </div>
                  <div className="border-t border-border-subtle px-3 py-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        handleDeletePlacement(selectedPlacement.placement_id)
                      }
                      className="w-full text-status-error"
                      data-testid="delete-placement"
                    >
                      <Trash2 size={11} className="mr-1" />
                      Delete placement
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="px-3 py-6 text-center text-caption text-content-muted">
                  Click a placement on the canvas to edit its position.
                </div>
              )}

              <div className="border-t border-border-subtle px-3 py-2">
                <Link
                  to={adminPath("/visual-editor/components")}
                  className="flex items-center justify-center gap-1 rounded-sm py-1.5 text-caption text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong"
                  data-testid="composition-link-to-components"
                >
                  <ArrowLeftRight size={11} />
                  Edit underlying components
                </Link>
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  )
}
