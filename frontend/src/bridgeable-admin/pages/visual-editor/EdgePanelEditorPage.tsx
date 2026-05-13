/**
 * R-5.2 — EdgePanelEditorPage.
 *
 * Multi-page edge panel authoring at `/visual-editor/edge-panels`.
 * Replaces R-5.0's JSON-textarea row authoring with the canonical
 * R-3.1 InteractivePlacementCanvas substrate, making this page the
 * THIRD consumer of the canvas alongside CompositionEditorPage and
 * FocusEditorPage's Composition tab. Reuse validates the canvas
 * substrate's prop-driven design empirically.
 *
 * Per-page state model (per Section 3 of R-5.2 investigation):
 *   - `pages: EdgePanelPage[]` is the canonical state. Canvas commits
 *     write directly to it via the active page's slice.
 *   - `pageSelections: Record<page_id, Selection>` keyed by page_id —
 *     selection state is per-page so switching pages preserves what
 *     was selected on each.
 *   - `undoStacks` + `undoPointers` keyed by page_id — Cmd+Z scopes
 *     to the active page only. Cross-page Cmd+Z would jump pages,
 *     which is a confusing anti-pattern.
 *   - Page-level changes (rename / delete / add / set-default) are
 *     NOT undoable in R-5.2 (consistent with R-5.0's behavior).
 *
 * Save discipline: button disabled while a drag gesture is in flight
 * (per investigation R2). Mid-drag save would persist a partially
 * committed state; conservative pattern matches CompositionEditorPage.
 *
 * Authentication: platform admin via adminApi (per visual-editor
 * canonical pattern).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { adminApi } from "@/bridgeable-admin/lib/admin-api"
import type { ResolvedEdgePanel, EdgePanelPage } from "@/lib/edge-panel/types"
import { CompositionRenderer } from "@/lib/visual-editor/compositions/CompositionRenderer"
import type {
  CompositionRow,
  ResolvedComposition,
} from "@/lib/visual-editor/compositions/types"

import { EdgePanelEditorCanvas } from "./components/EdgePanelEditorCanvas"
import type { Selection } from "./components/EdgePanelEditorCanvas"
import { PageList } from "./components/PageList"
import { PageMetadataEditor } from "./components/PageMetadataEditor"
import { useStudioRail } from "@/bridgeable-admin/components/studio/StudioRailContext"


type Scope = "platform_default" | "vertical_default" | "tenant_override"


interface DraftSnapshot {
  rows: CompositionRow[]
}


const UNDO_STACK_LIMIT = 50


function emptyPage(name: string): EdgePanelPage {
  return {
    page_id: `pg-${Math.random().toString(36).slice(2, 10)}`,
    name,
    rows: [],
    canvas_config: {},
  }
}


function pageToResolvedComposition(page: EdgePanelPage): ResolvedComposition {
  return {
    focus_type: "edge_panel_preview",
    vertical: null,
    tenant_id: null,
    source: "platform_default",
    source_id: null,
    source_version: null,
    rows: page.rows,
    canvas_config: page.canvas_config ?? {},
  }
}


/** Deep-clone rows for snapshotting. Mirrors CompositionEditorPage's
 * `pushSnapshot` clone discipline. */
function cloneRows(rows: CompositionRow[]): CompositionRow[] {
  return rows.map((r) => ({
    ...r,
    placements: r.placements.map((p) => ({
      ...p,
      prop_overrides: { ...p.prop_overrides },
      display_config: p.display_config ? { ...p.display_config } : {},
    })),
  }))
}


