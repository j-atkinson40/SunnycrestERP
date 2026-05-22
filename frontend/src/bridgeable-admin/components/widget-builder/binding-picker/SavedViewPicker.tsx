/**
 * SavedViewPicker — WB-6 filtered combobox for saved-view selection.
 *
 * Renders the operator-as-platform-builder selection surface: a button
 * trigger displaying the current selection (or "Pick a saved view"),
 * + a Popover containing search input + filtered list.
 *
 * Shape-compatibility filter (Area 5 Lock 6a): when invoked from a
 * `requiresArrayShape=true` caller (repeater_atom binding), only saved
 * views whose `presentation.mode` produces rows surface
 * (list/table/kanban/cards/calendar). Chart/stat views are filtered out.
 * When `requiresArrayShape=false`, all views surface.
 *
 * Uncontrolled-with-sync (FF-6 pattern): search input holds local
 * state; selection commits propagate via `onChange`.
 */
import { useMemo, useState } from "react"

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/lib/utils"
import type { SavedView } from "@/types/saved-views"


const ARRAY_SHAPED_MODES = new Set([
  "list",
  "table",
  "kanban",
  "cards",
  "calendar",
])


export interface SavedViewPickerProps {
  savedViews: SavedView[]
  value: string | null
  onChange: (savedViewId: string | null) => void
  requiresArrayShape?: boolean
  disabled?: boolean
  testId?: string
}


export function SavedViewPicker({
  savedViews,
  value,
  onChange,
  requiresArrayShape = false,
  disabled = false,
  testId,
}: SavedViewPickerProps) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState("")

  const filteredViews = useMemo(() => {
    let pool = savedViews
    if (requiresArrayShape) {
      pool = pool.filter((v) =>
        ARRAY_SHAPED_MODES.has(v.config.presentation.mode),
      )
    }
    const q = search.trim().toLowerCase()
    if (!q) return pool
    return pool.filter((v) =>
      v.title.toLowerCase().includes(q) ||
      v.config.query.entity_type.toLowerCase().includes(q),
    )
  }, [savedViews, requiresArrayShape, search])

  const selected = value ? savedViews.find((v) => v.id === value) : null

  const triggerLabel = selected
    ? selected.title
    : "Pick a saved view"

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        data-testid={testId}
        disabled={disabled}
        className={cn(
          "w-full rounded-md border border-border-base bg-surface-raised px-2 py-1.5 text-left text-body-sm text-content-base hover:border-border-strong focus:outline-none focus-ring-accent disabled:cursor-not-allowed disabled:opacity-50",
          !selected && "text-content-subtle italic",
        )}
      >
        {triggerLabel}
        {selected && (
          <span className="ml-2 text-caption text-content-muted">
            {selected.config.query.entity_type}
          </span>
        )}
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-(--anchor-width) min-w-[18rem] max-w-md p-0"
      >
        <div className="border-b border-border-subtle p-2">
          <input
            data-testid={testId ? `${testId}-search` : undefined}
            type="text"
            placeholder="Search saved views…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border border-border-base bg-surface-base px-2 py-1 text-body-sm focus:outline-none focus-ring-accent"
            autoFocus
          />
        </div>
        <div
          data-testid={testId ? `${testId}-results` : undefined}
          className="max-h-72 overflow-y-auto p-1"
        >
          {filteredViews.length === 0 ? (
            <div className="px-2 py-3 text-caption text-content-subtle">
              {savedViews.length === 0
                ? "No saved views in this tenant yet."
                : "No matches. Try a different search."}
            </div>
          ) : (
            <ul className="flex flex-col">
              {filteredViews.map((v) => (
                <li key={v.id}>
                  <button
                    type="button"
                    data-testid={
                      testId ? `${testId}-option-${v.id}` : undefined
                    }
                    onClick={() => {
                      onChange(v.id)
                      setOpen(false)
                      setSearch("")
                    }}
                    className={cn(
                      "flex w-full items-center justify-between rounded-sm px-2 py-1.5 text-left text-body-sm hover:bg-accent-subtle focus:bg-accent-subtle focus:outline-none",
                      value === v.id && "bg-accent-subtle",
                    )}
                  >
                    <span className="flex flex-col">
                      <span className="font-medium text-content-strong">
                        {v.title}
                      </span>
                      <span className="text-caption text-content-muted">
                        {v.config.query.entity_type} ·{" "}
                        {v.config.presentation.mode}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
