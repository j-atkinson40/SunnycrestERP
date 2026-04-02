// library.tsx — Legacy Studio library page
// Route: /legacy/library

import { useState, useEffect, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Loader2, Plus, Search, MoreHorizontal } from "lucide-react"

interface LegacyProofSummary {
  id: string
  source: string
  legacy_type: string
  print_name: string | null
  inscription_name: string | null
  inscription_dates: string | null
  customer_name: string | null
  deceased_name: string | null
  service_date: string | null
  status: string
  proof_url: string | null
  family_approved: boolean
  version_count: number
  order_id: string | null
  created_at: string | null
}

const STATUS_BADGES: Record<string, { label: string; className: string }> = {
  draft: { label: "Draft", className: "bg-gray-100 text-gray-700" },
  proof_generated: { label: "Proof generated", className: "bg-blue-100 text-blue-700" },
  proof_sent: { label: "Proof sent", className: "bg-purple-100 text-purple-700" },
  approved: { label: "Approved", className: "bg-green-100 text-green-700" },
  sent_to_print: { label: "Sent to print", className: "bg-teal-100 text-teal-700" },
  printed: { label: "Printed", className: "bg-emerald-100 text-emerald-800" },
  cancelled: { label: "Cancelled", className: "bg-red-100 text-red-700" },
}

const FILTER_OPTIONS = [
  { value: "", label: "All" },
  { value: "draft", label: "Draft" },
  { value: "proof_generated", label: "Generated" },
  { value: "approved", label: "Approved" },
  { value: "printed", label: "Printed" },
]

export default function LegacyLibraryPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState<LegacyProofSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)

  const fetchLibrary = useCallback(async () => {
    try {
      const params = new URLSearchParams()
      if (search) params.set("q", search)
      if (statusFilter) params.set("status", statusFilter)
      params.set("page", String(page))
      params.set("per_page", "20")

      const res = await apiClient.get(`/legacy-studio/library?${params}`)
      setItems(res.data.items || [])
      setTotal(res.data.total || 0)
    } catch {
      toast.error("Could not load library")
    } finally {
      setLoading(false)
    }
  }, [search, statusFilter, page])

  useEffect(() => { fetchLibrary() }, [fetchLibrary])

  // Debounced search
  useEffect(() => {
    const t = setTimeout(() => { setPage(1); fetchLibrary() }, 300)
    return () => clearTimeout(t)
  }, [search])

  function timeAgo(dateStr: string | null): string {
    if (!dateStr) return ""
    const diff = Date.now() - new Date(dateStr).getTime()
    const hrs = Math.floor(diff / 3600000)
    if (hrs < 1) return "just now"
    if (hrs < 24) return `${hrs}h ago`
    return `${Math.floor(hrs / 24)}d ago`
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Legacy Library</h1>
          <p className="text-sm text-gray-500 mt-1">All proofs generated on this account</p>
        </div>
        <Button onClick={() => navigate("/legacy/generator")}>
          <Plus className="h-4 w-4 mr-1" /> New proof
        </Button>
      </div>

      {/* Search + filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, funeral home, or print..."
            className="pl-9"
          />
        </div>
        <div className="flex gap-1.5 flex-wrap">
          {FILTER_OPTIONS.map((f) => (
            <button
              key={f.value}
              onClick={() => { setStatusFilter(f.value); setPage(1) }}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                statusFilter === f.value
                  ? "bg-gray-900 text-white border-gray-900"
                  : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Results grid */}
      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-gray-500 mb-4">No legacies found</p>
          <Button onClick={() => navigate("/legacy/generator")}>
            <Plus className="h-4 w-4 mr-1" /> New proof
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => {
            const sb = STATUS_BADGES[item.status] || STATUS_BADGES.draft
            return (
              <div
                key={item.id}
                className="bg-white rounded-lg border border-gray-200 overflow-hidden hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => navigate(`/legacy/library/${item.id}`)}
              >
                {/* Proof thumbnail */}
                {item.proof_url ? (
                  <div className="aspect-[16/4.5] bg-gray-100 overflow-hidden">
                    <img src={item.proof_url} alt="" className="w-full h-full object-cover" />
                  </div>
                ) : (
                  <div className="aspect-[16/4.5] bg-gray-50 flex items-center justify-center">
                    <span className="text-xs text-gray-400">No proof yet</span>
                  </div>
                )}

                {/* Card body */}
                <div className="p-3 space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Badge className={`text-[10px] ${sb.className}`}>{sb.label}</Badge>
                    {item.family_approved && (
                      <span className="text-[10px] text-green-600 font-medium">Family approved</span>
                    )}
                  </div>
                  <p className="font-medium text-sm text-gray-900">{item.inscription_name || "Untitled"}</p>
                  {item.print_name && (
                    <p className="text-xs text-gray-500">{item.print_name}</p>
                  )}
                  {item.customer_name && (
                    <p className="text-xs text-gray-500">{item.customer_name}</p>
                  )}
                  {item.service_date && (
                    <p className="text-xs text-gray-400">Service: {item.service_date}</p>
                  )}
                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[11px] text-gray-400">
                      {item.version_count > 0 ? `v${item.version_count + 1} · ` : ""}
                      {timeAgo(item.created_at)}
                    </span>
                    {item.order_id && (
                      <Badge variant="outline" className="text-[10px]">Order linked</Badge>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Pagination */}
      {total > 20 && (
        <div className="flex justify-center gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Previous
          </Button>
          <span className="text-sm text-gray-500 self-center">
            Page {page} of {Math.ceil(total / 20)}
          </span>
          <Button variant="outline" size="sm" disabled={page >= Math.ceil(total / 20)} onClick={() => setPage(page + 1)}>
            Next
          </Button>
        </div>
      )}
    </div>
  )
}
