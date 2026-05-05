/**
 * TenantPicker — Visual Editor scope-selector helper.
 *
 * Renders a search input + result list against
 * /api/platform/admin/tenants/lookup. Calls back with the selected
 * tenant {id, name, vertical}. Used by the three Visual Editor
 * pages when the scope is `tenant_override` — operator must select
 * a specific tenant before tenant-override controls activate.
 *
 * No selection = no scope. The editor pages render a banner +
 * disable controls until selection happens (see VisualEditorLayout's
 * scopeIndicator prop + useTenantOverrideScope hook).
 */
import { useEffect, useRef, useState } from "react"
import { Search } from "lucide-react"
import { adminApi } from "@/bridgeable-admin/lib/admin-api"


export interface TenantSummary {
  id: string
  slug: string
  name: string
  vertical: string | null
}


interface TenantPickerProps {
  selected: TenantSummary | null
  onSelect: (tenant: TenantSummary | null) => void
  /** Optional placeholder text when no tenant selected. */
  placeholder?: string
}


export function TenantPicker({
  selected,
  onSelect,
  placeholder = "Search tenants by name or slug…",
}: TenantPickerProps) {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<TenantSummary[]>([])
  const [open, setOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (!open) return
    debounceRef.current = setTimeout(async () => {
      setIsLoading(true)
      try {
        const { data } = await adminApi.get<TenantSummary[]>(
          "/api/platform/admin/tenants/lookup",
          { params: { q: query || undefined, limit: 25 } },
        )
        setResults(data)
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error("[tenant-picker] lookup failed", err)
        setResults([])
      } finally {
        setIsLoading(false)
      }
    }, 250)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [query, open])

  if (selected) {
    return (
      <div
        className="flex items-center gap-2 rounded-sm border border-border-base bg-surface-elevated px-3 py-2"
        data-testid="tenant-picker-selected"
      >
        <div className="flex flex-col gap-0.5">
          <span className="text-body-sm font-medium text-content-strong">
            {selected.name}
          </span>
          <span className="text-caption text-content-muted">
            {selected.vertical ?? "no-vertical"} · {selected.slug} ·{" "}
            <code className="font-plex-mono text-content-subtle">
              {selected.id.slice(0, 8)}…
            </code>
          </span>
        </div>
        <button
          type="button"
          onClick={() => onSelect(null)}
          className="ml-auto text-caption text-content-muted hover:text-content-strong"
          data-testid="tenant-picker-clear"
        >
          Change
        </button>
      </div>
    )
  }

  return (
    <div className="relative" data-testid="tenant-picker">
      <div className="flex items-center gap-2 rounded-sm border border-border-base bg-surface-raised px-3 py-2">
        <Search size={14} className="text-content-muted" />
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          placeholder={placeholder}
          className="flex-1 bg-transparent text-body-sm text-content-base outline-none placeholder:text-content-subtle"
          data-testid="tenant-picker-input"
        />
      </div>
      {open && (
        <div className="absolute left-0 right-0 z-10 mt-1 max-h-80 overflow-y-auto rounded-sm border border-border-subtle bg-surface-raised shadow-level-2">
          {isLoading && (
            <div className="px-3 py-2 text-caption text-content-muted">
              Searching…
            </div>
          )}
          {!isLoading && results.length === 0 && (
            <div className="px-3 py-2 text-caption text-content-muted">
              No tenants match.
            </div>
          )}
          {!isLoading &&
            results.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => {
                  onSelect(t)
                  setOpen(false)
                  setQuery("")
                }}
                className="flex w-full items-start gap-2 px-3 py-2 text-left hover:bg-accent-subtle/40"
                data-testid={`tenant-picker-result-${t.slug}`}
              >
                <div className="flex flex-col gap-0.5">
                  <span className="text-body-sm font-medium text-content-strong">
                    {t.name}
                  </span>
                  <span className="text-caption text-content-muted">
                    {t.vertical ?? "no-vertical"} · {t.slug}
                  </span>
                </div>
              </button>
            ))}
        </div>
      )}
    </div>
  )
}