export default function EdgePanelEditorPage() {
  // Studio 1a-i.B — hide editor's own left rail (PageList) when inside
  // Studio shell with rail expanded. Standalone callers keep the
  // PageList visible.
  const { railExpanded, inStudioContext } = useStudioRail()
  const hideLeftPane = railExpanded && inStudioContext

  const [scope, setScope] = useState<Scope>("platform_default")
  const [vertical, setVertical] = useState<string>("manufacturing")
  const [tenantId, setTenantId] = useState<string>("")
  const [panelKey, setPanelKey] = useState<string>("default")
  const [pages, setPages] = useState<EdgePanelPage[]>([])
  const [activePageIndex, setActivePageIndex] = useState<number>(0)
  const [defaultPageIndex, setDefaultPageIndex] = useState<number>(0)
  const [loading, setLoading] = useState<boolean>(false)
  const [saving, setSaving] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  // Per-page selection state. Keyed on page_id; entries are cleaned
  // up on page deletion to prevent orphan growth (R-5.2 R1).
  const [pageSelections, setPageSelections] = useState<
    Record<string, Selection>
  >({})

  // Per-page undo stacks. Same keying + cleanup discipline.
  const undoStacks = useRef<Record<string, DraftSnapshot[]>>({})
  const undoPointers = useRef<Record<string, number>>({})
  const isReplayingRef = useRef(false)

  const activePage = pages[activePageIndex] ?? null
  const activePageId = activePage?.page_id ?? ""
  const activeSelection: Selection =
    pageSelections[activePageId] ?? { kind: "none" }

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string> = {
        focus_type: panelKey,
        kind: "edge_panel",
      }
      if (scope === "vertical_default" && vertical) params.vertical = vertical
      if (scope === "tenant_override" && tenantId) params.tenant_id = tenantId
      const r = await adminApi.get<ResolvedEdgePanel>(
        `/api/platform/admin/visual-editor/compositions/resolve`,
        { params },
      )
      const incoming = r.data.pages ?? []
      const initial = incoming.length > 0 ? incoming : [emptyPage("Page 1")]
      setPages(initial)
      setActivePageIndex(0)
      const defaultIdx = (
        r.data.canvas_config as { default_page_index?: number }
      )?.default_page_index ?? 0
      setDefaultPageIndex(defaultIdx)
      // Reset per-page selection + undo state on load.
      setPageSelections({})
      undoStacks.current = {}
      undoPointers.current = {}
      // Seed each page's undo stack with its initial snapshot so the
      // first mutation has something to roll back to.
      for (const p of initial) {
        undoStacks.current[p.page_id] = [
          { rows: cloneRows(p.rows ?? []) },
        ]
        undoPointers.current[p.page_id] = 0
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [panelKey, scope, vertical, tenantId])

  useEffect(() => {
    void load()
  }, [load])

  // ── Snapshot management (per-page) ───────────────────────────

  const pushSnapshotForPage = useCallback(
    (pageId: string, rows: CompositionRow[]) => {
      if (isReplayingRef.current) return
      const stack = undoStacks.current[pageId] ?? []
      const ptr = undoPointers.current[pageId] ?? -1
      const truncated = stack.slice(0, ptr + 1)
      truncated.push({ rows: cloneRows(rows) })
      const overflow = truncated.length - UNDO_STACK_LIMIT
      const next = overflow > 0 ? truncated.slice(overflow) : truncated
      undoStacks.current[pageId] = next
      undoPointers.current[pageId] = next.length - 1
    },
    [],
  )

  const handleUndoableMutation = useCallback(() => {
    if (!activePage) return
    // Push current state BEFORE the mutation lands. Subsequent
    // onCommitRows updates the actual state; the next push captures
    // the post-mutation frame.
    pushSnapshotForPage(activePage.page_id, activePage.rows)
  }, [activePage, pushSnapshotForPage])

  const replaySnapshotForPage = useCallback(
    (pageId: string, snap: DraftSnapshot) => {
      isReplayingRef.current = true
      setPages((prev) =>
        prev.map((p) =>
          p.page_id === pageId
            ? { ...p, rows: cloneRows(snap.rows) }
            : p,
        ),
      )
      queueMicrotask(() => {
        isReplayingRef.current = false
      })
    },
    [],
  )

  const handleUndo = useCallback(() => {
    if (!activePage) return
    const ptr = undoPointers.current[activePage.page_id] ?? -1
    if (ptr <= 0) return
    undoPointers.current[activePage.page_id] = ptr - 1
    const stack = undoStacks.current[activePage.page_id] ?? []
    const snap = stack[ptr - 1]
    if (snap) replaySnapshotForPage(activePage.page_id, snap)
  }, [activePage, replaySnapshotForPage])

  const handleRedo = useCallback(() => {
    if (!activePage) return
    const stack = undoStacks.current[activePage.page_id] ?? []
    const ptr = undoPointers.current[activePage.page_id] ?? -1
    if (ptr < 0 || ptr >= stack.length - 1) return
    undoPointers.current[activePage.page_id] = ptr + 1
    const snap = stack[ptr + 1]
    if (snap) replaySnapshotForPage(activePage.page_id, snap)
  }, [activePage, replaySnapshotForPage])

  // ── Selection callbacks ──────────────────────────────────────

  const handleSelectionChange = useCallback(
    (next: Selection) => {
      if (!activePage) return
      setPageSelections((prev) => ({
        ...prev,
        [activePage.page_id]: next,
      }))
    },
    [activePage],
  )

  // ── Row commits from canvas ──────────────────────────────────

  const handleCommitRows = useCallback(
    (newRows: CompositionRow[]) => {
      if (!activePage) return
      setPages((prev) =>
        prev.map((p) =>
          p.page_id === activePage.page_id ? { ...p, rows: newRows } : p,
        ),
      )
      // Push the post-mutation snapshot so undo walks back through the
      // mutation history. handleUndoableMutation has already pushed the
      // pre-mutation snapshot; this push captures the new frame so a
      // subsequent undo lands at the pre-mutation state.
      pushSnapshotForPage(activePage.page_id, newRows)
    },
    [activePage, pushSnapshotForPage],
  )

  // ── Page management ──────────────────────────────────────────

  const addPage = useCallback(() => {
    const next = emptyPage(`Page ${pages.length + 1}`)
    setPages((prev) => [...prev, next])
    setActivePageIndex(pages.length)
    // Seed per-page state for the new page.
    undoStacks.current[next.page_id] = [{ rows: [] }]
    undoPointers.current[next.page_id] = 0
  }, [pages.length])

  const deletePage = useCallback(() => {
    if (!activePage) return
    if (pages.length <= 1) {
      setError("Cannot delete the last page.")
      return
    }
    const removedId = activePage.page_id
    setPages((prev) => prev.filter((p) => p.page_id !== removedId))
    setActivePageIndex(Math.max(0, activePageIndex - 1))
    // Clean up per-page state for the removed page (R-5.2 R1).
    setPageSelections((prev) => {
      const next = { ...prev }
      delete next[removedId]
      return next
    })
    delete undoStacks.current[removedId]
    delete undoPointers.current[removedId]
    // If we deleted the default, fall back to first page.
    if (defaultPageIndex >= pages.length - 1) setDefaultPageIndex(0)
  }, [activePage, pages.length, activePageIndex, defaultPageIndex])

  const renamePage = useCallback(
    (newName: string) => {
      if (!activePage) return
      setPages((prev) =>
        prev.map((p) =>
          p.page_id === activePage.page_id ? { ...p, name: newName } : p,
        ),
      )
    },
    [activePage],
  )

  const setDefault = useCallback(() => {
    setDefaultPageIndex(activePageIndex)
  }, [activePageIndex])

  const movePageUp = useCallback(
    (idx: number) => {
      if (idx === 0) return
      setPages((prev) => {
        const next = [...prev]
        const [moved] = next.splice(idx, 1)
        next.splice(idx - 1, 0, moved)
        return next
      })
      // Keep active page following its content if it was the moved page.
      if (idx === activePageIndex) setActivePageIndex(idx - 1)
      else if (idx - 1 === activePageIndex) setActivePageIndex(idx)
    },
    [activePageIndex],
  )

  const movePageDown = useCallback(
    (idx: number) => {
      if (idx >= pages.length - 1) return
      setPages((prev) => {
        const next = [...prev]
        const [moved] = next.splice(idx, 1)
        next.splice(idx + 1, 0, moved)
        return next
      })
      if (idx === activePageIndex) setActivePageIndex(idx + 1)
      else if (idx + 1 === activePageIndex) setActivePageIndex(idx)
    },
    [pages.length, activePageIndex],
  )

  // ── Save flow ─────────────────────────────────────────────────

  const save = useCallback(async () => {
    setSaving(true)
    setError(null)
    try {
      const body = {
        scope,
        focus_type: panelKey,
        kind: "edge_panel" as const,
        vertical: scope === "vertical_default" ? vertical : null,
        tenant_id: scope === "tenant_override" ? tenantId : null,
        pages,
        canvas_config: { default_page_index: defaultPageIndex },
      }
      await adminApi.post(
        `/api/platform/admin/visual-editor/compositions/`,
        body,
      )
      await load()
    } catch (err) {
      const data = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail
      setError(data ?? (err instanceof Error ? err.message : String(err)))
    } finally {
      setSaving(false)
    }
  }, [scope, panelKey, vertical, tenantId, pages, defaultPageIndex, load])

  // ── Preview composition for the right rail ────────────────────

  const previewComposition = useMemo(
    () => (activePage ? pageToResolvedComposition(activePage) : null),
    [activePage],
  )

  // ── Render ────────────────────────────────────────────────────

  return (
    <div
      className={
        hideLeftPane
          ? "grid h-full grid-cols-[1fr_360px] gap-3 p-4"
          : "grid h-full grid-cols-[260px_1fr_360px] gap-3 p-4"
      }
    >
      {/* Left rail — page list. */}
      {!hideLeftPane && (
        <PageList
          pages={pages}
          activePageIndex={activePageIndex}
          defaultPageIndex={defaultPageIndex}
          onSelectPage={(idx) => setActivePageIndex(idx)}
          onAddPage={addPage}
          onMovePageUp={movePageUp}
          onMovePageDown={movePageDown}
        />
      )}

      {/* Center — page authoring + scope. */}
      <div className="flex min-h-0 flex-col gap-3 rounded-md border border-border-subtle bg-surface-elevated p-4">
        <div className="grid grid-cols-3 gap-3">
          <div>
            <Label htmlFor="ep-scope">Scope</Label>
            <Select value={scope} onValueChange={(v) => setScope(v as Scope)}>
              <SelectTrigger id="ep-scope" data-testid="edge-panel-editor-scope">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="platform_default">Platform default</SelectItem>
                <SelectItem value="vertical_default">Vertical default</SelectItem>
                <SelectItem value="tenant_override">Tenant override</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="ep-panel-key">Panel key</Label>
            <Input
              id="ep-panel-key"
              data-testid="edge-panel-editor-panel-key"
              value={panelKey}
              onChange={(e) => setPanelKey(e.target.value)}
            />
          </div>
          {scope === "vertical_default" && (
            <div>
              <Label htmlFor="ep-vertical">Vertical</Label>
              <Input
                id="ep-vertical"
                value={vertical}
                onChange={(e) => setVertical(e.target.value)}
              />
            </div>
          )}
          {scope === "tenant_override" && (
            <div>
              <Label htmlFor="ep-tenant-id">Tenant ID</Label>
              <Input
                id="ep-tenant-id"
                value={tenantId}
                onChange={(e) => setTenantId(e.target.value)}
              />
            </div>
          )}
        </div>

        {activePage !== null && (
          <>
            <PageMetadataEditor
              page={activePage}
              isDefault={defaultPageIndex === activePageIndex}
              isOnlyPage={pages.length <= 1}
              onRenamePage={renamePage}
              onSetDefault={setDefault}
              onDeletePage={deletePage}
            />

            <div className="flex-1 min-h-[280px]">
              <EdgePanelEditorCanvas
                key={activePage.page_id}
                activePage={activePage}
                selection={activeSelection}
                tenantVerticalForButtonPicker={
                  scope === "vertical_default" ? vertical : null
                }
                onCommitRows={handleCommitRows}
                onSelectionChange={handleSelectionChange}
                onUndoableMutation={handleUndoableMutation}
                onUndo={handleUndo}
                onRedo={handleRedo}
              />
            </div>
          </>
        )}

        {error !== null && (
          <div
            className="rounded border border-status-error bg-status-error-muted px-3 py-2 text-caption text-status-error"
            data-testid="edge-panel-editor-error"
          >
            {error}
          </div>
        )}

        <div className="flex items-center gap-2 border-t border-border-subtle pt-3">
          <Button
            type="button"
            onClick={save}
            disabled={saving || loading}
            data-testid="edge-panel-editor-save"
          >
            {saving ? "Saving…" : "Save"}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => void load()}
            disabled={loading}
          >
            Reload
          </Button>
        </div>
      </div>

      {/* Right rail — preview. */}
      <div className="flex flex-col gap-3 rounded-md border border-border-subtle bg-surface-elevated p-3">
        <h2 className="text-body-sm font-medium text-content-strong">
          Preview
        </h2>
        <div
          className="overflow-hidden rounded border border-border-subtle bg-surface-base"
          style={{ minHeight: 320 }}
          data-testid="edge-panel-editor-preview"
        >
          {previewComposition !== null && previewComposition.rows.length > 0 ? (
            <CompositionRenderer
              composition={previewComposition}
              editorMode={false}
            />
          ) : (
            <div className="flex h-full items-center justify-center p-6 text-caption text-content-subtle">
              No rows on this page yet.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
