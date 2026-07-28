/**
 * AddLineCombobox — S-3b add-line entry for the quote edit canvas.
 *
 * The FIRST portaled interactive surface inside a Focus core (per the
 * S-3b dispatch), so it routes through `FocusPopover` — which lifts the
 * popup ABOVE the Focus z-layer and self-asserts `pointer-events: auto`
 * (base-ui's default z-50 would bury it under the Focus backdrop). If a
 * portaled surface can't self-assert this way it's the NAMED STOP; this
 * one can.
 *
 * Behavior: type a product name → best-effort typeahead against the
 * catalog (`products.view`; degrades to free-text on error). Picking a
 * suggestion adds a line with the resolved product id; pressing Enter on
 * free text adds a ref the preview endpoint will resolve — and REFUSE
 * (with candidates) if it's ambiguous. No client-side price guessing.
 */

import { useEffect, useRef, useState } from "react"
import { Plus, Search } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  FocusPopover,
  FocusPopoverContent,
  FocusPopoverTrigger,
} from "@/components/focus/FocusPopover"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import {
  searchQuoteProducts,
  type ProductSuggestion,
} from "@/services/quote-preview-service"

export interface AddLineComboboxProps {
  onAdd: (line: { productRef: string; productId?: string }) => void
}

export function AddLineCombobox({ onAdd }: AddLineComboboxProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [suggestions, setSuggestions] = useState<ProductSuggestion[]>([])
  const debounced = useDebouncedValue(query, 200)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!open) return
    const q = debounced.trim()
    if (q.length < 2) {
      setSuggestions([])
      return
    }
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    searchQuoteProducts(q, ctrl.signal)
      .then((rows) => setSuggestions(rows))
      // Best-effort: on error (incl. permission) fall back to free-text.
      .catch(() => setSuggestions([]))
    return () => ctrl.abort()
  }, [debounced, open])

  function commit(line: { productRef: string; productId?: string }) {
    if (!line.productRef.trim()) return
    onAdd({ productRef: line.productRef.trim(), productId: line.productId })
    setQuery("")
    setSuggestions([])
    setOpen(false)
  }

  return (
    <FocusPopover open={open} onOpenChange={setOpen}>
      <FocusPopoverTrigger
        render={
          <Button variant="outline" size="sm" data-testid="quote-add-line">
            <Plus className="size-3.5" />
            Add line
          </Button>
        }
      />
      <FocusPopoverContent
        align="start"
        className="w-80 p-2"
        data-testid="quote-add-line-popover"
      >
        <div className="flex items-center gap-2 rounded border border-border-subtle bg-surface-sunken px-2">
          <Search className="size-3.5 shrink-0 text-content-muted" />
          <Input
            autoFocus
            value={query}
            placeholder="Search a product, or type + Enter"
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault()
                // Enter on a lone suggestion picks it; else free-text ref.
                if (suggestions.length === 1) {
                  commit({
                    productRef: suggestions[0].name,
                    productId: suggestions[0].id,
                  })
                } else {
                  commit({ productRef: query })
                }
              }
            }}
            className="h-8 border-0 bg-transparent px-0 shadow-none focus-visible:ring-0"
            data-testid="quote-add-line-input"
          />
        </div>

        {suggestions.length > 0 && (
          <ul className="mt-2 max-h-56 overflow-y-auto" role="listbox">
            {suggestions.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={false}
                  onClick={() =>
                    commit({ productRef: s.name, productId: s.id })
                  }
                  className="flex w-full items-center rounded px-2 py-1.5 text-left text-body-sm text-content-base hover:bg-accent-subtle hover:text-content-strong"
                >
                  {s.name}
                </button>
              </li>
            ))}
          </ul>
        )}
      </FocusPopoverContent>
    </FocusPopover>
  )
}
