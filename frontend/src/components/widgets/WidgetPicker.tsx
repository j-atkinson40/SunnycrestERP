// WidgetPicker — slide-in panel showing available widgets not on the dashboard.
// Phase II Batch 1a — migrated from hardcoded Tailwind greys/blues to
// DESIGN_LANGUAGE tokens. Matches DL §6 slide-over pattern + uses refreshed
// Input primitive (Session 2) + Badge primitive (Session 3 via status tokens).

import { useState, useMemo } from "react"
import { X, Search, Plus, Lock } from "lucide-react"
import { Input } from "@/components/ui/input"
import type { WidgetDefinition } from "./types"

interface WidgetPickerProps {
  available: WidgetDefinition[]
  currentWidgetIds: string[]
  onAdd: (widgetId: string) => void
  onClose: () => void
}

const CATEGORIES = [
  { key: "all", label: "All" },
  { key: "operations", label: "Operations" },
  { key: "production", label: "Production" },
  { key: "financial", label: "Financial" },
  { key: "safety", label: "Safety" },
  { key: "crm", label: "CRM" },
  { key: "intelligence", label: "AI" },
]

export default function WidgetPicker({
  available,
  currentWidgetIds,
  onAdd,
  onClose,
}: WidgetPickerProps) {
  const [search, setSearch] = useState("")
  const [category, setCategory] = useState("all")

  const currentSet = useMemo(() => new Set(currentWidgetIds), [currentWidgetIds])

  const filtered = useMemo(() => {
    return available.filter((w) => {
      // Exclude already added
      if (currentSet.has(w.widget_id)) return false
      // Search filter
      if (
        search &&
        !w.title.toLowerCase().includes(search.toLowerCase()) &&
        !w.description?.toLowerCase().includes(search.toLowerCase())
      )
        return false
      // Category filter
      if (category !== "all" && w.category !== category) return false
      return true
    })
  }, [available, currentSet, search, category])

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-80 bg-surface-raised shadow-level-3 border-l border-border-subtle flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border-subtle px-4 py-3">
        <h2 className="text-body-sm font-semibold text-content-strong">Add widgets</h2>
        <button
          onClick={onClose}
          className="text-content-subtle hover:text-content-muted transition-colors duration-quick ease-settle focus-ring-brass rounded-sm"
          aria-label="Close widget picker"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Search */}
      <div className="px-4 pt-3 pb-2">
        <div className="relative">
          <Search
            className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-content-subtle pointer-events-none"
            aria-hidden="true"
          />
          <Input
            type="text"
            placeholder="Search widgets..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8"
          />
        </div>
      </div>

      {/* Category filters */}
      <div className="flex gap-1 overflow-x-auto px-4 pb-2">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.key}
            onClick={() => setCategory(cat.key)}
            className={`shrink-0 rounded-full px-2.5 py-1 text-caption font-medium transition-colors duration-quick ease-settle focus-ring-brass ${
              category === cat.key
                ? "bg-brass text-content-on-brass"
                : "bg-brass-subtle text-content-muted hover:bg-brass-muted"
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Widget list */}
      <div className="flex-1 overflow-y-auto px-4 py-2 space-y-2">
        {filtered.length === 0 && (
          <p className="text-center text-body-sm text-content-subtle py-8">
            {search ? "No matching widgets" : "All widgets added"}
          </p>
        )}
        {filtered.map((w) => (
          <div
            key={w.widget_id}
            className="rounded-md border border-border-subtle p-3 hover:border-border-base transition-colors duration-quick ease-settle"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-body-sm font-medium text-content-strong truncate">
                    {w.title}
                  </span>
                  {!w.is_available && (
                    <Lock
                      className="h-3 w-3 text-content-subtle shrink-0"
                      aria-label="Locked"
                    />
                  )}
                </div>
                <p className="text-caption text-content-muted mt-0.5 line-clamp-2">
                  {w.description}
                </p>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="text-micro font-plex-mono text-content-subtle">
                    {w.default_size}
                  </span>
                  {w.required_extension && !w.is_available && (
                    <span className="text-micro text-status-warning">
                      Requires {w.required_extension}
                    </span>
                  )}
                </div>
              </div>

              {w.is_available ? (
                <button
                  onClick={() => onAdd(w.widget_id)}
                  className="shrink-0 flex items-center gap-1 rounded-sm bg-brass px-2.5 py-1.5 text-caption font-medium text-content-on-brass hover:bg-brass-hover transition-colors duration-quick ease-settle focus-ring-brass"
                >
                  <Plus className="h-3 w-3" />
                  Add
                </button>
              ) : (
                <span className="shrink-0 text-micro text-content-subtle px-2 py-1">
                  Locked
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
