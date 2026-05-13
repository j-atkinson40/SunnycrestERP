/**
 * ThemeEditorPage — Phase 2 of the Admin Visual Editor.
 *
 * Three-pane layout:
 *
 *   ┌─ Top bar ─────────────────────────────────────────────┐
 *   │  Title  │  Save · Discard · History · Unsaved badge   │
 *   ├──────────┬────────────────────────┬───────────────────┤
 *   │ Left     │ Center                 │ Right             │
 *   │ Scope    │ Token editor           │ Live preview      │
 *   │ + Mode   │ (catalog + controls)   │ (17 components)   │
 *   └──────────┴────────────────────────┴───────────────────┘
 *
 * Edits flow as: operator interacts with a control in the center
 * pane → `setDraft({ ...draft, [tokenName]: nextValue })` → React
 * re-renders → CSS variables on the preview canvas wrapper update
 * → all components inside the preview re-render with new values.
 *
 * Saves debounce 1.5s after the last edit. Manual save button
 * commits immediately. Failed saves keep the draft state intact
 * so the operator can retry.
 *
 * Critically, the draft theme is applied ONLY to the preview
 * canvas wrapper — never to `document.documentElement`. The
 * editor's own UI (this page's own surfaces) stays unchanged so
 * the operator can read controls + buttons regardless of the
 * draft they're working on.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  AlertCircle,
  ArrowLeftRight,
  History,
  Loader2,
  Save,
  Undo2,
} from "lucide-react"
import { Link } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  themesService,
  type ResolvedTheme,
  type ThemeMode,
  type ThemeRecord,
  type ThemeScope,
} from "@/bridgeable-admin/services/themes-service"
import {
  composeEffective,
  emptyStack,
  stackFromResolved,
  type ThemeStack,
  type TokenOverrideMap,
} from "@/lib/visual-editor/themes/theme-resolver"
import {
  TOKEN_CATALOG,
  type TokenEntry,
} from "@/lib/visual-editor/themes/token-catalog"
import { TokenEditorPane } from "./TokenEditorPane"
import { PreviewCanvas } from "./PreviewCanvas"
import { useStudioRail } from "@/bridgeable-admin/components/studio/StudioRailContext"
import {
  TenantPicker,
  type TenantSummary,
} from "@/bridgeable-admin/components/TenantPicker"


const VERTICALS = ["funeral_home", "manufacturing", "cemetery", "crematory"] as const


export default function ThemeEditorPage() {
  // Studio 1a-i.B — hide editor's own left pane when inside Studio shell
  // with rail expanded. Standalone callers keep left pane visible.
  const { railExpanded, inStudioContext } = useStudioRail()
  const hideLeftPane = railExpanded && inStudioContext

  // ── Editing scope ──────────────────────────────────────
  const [scope, setScope] = useState<ThemeScope>("platform_default")
  const [vertical, setVertical] = useState<string>("funeral_home")
  const [tenantIdInput, setTenantIdInput] = useState<string>("")
  const [selectedTenant, setSelectedTenant] = useState<TenantSummary | null>(null)
  const [editingMode, setEditingMode] = useState<ThemeMode>("light")

  // ── Preview-only mode (orthogonal to editing mode) ─────
  const [previewMode, setPreviewMode] = useState<ThemeMode>("light")
  const [previewVertical, setPreviewVertical] = useState<string>("all")

  // ── Loading / save state ────────────────────────────────
  const [resolved, setResolved] = useState<ResolvedTheme | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState<boolean>(false)

  // ── Draft + active row state ────────────────────────────
  const [draft, setDraft] = useState<TokenOverrideMap>({})
  const [activeRow, setActiveRow] = useState<ThemeRecord | null>(null)

  // ── Token-pane local UI state ───────────────────────────
  const [search, setSearch] = useState<string>("")
  const [showOnlyOverridden, setShowOnlyOverridden] = useState<boolean>(false)
  const [filterToComponentKey, setFilterToComponentKey] = useState<string | null>(null)

  // ── Effective stack derived from resolved + draft ───────
  const stack: ThemeStack = useMemo(() => {
    const base = resolved ? stackFromResolved(resolved, draft) : emptyStack()
    return { ...base, draft }
  }, [resolved, draft])

  // Effective tokens map for the preview canvas wrapper.
  const effectiveTokens = useMemo(() => {
    return composeEffective(previewMode, stack)
  }, [previewMode, stack])

  // ── Resolve theme from backend whenever scope changes ───
  const resolveAndLoadActive = useCallback(async () => {
    setIsLoading(true)
    setLoadError(null)
    try {
      const resolveParams: {
        mode: ThemeMode
        vertical?: string | null
        tenant_id?: string | null
      } = { mode: editingMode }
      if (scope === "vertical_default" || scope === "tenant_override") {
        resolveParams.vertical = vertical || undefined
      }
      if (scope === "tenant_override") {
        resolveParams.tenant_id = tenantIdInput || undefined
      }

      const resolveResult = await themesService.resolve(resolveParams)
      setResolved(resolveResult)

      // Find the active row at the editing scope (if any) so we
      // know whether to PATCH or POST on save.
      const listParams: {
        scope: ThemeScope
        mode: ThemeMode
        vertical?: string
        tenant_id?: string
      } = { scope, mode: editingMode }
      if (scope === "vertical_default") listParams.vertical = vertical
      if (scope === "tenant_override") listParams.tenant_id = tenantIdInput

      const rows = await themesService.list(listParams)
      const active = rows.find((r) => r.is_active) ?? null
      setActiveRow(active)
      // Seed the draft with the active row's existing overrides
      // so the editor opens "in sync" with the saved state.
      // Operator edits add/remove keys from this seed.
      setDraft(
        active
          ? Object.fromEntries(
              Object.entries(active.token_overrides).map(([k, v]) => [
                k,
                String(v),
              ]),
            )
          : {},
      )
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[theme-editor] resolve failed", err)
      setLoadError(
        err instanceof Error ? err.message : "Failed to load theme",
      )
    } finally {
      setIsLoading(false)
    }
  }, [scope, vertical, tenantIdInput, editingMode])

  useEffect(() => {
    void resolveAndLoadActive()
  }, [resolveAndLoadActive])

  // Keep preview mode in sync with editing mode initially. The
  // operator can independently flip preview without losing the
  // editing-mode value.
  useEffect(() => {
    setPreviewMode(editingMode)
  }, [editingMode])

  // ── Token edit handler ─────────────────────────────────
  const handleTokenChange = useCallback(
    (tokenName: string, value: string | undefined) => {
      // Special sentinel from the component-filter banner clear button.
      if (tokenName === "__clear-filter__") {
        setFilterToComponentKey(null)
        return
      }

      setDraft((prev) => {
        const next = { ...prev }
        if (value === undefined) {
          // Reset = remove the override at this scope. The
          // resolver will fall back to the parent layer.
          delete next[tokenName]
        } else {
          next[tokenName] = value
        }
        return next
      })
    },
    [],
  )

  // ── Unsaved-changes detection ───────────────────────────
  const persistedOverrides = useMemo(() => {
    if (!activeRow) return {}
    const out: Record<string, string> = {}
    for (const [k, v] of Object.entries(activeRow.token_overrides)) {
      out[k] = String(v)
    }
    return out
  }, [activeRow])

  const unsavedChanges = useMemo(() => {
    const keys = new Set([
      ...Object.keys(draft),
      ...Object.keys(persistedOverrides),
    ])
    let count = 0
    for (const k of keys) {
      if (draft[k] !== persistedOverrides[k]) count += 1
    }
    return count
  }, [draft, persistedOverrides])

  const hasUnsaved = unsavedChanges > 0

  // ── Save (manual + debounced autosave) ──────────────────
  const handleSave = useCallback(async () => {
    if (!hasUnsaved && activeRow) return
    setIsSaving(true)
    setSaveError(null)
    try {
      if (activeRow) {
        const updated = await themesService.update(activeRow.id, draft)
        setActiveRow(updated)
      } else {
        const created = await themesService.create({
          scope,
          vertical: scope === "vertical_default" ? vertical : null,
          tenant_id: scope === "tenant_override" ? tenantIdInput : null,
          mode: editingMode,
          token_overrides: draft,
        })
        setActiveRow(created)
      }
      // Re-resolve so the inheritance indicators reflect the new
      // saved state (the active row's overrides become the
      // "platform_default" / "vertical_default" / "tenant_override"
      // layer in the resolved stack — the draft stays equal to the
      // saved overrides).
      await resolveAndLoadActive()
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[theme-editor] save failed", err)
      setSaveError(
        err instanceof Error ? err.message : "Failed to save theme",
      )
    } finally {
      setIsSaving(false)
    }
  }, [
    activeRow,
    draft,
    editingMode,
    hasUnsaved,
    resolveAndLoadActive,
    scope,
    tenantIdInput,
    vertical,
  ])

  // Debounced autosave at 1.5s of inactivity.
  const autosaveTimerRef = useRef<number | null>(null)
  useEffect(() => {
    if (!hasUnsaved) return
    if (autosaveTimerRef.current !== null) {
      window.clearTimeout(autosaveTimerRef.current)
    }
    autosaveTimerRef.current = window.setTimeout(() => {
      void handleSave()
    }, 1500)
    return () => {
      if (autosaveTimerRef.current !== null) {
        window.clearTimeout(autosaveTimerRef.current)
        autosaveTimerRef.current = null
      }
    }
  }, [draft, hasUnsaved, handleSave])

  const handleDiscard = useCallback(() => {
    setDraft({ ...persistedOverrides })
  }, [persistedOverrides])

  // ── Render ──────────────────────────────────────────────
  return (
    <div
      className="flex h-[calc(100vh-3rem)] flex-col"
      data-testid="theme-editor-page"
    >
      {/* ── Top bar ──────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-4 border-b border-border-subtle bg-surface-elevated px-6 py-3">
        <div>
          <h1 className="text-h3 font-plex-serif font-medium text-content-strong">
            Theme editor
          </h1>
          <p className="text-caption text-content-muted">
            Phase 2 of the Admin Visual Editor — token-driven live preview.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/admin/components"
            className="flex items-center gap-1 text-caption text-content-muted hover:text-content-strong"
            data-testid="nav-to-components"
          >
            <ArrowLeftRight size={12} />
            Edit components
          </Link>
          <Link
            to="/admin/workflows"
            className="flex items-center gap-1 text-caption text-content-muted hover:text-content-strong"
            data-testid="nav-to-workflows"
          >
            <ArrowLeftRight size={12} />
            Edit workflows
          </Link>
          <Link
            to="/admin/registry"
            className="flex items-center gap-1 text-caption text-content-muted hover:text-content-strong"
            data-testid="nav-to-registry"
          >
            <ArrowLeftRight size={12} />
            Registry
          </Link>
          {hasUnsaved && (
            <Badge variant="warning" data-testid="theme-editor-unsaved-badge">
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
              data-testid="theme-editor-save-error"
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
            data-testid="theme-editor-discard"
          >
            <Undo2 size={14} className="mr-1" />
            Discard
          </Button>
          <Button
            size="sm"
            onClick={() => void handleSave()}
            disabled={!hasUnsaved || isSaving}
            data-testid="theme-editor-save"
          >
            <Save size={14} className="mr-1" />
            Save
          </Button>
          <Button
            variant="outline"
            size="sm"
            data-testid="theme-editor-history"
            // Phase 3 surface — the button is a deliberate stub.
            disabled
          >
            <History size={14} className="mr-1" />
            History
          </Button>
        </div>
      </div>

      {/* ── Three-pane body ─────────────────────────────── */}
      <div
        className={
          hideLeftPane
            ? "grid flex-1 grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] overflow-hidden"
            : "grid flex-1 grid-cols-[280px_minmax(0,1fr)_minmax(0,1.2fr)] overflow-hidden"
        }
      >
        {/* ── Left pane — scope + mode ──────────────────── */}
        {!hideLeftPane && (
        <aside
          className="border-r border-border-subtle bg-surface-sunken p-4"
          data-testid="theme-editor-scope-pane"
        >
          <div className="mb-4">
            <label className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted">
              Editing scope
            </label>
            <div className="flex flex-col gap-1">
              {(
                [
                  ["platform_default", "Platform default"],
                  ["vertical_default", "Vertical default"],
                  ["tenant_override", "Tenant override"],
                ] as Array<[ThemeScope, string]>
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
            <div className="mb-4">
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
            <div className="mb-4">
              <label className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted">
                Tenant
              </label>
              <TenantPicker
                selected={selectedTenant}
                onSelect={(t) => {
                  setSelectedTenant(t)
                  setTenantIdInput(t?.id ?? "")
                }}
              />
              <p className="mt-1 text-caption text-content-muted">
                Admin-side support tooling — pick a specific tenant before
                editing their override. Full tenant Workshop UI ships in a
                later phase.
              </p>
            </div>
          )}

          <div className="mb-4">
            <label className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted">
              Editing mode
            </label>
            <div className="flex gap-1 rounded-md border border-border-subtle bg-surface-raised p-0.5">
              <button
                type="button"
                data-testid="editing-mode-light"
                onClick={() => setEditingMode("light")}
                className={`flex-1 rounded-sm px-2 py-1 text-caption ${
                  editingMode === "light"
                    ? "bg-accent-subtle text-content-strong"
                    : "text-content-muted hover:bg-accent-subtle/40"
                }`}
              >
                Light
              </button>
              <button
                type="button"
                data-testid="editing-mode-dark"
                onClick={() => setEditingMode("dark")}
                className={`flex-1 rounded-sm px-2 py-1 text-caption ${
                  editingMode === "dark"
                    ? "bg-accent-subtle text-content-strong"
                    : "text-content-muted hover:bg-accent-subtle/40"
                }`}
              >
                Dark
              </button>
            </div>
            <p className="mt-1 text-caption text-content-muted">
              Mode is part of theme identity. Editing light leaves dark
              untouched.
            </p>
          </div>

          <div className="mb-4">
            <label className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted">
              Preview vertical filter
            </label>
            <select
              value={previewVertical}
              onChange={(e) => setPreviewVertical(e.target.value)}
              data-testid="preview-vertical-select"
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

          {isLoading && (
            <div className="flex items-center gap-1 text-caption text-content-muted">
              <Loader2 size={12} className="animate-spin" />
              Resolving theme…
            </div>
          )}
          {loadError && (
            <div className="text-caption text-status-error">
              {loadError}
            </div>
          )}
          {activeRow && (
            <p className="text-caption text-content-muted">
              Active record version{" "}
              <span className="font-plex-mono text-content-strong">
                v{activeRow.version}
              </span>
              {" — "}
              {Object.keys(activeRow.token_overrides).length} override
              {Object.keys(activeRow.token_overrides).length === 1 ? "" : "s"}
            </p>
          )}
        </aside>
        )}

        {/* ── Center pane — token editor ─────────────────── */}
        <TokenEditorPane
          mode={editingMode}
          stack={stack}
          effectiveTokens={effectiveTokens}
          onTokenChange={handleTokenChange}
          filterToComponentKey={filterToComponentKey}
          showOnlyOverridden={showOnlyOverridden}
          onShowOnlyOverriddenChange={setShowOnlyOverridden}
          search={search}
          onSearchChange={setSearch}
          editingScope={scope}
        />

        {/* ── Right pane — live preview ──────────────────── */}
        <PreviewCanvas
          effectiveTokens={effectiveTokens}
          previewMode={previewMode}
          onPreviewModeChange={setPreviewMode}
          selectedRegistryKey={filterToComponentKey}
          onComponentSelect={setFilterToComponentKey}
          filterVertical={previewVertical}
        />
      </div>
    </div>
  )
}


// Re-export for convenience.
export { TOKEN_CATALOG }
export type { TokenEntry }
