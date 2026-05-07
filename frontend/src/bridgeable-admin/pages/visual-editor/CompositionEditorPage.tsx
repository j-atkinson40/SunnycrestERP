/**
 * CompositionEditorPage — row-aware composition editor (R-3.1).
 *
 * Three-pane preview-dominant layout:
 *
 *   ┌─ Left (260px) ──┬─ Center (canvas) ──────┬─ Right (320px) ──┐
 *   │ Component       │ InteractivePlacement   │ Selection-driven  │
 *   │  palette        │   Canvas (row-aware)   │ inspector:        │
 *   │  (canvas-       │  with RowControlsStrip │  - none → hint    │
 *   │   placeable)    │  per row               │  - placement → grid│
 *   │                 │                        │  - multi → bulk   │
 *   │                 │                        │  - row → row ctrls│
 *   └─────────────────┴─────────────────────────┴───────────────────┘
 *
 * R-3.1 changes from R-3.0:
 *   - Internal state shifts from legacy `Placement[]` (flat) to canonical
 *     `CompositionRow[]` (nested). Legacy shim retired.
 *   - Selection generalizes from `Set<string>` to `Selection` discriminated
 *     union with row-mode added.
 *   - New row handlers: handleAddRow, handleDeleteRow, handleReorderRow,
 *     handleChangeRowColumnCount.
 *   - Delete row prompts confirmation when row has placements; instant
 *     delete for empty rows.
 *   - Cross-row drag-drop with stay-in-place source + line preview.
 *   - Column-count picker rejects decreases that would clip placements.
 *
 * Undo stack: whole-state snapshot model preserved verbatim from R-3.0;
 * just the field name changes (`placements` → `rows`).
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
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
  CanvasConfig,
  CompositionRecord,
  CompositionRow,
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
import {
  InteractivePlacementCanvas,
  type Selection,
} from "@/bridgeable-admin/components/visual-editor/composition-canvas/InteractivePlacementCanvas"
import { ColumnCountPopover } from "@/bridgeable-admin/components/visual-editor/composition-canvas/ColumnCountPopover"


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


interface DraftSnapshot {
  rows: CompositionRow[]
  canvasConfig: CanvasConfig
}


const UNDO_STACK_LIMIT = 50


function defaultCanvasConfig(): CanvasConfig {
  return {
    gap_size: 12,
    background_treatment: "surface-base",
  }
}


function newRowId(): string {
  // Stable enough for editor session; backend assigns canonical UUIDs
  // on save via service-layer normalization.
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID()
  }
  return `row-${Math.random().toString(36).slice(2, 10)}-${Date.now()}`
}


function newPlacementId(allRows: CompositionRow[]): string {
  let i = allRows.flatMap((r) => r.placements).length + 1
  const existingIds = new Set(
    allRows.flatMap((r) => r.placements.map((p) => p.placement_id)),
  )
  while (existingIds.has(`p${i}`)) i += 1
  return `p${i}`
}


/** Find first available starting_column in a row that fits a placement
 * of given column_span. Returns the leftmost gap; returns 0 if the row
 * is empty. Returns -1 if no gap fits the span (caller decides what
 * to do — typically: add to a new row OR reject). */
