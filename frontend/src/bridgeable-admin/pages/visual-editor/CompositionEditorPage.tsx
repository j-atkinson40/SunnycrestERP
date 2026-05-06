/**
 * CompositionEditorPage — canvas-based Focus composition editor
 * (May 2026 composition layer + drag-drop interaction layer).
 *
 * v2 layout: three-pane preview-dominant matching the redesigned
 * component editor:
 *
 *   ┌─ Left (260px) ──┬─ Center (canvas) ──────┬─ Right (320px) ──┐
 *   │ Component       │ InteractivePlacement   │ Placement controls│
 *   │  palette        │   Canvas (drag/resize/ │ + canvas config   │
 *   │  (canvas-       │    multi-select/       │ + scope selector  │
 *   │   placeable)    │    marquee)            │ + multi-select bulk│
 *   └─────────────────┴─────────────────────────┴───────────────────┘
 *
 * Interaction model: drag placements to reposition (grid snap), grab
 * 8 corner/edge resize handles when single-selected, click to select,
 * shift-click to add to selection, marquee-select on canvas
 * background. Undo/redo via Cmd+Z / Cmd+Shift+Z (capped at 50
 * entries). Keyboard shortcuts: Delete (remove selected), arrow keys
 * (nudge by one cell), Cmd+D (duplicate). The form-based grid editor
 * stays in the right rail as a fallback for single-selected
 * placements — power users can drag, precise users can type.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Link } from "react-router-dom"
import {
  AlertCircle,
  ArrowLeftRight,
  Grid3x3,
  Loader2,
  Moon,
  PanelRightClose,
  PanelRightOpen,
  Plus,
  Redo2,
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
import { InteractivePlacementCanvas } from "@/bridgeable-admin/components/visual-editor/composition-canvas/InteractivePlacementCanvas"


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


type CanvasConfig = CompositionRecord["canvas_config"]


interface DraftSnapshot {
  placements: Placement[]
  canvasConfig: CanvasConfig
}


const UNDO_STACK_LIMIT = 50


function defaultCanvasConfig(): CanvasConfig {
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
  const [draftCanvasConfig, setDraftCanvasConfig] = useState<CanvasConfig>(
    defaultCanvasConfig(),
  )
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  const [isLoading, setIsLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  // ── Preview state ────────────────────────────────────────
  const [previewMode, setPreviewMode] = useState<PreviewMode>("light")
  const [rightRailCollapsed, setRightRailCollapsed] = useState(false)
  const [paletteSearch, setPaletteSearch] = useState("")
  const [showGrid, setShowGrid] = useState(true)

  // ── Undo / redo stack ─────────────────────────────────────
  // Stack of historical snapshots; pointer = current position.
  // Push on every commit (drag, resize, add, delete, nudge).
  // Replay snapshot on undo/redo.
  const undoStack = useRef<DraftSnapshot[]>([])
  const undoPointer = useRef<number>(-1)
  const isReplayingRef = useRef(false)

  const pushSnapshot = useCallback(
    (placements: Placement[], canvasConfig: CanvasConfig) => {
      if (isReplayingRef.current) return
      // Drop any "redo" tail past the current pointer.
      undoStack.current = undoStack.current.slice(0, undoPointer.current + 1)
      undoStack.current.push({
        placements: placements.map((p) => ({
          ...p,
          grid: { ...p.grid },
          prop_overrides: { ...p.prop_overrides },
          display_config: p.display_config ? { ...p.display_config } : {},
        })),
        canvasConfig: { ...canvasConfig },
      })
      // Cap the stack.
      if (undoStack.current.length > UNDO_STACK_LIMIT) {
        const overflow = undoStack.current.length - UNDO_STACK_LIMIT
        undoStack.current = undoStack.current.slice(overflow)
      }
      undoPointer.current = undoStack.current.length - 1
    },
    [],
  )

  const replaySnapshot = useCallback((snap: DraftSnapshot) => {
    isReplayingRef.current = true
    setDraftPlacements(snap.placements.map((p) => ({ ...p, grid: { ...p.grid } })))
    setDraftCanvasConfig({ ...snap.canvasConfig })
    // Allow next commit to push fresh.
    queueMicrotask(() => {
      isReplayingRef.current = false
    })
  }, [])

  const handleUndo = useCallback(() => {
    if (undoPointer.current <= 0) return
    undoPointer.current -= 1
    const snap = undoStack.current[undoPointer.current]
    if (snap) replaySnapshot(snap)
  }, [replaySnapshot])

  const handleRedo = useCallback(() => {
    if (undoPointer.current >= undoStack.current.length - 1) return
    undoPointer.current += 1
    const snap = undoStack.current[undoPointer.current]
    if (snap) replaySnapshot(snap)
  }, [replaySnapshot])

  const canUndo = undoPointer.current > 0
  const canRedo =
    undoPointer.current >= 0 &&
    undoPointer.current < undoStack.current.length - 1

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

      // Reset undo stack when loading a different active row.
      undoStack.current = []
      undoPointer.current = -1
      isReplayingRef.current = true
      if (active) {
        setDraftPlacements([...active.placements])
        setDraftCanvasConfig({ ...active.canvas_config })
      } else {
        setDraftPlacements([])
        setDraftCanvasConfig(defaultCanvasConfig())
      }
      // Push initial snapshot once the state settles.
      queueMicrotask(() => {
        isReplayingRef.current = false
        pushSnapshot(
          active ? [...active.placements] : [],
          active ? { ...active.canvas_config } : defaultCanvasConfig(),
        )
      })
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[composition-editor] resolve failed", err)
      setLoadError(err instanceof Error ? err.message : "Failed to load")
    } finally {
      setIsLoading(false)
    }
  }, [scope, vertical, tenantIdInput, focusType, pushSnapshot])

  useEffect(() => {
    void resolveAndLoadActive()
  }, [resolveAndLoadActive])

  // Reset selection when scope / focus changes.
  useEffect(() => {
    setSelectedIds(new Set())
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
    isReplayingRef.current = true
    if (activeRow) {
      setDraftPlacements([...activeRow.placements])
      setDraftCanvasConfig({ ...activeRow.canvas_config })
    } else {
      setDraftPlacements([])
      setDraftCanvasConfig(defaultCanvasConfig())
    }
    setSelectedIds(new Set())
    queueMicrotask(() => {
      isReplayingRef.current = false
    })
  }, [activeRow])

  // ── Placement operations (each pushes an undo snapshot) ──
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
      const next = [...draftPlacements, newPlacement]
      setDraftPlacements(next)
      setSelectedIds(new Set([newPlacement.placement_id]))
      pushSnapshot(next, draftCanvasConfig)
    },
    [draftPlacements, draftCanvasConfig, pushSnapshot],
  )

  const handleDeleteSelected = useCallback(() => {
    if (selectedIds.size === 0) return
    const next = draftPlacements.filter(
      (x) => !selectedIds.has(x.placement_id),
    )
    setDraftPlacements(next)
    setSelectedIds(new Set())
    pushSnapshot(next, draftCanvasConfig)
  }, [draftPlacements, draftCanvasConfig, selectedIds, pushSnapshot])

  const handleDuplicateSelected = useCallback(() => {
    if (selectedIds.size === 0) return
    const additions: Placement[] = []
    let working = [...draftPlacements]
    for (const id of selectedIds) {
      const src = working.find((p) => p.placement_id === id)
      if (!src) continue
      // Copy metadata; offset by one row, find empty slot.
      const entry = palette.find(
        (e) =>
          e.metadata.type === src.component_kind &&
          e.metadata.name === src.component_name,
      )
      const meta = entry
        ? getCanvasMetadata(entry)
        : { defaultDimensions: { columns: src.grid.column_span, rows: src.grid.row_span } }
      const grid = findEmptyGridSlot(
        working,
        { columns: src.grid.column_span, rows: meta.defaultDimensions.rows },
        draftCanvasConfig.total_columns ?? 12,
      )
      const dup: Placement = {
        placement_id: nextPlacementId(working),
        component_kind: src.component_kind,
        component_name: src.component_name,
        grid,
        prop_overrides: { ...src.prop_overrides },
        display_config: src.display_config ? { ...src.display_config } : {},
      }
      working = [...working, dup]
      additions.push(dup)
    }
    if (additions.length === 0) return
    setDraftPlacements(working)
    setSelectedIds(new Set(additions.map((p) => p.placement_id)))
    pushSnapshot(working, draftCanvasConfig)
  }, [draftPlacements, draftCanvasConfig, selectedIds, palette, pushSnapshot])

  const handleNudgeSelected = useCallback(
    (dx: number, dy: number) => {
      if (selectedIds.size === 0) return
      const totalCols = draftCanvasConfig.total_columns ?? 12
      const next = draftPlacements.map((p) => {
        if (!selectedIds.has(p.placement_id)) return p
        const newColStart = Math.max(
          1,
          Math.min(totalCols - p.grid.column_span + 1, p.grid.column_start + dx),
        )
        const newRowStart = Math.max(1, p.grid.row_start + dy)
        return {
          ...p,
          grid: {
            ...p.grid,
            column_start: newColStart,
            row_start: newRowStart,
          },
        }
      })
      setDraftPlacements(next)
      pushSnapshot(next, draftCanvasConfig)
    },
    [draftPlacements, draftCanvasConfig, selectedIds, pushSnapshot],
  )

  const handleUpdateGrid = useCallback(
    (placementId: string, patch: Partial<Placement["grid"]>) => {
      const next = draftPlacements.map((x) =>
        x.placement_id === placementId
          ? { ...x, grid: { ...x.grid, ...patch } }
          : x,
      )
      setDraftPlacements(next)
      pushSnapshot(next, draftCanvasConfig)
    },
    [draftPlacements, draftCanvasConfig, pushSnapshot],
  )

  // ── Canvas drag/resize commits ───────────────────────────
  const handlePlacementsChange = useCallback(
    (next: Placement[]) => {
      setDraftPlacements(next)
    },
    [],
  )
  const handleCommitDrag = useCallback(
    (
      _updates: Array<{ placementId: string; newGrid: Placement["grid"] }>,
    ) => {
      // The component already applied the updates via
      // onPlacementsChange before calling onCommitDrag; we just push
      // the snapshot using the latest state via a microtask so
      // setDraftPlacements has settled.
      queueMicrotask(() => {
        setDraftPlacements((current) => {
          pushSnapshot(current, draftCanvasConfig)
          return current
        })
      })
    },
    [draftCanvasConfig, pushSnapshot],
  )
  const handleCommitResize = useCallback(
    (_placementId: string, _newGrid: Placement["grid"]) => {
      queueMicrotask(() => {
        setDraftPlacements((current) => {
          pushSnapshot(current, draftCanvasConfig)
          return current
        })
      })
    },
    [draftCanvasConfig, pushSnapshot],
  )

  // ── Selection ────────────────────────────────────────────
  const handleSelect = useCallback(
    (id: string, opts: { shift: boolean }) => {
      setSelectedIds((prev) => {
        if (opts.shift) {
          const next = new Set(prev)
          if (next.has(id)) next.delete(id)
          else next.add(id)
          return next
        }
        return new Set([id])
      })
    },
    [],
  )
  const handleDeselectAll = useCallback(() => {
    setSelectedIds(new Set())
  }, [])
  const handleMarqueeSelect = useCallback(
    (ids: string[], opts: { shift: boolean }) => {
      setSelectedIds((prev) => {
        if (opts.shift) {
          const next = new Set(prev)
          for (const id of ids) next.add(id)
          return next
        }
        return new Set(ids)
      })
    },
    [],
  )

  const selectedPlacement = useMemo(
    () =>
      selectedIds.size === 1
        ? draftPlacements.find((p) =>
            selectedIds.has(p.placement_id),
          ) ?? null
        : null,
    [draftPlacements, selectedIds],
  )

  // ── Keyboard shortcuts ───────────────────────────────────
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Don't intercept while user is typing in an input/textarea/etc.
      const target = e.target as HTMLElement | null
      if (target) {
        const tag = target.tagName
        if (
          tag === "INPUT" ||
          tag === "TEXTAREA" ||
          tag === "SELECT" ||
          target.isContentEditable
        ) {
          return
        }
      }

      const meta = e.metaKey || e.ctrlKey

      // Undo / redo
      if (meta && e.key.toLowerCase() === "z") {
        e.preventDefault()
        if (e.shiftKey) handleRedo()
        else handleUndo()
        return
      }
      if (meta && e.key.toLowerCase() === "y") {
        e.preventDefault()
        handleRedo()
        return
      }

      // Duplicate
      if (meta && e.key.toLowerCase() === "d") {
        e.preventDefault()
        handleDuplicateSelected()
        return
      }

      // Delete selected
      if ((e.key === "Backspace" || e.key === "Delete") && !meta) {
        if (selectedIds.size > 0) {
          e.preventDefault()
          handleDeleteSelected()
        }
        return
      }

      // Arrow nudge
      if (e.key.startsWith("Arrow") && !meta) {
        if (selectedIds.size === 0) return
        e.preventDefault()
        const step = e.shiftKey ? 3 : 1
        switch (e.key) {
          case "ArrowLeft":
            handleNudgeSelected(-step, 0)
            break
          case "ArrowRight":
            handleNudgeSelected(step, 0)
            break
          case "ArrowUp":
            handleNudgeSelected(0, -step)
            break
          case "ArrowDown":
            handleNudgeSelected(0, step)
            break
        }
      }

      // Escape clears selection
      if (e.key === "Escape") {
        setSelectedIds(new Set())
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [
    handleUndo,
    handleRedo,
    handleDuplicateSelected,
    handleDeleteSelected,
    handleNudgeSelected,
    selectedIds.size,
  ])

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

        {/* ── CENTER: Interactive canvas ─────────────────── */}
        <main
          className="relative flex flex-1 flex-col overflow-hidden bg-surface-sunken"
          data-testid="canvas-pane"
        >
          <div className="flex items-center justify-between border-b border-border-subtle bg-surface-elevated px-4 py-2">
            <div className="flex items-center gap-3">
              <span className="text-body-sm font-medium text-content-strong">
                {focusType}
              </span>
              <Badge variant="outline">{scope.replace("_", " ")}</Badge>
              {scope === "vertical_default" && (
                <Badge variant="outline">{vertical}</Badge>
              )}
              {resolved?.source && (
                <Badge variant="outline">source: {resolved.source}</Badge>
              )}
              {selectedIds.size > 0 && (
                <Badge variant="info" data-testid="selection-count-badge">
                  {selectedIds.size} selected
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
                onClick={handleUndo}
                disabled={!canUndo}
                aria-label="Undo (Cmd+Z)"
                className="rounded-sm border border-border-base p-1 text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong disabled:opacity-30"
                data-testid="composition-undo-button"
              >
                <Undo2 size={12} />
              </button>
              <button
                type="button"
                onClick={handleRedo}
                disabled={!canRedo}
                aria-label="Redo (Cmd+Shift+Z)"
                className="rounded-sm border border-border-base p-1 text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong disabled:opacity-30"
                data-testid="composition-redo-button"
              >
                <Redo2 size={12} />
              </button>
              <button
                type="button"
                onClick={() => setShowGrid((g) => !g)}
                aria-pressed={showGrid}
                aria-label="Toggle grid overlay"
                className={`rounded-sm border border-border-base p-1 hover:bg-accent-subtle/40 ${showGrid ? "bg-accent-subtle/60 text-content-strong" : "text-content-muted hover:text-content-strong"}`}
                data-testid="composition-grid-toggle"
              >
                <Grid3x3 size={12} />
              </button>
              <button
                type="button"
                onClick={() =>
                  setPreviewMode((m) => (m === "light" ? "dark" : "light"))
                }
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
              showGrid={showGrid}
              interactionsEnabled={!isSaving}
              onSelect={handleSelect}
              onDeselectAll={handleDeselectAll}
              onPlacementsChange={handlePlacementsChange}
              onCommitDrag={handleCommitDrag}
              onCommitResize={handleCommitResize}
              onMarqueeSelect={handleMarqueeSelect}
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
                    onChange={(e) => {
                      const next = {
                        ...draftCanvasConfig,
                        total_columns: Number(e.target.value),
                      }
                      setDraftCanvasConfig(next)
                      pushSnapshot(draftPlacements, next)
                    }}
                    className="w-14 rounded-sm border border-border-base bg-surface-raised px-1 py-0.5 font-plex-mono"
                    data-testid="canvas-cols-input"
                  />
                  <span className="text-content-muted">Gap:</span>
                  <input
                    type="number"
                    min={0}
                    max={48}
                    value={draftCanvasConfig.gap_size ?? 12}
                    onChange={(e) => {
                      const next = {
                        ...draftCanvasConfig,
                        gap_size: Number(e.target.value),
                      }
                      setDraftCanvasConfig(next)
                      pushSnapshot(draftPlacements, next)
                    }}
                    className="w-14 rounded-sm border border-border-base bg-surface-raised px-1 py-0.5 font-plex-mono"
                  />
                </div>
                <div className="mt-1.5">
                  <label className="block text-caption text-content-muted">
                    Background
                  </label>
                  <select
                    value={
                      draftCanvasConfig.background_treatment ?? "surface-base"
                    }
                    onChange={(e) => {
                      const next = {
                        ...draftCanvasConfig,
                        background_treatment: e.target.value,
                      }
                      setDraftCanvasConfig(next)
                      pushSnapshot(draftPlacements, next)
                    }}
                    className="mt-0.5 w-full rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-strong"
                  >
                    <option value="surface-base">surface-base</option>
                    <option value="surface-elevated">surface-elevated</option>
                    <option value="surface-sunken">surface-sunken</option>
                  </select>
                </div>
              </div>

              {/* Selected placement controls (single-select) OR
                  multi-select bulk actions. */}
              {selectedIds.size > 1 ? (
                <div
                  className="flex-1 overflow-y-auto px-3 py-2"
                  data-testid="multi-select-controls"
                >
                  <div className="text-body-sm font-medium text-content-strong">
                    {selectedIds.size} placements selected
                  </div>
                  <div className="mt-2 text-caption text-content-muted">
                    Drag any selected placement to move all together.
                    Arrow keys nudge by one cell. Shift+arrow nudges
                    by three cells.
                  </div>
                  <div className="mt-3 flex flex-col gap-1.5">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={handleDuplicateSelected}
                      data-testid="bulk-duplicate"
                    >
                      Duplicate ({selectedIds.size})
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={handleDeleteSelected}
                      className="text-status-error"
                      data-testid="bulk-delete"
                    >
                      <Trash2 size={11} className="mr-1" />
                      Delete ({selectedIds.size})
                    </Button>
                  </div>
                </div>
              ) : selectedPlacement ? (
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
                      {(
                        [
                          "column_start",
                          "column_span",
                          "row_start",
                          "row_span",
                        ] as const
                      ).map((k) => (
                        <label key={k} className="flex flex-col">
                          <span className="text-content-muted">{k}</span>
                          <input
                            type="number"
                            min={1}
                            value={selectedPlacement.grid[k]}
                            onChange={(e) =>
                              handleUpdateGrid(
                                selectedPlacement.placement_id,
                                {
                                  [k]: Number(e.target.value),
                                },
                              )
                            }
                            className="rounded-sm border border-border-base bg-surface-raised px-1 py-0.5 font-plex-mono text-content-strong"
                            data-testid={`placement-grid-${k}`}
                          />
                        </label>
                      ))}
                    </div>
                  </div>
                  <div className="border-t border-border-subtle px-3 py-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={handleDeleteSelected}
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
                  Click a placement on the canvas to edit. Shift-click
                  to multi-select. Drag the canvas background to
                  marquee-select.
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
