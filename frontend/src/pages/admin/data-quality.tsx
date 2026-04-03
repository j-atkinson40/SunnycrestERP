// data-quality.tsx — Unified data quality page
// Route: /admin/data-quality

import { useState, useEffect, useCallback } from "react"
import { Link } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Loader2, Check, X, MapPin, Phone, Globe, Pencil } from "lucide-react"

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
  const [allSuggestions, setAllSuggestions] = useState<NameSuggestion[]>([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [applying, setApplying] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [edits, setEdits] = useState<Record<string, string>>({})
  const [editing, setEditing] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const perPage = 25

  // Load ALL pending suggestions in one shot
  const loadAllSuggestions = useCallback(async () => {
    setLoading(true)
    try {
      // Fetch first page to get total
      const first = await apiClient.get("/ai/name-suggestions?status=pending&page=1&per_page=100")
      let items: NameSuggestion[] = first.data.items || []
      const pages = first.data.pages || 1

      // Fetch remaining pages if any
      for (let p = 2; p <= pages; p++) {
        const res = await apiClient.get(`/ai/name-suggestions?status=pending&page=${p}&per_page=100`)
        items = items.concat(res.data.items || [])
      }

      setAllSuggestions(items)
    } catch {
      setAllSuggestions([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadAllSuggestions() }, [loadAllSuggestions])

  // Paginate locally
  const totalPages = Math.ceil(allSuggestions.length / perPage)
  const pageSuggestions = allSuggestions.slice((page - 1) * perPage, page * perPage)

  const editCount = Object.keys(edits).filter((id) => {
    const s = allSuggestions.find((x) => x.id === id)
    return s && edits[id] !== s.suggested_name
  }).length

  async function handleApply(id: string) {
    try {
      const customName = edits[id]
      await apiClient.post(`/ai/name-suggestions/${id}/apply`, {
        apply_address: true, apply_phone: true, apply_website: true,
        ...(customName ? { name: customName } : {}),
      })
      toast.success("Name updated")
      setAllSuggestions((prev) => prev.filter((s) => s.id !== id))
      setEdits((prev) => { const n = { ...prev }; delete n[id]; return n })
      if (editing === id) setEditing(null)
    } catch { toast.error("Failed to apply") }
  }

  async function handleReject(id: string) {
    try {
      await apiClient.post(`/ai/name-suggestions/${id}/reject`)
      setAllSuggestions((prev) => prev.filter((s) => s.id !== id))
      setEdits((prev) => { const n = { ...prev }; delete n[id]; return n })
    } catch { toast.error("Failed to reject") }
  }

  async function handleApplyAll() {
    // If items are selected, apply those. Otherwise apply everything.
    const ids = selected.size > 0
      ? [...selected]
      : allSuggestions.map((s) => s.id)

    if (ids.length === 0) { toast.error("No suggestions to apply"); return }

    const editedCount = ids.filter((id) => {
      const s = allSuggestions.find((x) => x.id === id)
      return s && edits[id] && edits[id] !== s.suggested_name
    }).length

    const msg = selected.size > 0
      ? `Apply ${ids.length} selected suggestions${editedCount > 0 ? ` (${editedCount} edited)` : ""}?`
      : `Apply all ${ids.length} suggestions${editedCount > 0 ? ` (${editedCount} edited)` : ""}?`

    if (!window.confirm(msg)) return

    setApplying(true)
    try {
      // Build name overrides from edits
      const name_overrides: Record<string, string> = {}
      for (const id of ids) {
        if (edits[id]) {
          const s = allSuggestions.find((x) => x.id === id)
          if (s && edits[id] !== s.suggested_name) {
            name_overrides[id] = edits[id]
          }
        }
      }

      // Apply in batches of 10 to avoid timeout
      let totalApplied = 0
      for (let i = 0; i < ids.length; i += 10) {
        const batch = ids.slice(i, i + 10)
        const batchOverrides: Record<string, string> = {}
        for (const id of batch) {
          if (name_overrides[id]) batchOverrides[id] = name_overrides[id]
        }
        const res = await apiClient.post("/ai/name-suggestions/apply-bulk", {
          suggestion_ids: batch,
          name_overrides: batchOverrides,
        })
        totalApplied += res.data.applied || 0
      }

      toast.success(`Applied ${totalApplied} names${editedCount > 0 ? ` (${editedCount} with your edits)` : ""}`)
      setSelected(new Set())
      setEdits({})
      setEditing(null)
      setPage(1)
      loadAllSuggestions()
    } catch { toast.error("Failed to apply bulk") }
    finally { setApplying(false) }
  }

  async function handleRunAgent() {
    setRunning(true)
    toast.info("Running name enrichment... this may take a few minutes.")
    try {
      const res = await apiClient.get("/ai/name-enrichment/run")
      if (res.data.error) { toast.error(res.data.detail || "Agent error"); return }
      toast.success(`Done — ${res.data.suggestions_created} suggestions created`)
      setPage(1)
      loadAllSuggestions()
    } catch (err: any) { toast.error(err?.response?.data?.detail || err?.message || "Failed to run enrichment") }
    finally { setRunning(false) }
  }

  function toggleSelect(id: string) {
    setSelected((prev) => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n })
  }

  function toggleSelectAll() {
    if (selected.size === allSuggestions.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(allSuggestions.map((s) => s.id)))
    }
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
          <div className="text-2xl font-bold">{allSuggestions.length}</div>
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
          ) : allSuggestions.length === 0 ? (
            <div className="text-center py-16 space-y-2">
              <div className="inline-flex items-center gap-2 bg-green-50 text-green-700 px-4 py-2 rounded-full text-sm font-medium"><Check className="h-4 w-4" /> All names look complete</div>
              <p className="text-sm text-gray-400">Run the enrichment agent to check for new shorthand names.</p>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-3">
                  <p className="text-sm text-gray-500">{allSuggestions.length} suggestions pending</p>
                  {editCount > 0 && (
                    <Badge variant="secondary" className="text-blue-600 bg-blue-50">{editCount} edited</Badge>
                  )}
                </div>
                <div className="flex gap-2">
                  {selected.size > 0 && (
                    <Button size="sm" variant="outline" onClick={() => setSelected(new Set())}>
                      Clear selection
                    </Button>
                  )}
                  <Button size="sm" disabled={applying} onClick={handleApplyAll}>
                    {applying ? <><Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> Applying...</> : (
                      <><Check className="h-3.5 w-3.5 mr-1" /> {selected.size > 0 ? `Apply ${selected.size} selected` : `Apply all ${allSuggestions.length}`}</>
                    )}
                  </Button>
                </div>
              </div>

              <div className="rounded-md border overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                    <tr>
                      <th className="px-3 py-2 w-8">
                        <input
                          type="checkbox"
                          checked={selected.size === allSuggestions.length && allSuggestions.length > 0}
                          onChange={toggleSelectAll}
                          className="rounded"
                          title="Select all"
                        />
                      </th>
                      <th className="px-3 py-2 text-left">Current</th>
                      <th className="px-3 py-2 text-left">Suggested</th>
                      <th className="px-3 py-2 text-left">Extra</th>
                      <th className="px-3 py-2 text-left">Conf.</th>
                      <th className="px-3 py-2 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {pageSuggestions.map((s) => (
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
                          {editing === s.id ? (
                            <input
                              autoFocus
                              className="w-full border rounded px-2 py-1 text-sm text-green-700 font-medium focus:outline-none focus:ring-1 focus:ring-blue-400"
                              value={edits[s.id] ?? s.suggested_name}
                              onChange={(e) => setEdits((prev) => ({ ...prev, [s.id]: e.target.value }))}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") { setEditing(null) }
                                if (e.key === "Escape") { setEditing(null); setEdits((prev) => { const n = { ...prev }; delete n[s.id]; return n }) }
                              }}
                              onBlur={() => setEditing(null)}
                            />
                          ) : (
                            <div
                              className="text-green-700 font-medium cursor-pointer group flex items-center gap-1"
                              onClick={() => { setEditing(s.id); if (!edits[s.id]) setEdits((prev) => ({ ...prev, [s.id]: s.suggested_name })) }}
                            >
                              <span>{edits[s.id] || s.suggested_name}</span>
                              <Pencil className="h-3 w-3 text-gray-300 group-hover:text-gray-500 shrink-0" />
                            </div>
                          )}
                          {edits[s.id] && edits[s.id] !== s.suggested_name && (
                            <div className="text-[10px] text-blue-500 mt-0.5">edited</div>
                          )}
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

              {/* Pagination + edit summary */}
              <div className="flex items-center justify-between">
                <p className="text-xs text-gray-400">
                  Showing {(page - 1) * perPage + 1}–{Math.min(page * perPage, allSuggestions.length)} of {allSuggestions.length}
                  {editCount > 0 && <span className="text-blue-500 ml-2">• {editCount} name{editCount !== 1 ? "s" : ""} edited (edits preserved across pages)</span>}
                </p>
                {totalPages > 1 && (
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
                    <span className="text-sm text-gray-500 self-center">Page {page} of {totalPages}</span>
                    <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</Button>
                  </div>
                )}
              </div>
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
