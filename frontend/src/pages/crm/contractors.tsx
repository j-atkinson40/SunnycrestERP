// contractors.tsx — CRM contractors list page
// Route: /crm/contractors
// Only shown in nav when a contractor extension is enabled (wastewater, redi_rock, general_precast)

import { useState, useEffect, useCallback } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Loader2, Search } from "lucide-react"
import { useExtensions } from "@/contexts/extension-context"

interface ContractorSummary {
  id: string
  name: string
  city: string | null
  state: string | null
  customer_type: string | null
  contractor_type: string | null
  is_customer: boolean
  is_vendor: boolean
  linked_customer_id: string | null
  last_activity_date: string | null
  created_at: string | null
}

type ContractorTab = "all" | "wastewater" | "redi_rock" | "general"

export default function ContractorsPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { isExtensionEnabled } = useExtensions()

  const hasWastewater = isExtensionEnabled("wastewater")
  const hasRediRock = isExtensionEnabled("redi_rock")
  const hasGeneral = isExtensionEnabled("general_precast")

  // Determine default tab
  const urlTab = params.get("type") as ContractorTab | null
  const defaultTab: ContractorTab = urlTab
    || (hasWastewater ? "wastewater" : hasRediRock ? "redi_rock" : hasGeneral ? "general" : "all")

  const [tab, setTab] = useState<ContractorTab>(defaultTab)
  const [items, setItems] = useState<ContractorSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)

  const tabs: Array<{ key: ContractorTab; label: string; show: boolean }> = [
    { key: "wastewater", label: "Wastewater", show: hasWastewater },
    { key: "redi_rock", label: "Redi-Rock", show: hasRediRock },
    { key: "general", label: "General", show: hasGeneral },
    { key: "all", label: "All contractors", show: (hasWastewater && hasRediRock) || (hasWastewater && hasGeneral) || (hasRediRock && hasGeneral) },
  ]
  const visibleTabs = tabs.filter((t) => t.show)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const p = new URLSearchParams()
      p.set("role", "customer")
      p.set("crm_filter", "false") // Get all contractors, we filter client-side by tab
      if (search) p.set("q", search)
      p.set("page", String(page))
      p.set("per_page", "20")

      const res = await apiClient.get(`/companies?${p}`)
      const allItems: ContractorSummary[] = (res.data.items || []).filter(
        (i: ContractorSummary) => i.customer_type === "contractor"
      )

      // Filter by tab
      let filtered = allItems
      if (tab === "wastewater") {
        filtered = allItems.filter((i) => i.contractor_type === "wastewater_only" || i.contractor_type === "full_service")
      } else if (tab === "redi_rock") {
        filtered = allItems.filter((i) => i.contractor_type === "redi_rock_only" || i.contractor_type === "full_service")
      } else if (tab === "general") {
        filtered = allItems.filter((i) => i.contractor_type === "general" || i.contractor_type === "occasional")
      }

      setItems(filtered)
      setTotal(res.data.total || 0)
    } catch {
      toast.error("Could not load contractors")
    } finally {
      setLoading(false)
    }
  }, [search, page, tab])

  useEffect(() => { fetchData() }, [fetchData])

  function timeAgo(dateStr: string | null): string {
    if (!dateStr) return "\u2014"
    const diff = Date.now() - new Date(dateStr).getTime()
    const days = Math.floor(diff / 86400000)
    if (days === 0) return "Today"
    if (days === 1) return "Yesterday"
    if (days < 30) return `${days}d ago`
    return `${Math.floor(days / 30)}mo ago`
  }

  const TYPE_BADGE: Record<string, string> = {
    wastewater_only: "Wastewater",
    redi_rock_only: "Redi-Rock",
    full_service: "Full service",
    general: "General",
    occasional: "Occasional",
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Contractors</h1>
        <p className="text-sm text-gray-500 mt-1">Manage contractor relationships for enabled product lines</p>
      </div>

      {/* Tabs */}
      {visibleTabs.length > 1 && (
        <div className="flex gap-1.5">
          {visibleTabs.map((t) => (
            <button
              key={t.key}
              onClick={() => { setTab(t.key); setPage(1) }}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                tab === t.key
                  ? "bg-gray-900 text-white border-gray-900"
                  : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <Input
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1) }}
          placeholder="Search contractors..."
          className="pl-9"
        />
      </div>

      {/* Results */}
      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-gray-500">No contractors found</p>
        </div>
      ) : (
        <div className="rounded-md border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3 hidden md:table-cell">Location</th>
                <th className="px-4 py-3 hidden lg:table-cell">Last Activity</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map((item) => (
                <tr
                  key={item.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => navigate(`/crm/companies/${item.id}`)}
                >
                  <td className="px-4 py-3 font-medium text-gray-900">{item.name}</td>
                  <td className="px-4 py-3">
                    {item.contractor_type && (
                      <Badge variant="secondary" className="text-xs">
                        {TYPE_BADGE[item.contractor_type] || item.contractor_type}
                      </Badge>
                    )}
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell text-gray-500">
                    {item.city && item.state ? `${item.city}, ${item.state}` : item.city || item.state || "\u2014"}
                  </td>
                  <td className="px-4 py-3 hidden lg:table-cell text-gray-400 text-xs">
                    {timeAgo(item.last_activity_date || item.created_at)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button variant="outline" size="sm" onClick={(e) => { e.stopPropagation(); navigate(`/crm/companies/${item.id}`) }}>
                      View
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {total > 20 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-500">
            Page {page}
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
            <Button variant="outline" size="sm" disabled={items.length < 20} onClick={() => setPage(page + 1)}>Next</Button>
          </div>
        </div>
      )}
    </div>
  )
}
