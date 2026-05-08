/**
 * R-5.0 — EdgePanelEditorPage.
 *
 * Multi-page edge panel authoring at `/visual-editor/edge-panels`.
 * Mirrors the Compositions tab's row-based shape per page; per brief
 * §8 the rendering kind is `kind="edge_panel"` + `pages` JSONB array.
 *
 * v1 ships:
 *   - Scope selector (platform_default / vertical_default / tenant_override)
 *   - Panel-key selector (focus_type column carries the slug for
 *     edge-panel kind; defaults "default")
 *   - Page-list left-rail (add page / delete page / select / set
 *     default)
 *   - Per-page name editor + page-canvas authoring (textarea-driven
 *     row JSON for v1; the visual canvas embed is a Phase R-5.x
 *     polish per Spec-Override Discipline — too tightly coupled to
 *     CompositionEditorPage's single-page state model to retrofit
 *     in this commit. Authoring-via-JSON-textarea remains a
 *     working canonical author surface; rebuild pending arc).
 *   - Live preview panel mirroring the runtime panel shape.
 *   - Save round-trip via /api/platform/admin/visual-editor/compositions/.
 *
 * Authentication: platform admin via adminApi (per visual-editor
 * canonical pattern).
 */
import { useCallback, useEffect, useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
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
import type { ResolvedComposition } from "@/lib/visual-editor/compositions/types"


type Scope = "platform_default" | "vertical_default" | "tenant_override"


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


export default function EdgePanelEditorPage() {
  const [scope, setScope] = useState<Scope>("platform_default")
  const [vertical, setVertical] = useState<string>("manufacturing")
  const [tenantId, setTenantId] = useState<string>("")
  const [panelKey, setPanelKey] = useState<string>("default")
  const [pages, setPages] = useState<EdgePanelPage[]>([])
  const [activePageIndex, setActivePageIndex] = useState<number>(0)
  const [defaultPageIndex, setDefaultPageIndex] = useState<number>(0)
  const [rowsJson, setRowsJson] = useState<string>("[]")
  const [loading, setLoading] = useState<boolean>(false)
  const [saving, setSaving] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  const activePage = pages[activePageIndex] ?? null

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
      setPages(incoming.length > 0 ? incoming : [emptyPage("Page 1")])
      setActivePageIndex(0)
      const defaultIdx = (
        r.data.canvas_config as { default_page_index?: number }
      )?.default_page_index ?? 0
      setDefaultPageIndex(defaultIdx)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [panelKey, scope, vertical, tenantId])

  useEffect(() => {
    void load()
  }, [load])

  // Sync rowsJson with the active page's rows.
  useEffect(() => {
    if (activePage) {
      setRowsJson(JSON.stringify(activePage.rows ?? [], null, 2))
    }
  }, [activePage])

  const updateActivePageRows = useCallback(() => {
    try {
      const parsed = JSON.parse(rowsJson)
      if (!Array.isArray(parsed)) {
        setError("rows must be a JSON array")
        return
      }
      setError(null)
      setPages((prev) =>
        prev.map((p, i) =>
          i === activePageIndex ? { ...p, rows: parsed } : p,
        ),
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [rowsJson, activePageIndex])

  const addPage = useCallback(() => {
    const next = emptyPage(`Page ${pages.length + 1}`)
    setPages((prev) => [...prev, next])
    setActivePageIndex(pages.length)
  }, [pages.length])

  const deletePage = useCallback(() => {
    if (pages.length <= 1) {
      setError("Cannot delete the last page.")
      return
    }
    setPages((prev) => prev.filter((_, i) => i !== activePageIndex))
    setActivePageIndex(Math.max(0, activePageIndex - 1))
  }, [pages.length, activePageIndex])

  const renamePage = useCallback(
    (newName: string) => {
      setPages((prev) =>
        prev.map((p, i) =>
          i === activePageIndex ? { ...p, name: newName } : p,
        ),
      )
    },
    [activePageIndex],
  )

  const setDefault = useCallback(() => {
    setDefaultPageIndex(activePageIndex)
  }, [activePageIndex])

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

  const previewComposition = useMemo(
    () => (activePage ? pageToResolvedComposition(activePage) : null),
    [activePage],
  )

  return (
    <div className="grid h-full grid-cols-[260px_1fr_360px] gap-3 p-4">
      {/* Left rail — page list. */}
      <div className="flex flex-col gap-3 rounded-md border border-border-subtle bg-surface-elevated p-3">
        <div className="flex items-center justify-between">
          <h2 className="text-body-sm font-medium text-content-strong">
            Pages
          </h2>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={addPage}
            data-testid="edge-panel-editor-add-page"
          >
            + Add page
          </Button>
        </div>
        <ul className="flex flex-col gap-1" data-testid="edge-panel-editor-page-list">
          {pages.map((page, idx) => (
            <li key={page.page_id}>
              <button
                type="button"
                onClick={() => setActivePageIndex(idx)}
                data-testid={`edge-panel-editor-page-${idx}`}
                data-active={idx === activePageIndex ? "true" : "false"}
                className={`flex w-full items-center justify-between rounded px-2 py-1 text-left text-body-sm ${
                  idx === activePageIndex
                    ? "bg-accent-subtle text-content-strong"
                    : "text-content-muted hover:bg-surface-sunken"
                }`}
              >
                <span>{page.name}</span>
                {idx === defaultPageIndex && (
                  <span className="text-micro text-accent">DEFAULT</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      </div>

      {/* Center — page authoring + scope. */}
      <div className="flex flex-col gap-3 rounded-md border border-border-subtle bg-surface-elevated p-4">
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
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="ep-page-name">Page name</Label>
                <Input
                  id="ep-page-name"
                  data-testid="edge-panel-editor-page-name"
                  value={activePage.name}
                  onChange={(e) => renamePage(e.target.value)}
                />
              </div>
              <div className="flex items-end gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={setDefault}
                  data-testid="edge-panel-editor-set-default"
                >
                  Set as default page
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="destructive"
                  onClick={deletePage}
                  data-testid="edge-panel-editor-delete-page"
                  disabled={pages.length <= 1}
                >
                  Delete page
                </Button>
              </div>
            </div>

            <div>
              <Label htmlFor="ep-rows-json">
                Rows (JSON — composition row array)
              </Label>
              <Textarea
                id="ep-rows-json"
                data-testid="edge-panel-editor-rows-json"
                rows={14}
                value={rowsJson}
                onChange={(e) => setRowsJson(e.target.value)}
                onBlur={updateActivePageRows}
                className="font-plex-mono text-caption"
              />
              <p className="mt-1 text-caption text-content-muted">
                Edit the row JSON, then click outside to apply. Use the
                Compositions tab&apos;s row authoring patterns. Drag-drop
                authoring lands in R-5.x.
              </p>
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
