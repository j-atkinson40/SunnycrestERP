// WidgetPicker — slide-in panel showing available widgets not on the dashboard

import { useState, useMemo } from "react"
import { X, Search, Plus, Lock } from "lucide-react"
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
    <div className="fixed inset-y-0 right-0 z-50 w-80 bg-white shadow-2xl border-l border-gray-200 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h2 className="text-sm font-semibold text-gray-800">Add widgets</h2>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Search */}
      <div className="px-4 pt-3 pb-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-gray-400" />
          <input
            type="text"
            placeholder="Search widgets..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border border-gray-200 py-2 pl-8 pr-3 text-sm focus:border-blue-300 focus:outline-none focus:ring-1 focus:ring-blue-300"
          />
        </div>
      </div>

      {/* Category filters */}
      <div className="flex gap-1 overflow-x-auto px-4 pb-2">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.key}
            onClick={() => setCategory(cat.key)}
            className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
              category === cat.key
                ? "bg-gray-900 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Widget list */}
      <div className="flex-1 overflow-y-auto px-4 py-2 space-y-2">
        {filtered.length === 0 && (
          <p className="text-center text-sm text-gray-400 py-8">
            {search ? "No matching widgets" : "All widgets added"}
          </p>
        )}
        {filtered.map((w) => (
          <div
            key={w.widget_id}
            className="rounded-lg border border-gray-200 p-3 hover:border-gray-300 transition-colors"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-medium text-gray-800 truncate">
                    {w.title}
                  </span>
                  {!w.is_available && (
                    <Lock className="h-3 w-3 text-gray-400 shrink-0" />
                  )}
                </div>
                <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                  {w.description}
                </p>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="text-[10px] font-mono text-gray-400">
                    {w.default_size}
                  </span>
                  {w.required_extension && !w.is_available && (
                    <span className="text-[10px] text-amber-600">
                      Requires {w.required_extension}
                    </span>
                  )}
                </div>
              </div>

              {w.is_available ? (
                <button
                  onClick={() => onAdd(w.widget_id)}
                  className="shrink-0 flex items-center gap-1 rounded-md bg-gray-900 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-gray-700 transition-colors"
                >
                  <Plus className="h-3 w-3" />
                  Add
                </button>
              ) : (
                <span className="shrink-0 text-[10px] text-gray-400 px-2 py-1">
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
