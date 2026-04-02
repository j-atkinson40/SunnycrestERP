// library.tsx — Legacy Studio library page
// Route: /legacy/library

import { useState, useEffect, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Loader2, Plus, Search, MoreHorizontal, Download, Mail, Eye, Pencil, FileText, ExternalLink } from "lucide-react"

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
  tif_url: string | null
  family_approved: boolean
  version_count: number
  order_id: string | null
  order_number: string | null
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
  const [mobileSheet, setMobileSheet] = useState<string | null>(null)
  const [imgErrors, setImgErrors] = useState<Set<string>>(new Set())

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

  function fmtDate(dateStr: string | null): string {
    if (!dateStr) return ""
    return new Date(dateStr).toLocaleDateString("en-US", { month: "short", day: "numeric" })
  }

  async function handleConvertToOrder(itemId: string, e: React.MouseEvent) {
    e.stopPropagation()
    try {
      const res = await apiClient.post(`/legacy-studio/${itemId}/convert-to-order`, {})
      toast.success(res.data.action === "created" ? "Draft order created" : "Linked to order")
      navigate(`/ar/orders/${res.data.order_id}`)
    } catch {
      toast.error("Failed to create order")
    }
  }

  async function handleSendToPrint(itemId: string, e: React.MouseEvent) {
    e.stopPropagation()
    try {
      await apiClient.post(`/legacy-studio/${itemId}/mark-printed`, {})
      toast.success("Sent to print shop")
      fetchLibrary()
    } catch {
      toast.error("Failed")
    }
  }

  function getQuickActions(item: LegacyProofSummary): { label: string; icon: React.ReactNode; action: (e: React.MouseEvent) => void }[] {
    const actions: { label: string; icon: React.ReactNode; action: (e: React.MouseEvent) => void }[] = []

    if (item.status === "draft") {
      actions.push({
        label: "Open in Compositor",
        icon: <Pencil className="h-3.5 w-3.5" />,
        action: (e) => { e.stopPropagation(); navigate(`/legacy/generator?legacyId=${item.id}`) },
      })
      if (!item.order_id) {
        actions.push({
          label: "Create order",
          icon: <FileText className="h-3.5 w-3.5" />,
          action: (e) => handleConvertToOrder(item.id, e),
        })
      }
    } else if (item.status === "proof_generated") {
      actions.push({
        label: "Review proof",
        icon: <Eye className="h-3.5 w-3.5" />,
        action: (e) => { e.stopPropagation(); navigate(`/legacy/library/${item.id}`) },
      })
      if (!item.order_id) {
        actions.push({
          label: "Create order",
          icon: <FileText className="h-3.5 w-3.5" />,
          action: (e) => handleConvertToOrder(item.id, e),
        })
      }
    } else if (item.status === "approved") {
      actions.push({
        label: "View proof",
        icon: <Eye className="h-3.5 w-3.5" />,
        action: (e) => { e.stopPropagation(); navigate(`/legacy/library/${item.id}`) },
      })
      actions.push({
        label: "Send to print shop",
        icon: <Mail className="h-3.5 w-3.5" />,
        action: (e) => handleSendToPrint(item.id, e),
      })
      if (item.tif_url) {
        actions.push({
          label: "Download TIF",
          icon: <Download className="h-3.5 w-3.5" />,
          action: (e) => { e.stopPropagation(); window.open(item.tif_url!, "_blank") },
        })
      }
    } else if (item.status === "printed" || item.status === "sent_to_print") {
      actions.push({
        label: "View proof",
        icon: <Eye className="h-3.5 w-3.5" />,
        action: (e) => { e.stopPropagation(); navigate(`/legacy/library/${item.id}`) },
      })
      if (item.tif_url) {
        actions.push({
          label: "Download TIF",
          icon: <Download className="h-3.5 w-3.5" />,
          action: (e) => { e.stopPropagation(); window.open(item.tif_url!, "_blank") },
        })
      }
    }

    return actions
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
            const actions = getQuickActions(item)
            const hasProofImage = item.proof_url && !imgErrors.has(item.id)

            return (
              <div
                key={item.id}
                className="group bg-white rounded-lg border border-gray-200 overflow-hidden hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => navigate(`/legacy/library/${item.id}`)}
              >
                {/* Image area with hover overlay */}
                <div className="relative aspect-[16/4.5] bg-gray-100 overflow-hidden">
                  {hasProofImage ? (
                    <img
                      src={item.proof_url!}
                      alt=""
                      className="w-full h-full object-cover"
                      onError={() => setImgErrors((prev) => new Set(prev).add(item.id))}
                    />
                  ) : (
                    <div className="w-full h-full bg-gray-50 flex items-center justify-center">
                      <span className="text-xs text-gray-400">No proof yet</span>
                    </div>
                  )}

                  {/* Desktop: hover overlay with quick actions */}
                  {actions.length > 0 && (
                    <div className="absolute inset-0 bg-black/45 opacity-0 group-hover:opacity-100 transition-opacity duration-150 hidden sm:flex flex-col items-center justify-center gap-1.5 px-6">
                      {actions.map((a, i) => (
                        <button
                          key={i}
                          onClick={a.action}
                          className="w-full flex items-center justify-center gap-1.5 bg-white text-gray-800 rounded-md py-1.5 px-3.5 text-[13px] font-medium hover:bg-blue-50 transition-colors"
                        >
                          {a.icon} {a.label}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Mobile: ··· button (always visible) */}
                  {actions.length > 0 && (
                    <button
                      className="absolute bottom-1.5 right-1.5 sm:hidden bg-white/90 rounded-full p-1.5 shadow-sm"
                      onClick={(e) => { e.stopPropagation(); setMobileSheet(mobileSheet === item.id ? null : item.id) }}
                    >
                      <MoreHorizontal className="h-4 w-4 text-gray-600" />
                    </button>
                  )}
                </div>

                {/* Mobile bottom sheet */}
                {mobileSheet === item.id && (
                  <div className="sm:hidden border-t border-gray-100 bg-gray-50 p-2 space-y-1">
                    {actions.map((a, i) => (
                      <button
                        key={i}
                        onClick={a.action}
                        className="w-full flex items-center gap-2 bg-white rounded-md py-2 px-3 text-sm text-gray-700 hover:bg-blue-50"
                      >
                        {a.icon} {a.label}
                      </button>
                    ))}
                  </div>
                )}

                {/* Card body */}
                <div className="p-3 space-y-1">
                  {/* Badges row */}
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <Badge className={`text-[10px] ${sb.className}`}>{sb.label}</Badge>
                    {item.family_approved && (
                      <span className="text-[10px] text-green-600 font-medium">Family approved</span>
                    )}
                    {item.order_id && (
                      <Badge
                        variant="outline"
                        className="text-[10px] cursor-pointer hover:bg-blue-50 text-blue-600 border-blue-200"
                        onClick={(e) => { e.stopPropagation(); navigate(`/ar/orders/${item.order_id}`) }}
                      >
                        <ExternalLink className="h-2.5 w-2.5 mr-0.5" />
                        {item.order_number ? `Order #${item.order_number}` : "Order linked"}
                      </Badge>
                    )}
                  </div>

                  {/* Name */}
                  <p className="font-semibold text-[15px] text-gray-900 leading-tight">
                    {item.inscription_name || item.deceased_name || "Untitled"}
                  </p>

                  {/* Print name */}
                  {item.print_name && (
                    <p className="text-[13px] text-gray-500">{item.print_name}</p>
                  )}

                  {/* Funeral home */}
                  {item.customer_name && (
                    <p className="text-xs text-gray-500">{item.customer_name}</p>
                  )}

                  {/* Date + time ago */}
                  <p className="text-[11px] text-gray-400">
                    {item.service_date && <>{fmtDate(item.service_date)} · </>}
                    {timeAgo(item.created_at)}
                  </p>
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