function findAvailableStartingColumn(
  row: CompositionRow,
  span: number,
): number {
  // Sort placements by starting_column to walk gaps left-to-right.
  const sorted = [...row.placements].sort(
    (a, b) => a.starting_column - b.starting_column,
  )
  let cursor = 0
  for (const p of sorted) {
    if (p.starting_column - cursor >= span) {
      return cursor
    }
    cursor = Math.max(cursor, p.starting_column + p.column_span)
  }
  // Try fitting after the last placement.
  if (row.column_count - cursor >= span) {
    return cursor
  }
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
  const [draftRows, setDraftRows] = useState<CompositionRow[]>([])
  const [draftCanvasConfig, setDraftCanvasConfig] = useState<CanvasConfig>(
    defaultCanvasConfig(),
  )
  const [selection, setSelection] = useState<Selection>({ kind: "none" })

  const [isLoading, setIsLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  // ── Preview state ────────────────────────────────────────
  const [previewMode, setPreviewMode] = useState<PreviewMode>("light")
  const [rightRailCollapsed, setRightRailCollapsed] = useState(false)
  const [paletteSearch, setPaletteSearch] = useState("")
  const [showGrid, setShowGrid] = useState(true)

  // ── Delete-row confirmation modal ────────────────────────
  const [deleteRowConfirm, setDeleteRowConfirm] = useState<{
    rowId: string
    placementCount: number
  } | null>(null)

  // ── Undo / redo stack ─────────────────────────────────────
  const undoStack = useRef<DraftSnapshot[]>([])
  const undoPointer = useRef<number>(-1)
  const isReplayingRef = useRef(false)

  const pushSnapshot = useCallback(
    (rows: CompositionRow[], canvasConfig: CanvasConfig) => {
      if (isReplayingRef.current) return
      undoStack.current = undoStack.current.slice(0, undoPointer.current + 1)
      undoStack.current.push({
        rows: rows.map((r) => ({
          ...r,
          placements: r.placements.map((p) => ({
            ...p,
            prop_overrides: { ...p.prop_overrides },
            display_config: p.display_config ? { ...p.display_config } : {},
          })),
        })),
        canvasConfig: { ...canvasConfig },
      })
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
    setDraftRows(
      snap.rows.map((r) => ({
        ...r,
        placements: r.placements.map((p) => ({ ...p })),
      })),
    )
    setDraftCanvasConfig({ ...snap.canvasConfig })
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

      undoStack.current = []
      undoPointer.current = -1
      isReplayingRef.current = true
      if (active) {
        setDraftRows(active.rows ?? [])
        setDraftCanvasConfig({ ...(active.canvas_config ?? {}) })
      } else {
        setDraftRows([])
        setDraftCanvasConfig(defaultCanvasConfig())
      }
      queueMicrotask(() => {
        isReplayingRef.current = false
        pushSnapshot(
          active ? (active.rows ?? []) : [],
          active ? { ...(active.canvas_config ?? {}) } : defaultCanvasConfig(),
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

  useEffect(() => {
    setSelection({ kind: "none" })
  }, [scope, focusType])

  // ── Save / discard / autosave ────────────────────────────
  const persistedSnapshot = useMemo(() => {
    if (!activeRow) {
      return JSON.stringify([[], defaultCanvasConfig()])
    }
    return JSON.stringify([activeRow.rows ?? [], activeRow.canvas_config ?? {}])
  }, [activeRow])
  const draftSnapshot = useMemo(
    () => JSON.stringify([draftRows, draftCanvasConfig]),
    [draftRows, draftCanvasConfig],
  )
  const hasUnsaved = draftSnapshot !== persistedSnapshot

  const handleSave = useCallback(async () => {
    if (!hasUnsaved && activeRow) return
    setIsSaving(true)
    setSaveError(null)
    try {
      if (activeRow) {
        const updated = await focusCompositionsService.update(activeRow.id, {
          rows: draftRows,
          canvas_config: draftCanvasConfig,
        })
        setActiveRow(updated)
      } else {
        const created = await focusCompositionsService.create({
          scope,
          focus_type: focusType,
          vertical: scope === "vertical_default" ? vertical : null,
          tenant_id: scope === "tenant_override" ? tenantIdInput : null,
          rows: draftRows,
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
    draftRows,
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
      setDraftRows(activeRow.rows ?? [])
      setDraftCanvasConfig({ ...(activeRow.canvas_config ?? {}) })
    } else {
      setDraftRows([])
      setDraftCanvasConfig(defaultCanvasConfig())
    }
    setSelection({ kind: "none" })
    queueMicrotask(() => {
      isReplayingRef.current = false
    })
  }, [activeRow])

  // ── Selected placement(s) helper ─────────────────────────
  const selectedPlacementIds = useMemo(
    () => selection.placementIds ?? new Set<string>(),
    [selection],
  )
  const selectedPlacement = useMemo<Placement | null>(() => {
    if (selection.kind !== "placement" || !selection.placementIds) return null
    const id = Array.from(selection.placementIds)[0]
    if (!id) return null
    for (const r of draftRows) {
      for (const p of r.placements) {
        if (p.placement_id === id) return p
      }
    }
    return null
  }, [draftRows, selection])

  const selectedRow = useMemo<CompositionRow | null>(() => {
    if (selection.kind !== "row" || !selection.rowId) return null
    return draftRows.find((r) => r.row_id === selection.rowId) ?? null
  }, [draftRows, selection])

  // ── Row management handlers ──────────────────────────────
  const handleAddRow = useCallback(
    (insertIndex: number, columnCount = 12) => {
      const next = [...draftRows]
      const newRow = makeRow(columnCount)
      next.splice(insertIndex, 0, newRow)
      setDraftRows(next)
      setSelection({ kind: "row", rowId: newRow.row_id })
      pushSnapshot(next, draftCanvasConfig)
    },
    [draftRows, draftCanvasConfig, pushSnapshot],
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
        // Instant delete for empty rows.
        const next = draftRows.filter((r) => r.row_id !== rowId)
        setDraftRows(next)
        setSelection({ kind: "none" })
        pushSnapshot(next, draftCanvasConfig)
      } else {
        // Confirmation modal for rows with placements.
        setDeleteRowConfirm({
          rowId,
          placementCount: row.placements.length,
        })
      }
    },
    [draftRows, draftCanvasConfig, pushSnapshot],
  )

  const handleConfirmDeleteRow = useCallback(() => {
    if (!deleteRowConfirm) return
    const next = draftRows.filter((r) => r.row_id !== deleteRowConfirm.rowId)
    setDraftRows(next)
    setSelection({ kind: "none" })
    pushSnapshot(next, draftCanvasConfig)
    setDeleteRowConfirm(null)
  }, [deleteRowConfirm, draftRows, draftCanvasConfig, pushSnapshot])

  const handleCancelDeleteRow = useCallback(() => {
    setDeleteRowConfirm(null)
  }, [])

  const handleReorderRow = useCallback(
    ({ fromIndex, toIndex }: { fromIndex: number; toIndex: number }) => {
      if (fromIndex === toIndex) return
      const next = [...draftRows]
      const [moved] = next.splice(fromIndex, 1)
      next.splice(toIndex, 0, moved)
      setDraftRows(next)
      pushSnapshot(next, draftCanvasConfig)
    },
    [draftRows, draftCanvasConfig, pushSnapshot],
  )

  const handleChangeRowColumnCount = useCallback(
    (rowId: string, newColumnCount: number) => {
      const next = draftRows.map((r) =>
        r.row_id === rowId ? { ...r, column_count: newColumnCount } : r,
      )
      setDraftRows(next)
      pushSnapshot(next, draftCanvasConfig)
    },
    [draftRows, draftCanvasConfig, pushSnapshot],
  )

  // ── Placement operations ─────────────────────────────────
  const handleAddPlacement = useCallback(
    (entry: RegistryEntry) => {
      const meta = getCanvasMetadata(entry)
      // Place into the selected row if one is selected; else last row;
      // else create a new row (auto-create on empty composition).
      let rows = [...draftRows]
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
      const span = Math.min(meta.defaultDimensions.columns, targetRow.column_count)
      let startingColumn = findAvailableStartingColumn(targetRow, span)
      // If no slot fits, append to a fresh row beneath this one.
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
        placement_id: newPlacementId(rows),
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
      setDraftRows(rows)
      setSelection({
        kind: "placement",
        placementIds: new Set([newPlacement.placement_id]),
      })
      pushSnapshot(rows, draftCanvasConfig)
    },
    [draftRows, draftCanvasConfig, selection, pushSnapshot],
  )

  const handleDeleteSelectedPlacements = useCallback(() => {
    const ids = selectedPlacementIds
    if (ids.size === 0) return
    const next = draftRows.map((r) => ({
      ...r,
      placements: r.placements.filter((p) => !ids.has(p.placement_id)),
    }))
    setDraftRows(next)
    setSelection({ kind: "none" })
    pushSnapshot(next, draftCanvasConfig)
  }, [draftRows, draftCanvasConfig, selectedPlacementIds, pushSnapshot])

  const handleDuplicateSelectedPlacements = useCallback(() => {
    const ids = selectedPlacementIds
    if (ids.size === 0) return
    let working: CompositionRow[] = draftRows.map((r) => ({
      ...r,
      placements: [...r.placements],
    }))
    const newIds: string[] = []
    for (const id of ids) {
      // Find which row contains the source.
      let srcRowIdx = -1
      let src: Placement | null = null
      for (let i = 0; i < working.length; i++) {
        const found = working[i].placements.find((p) => p.placement_id === id)
        if (found) {
          srcRowIdx = i
          src = found
          break
        }
      }
      if (!src || srcRowIdx < 0) continue
      const targetRow = working[srcRowIdx]
      const startingColumn = findAvailableStartingColumn(
        targetRow,
        src.column_span,
      )
      if (startingColumn < 0) continue
      const dup: Placement = {
        ...src,
        placement_id: newPlacementId(working),
        starting_column: startingColumn,
        prop_overrides: { ...src.prop_overrides },
        display_config: src.display_config ? { ...src.display_config } : {},
      }
      newIds.push(dup.placement_id)
      working = working.map((r, i) =>
        i === srcRowIdx ? { ...r, placements: [...r.placements, dup] } : r,
      )
    }
    if (newIds.length === 0) return
    setDraftRows(working)
    setSelection({
      kind: newIds.length === 1 ? "placement" : "placements-multi",
      placementIds: new Set(newIds),
    })
    pushSnapshot(working, draftCanvasConfig)
  }, [draftRows, draftCanvasConfig, selectedPlacementIds, pushSnapshot])

  const handleNudgeSelected = useCallback(
    (dx: number) => {
      const ids = selectedPlacementIds
      if (ids.size === 0) return
      // R-3.1 constraint: in-row arrow nudge only. Cross-row keyboard
      // nav deferred to R-3.2 polish.
      const next = draftRows.map((r) => ({
        ...r,
        placements: r.placements.map((p) => {
          if (!ids.has(p.placement_id)) return p
          const newStart = Math.max(
            0,
            Math.min(r.column_count - p.column_span, p.starting_column + dx),
          )
          return { ...p, starting_column: newStart }
        }),
      }))
      setDraftRows(next)
      pushSnapshot(next, draftCanvasConfig)
    },
    [draftRows, draftCanvasConfig, selectedPlacementIds, pushSnapshot],
  )

  const handleUpdatePlacementGrid = useCallback(
    (
      placementId: string,
      patch: { starting_column?: number; column_span?: number },
    ) => {
      const next = draftRows.map((r) => ({
        ...r,
        placements: r.placements.map((p) => {
          if (p.placement_id !== placementId) return p
          const newCol = patch.starting_column ?? p.starting_column
          const newSpan = patch.column_span ?? p.column_span
          // Clamp into row's column_count.
          const span = Math.max(1, Math.min(r.column_count, newSpan))
          const start = Math.max(0, Math.min(r.column_count - span, newCol))
          return { ...p, starting_column: start, column_span: span }
        }),
      }))
      setDraftRows(next)
      pushSnapshot(next, draftCanvasConfig)
    },
    [draftRows, draftCanvasConfig, pushSnapshot],
  )

  // ── Canvas drag/resize commit ────────────────────────────
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
      let next: CompositionRow[]
      if (sourceRowId === targetRowId) {
        // Within-row move (anchor + siblings).
        next = draftRows.map((r) => {
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
      } else {
        // Cross-row move: only the dragged placement moves.
        const moved = draftRows
          .find((r) => r.row_id === sourceRowId)
          ?.placements.find((p) => p.placement_id === placementId)
        if (!moved) return
        next = draftRows.map((r) => {
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
      }
      setDraftRows(next)
      pushSnapshot(next, draftCanvasConfig)
    },
    [draftRows, draftCanvasConfig, pushSnapshot],
  )

  const handleCommitPlacementResize = useCallback(
    (input: {
      placementId: string
      rowId: string
      newStartingColumn: number
      newColumnSpan: number
    }) => {
      const next = draftRows.map((r) => {
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
      })
      setDraftRows(next)
      pushSnapshot(next, draftCanvasConfig)
    },
    [draftRows, draftCanvasConfig, pushSnapshot],
  )

  // ── Selection handlers ──────────────────────────────────
  const handleSelectPlacement = useCallback(
    (id: string, opts: { shift: boolean }) => {
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
    },
    [],
  )

  const handleSelectRow = useCallback((rowId: string) => {
    setSelection({ kind: "row", rowId })
  }, [])

  const handleDeselectAll = useCallback(() => {
    setSelection({ kind: "none" })
  }, [])

  const handleMarqueeSelect = useCallback((ids: string[]) => {
    if (ids.length === 0) {
      setSelection({ kind: "none" })
    } else if (ids.length === 1) {
      setSelection({ kind: "placement", placementIds: new Set(ids) })
    } else {
      setSelection({ kind: "placements-multi", placementIds: new Set(ids) })
    }
  }, [])

  // ── Keyboard shortcuts ───────────────────────────────────
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
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
      if (meta && e.key.toLowerCase() === "d") {
        e.preventDefault()
        handleDuplicateSelectedPlacements()
        return
      }
      if ((e.key === "Backspace" || e.key === "Delete") && !meta) {
        if (selectedPlacementIds.size > 0) {
          e.preventDefault()
          handleDeleteSelectedPlacements()
        }
        return
      }
      // R-3.1: arrow nudge is in-row only (column axis); ArrowUp/Down
      // do nothing in R-3.1 (cross-row nav deferred to R-3.2 polish).
      if (e.key === "ArrowLeft" && !meta && selectedPlacementIds.size > 0) {
        e.preventDefault()
        handleNudgeSelected(e.shiftKey ? -3 : -1)
        return
      }
      if (e.key === "ArrowRight" && !meta && selectedPlacementIds.size > 0) {
        e.preventDefault()
        handleNudgeSelected(e.shiftKey ? 3 : 1)
        return
      }
      if (e.key === "Escape") {
        setSelection({ kind: "none" })
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [
    handleUndo,
    handleRedo,
    handleDuplicateSelectedPlacements,
    handleDeleteSelectedPlacements,
    handleNudgeSelected,
    selectedPlacementIds.size,
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
          {/* Top toolbar */}
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
              {selectedPlacementIds.size > 0 && (
                <Badge variant="info" data-testid="selection-count-badge">
                  {selectedPlacementIds.size} selected
                </Badge>
              )}
              {selection.kind === "row" && selection.rowId && (
                <Badge variant="info" data-testid="row-selection-badge">
                  row selected
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
              <Button
                size="sm"
                variant="ghost"
                onClick={() => handleAddRow(draftRows.length, 12)}
                data-testid="composition-add-row-button"
              >
                <Plus size={11} className="mr-1" />
                Add row
              </Button>
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
              rows={draftRows}
              gapSize={draftCanvasConfig.gap_size ?? 12}
              backgroundTreatment={draftCanvasConfig.background_treatment}
              selection={selection}
              showGrid={showGrid}
              interactionsEnabled={!isSaving}
              onSelectPlacement={handleSelectPlacement}
              onSelectRow={handleSelectRow}
              onDeselectAll={handleDeselectAll}
              onCommitPlacementMove={handleCommitPlacementMove}
              onCommitPlacementResize={handleCommitPlacementResize}
              onCommitRowReorder={handleReorderRow}
              onMarqueeSelect={handleMarqueeSelect}
              onAddRowAbove={handleAddRowAbove}
              onAddRowBelow={handleAddRowBelow}
              onDeleteRow={handleRequestDeleteRow}
              onChangeRowColumnCount={handleChangeRowColumnCount}
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
                    onClick={handleSave}
                    disabled={!hasUnsaved || isSaving}
                    data-testid="composition-save-button"
                  >
                    <Save size={12} className="mr-1" />
                    Save
                  </Button>
                </div>
              </div>

              {/* Scope picker */}
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

              {/* Canvas config (gap + background only; per-row column_count
                  is on each row's own picker now). */}
              <div className="border-b border-border-subtle px-3 py-2">
                <div className="text-micro uppercase tracking-wider text-content-muted">
                  Canvas
                </div>
                <div className="mt-1.5 flex items-center gap-2 text-caption">
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
                      pushSnapshot(draftRows, next)
                    }}
                    className="w-14 rounded-sm border border-border-base bg-surface-raised px-1 py-0.5 font-plex-mono"
                    data-testid="canvas-gap-input"
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
                      pushSnapshot(draftRows, next)
                    }}
                    className="mt-0.5 w-full rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-strong"
                  >
                    <option value="surface-base">surface-base</option>
                    <option value="surface-elevated">surface-elevated</option>
                    <option value="surface-sunken">surface-sunken</option>
                  </select>
                </div>
              </div>

              {/* Selection-driven inspector — 4 modes. */}
              <SelectionInspector
                selection={selection}
                draftRows={draftRows}
                selectedPlacement={selectedPlacement}
                selectedRow={selectedRow}
                onUpdatePlacementGrid={handleUpdatePlacementGrid}
                onDeleteSelectedPlacements={handleDeleteSelectedPlacements}
                onDuplicateSelectedPlacements={handleDuplicateSelectedPlacements}
                onChangeRowColumnCount={(n) => {
                  if (selection.kind === "row" && selection.rowId) {
                    handleChangeRowColumnCount(selection.rowId, n)
                  }
                }}
                onChangeRowHeight={(rowId, value) => {
                  const next = draftRows.map((r) =>
                    r.row_id === rowId ? { ...r, row_height: value } : r,
                  )
                  setDraftRows(next)
                  pushSnapshot(next, draftCanvasConfig)
                }}
                onDeleteRow={handleRequestDeleteRow}
              />

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

      {/* Delete row confirmation modal */}
      {deleteRowConfirm && (
        <DeleteRowConfirmModal
          placementCount={deleteRowConfirm.placementCount}
          onConfirm={handleConfirmDeleteRow}
          onCancel={handleCancelDeleteRow}
        />
      )}
    </div>
  )
}


// ─── Selection-driven right-rail inspector ──────────────────────


function SelectionInspector({
  selection,
  draftRows,
  selectedPlacement,
  selectedRow,
  onUpdatePlacementGrid,
  onDeleteSelectedPlacements,
  onDuplicateSelectedPlacements,
  onChangeRowColumnCount,
  onChangeRowHeight,
  onDeleteRow,
}: {
  selection: Selection
  draftRows: CompositionRow[]
  selectedPlacement: Placement | null
  selectedRow: CompositionRow | null
  onUpdatePlacementGrid: (
    id: string,
    patch: { starting_column?: number; column_span?: number },
  ) => void
  onDeleteSelectedPlacements: () => void
  onDuplicateSelectedPlacements: () => void
  onChangeRowColumnCount: (n: number) => void
  onChangeRowHeight: (rowId: string, value: "auto" | number) => void
  onDeleteRow: (rowId: string) => void
}): ReactNode {
  void draftRows

  if (selection.kind === "placements-multi") {
    const count = selection.placementIds?.size ?? 0
    return (
      <div
        className="flex-1 overflow-y-auto px-3 py-2"
        data-testid="multi-select-controls"
      >
        <div className="text-body-sm font-medium text-content-strong">
          {count} placements selected
        </div>
        <div className="mt-2 text-caption text-content-muted">
          Drag any selected placement to move all together within the same row.
          Arrow keys nudge by one cell. Shift+arrow nudges by three cells.
          Cross-row drag moves only the dragged placement (R-3.1 constraint).
        </div>
        <div className="mt-3 flex flex-col gap-1.5">
          <Button
            size="sm"
            variant="ghost"
            onClick={onDuplicateSelectedPlacements}
            data-testid="bulk-duplicate"
          >
            Duplicate ({count})
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={onDeleteSelectedPlacements}
            className="text-status-error"
            data-testid="bulk-delete"
          >
            <Trash2 size={11} className="mr-1" />
            Delete ({count})
          </Button>
        </div>
      </div>
    )
  }

  if (selection.kind === "placement" && selectedPlacement) {
    return (
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
            Position within row
          </div>
          <div className="mt-1.5 grid grid-cols-2 gap-2 text-caption">
            <label className="flex flex-col">
              <span className="text-content-muted">starting_column</span>
              <input
                type="number"
                min={0}
                value={selectedPlacement.starting_column}
                onChange={(e) =>
                  onUpdatePlacementGrid(selectedPlacement.placement_id, {
                    starting_column: Number(e.target.value),
                  })
                }
                className="rounded-sm border border-border-base bg-surface-raised px-1 py-0.5 font-plex-mono text-content-strong"
                data-testid="placement-grid-starting-column"
              />
            </label>
            <label className="flex flex-col">
              <span className="text-content-muted">column_span</span>
              <input
                type="number"
                min={1}
                value={selectedPlacement.column_span}
                onChange={(e) =>
                  onUpdatePlacementGrid(selectedPlacement.placement_id, {
                    column_span: Number(e.target.value),
                  })
                }
                className="rounded-sm border border-border-base bg-surface-raised px-1 py-0.5 font-plex-mono text-content-strong"
                data-testid="placement-grid-column-span"
              />
            </label>
          </div>
        </div>
        <div className="border-t border-border-subtle px-3 py-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={onDeleteSelectedPlacements}
            className="w-full text-status-error"
            data-testid="delete-placement"
          >
            <Trash2 size={11} className="mr-1" />
            Delete placement
          </Button>
        </div>
      </div>
    )
  }

  if (selection.kind === "row" && selectedRow) {
    const isAuto = selectedRow.row_height === "auto"
    return (
      <div className="flex-1 overflow-y-auto" data-testid="row-controls">
        <div className="border-b border-border-subtle px-3 py-2">
          <div className="text-body-sm font-medium text-content-strong">
            Row
          </div>
          <div className="font-plex-mono text-caption text-content-muted">
            {selectedRow.row_id.slice(0, 8)} · {selectedRow.placements.length}{" "}
            placement{selectedRow.placements.length === 1 ? "" : "s"}
          </div>
        </div>
        <div className="px-3 py-2">
          <div className="mb-1.5 text-micro uppercase tracking-wider text-content-muted">
            Column count
          </div>
          <ColumnCountPopover
            row={selectedRow}
            onChange={onChangeRowColumnCount}
            triggerTestId="inspector-column-count-trigger"
            triggerClassName="inline-flex h-7 items-center gap-1 rounded-sm border border-border-base bg-surface-raised px-2 font-plex-mono text-caption text-content-strong hover:bg-accent-subtle/40"
          />
        </div>
        <div className="px-3 py-2">
          <div className="mb-1.5 text-micro uppercase tracking-wider text-content-muted">
            Row height
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onChangeRowHeight(selectedRow.row_id, "auto")}
              data-testid="row-height-auto"
              data-active={isAuto ? "true" : "false"}
              className={[
                "rounded-sm px-2 py-1 text-caption",
                isAuto
                  ? "bg-accent text-content-on-accent"
                  : "border border-border-base bg-surface-raised text-content-strong hover:bg-accent-subtle/40",
              ].join(" ")}
            >
              auto
            </button>
            <input
              type="number"
              min={48}
              max={1200}
              value={typeof selectedRow.row_height === "number" ? selectedRow.row_height : ""}
              placeholder="px"
              onChange={(e) => {
                const v = e.target.value
                if (v === "") {
                  onChangeRowHeight(selectedRow.row_id, "auto")
                } else {
                  const n = Number(v)
                  if (!Number.isNaN(n) && n > 0) {
                    onChangeRowHeight(selectedRow.row_id, n)
                  }
                }
              }}
              className="w-20 rounded-sm border border-border-base bg-surface-raised px-1 py-0.5 font-plex-mono text-caption text-content-strong"
              data-testid="row-height-px-input"
            />
          </div>
        </div>
        <div className="border-t border-border-subtle px-3 py-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onDeleteRow(selectedRow.row_id)}
            className="w-full text-status-error"
            data-testid="row-inspector-delete"
          >
            <Trash2 size={11} className="mr-1" />
            Delete row
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="px-3 py-6 text-center text-caption text-content-muted">
      Click a placement to edit its position within the row. Click a row's
      controls strip to edit the row. Shift-click multiple placements to
      multi-select.
    </div>
  )
}


// ─── Delete row confirmation modal ──────────────────────────────


function DeleteRowConfirmModal({
  placementCount,
  onConfirm,
  onCancel,
}: {
  placementCount: number
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <div
      className="fixed inset-0 z-[var(--z-modal,80)] flex items-center justify-center bg-black/40 backdrop-blur-sm"
      data-testid="delete-row-confirm-modal"
      onClick={onCancel}
    >
      <div
        className="w-[420px] max-w-[90vw] rounded-lg border border-border-subtle bg-surface-raised p-5 shadow-level-3"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-h4 font-plex-serif font-medium text-content-strong">
          Delete row?
        </div>
        <div className="mt-2 text-caption text-content-muted">
          This row contains {placementCount} placement
          {placementCount === 1 ? "" : "s"}. Deleting the row will remove{" "}
          {placementCount === 1 ? "it" : "them"}. Cmd+Z reverses this.
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={onCancel}
            data-testid="delete-row-cancel"
          >
            Cancel
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={onConfirm}
            data-testid="delete-row-confirm"
          >
            <Trash2 size={11} className="mr-1" />
            Delete
          </Button>
        </div>
      </div>
    </div>
  )
}
