// data-quality.tsx — Unified data quality page
// Route: /admin/data-quality

import { useState, useEffect, useCallback } from "react"
import { Link } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Loader2, Check, X, MapPin, Phone, Globe } from "lucide-react"

interface NameSuggestion {
  id: string
  current_name: string
  suggested_name: string
  confidence: number | null
  suggestion_source: string | null
  suggested_phone: string | null
  suggested_website: string | null
  suggested_address_line1: string | null
  company_id: string
  customer_type: string | null
  city: string | null
  state: string | null
}

export default function DataQualityPage() {
  const [tab, setTab] = useState<"names" | "duplicates">("names")
  const [suggestions, setSuggestions] = useState<NameSuggestion[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [pendingCount, setPendingCount] = useState(0)

  const loadSuggestions = useCallback(async () => {
    try {
      const res = await apiClient.get(`/ai/name-suggestions?status=pending&page=${page}&per_page=20`)
      setSuggestions(res.data.items || [])
      setTotal(res.data.total || 0)
      setPendingCount(res.data.total || 0)
    } catch { setSuggestions([]) }
    finally { setLoading(false) }
  }, [page])

  useEffect(() => { loadSuggestions() }, [loadSuggestions])

  async function handleApply(id: string) {
    try {
      await apiClient.post(`/ai/name-suggestions/${id}/apply`, { apply_address: true, apply_phone: true, apply_website: true })
      toast.success("Name updated")
      setSuggestions((prev) => prev.filter((s) => s.id !== id))
      setPendingCount((n) => n - 1)
    } catch { toast.error("Failed") }
  }

  async function handleReject(id: string) {
    try {
      await apiClient.post(`/ai/name-suggestions/${id}/reject`)
      setSuggestions((prev) => prev.filter((s) => s.id !== id))
      setPendingCount((n) => n - 1)
    } catch { toast.error("Failed") }
  }

  async function handleApplyBulk() {
    const ids = selected.size > 0 ? [...selected] : suggestions.filter((s) => (s.confidence || 0) >= 0.85).map((s) => s.id)
    if (ids.length === 0) { toast.error("No suggestions to apply"); return }
    if (!window.confirm(`Apply ${ids.length} name suggestions?`)) return
    try {
      const res = await apiClient.post("/ai/name-suggestions/apply-bulk", { suggestion_ids: ids })
      toast.success(`Applied ${res.data.applied} names`)
      setSelected(new Set())
      loadSuggestions()
    } catch { toast.error("Failed") }
  }

  async function handleRunAgent() {
    setRunning(true)
    toast.info("Running name enrichment... this may take a few minutes.")
    try {
      const res = await apiClient.get("/ai/name-enrichment/run")
      if (res.data.error) { toast.error(res.data.detail || "Agent error"); return }
      toast.success(`Done — ${res.data.suggestions_created} suggestions created`)
      loadSuggestions()
    } catch (err: any) { toast.error(err?.response?.data?.detail || err?.message || "Failed to run enrichment") }
    finally { setRunning(false) }
  }

  function toggleSelect(id: string) {
    setSelected((prev) => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n })
  }

  const TYPE_LABELS: Record<string, string> = { cemetery: "Cemetery", funeral_home: "Funeral Home" }

  return (
    <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Data Quality</h1>
          <p className="text-sm text-gray-500 mt-1">Review and improve your company records</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={running} onClick={handleRunAgent}>
            {running ? <><Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> Running...</> : "Run name enrichment"}
          </Button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <button onClick={() => setTab("names")} className={`p-3 rounded-lg border text-center ${tab === "names" ? "border-blue-400 bg-blue-50" : "border-gray-200"}`}>
          <div className="text-2xl font-bold">{pendingCount}</div>
          <div className="text-xs text-gray-500">Name suggestions</div>
        </button>
        <button onClick={() => setTab("duplicates")} className={`p-3 rounded-lg border text-center ${tab === "duplicates" ? "border-blue-400 bg-blue-50" : "border-gray-200"}`}>
          <div className="text-2xl font-bold">—</div>
          <div className="text-xs text-gray-500">Duplicates</div>
        </button>
      </div>

      {/* Tabs */}
      {tab === "names" && (
        <>
          {loading ? (
            <div className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-gray-400" /></div>
          ) : suggestions.length === 0 ? (
            <div className="text-center py-16 space-y-2">
              <div className="inline-flex items-center gap-2 bg-green-50 text-green-700 px-4 py-2 rounded-full text-sm font-medium"><Check className="h-4 w-4" /> All names look complete</div>
              <p className="text-sm text-gray-400">Run the enrichment agent to check for new shorthand names.</p>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-500">{total} suggestions pending</p>
                <Button size="sm" onClick={handleApplyBulk}>
                  <Check className="h-3.5 w-3.5 mr-1" /> {selected.size > 0 ? `Apply ${selected.size} selected` : "Apply all high confidence"}
                </Button>
              </div>

              <div className="rounded-md border overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                    <tr>
                      <th className="px-3 py-2 w-8"></th>
                      <th className="px-3 py-2 text-left">Current</th>
                      <th className="px-3 py-2 text-left">Suggested</th>
                      <th className="px-3 py-2 text-left">Extra</th>
                      <th className="px-3 py-2 text-left">Conf.</th>
                      <th className="px-3 py-2 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {suggestions.map((s) => (
                      <tr key={s.id} className={selected.has(s.id) ? "bg-blue-50" : ""}>
                        <td className="px-3 py-2.5">
                          <input type="checkbox" checked={selected.has(s.id)} onChange={() => toggleSelect(s.id)} className="rounded" />
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="text-red-600 font-medium">{s.current_name}</div>
                          <div className="flex gap-1 mt-0.5">
                            {s.customer_type && <Badge className="text-[10px]">{TYPE_LABELS[s.customer_type] || s.customer_type}</Badge>}
                            {s.city && <span className="text-[10px] text-gray-400">{s.city}, {s.state}</span>}
                          </div>
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="text-green-700 font-medium">{s.suggested_name}</div>
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="flex gap-1">
                            {s.suggested_address_line1 && <span title={s.suggested_address_line1}><MapPin className="h-3.5 w-3.5 text-gray-400" /></span>}
                            {s.suggested_phone && <span title={s.suggested_phone}><Phone className="h-3.5 w-3.5 text-gray-400" /></span>}
                            {s.suggested_website && <span title={s.suggested_website}><Globe className="h-3.5 w-3.5 text-gray-400" /></span>}
                          </div>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={`font-medium ${(s.confidence || 0) >= 0.85 ? "text-green-600" : (s.confidence || 0) >= 0.65 ? "text-amber-600" : "text-red-500"}`}>
                            {s.confidence ? `${Math.round(s.confidence * 100)}%` : "—"}
                          </span>
                          <span className="text-[10px] text-gray-400 ml-1">{s.suggestion_source === "google_places" ? "Google" : "AI"}</span>
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          <div className="flex gap-1 justify-end">
                            <Button size="sm" variant="outline" onClick={() => handleApply(s.id)}><Check className="h-3 w-3" /></Button>
                            <Button size="sm" variant="ghost" onClick={() => handleReject(s.id)}><X className="h-3 w-3" /></Button>
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

      {tab === "duplicates" && (
        <div className="text-center py-8">
          <Link to="/crm/companies/duplicates" className="text-blue-600 hover:underline">Open duplicate review →</Link>
        </div>
      )}
    </div>
  )
}
