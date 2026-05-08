/**
 * R-5.1 — `/settings/edge-panel` — per-user edge panel customization.
 *
 * Three-pane layout at lg+ (page list / page editor / live preview);
 * stacks vertically below lg.
 *
 * State model:
 *   - tenantDefault: ResolvedEdgePanel (fetched via
 *     resolveEdgePanelTenantDefault) — what ships from admin.
 *   - userOverride: EdgePanelUserOverride — currently-edited
 *     override blob (JSON shape stored at
 *     User.preferences.edge_panel_overrides[panel_key]).
 *   - lastSavedOverride: same shape, used for unsaved-changes
 *     indicator + Discard.
 *
 * Save semantics: manual save (no autosave). The unsaved-changes
 * indicator + Save button reveal when state diverges from last
 * persisted. Discard reverts. Reset opens panel-level confirmation
 * dialog.
 *
 * The live preview pane uses applyUserOverride to compute the
 * effective EdgePanelPage[] client-side and renders the active page
 * via CompositionRenderer with editorMode={false}. Parity with
 * backend resolver semantics is enforced by applyOverride.test.ts.
 */
import { useEffect, useMemo, useState } from "react"
import {
  AlertCircle,
  CheckCircle,
  Eye,
  EyeOff,
  GripVertical,
  Plus,
  RotateCcw,
} from "lucide-react"
import { toast } from "sonner"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/contexts/auth-context"
import { applyUserOverride } from "@/lib/edge-panel/applyOverride"
import {
  getEdgePanelPreferences,
  getEdgePanelTenantConfig,
  patchEdgePanelPreferences,
  resolveEdgePanelTenantDefault,
} from "@/lib/edge-panel/edge-panel-service"
import type {
  EdgePanelPage,
  EdgePanelTenantConfig,
  EdgePanelUserOverride,
  ResolvedEdgePanel,
} from "@/lib/edge-panel/types"
import { CompositionRenderer } from "@/lib/visual-editor/compositions/CompositionRenderer"
import type {
  CompositionRow,
  ResolvedComposition,
} from "@/lib/visual-editor/compositions/types"

import { PageEditor, type PageOverrideSlice } from "@/components/settings/edge-panel/PageEditor"
import { PanelLevelReset } from "@/components/settings/edge-panel/ResetDialogs"


const PANEL_KEY = "default"


function newPageId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID()
  }
  return `pg-${Math.random().toString(36).slice(2)}-${Date.now()}`
}


/** Convert a single EdgePanelPage to a ResolvedComposition for the
 *  CompositionRenderer (rows + canvas_config + standard scaffolding). */
function pageToResolvedComposition(
  page: EdgePanelPage,
  panelKey: string,
): ResolvedComposition {
  return {
    focus_type: panelKey,
    vertical: null,
    tenant_id: null,
    source: "platform_default",
    source_id: null,
    source_version: null,
    rows: page.rows,
    canvas_config: page.canvas_config ?? {},
  }
}


/** Equality check on full override JSON shapes — used for unsaved-
 *  changes detection. JSON.stringify is sufficient for this purpose
 *  given override payloads are bounded (~few KB). */
function deepEqualJson(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b)
}


