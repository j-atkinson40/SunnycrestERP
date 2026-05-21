/**
 * WidgetListPage — WB-4b widget definition list view.
 *
 * Mounted at `/studio/widgets`. Lists every composed widget for the
 * tenant (rows that carry a `composition_blob`). Filter by tier_scope
 * (All / Platform / Vertical). "+ New Widget" creates a new draft
 * via the existing `widgetBuilderService.create` + navigates to the
 * editor.
 *
 * Phase 1 — no delete, no duplicate, no bulk ops, no search, no
 * per-tenant filtering. Bounded surface; later phases add affordances
 * as operator signal warrants.
 */
import { Loader2 } from "lucide-react"
import { useCallback, useState } from "react"
import { Link, useNavigate } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import {
  useWidgetList,
  type TierScopeFilter,
} from "@/bridgeable-admin/hooks/useWidgetList"
import { widgetBuilderService } from "@/bridgeable-admin/services/widget-builder-service"


const TIER_OPTIONS: { value: TierScopeFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "platform", label: "Platform" },
  { value: "vertical", label: "Vertical" },
]


export default function WidgetListPage() {
  const navigate = useNavigate()
  const { widgets, loading, error, tierFilter, setTierFilter, refresh } =
    useWidgetList()
  const [createBusy, setCreateBusy] = useState(false)

  const handleCreate = useCallback(async () => {
    setCreateBusy(true)
    try {
      const r = await widgetBuilderService.create({
        title: "Untitled widget",
        tier_scope: "vertical",
      })
      navigate(adminPath(`/studio/widget-builder/${r.widget_id}`))
    } catch {
      setCreateBusy(false)
      // Best-effort refresh in case the create succeeded server-side.
      refresh()
    }
  }, [navigate, refresh])

  return (
    <div
      data-testid="widget-list-page"
      className="flex h-full flex-col bg-surface-base"
    >
      <header
        data-testid="widget-list-header"
        className="flex items-center gap-3 border-b border-border-subtle bg-surface-raised px-6 py-3"
      >
        <h1 className="text-h2 text-content-strong">Widgets</h1>
        <div className="flex-1" />
        <div className="flex items-center gap-1" data-testid="widget-list-tier-filter">
          {TIER_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              data-testid={`widget-list-tier-filter-${opt.value}`}
              data-active={tierFilter === opt.value ? "true" : "false"}
              onClick={() => setTierFilter(opt.value)}
              className={cn(
                "rounded-md border px-2.5 py-1 text-body-sm transition-colors",
                tierFilter === opt.value
                  ? "border-accent bg-accent-subtle text-content-strong"
                  : "border-border-subtle bg-surface-elevated text-content-muted hover:bg-surface-raised",
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <Button
          data-testid="widget-list-new-button"
          onClick={handleCreate}
          disabled={createBusy}
        >
          {createBusy ? (
            <Loader2 size={16} className="animate-spin mr-2" />
          ) : null}
          + New Widget
        </Button>
      </header>

      <main className="flex-1 overflow-auto px-6 py-4">
        {loading ? (
          <div
            data-testid="widget-list-loading"
            className="flex h-32 items-center justify-center text-content-muted"
          >
            <Loader2 size={20} className="animate-spin" />
          </div>
        ) : error ? (
          <div
            data-testid="widget-list-error"
            role="alert"
            className="rounded-md border border-status-error/30 bg-status-error-muted px-4 py-2 text-body-sm text-status-error"
          >
            {error}
          </div>
        ) : widgets.length === 0 ? (
          <div
            data-testid="widget-list-empty"
            className="flex h-48 flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border-base bg-surface-elevated text-content-muted"
          >
            <span className="text-body">No widgets yet.</span>
            <span className="text-body-sm">
              Click + New Widget to compose your first.
            </span>
          </div>
        ) : (
          <ul
            data-testid="widget-list-rows"
            className="flex flex-col gap-1.5"
          >
            {widgets.map((w) => (
              <li key={w.widget_id}>
                <Link
                  data-testid={`widget-list-row-${w.widget_id}`}
                  to={adminPath(`/studio/widget-builder/${w.widget_id}`)}
                  className={cn(
                    "flex items-center gap-3 rounded-md border border-border-subtle",
                    "bg-surface-raised px-4 py-2.5 hover:bg-surface-elevated",
                  )}
                >
                  <span className="flex-1 truncate text-body text-content-strong">
                    {w.title || "Untitled widget"}
                  </span>
                  <Badge variant="secondary" data-testid="widget-list-row-tier">
                    {w.tier_scope === "platform" ? "Platform" : "Vertical"}
                  </Badge>
                  <span
                    className="text-caption text-content-muted"
                    data-testid="widget-list-row-state"
                  >
                    {w.published_composition_blob === null
                      ? "Draft"
                      : w.published_composition_blob !== w.composition_blob
                        ? "Draft (unpublished changes)"
                        : "Published"}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  )
}
