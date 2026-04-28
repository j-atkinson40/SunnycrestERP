// WidgetPicker — slide-in panel showing available widgets not on the dashboard.
// Phase II Batch 1a — migrated from hardcoded Tailwind greys/blues to
// DESIGN_LANGUAGE tokens. Matches DL §6 slide-over pattern + uses refreshed
// Input primitive (Session 2) + Badge primitive (Session 3 via status tokens).
//
// Widget Library Phase W-2 — added optional `destination` prop. When
// `destination="sidebar"`, the picker filters to widgets that support
// the `spaces_pin` surface and changes the primary CTA label to
// "Pin to sidebar" (the parent supplies the actual onAdd handler that
// pins to the active space). Default destination remains "dashboard"
// for back-compat with all existing callers (Operations Board, Vault
// Overview, etc.).

import { useState, useMemo } from "react"
import { X, Search, Plus, Lock } from "lucide-react"
import { Input } from "@/components/ui/input"
import type { WidgetDefinition } from "./types"

interface WidgetPickerProps {
  available: WidgetDefinition[]
  currentWidgetIds: string[]
  onAdd: (widgetId: string) => void
  onClose: () => void
  /** Widget Library Phase W-2 — destination discriminator. "dashboard"
   *  (default) preserves the existing add-to-grid flow. "sidebar"
   *  filters to widgets that declare `spaces_pin` in
   *  supported_surfaces and labels the primary CTA "Pin to sidebar"
   *  so the user understands the destination. The actual pin-to-
   *  active-space mutation is the parent's responsibility (passed
   *  via onAdd). */
  destination?: "dashboard" | "sidebar"
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
  destination = "dashboard",
}: WidgetPickerProps) {
  const [search, setSearch] = useState("")
  const [category, setCategory] = useState("all")

  const currentSet = useMemo(() => new Set(currentWidgetIds), [currentWidgetIds])

  const filtered = useMemo(() => {
    return available.filter((w) => {
      // Exclude already added
      if (currentSet.has(w.widget_id)) return false
      // Widget Library Phase W-2 — sidebar destination filters to
      // widgets that support the spaces_pin surface. Per DESIGN_LANGUAGE
      // §12.5 composition rules, only widgets declaring spaces_pin are
      // valid sidebar pins. Widgets without it stay in the picker for
      // dashboard destination but are hidden in sidebar destination.
      if (
        destination === "sidebar" &&
        !(w.supported_surfaces ?? []).includes("spaces_pin")
      )
        return false
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
  }, [available, currentSet, search, category, destination])

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-80 bg-surface-raised shadow-level-3 border-l border-border-subtle flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border-subtle px-4 py-3">
        <h2 className="text-body-sm font-semibold text-content-strong">
          {destination === "sidebar" ? "Pin widget to sidebar" : "Add widgets"}
        </h2>
        <button
          onClick={onClose}
          className="text-content-subtle hover:text-content-muted transition-colors duration-quick ease-settle focus-ring-accent rounded-sm"
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
            className={`shrink-0 rounded-full px-2.5 py-1 text-caption font-medium transition-colors duration-quick ease-settle focus-ring-accent ${
              category === cat.key
                ? "bg-accent text-content-on-accent"
                : "bg-accent-subtle text-content-muted hover:bg-accent-muted"
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
            {search
              ? "No matching widgets"
              : destination === "sidebar"
              ? "No widgets available to pin to sidebar"
              : "All widgets added"}
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
                  <span className="text-micro font-mono text-content-subtle">
                    {w.default_size}
                  </span>
                  {/* Widget Library Phase W-1 — Section 12.2 variant
                      indicator. Phase W-1 minimum: shows the count
                      of declared variants + the default variant id.
                      Phase W-3 expands this into a rich preview /
                      variant picker per Section 12.5 catalog UI. */}
                  {w.variants && w.variants.length > 1 && (
                    <span className="text-micro text-content-subtle">
                      {w.variants.length} variants
                    </span>
                  )}
                  {w.required_extension && !w.is_available && (
                    <span className="text-micro text-status-warning">
                      Requires {w.required_extension}
                    </span>
                  )}
                  {!w.is_available && w.unavailable_reason === "vertical_required" && (
                    <span className="text-micro text-status-warning">
                      Vertical: {(w.required_vertical ?? []).join(", ")}
                    </span>
                  )}
                </div>
              </div>

              {w.is_available ? (
                <button
                  onClick={() => onAdd(w.widget_id)}
                  className="shrink-0 flex items-center gap-1 rounded-sm bg-accent px-2.5 py-1.5 text-caption font-medium text-content-on-accent hover:bg-accent-hover transition-colors duration-quick ease-settle focus-ring-accent"
                >
                  <Plus className="h-3 w-3" />
                  {destination === "sidebar" ? "Pin" : "Add"}
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