export default function EdgePanelSettingsPage() {
  const { company } = useAuth()
  const tenantVertical = company?.vertical ?? "manufacturing"

  const [tenantDefault, setTenantDefault] = useState<ResolvedEdgePanel | null>(
    null,
  )
  const [tenantConfig, setTenantConfig] = useState<EdgePanelTenantConfig | null>(
    null,
  )
  const [userOverride, setUserOverride] = useState<EdgePanelUserOverride>({})
  const [lastSavedOverride, setLastSavedOverride] = useState<EdgePanelUserOverride>({})
  const [activePageId, setActivePageId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [resetOpen, setResetOpen] = useState(false)

  // Fetch the three required data sources in parallel on mount.
  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    Promise.all([
      resolveEdgePanelTenantDefault(PANEL_KEY).catch(() => null),
      getEdgePanelPreferences().catch(() => null),
      getEdgePanelTenantConfig().catch(() => null),
    ])
      .then(([tenantDef, prefs, cfg]) => {
        if (cancelled) return
        setTenantDefault(tenantDef)
        setTenantConfig(cfg)
        const ov = prefs?.edge_panel_overrides?.[PANEL_KEY] ?? {}
        setUserOverride(ov)
        setLastSavedOverride(ov)
        // Initial active page: first tenant page or first personal page.
        const firstId =
          tenantDef?.pages?.[0]?.page_id ??
          ov.additional_pages?.[0]?.page_id ??
          null
        setActivePageId(firstId)
        setError(null)
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load")
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const effectivePages = useMemo(
    () => applyUserOverride(tenantDefault, userOverride),
    [tenantDefault, userOverride],
  )

  const unsavedChanges = useMemo(
    () => !deepEqualJson(userOverride, lastSavedOverride),
    [userOverride, lastSavedOverride],
  )

  const activePage = useMemo(
    () => effectivePages.find((p) => p.page_id === activePageId) ?? null,
    [effectivePages, activePageId],
  )

  const isActiveTenant = useMemo(() => {
    if (!activePageId) return false
    return (
      tenantDefault?.pages?.some((p) => p.page_id === activePageId) ?? false
    )
  }, [activePageId, tenantDefault])

  const tenantPageById = useMemo(() => {
    const m = new Map<string, EdgePanelPage>()
    for (const p of tenantDefault?.pages ?? []) m.set(p.page_id, p)
    return m
  }, [tenantDefault])

  const personalPageById = useMemo(() => {
    const m = new Map<string, EdgePanelPage>()
    for (const p of userOverride.additional_pages ?? []) m.set(p.page_id, p)
    return m
  }, [userOverride.additional_pages])

  const allPagesInOrder = useMemo<EdgePanelPage[]>(() => {
    return effectivePages
  }, [effectivePages])

  // ---------- Mutators ----------

  function patchUserOverride(updater: (prev: EdgePanelUserOverride) => EdgePanelUserOverride) {
    setUserOverride((prev) => updater(prev))
  }

  function updatePageOverride(
    pageId: string,
    updates: Partial<PageOverrideSlice>,
  ) {
    patchUserOverride((prev) => {
      const existing = prev.page_overrides?.[pageId] ?? {}
      const next = { ...existing, ...updates }
      // Remove empty arrays/null fields to keep JSON tidy.
      if (
        next.hidden_placement_ids &&
        next.hidden_placement_ids.length === 0
      ) {
        delete next.hidden_placement_ids
      }
      if (
        next.additional_placements &&
        next.additional_placements.length === 0
      ) {
        delete next.additional_placements
      }
      if (next.placement_order && next.placement_order.length === 0) {
        delete next.placement_order
      }
      const isEmpty = Object.keys(next).length === 0
      const map = { ...(prev.page_overrides ?? {}) }
      if (isEmpty) {
        delete map[pageId]
      } else {
        map[pageId] = next
      }
      return { ...prev, page_overrides: map }
    })
  }

  function updatePersonalPageRows(pageId: string, rows: CompositionRow[]) {
    patchUserOverride((prev) => {
      const pages = prev.additional_pages ?? []
      const next = pages.map((p) =>
        p.page_id === pageId ? { ...p, rows } : p,
      )
      return { ...prev, additional_pages: next }
    })
  }

  function renamePersonalPage(pageId: string, newName: string) {
    patchUserOverride((prev) => {
      const pages = prev.additional_pages ?? []
      const next = pages.map((p) =>
        p.page_id === pageId ? { ...p, name: newName } : p,
      )
      return { ...prev, additional_pages: next }
    })
  }

  function deletePersonalPage(pageId: string) {
    patchUserOverride((prev) => {
      const pages = (prev.additional_pages ?? []).filter(
        (p) => p.page_id !== pageId,
      )
      const order = prev.page_order_override?.filter((id) => id !== pageId)
      return {
        ...prev,
        additional_pages: pages,
        page_order_override: order,
      }
    })
    if (activePageId === pageId) {
      setActivePageId(tenantDefault?.pages?.[0]?.page_id ?? null)
    }
  }

  function resetPage(pageId: string) {
    patchUserOverride((prev) => {
      const map = { ...(prev.page_overrides ?? {}) }
      delete map[pageId]
      return { ...prev, page_overrides: map }
    })
  }

  function addPersonalPage() {
    const id = newPageId()
    const page: EdgePanelPage = {
      page_id: id,
      name: "New page",
      rows: [],
      canvas_config: {},
    }
    patchUserOverride((prev) => ({
      ...prev,
      additional_pages: [...(prev.additional_pages ?? []), page],
    }))
    setActivePageId(id)
  }

  function toggleHidePage(pageId: string) {
    patchUserOverride((prev) => {
      const set = new Set(prev.hidden_page_ids ?? [])
      if (set.has(pageId)) set.delete(pageId)
      else set.add(pageId)
      const arr = Array.from(set)
      return { ...prev, hidden_page_ids: arr.length === 0 ? undefined : arr }
    })
  }

  function reorderPages(newOrder: string[]) {
    patchUserOverride((prev) => ({
      ...prev,
      page_order_override: newOrder,
    }))
  }

  // ---------- Save / Discard / Reset ----------

  async function save() {
    setIsSaving(true)
    try {
      const payload = await patchEdgePanelPreferences({
        ...{}, // explicit object so we don't fall through types
        [PANEL_KEY]: userOverride,
      })
      // Server returns canonical post-save shape.
      const saved = payload.edge_panel_overrides[PANEL_KEY] ?? {}
      setLastSavedOverride(saved)
      setUserOverride(saved)
      toast.success("Edge panel saved")
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Save failed"
      toast.error(msg)
    } finally {
      setIsSaving(false)
    }
  }

  function discard() {
    setUserOverride(lastSavedOverride)
  }

  async function resetAll() {
    setIsSaving(true)
    try {
      const cleared: EdgePanelUserOverride = {}
      const payload = await patchEdgePanelPreferences({
        [PANEL_KEY]: cleared,
      })
      const saved = payload.edge_panel_overrides[PANEL_KEY] ?? {}
      setUserOverride(saved)
      setLastSavedOverride(saved)
      setActivePageId(tenantDefault?.pages?.[0]?.page_id ?? null)
      toast.success("Edge panel reset to default")
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Reset failed"
      toast.error(msg)
    } finally {
      setIsSaving(false)
      setResetOpen(false)
    }
  }

  // ---------- Render ----------

  if (isLoading) {
    return (
      <div className="p-6 text-content-muted" data-testid="edge-panel-settings-page">
        Loading edge panel preferences…
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6" data-testid="edge-panel-settings-page">
        <Alert variant="error">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Failed to load</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    )
  }

  if (!tenantConfig?.enabled) {
    return (
      <div className="p-6" data-testid="edge-panel-settings-page">
        <Alert variant="info">
          <AlertTitle>Edge panel is disabled</AlertTitle>
          <AlertDescription>
            Your tenant administrator has disabled the edge panel.
            Customizations are not available until it's re-enabled.
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  if (!tenantDefault || (tenantDefault.pages ?? []).length === 0) {
    return (
      <div className="p-6" data-testid="edge-panel-settings-page">
        <Alert variant="info">
          <AlertTitle>No edge panel configured</AlertTitle>
          <AlertDescription>
            Your tenant administrator hasn't published an edge panel yet.
            When they do, you'll be able to customize it here.
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  const allHidden =
    effectivePages.length === 0 && (tenantDefault.pages?.length ?? 0) > 0

  // Personal page mutators dispatched from the editor.
  const activePersonalPage = activePageId
    ? personalPageById.get(activePageId) ?? null
    : null
  const activeTenantPage = activePageId
    ? tenantPageById.get(activePageId) ?? null
    : null

  return (
    <div
      className="p-4 lg:p-6"
      data-testid="edge-panel-settings-page"
    >
      <header className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between mb-4">
        <div className="flex flex-col gap-1 max-w-2xl">
          <h1 className="text-h2 font-plex-serif text-content-strong">
            Customize your edge panel
          </h1>
          <p className="text-body-sm text-content-muted">
            Add, hide, and reorder buttons in your personal view of the
            edge panel. Your changes apply only for you. Press
            <span className="mx-1 rounded border border-border-base bg-surface-elevated px-1 font-mono text-caption">
              Cmd+Shift+E
            </span>
            anywhere to open the panel.
          </p>
          {unsavedChanges && (
            <span
              className="text-caption text-status-warning"
              data-testid="edge-panel-settings-unsaved-indicator"
            >
              <AlertCircle className="inline h-3 w-3 mr-1" /> Unsaved changes
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {unsavedChanges && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={discard}
                disabled={isSaving}
                data-testid="edge-panel-settings-discard"
              >
                Discard
              </Button>
              <Button
                size="sm"
                onClick={save}
                disabled={isSaving}
                data-testid="edge-panel-settings-save"
              >
                {isSaving ? (
                  "Saving…"
                ) : (
                  <>
                    <CheckCircle className="h-4 w-4" /> Save
                  </>
                )}
              </Button>
            </>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setResetOpen(true)}
            disabled={isSaving}
            data-testid="edge-panel-settings-reset-all"
          >
            <RotateCcw className="h-4 w-4" /> Reset to default
          </Button>
        </div>
      </header>

      {allHidden && (
        <Alert variant="warning" className="mb-4">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>All pages are hidden</AlertTitle>
          <AlertDescription>
            You've hidden every page. The edge panel won't show until at
            least one page is visible.
          </AlertDescription>
        </Alert>
      )}

      <div className="grid gap-3 lg:grid-cols-[260px_1fr_320px]">
        {/* Left rail — page list. */}
        <aside
          className="flex flex-col gap-2 lg:sticky lg:top-4 self-start"
          data-testid="edge-panel-settings-page-list"
        >
          <h2 className="text-micro uppercase tracking-wider text-content-muted px-1">
            Pages
          </h2>
          <ul className="flex flex-col gap-1">
            {allPagesInOrder.map((page) => {
              const isTenant = tenantPageById.has(page.page_id)
              const isPersonal = personalPageById.has(page.page_id)
              const isHidden = (userOverride.hidden_page_ids ?? []).includes(
                page.page_id,
              )
              const isActive = page.page_id === activePageId
              return (
                <li
                  key={page.page_id}
                  data-testid={`edge-panel-settings-page-row-${page.page_id}`}
                  data-active={isActive ? "true" : "false"}
                  className={`flex items-center gap-2 rounded-md border p-2 transition-colors ${
                    isActive
                      ? "border-accent bg-accent-subtle"
                      : "border-border-subtle bg-surface-elevated hover:bg-accent-subtle"
                  }`}
                >
                  <span className="text-content-subtle cursor-grab" aria-hidden>
                    <GripVertical className="h-4 w-4" />
                  </span>
                  <button
                    type="button"
                    className="flex-1 min-w-0 text-left flex flex-col"
                    onClick={() => setActivePageId(page.page_id)}
                  >
                    <span
                      className={
                        isHidden
                          ? "text-content-muted line-through"
                          : "text-content-strong"
                      }
                    >
                      {page.name}
                    </span>
                    <span className="text-caption text-content-muted">
                      {isTenant && "From admin"}
                      {isPersonal && "Personal"}
                    </span>
                  </button>
                  {isTenant && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => toggleHidePage(page.page_id)}
                      data-testid={`edge-panel-settings-page-hide-${page.page_id}`}
                      aria-label={isHidden ? "Show page" : "Hide page"}
                    >
                      {isHidden ? (
                        <Eye className="h-4 w-4" />
                      ) : (
                        <EyeOff className="h-4 w-4" />
                      )}
                    </Button>
                  )}
                </li>
              )
            })}
          </ul>
          <Button
            variant="outline"
            size="sm"
            onClick={addPersonalPage}
            type="button"
            data-testid="edge-panel-settings-add-personal-page"
          >
            <Plus className="h-4 w-4" /> Add personal page
          </Button>
          <PageOrderControls
            pages={allPagesInOrder}
            onReorder={reorderPages}
          />
        </aside>

        {/* Center — active page editor. */}
        <main className="min-w-0">
          {activePage ? (
            <PageEditor
              tenantPage={isActiveTenant ? activeTenantPage : null}
              personalPage={!isActiveTenant ? activePersonalPage : null}
              pageOverride={
                isActiveTenant && activePageId
                  ? (userOverride.page_overrides?.[activePageId] as
                      | PageOverrideSlice
                      | null) ?? null
                  : null
              }
              onUpdateOverride={(updates) =>
                activePageId && updatePageOverride(activePageId, updates)
              }
              onUpdatePersonalRows={(rows) =>
                activePageId && updatePersonalPageRows(activePageId, rows)
              }
              onRenamePersonalPage={(name) =>
                activePageId && renamePersonalPage(activePageId, name)
              }
              onResetPage={() => activePageId && resetPage(activePageId)}
              onDeletePersonalPage={() =>
                activePageId && deletePersonalPage(activePageId)
              }
              tenantVertical={tenantVertical}
            />
          ) : (
            <div className="p-4 text-content-muted">
              No page selected.
            </div>
          )}
        </main>

        {/* Right rail — live preview. */}
        <aside
          className="lg:sticky lg:top-4 self-start min-w-0"
          data-testid="edge-panel-settings-preview"
        >
          <h2 className="text-micro uppercase tracking-wider text-content-muted px-1 mb-2">
            Preview
          </h2>
          <div
            className="rounded-md border border-border-subtle bg-surface-elevated p-2"
            style={{
              maxHeight: "70vh",
              overflowY: "auto",
            }}
          >
            {activePage ? (
              <CompositionRenderer
                composition={pageToResolvedComposition(activePage, PANEL_KEY)}
                editorMode={false}
              />
            ) : (
              <div className="p-4 text-content-muted text-body-sm">
                Select a page to preview it.
              </div>
            )}
          </div>
        </aside>
      </div>

      <PanelLevelReset
        open={resetOpen}
        onClose={() => setResetOpen(false)}
        onConfirm={resetAll}
      />
    </div>
  )
}


/** Tiny up/down move-by-one control for page reordering. Dedicated
 *  component to keep the main page render readable. */
function PageOrderControls({
  pages,
  onReorder,
}: {
  pages: EdgePanelPage[]
  onReorder: (newOrder: string[]) => void
}) {
  if (pages.length < 2) return null
  return (
    <div
      className="flex flex-col gap-1 mt-1"
      data-testid="edge-panel-settings-page-reorder"
    >
      <div className="text-micro uppercase tracking-wider text-content-muted px-1">
        Reorder
      </div>
      {pages.map((page, idx) => (
        <div
          key={page.page_id}
          className="flex items-center gap-1 text-caption px-1"
        >
          <span className="flex-1 truncate text-content-muted">
            {idx + 1}. {page.name}
          </span>
          <Button
            variant="ghost"
            size="sm"
            disabled={idx === 0}
            onClick={() => {
              const next = [...pages.map((p) => p.page_id)]
              ;[next[idx - 1], next[idx]] = [next[idx], next[idx - 1]]
              onReorder(next)
            }}
            aria-label="Move page up"
            type="button"
          >
            ↑
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={idx === pages.length - 1}
            onClick={() => {
              const next = [...pages.map((p) => p.page_id)]
              ;[next[idx + 1], next[idx]] = [next[idx], next[idx + 1]]
              onReorder(next)
            }}
            aria-label="Move page down"
            type="button"
          >
            ↓
          </Button>
        </div>
      ))}
    </div>
  )
}
