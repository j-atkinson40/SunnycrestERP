// NaturalLanguageFilter.tsx — AI-powered text-based filtering for list views

import { useState } from "react"
import apiClient from "@/lib/api-client"
import { Sparkles, X } from "lucide-react"

interface FilterSet {
  date_from?: string | null
  date_to?: string | null
  status?: string | null
  customer_type?: string | null
  amount_min?: number | null
  amount_max?: number | null
  search_text?: string | null
  [key: string]: unknown
}

interface NaturalLanguageFilterProps {
  entityType: "orders" | "companies" | "invoices" | "legacies" | "activities"
  onFiltersApplied: (filters: FilterSet) => void
  placeholder?: string
}

export default function NaturalLanguageFilter({ entityType, onFiltersApplied, placeholder }: NaturalLanguageFilterProps) {
  const [query, setQuery] = useState("")
  const [chips, setChips] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [activeFilters, setActiveFilters] = useState<FilterSet>({})

  async function handleSubmit() {
    if (!query.trim()) return
    setLoading(true)
    try {
      const res = await apiClient.post("/ai/parse-filters", { query, entity_type: entityType })
      const data = res.data
      if (data.filters) {
        setActiveFilters(data.filters)
        setChips(data.chips || [])
        onFiltersApplied(data.filters)
        setQuery("")
      }
    } catch {
      // If AI feature disabled, silently ignore
    } finally {
      setLoading(false)
    }
  }

  function removeChip(idx: number) {
    const newChips = chips.filter((_, i) => i !== idx)
    setChips(newChips)
    if (newChips.length === 0) {
      setActiveFilters({})
      onFiltersApplied({})
    }
  }

  function clearAll() {
    setChips([])
    setActiveFilters({})
    onFiltersApplied({})
  }

  return (
    <div className="space-y-1.5">
      <div className="relative">
        <Sparkles className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-purple-400" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleSubmit() }}
          placeholder={placeholder || `Filter: "last month, funeral homes, over $2000"...`}
          className="w-full pl-9 pr-3 py-1.5 text-sm rounded-md border border-purple-200 bg-purple-50/30 placeholder:text-gray-400 focus:outline-none focus:ring-1 focus:ring-purple-300"
        />
        {loading && <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-purple-400">Parsing...</span>}
      </div>

      {chips.length > 0 && (
        <div className="flex flex-wrap gap-1.5 items-center">
          {chips.map((chip, i) => (
            <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full text-xs">
              {chip}
              <button onClick={() => removeChip(i)} className="hover:text-purple-900"><X className="h-3 w-3" /></button>
            </span>
          ))}
          <button onClick={clearAll} className="text-[10px] text-gray-400 hover:text-gray-600">Clear all</button>
        </div>
      )}
    </div>
  )
}
