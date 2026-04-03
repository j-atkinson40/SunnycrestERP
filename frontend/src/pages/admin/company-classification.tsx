// company-classification.tsx — AI company classification review page
// Route: /admin/company-classification

import { useState, useEffect, useCallback } from "react"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { Loader2, Check } from "lucide-react"

interface ReviewItem {
  id: string
  name: string
  city: string | null
  state: string | null
  customer_type: string | null
  contractor_type: string | null
  classification_confidence: number | null
  classification_reasons: string[]
  is_active_customer: boolean
  first_order_year: number | null
  original_name: string | null
  name_cleanup_actions: string[] | null
}

interface Summary { by_source: Record<string, number>; by_type: Record<string, number>; total: number }

const TYPE_OPTIONS = [
  { value: "funeral_home", label: "Funeral Home" },
  { value: "contractor", label: "Contractor" },
  { value: "cemetery", label: "Cemetery" },
  { value: "crematory", label: "Crematory" },
  { value: "church", label: "Church" },
  { value: "government", label: "Government" },
  { value: "licensee", label: "Licensee" },
  { value: "individual", label: "Individual" },
  { value: "other", label: "Other" },
]

export default function CompanyClassificationPage() {
  const [items, setItems] = useState<ReviewItem[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [tab, setTab] = useState<"review" | "all">("review")

  const loadQueue = useCallback(async () => {
    try {
      const res = await apiClient.get(`/companies/classify/review-queue?page=${page}&per_page=20`)
      setItems(res.data.items || [])
      setTotal(res.data.total || 0)
    } catch { /* silent */ }
    finally { setLoading(false) }
  }, [page])

  const loadSummary = useCallback(async () => {
    try {
      const res = await apiClient.get("/companies/classify/summary")
      setSummary(res.data)
    } catch { /* silent */ }
  }, [])

  useEffect(() => { loadQueue(); loadSummary() }, [loadQueue, loadSummary])

  async function handleRunBulk() {
    setRunning(true)
    toast.info("Running AI classification... this may take a few minutes.")
    try {
      const res = await apiClient.get("/companies/classify/run-bulk")
      const d = res.data
      toast.success(`Classified ${d.total_processed} companies. Auto: ${d.auto_classified}, Review: ${d.needs_review}, Unknown: ${d.unknown}`)
      loadQueue()
      loadSummary()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail || "Classification failed")
    } finally {
      setRunning(false)
    }
  }

  async function handleRevertName(id: string) {
    try {
      await apiClient.post(`/companies/${id}/revert-name`)
      toast.success("Name reverted to original")
      loadQueue()
    } catch { toast.error("Failed to revert") }
  }

  async function handleConfirm(id: string) {
    try {
      await apiClient.post(`/companies/${id}/classify/confirm`, {})
      setItems((prev) => prev.filter((i) => i.id !== id))
      setTotal((prev) => prev - 1)
      loadSummary()
    } catch { toast.error("Failed") }
  }

  async function handleChange(id: string, customerType: string) {
    try {
      await apiClient.post(`/companies/${id}/classify/confirm`, { customer_type: customerType })
      setItems((prev) => prev.filter((i) => i.id !== id))
      setTotal((prev) => prev - 1)
      loadSummary()
    } catch { toast.error("Failed") }
  }

  async function handleApproveAll() {
    const ids = items.map((i) => i.id)
    try {
      await apiClient.post("/companies/classify/confirm-bulk", { company_ids: ids })
      toast.success(`Approved ${ids.length} companies`)
      loadQueue()
      loadSummary()
    } catch { toast.error("Failed") }
  }

  function confColor(conf: number | null) {
    if (!conf) return "text-gray-400"
    if (conf >= 0.85) return "text-green-600"
    if (conf >= 0.60) return "text-amber-600"
    return "text-red-600"
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Company Classification</h1>
          <p className="text-sm text-gray-500 mt-1">AI-powered customer type classification</p>
        </div>
        <Button onClick={handleRunBulk} disabled={running}>
          {running ? <><Loader2 className="h-4 w-4 mr-1 animate-spin" /> Running...</> : "Run AI Classification"}
        </Button>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-4 gap-3">
          <Card className="p-3 text-center">
            <div className="text-2xl font-bold text-green-600">{summary.by_source.auto_high || 0}</div>
            <div className="text-xs text-gray-500">Auto-classified</div>
          </Card>
          <Card className="p-3 text-center">
            <div className="text-2xl font-bold text-amber-600">{summary.by_source.pending_review || 0}</div>
            <div className="text-xs text-gray-500">Needs review</div>
          </Card>
          <Card className="p-3 text-center">
            <div className="text-2xl font-bold text-gray-400">{summary.by_source.unclassified || 0}</div>
            <div className="text-xs text-gray-500">Unclassified</div>
          </Card>
          <Card className="p-3 text-center">
            <div className="text-2xl font-bold text-blue-600">{summary.by_source.manual || 0}</div>
            <div className="text-xs text-gray-500">Manual</div>
          </Card>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
        <button onClick={() => setTab("review")} className={`px-4 py-2 text-sm font-medium border-b-2 ${tab === "review" ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500"}`}>
          Needs Review ({total})
        </button>
        <button onClick={() => setTab("all")} className={`px-4 py-2 text-sm font-medium border-b-2 ${tab === "all" ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500"}`}>
          All Companies
        </button>
      </div>

      {tab === "review" && (
        <>
          {loading ? (
            <div className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-gray-400" /></div>
          ) : items.length === 0 ? (
            <div className="text-center py-16">
              <div className="inline-flex items-center gap-2 bg-green-50 text-green-700 px-4 py-2 rounded-full text-sm font-medium">
                <Check className="h-4 w-4" /> All classifications reviewed
              </div>
            </div>
          ) : (
            <>
              <div className="flex justify-end">
                <Button variant="outline" size="sm" onClick={handleApproveAll}>
                  <Check className="h-3.5 w-3.5 mr-1" /> Approve all on page
                </Button>
              </div>
              <div className="rounded-md border overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                    <tr>
                      <th className="px-4 py-2 text-left">Company</th>
                      <th className="px-4 py-2 text-left">Suggested Type</th>
                      <th className="px-4 py-2 text-left">Confidence</th>
                      <th className="px-4 py-2 text-left">Signals</th>
                      <th className="px-4 py-2 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {items.map((item) => (
                      <tr key={item.id}>
                        <td className="px-4 py-3">
                          <div className="font-medium">{item.name}</div>
                          {item.city && <div className="text-xs text-gray-400">{item.city}{item.state ? `, ${item.state}` : ""}</div>}
                          {item.original_name && item.name_cleanup_actions && (
                            <div className="mt-1 text-[11px] text-blue-600 bg-blue-50 rounded px-2 py-1">
                              <span className="font-medium">Cleaned:</span> {item.name_cleanup_actions.join(" · ")}
                              <span className="text-gray-400 ml-1">(was: {item.original_name})</span>
                              <button onClick={() => handleRevertName(item.id)} className="ml-1.5 underline hover:text-blue-800">Revert</button>
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <Badge>{item.customer_type || "Unknown"}</Badge>
                          {item.contractor_type && <Badge variant="outline" className="ml-1 text-[10px]">{item.contractor_type}</Badge>}
                        </td>
                        <td className={`px-4 py-3 font-medium ${confColor(item.classification_confidence)}`}>
                          {item.classification_confidence ? `${Math.round(item.classification_confidence * 100)}%` : "—"}
                        </td>
                        <td className="px-4 py-3">
                          <div className="space-y-0.5">
                            {(item.classification_reasons || []).slice(0, 2).map((r, i) => (
                              <div key={i} className="text-xs text-gray-500">{r}</div>
                            ))}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex gap-1 justify-end">
                            <Button size="sm" variant="outline" onClick={() => handleConfirm(item.id)}>
                              <Check className="h-3 w-3 mr-0.5" /> Correct
                            </Button>
                            <select
                              className="text-xs border rounded px-2 py-1"
                              defaultValue=""
                              onChange={(e) => { if (e.target.value) handleChange(item.id, e.target.value) }}
                            >
                              <option value="" disabled>Change...</option>
                              {TYPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                            </select>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {total > 20 && (
                <div className="flex justify-center gap-2">
                  <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
                  <Button variant="outline" size="sm" disabled={page >= Math.ceil(total / 20)} onClick={() => setPage(page + 1)}>Next</Button>
                </div>
              )}
            </>
          )}
        </>
      )}

      {tab === "all" && summary && (
        <Card className="p-4">
          <h3 className="font-semibold mb-3">Classification breakdown</h3>
          <div className="space-y-1">
            {Object.entries(summary.by_type).sort((a, b) => b[1] - a[1]).map(([type, count]) => (
              <div key={type} className="flex items-center justify-between text-sm">
                <span className="capitalize">{type.replace("_", " ")}</span>
                <span className="font-medium">{count}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
