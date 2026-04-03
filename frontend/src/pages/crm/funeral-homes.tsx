// funeral-homes.tsx — My Funeral Homes dashboard with health scoring
// Route: /crm/funeral-homes

import { useState, useEffect, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"
import { Loader2, Search, Plus } from "lucide-react"

interface FHItem {
  id: string
  name: string
  city: string | null
  state: string | null
  health_score: string
  health_reasons: string[]
  last_order_date: string | null
  order_count_12mo: number
  total_revenue_12mo: number
  avg_days_to_pay_recent: number | null
  most_ordered_vault_name: string | null
  primary_contact: { name: string; phone: string | null } | null
}

interface HealthSummary { healthy: number; watch: number; at_risk: number; unknown: number; total: number }

const HEALTH_ICONS: Record<string, string> = { healthy: "🟢", watch: "🟡", at_risk: "🔴", unknown: "⚪" }
const HEALTH_LABELS: Record<string, string> = { healthy: "Healthy", watch: "Watch", at_risk: "At risk", unknown: "Unknown" }
const BORDER_COLORS: Record<string, string> = { at_risk: "border-l-red-500 border-l-[3px]", watch: "border-l-amber-400 border-l-[3px]", healthy: "", unknown: "" }

export default function FuneralHomesPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState<FHItem[]>([])
  const [summary, setSummary] = useState<HealthSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [healthFilter, setHealthFilter] = useState("")
  const [sort, setSort] = useState("last_order")
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [inlineActivityId, setInlineActivityId] = useState<string | null>(null)
  const [actTitle, setActTitle] = useState("")
  const [actType, setActType] = useState("call")

  const fetchSummary = useCallback(async () => {
    try {
      const res = await apiClient.get("/companies/health-summary")
      setSummary(res.data)
    } catch { /* silent */ }
  }, [])

  const fetchData = useCallback(async () => {
    try {
      const params = new URLSearchParams({ page: String(page), per_page: "20", sort })
      if (search) params.set("q", search)
      if (healthFilter) params.set("health", healthFilter)
      const res = await apiClient.get(`/companies/funeral-homes?${params}`)
      setItems(res.data.items || [])
      setTotal(res.data.total || 0)
    } catch {
      toast.error("Could not load funeral homes")
    } finally {
      setLoading(false)
    }
  }, [search, healthFilter, sort, page])

  useEffect(() => { fetchSummary(); fetchData() }, [fetchSummary, fetchData])
  useEffect(() => { const t = setTimeout(() => { setPage(1); fetchData() }, 300); return () => clearTimeout(t) }, [search])

  function fmtCurrency(n: number) { return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n) }
  function daysAgo(dateStr: string | null) {
    if (!dateStr) return "—"
    const d = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86400000)
    return d === 0 ? "Today" : d === 1 ? "Yesterday" : `${d} days ago`
  }

  async function handleLogActivity(companyId: string) {
    if (!actTitle.trim()) return
    try {
      await apiClient.post(`/companies/${companyId}/activity`, { activity_type: actType, title: actTitle })
      toast.success("Activity logged")
      setInlineActivityId(null); setActTitle(""); setActType("call")
    } catch { toast.error("Failed") }
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">My Funeral Homes</h1>
        <p className="text-sm text-gray-500 mt-1">Account health and relationship overview</p>
      </div>

      {/* Health summary bar */}
      {summary && (
        <div className="grid grid-cols-4 gap-3">
          {(["healthy", "watch", "at_risk", "unknown"] as const).map((key) => (
            <button
              key={key}
              onClick={() => { setHealthFilter(healthFilter === key ? "" : key); setPage(1) }}
              className={`p-3 rounded-lg border text-center transition-colors ${
                healthFilter === key ? "border-blue-400 bg-blue-50 ring-2 ring-blue-200" : "border-gray-200 hover:border-gray-300"
              }`}
            >
              <div className="text-2xl font-bold">{HEALTH_ICONS[key]} {summary[key]}</div>
              <div className="text-xs text-gray-500">{HEALTH_LABELS[key]}</div>
            </button>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by name or city..." className="pl-9" />
        </div>
        <select value={sort} onChange={(e) => setSort(e.target.value)} className="rounded-md border px-3 py-2 text-sm bg-background">
          <option value="last_order">Last order</option>
          <option value="name">Name A–Z</option>
          <option value="revenue">Revenue (high–low)</option>
          <option value="health">Health (at risk first)</option>
        </select>
      </div>

      {/* List */}
      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-gray-400" /></div>
      ) : items.length === 0 ? (
        <div className="text-center py-16 text-gray-500">No funeral homes match your filters</div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id}>
              <Card className={`p-4 ${BORDER_COLORS[item.health_score] || ""}`}>
                <div className="flex items-start justify-between">
                  <div className="space-y-1 flex-1">
                    <div className="flex items-center gap-2">
                      <span>{HEALTH_ICONS[item.health_score] || "⚪"}</span>
                      <span className="font-semibold">{item.name}</span>
                      {item.city && item.state && <span className="text-sm text-gray-500">{item.city}, {item.state}</span>}
                    </div>
                    <div className="text-sm text-gray-600">
                      Last order: {daysAgo(item.last_order_date)}
                      {item.order_count_12mo > 0 && <> · Orders (12mo): {item.order_count_12mo} · Revenue: {fmtCurrency(item.total_revenue_12mo)}</>}
                    </div>
                    {item.avg_days_to_pay_recent != null && (
                      <div className="text-sm text-gray-500">Avg payment: {item.avg_days_to_pay_recent.toFixed(0)} days</div>
                    )}
                    {item.health_reasons.length > 0 && (
                      <div className="space-y-0.5 mt-1">
                        {item.health_reasons.map((r, i) => (
                          <div key={i} className={`text-xs ${item.health_score === "at_risk" ? "text-red-600" : "text-amber-600"}`}>⚠ {r}</div>
                        ))}
                      </div>
                    )}
                    {item.most_ordered_vault_name && <div className="text-xs text-gray-400">Most ordered: {item.most_ordered_vault_name}</div>}
                    {item.primary_contact && <div className="text-xs text-gray-400">Primary: {item.primary_contact.name}{item.primary_contact.phone ? ` · ${item.primary_contact.phone}` : ""}</div>}
                  </div>
                  <div className="flex gap-2 flex-shrink-0">
                    <Button variant="outline" size="sm" onClick={() => navigate(`/crm/companies/${item.id}`)}>View account</Button>
                    <Button variant="ghost" size="sm" onClick={() => setInlineActivityId(inlineActivityId === item.id ? null : item.id)}>
                      <Plus className="h-3.5 w-3.5 mr-0.5" /> Log
                    </Button>
                  </div>
                </div>
              </Card>
              {inlineActivityId === item.id && (
                <div className="ml-4 mt-1 p-3 border rounded-lg bg-gray-50 flex gap-2 items-end">
                  <div className="flex gap-1">
                    {["call", "note", "visit"].map((t) => (
                      <button key={t} onClick={() => setActType(t)} className={`px-2 py-1 text-xs rounded border ${actType === t ? "border-blue-400 bg-blue-50" : "border-gray-200"}`}>
                        {t === "call" ? "📞" : t === "note" ? "📝" : "🤝"}
                      </button>
                    ))}
                  </div>
                  <Input value={actTitle} onChange={(e) => setActTitle(e.target.value)} placeholder="Title..." className="flex-1 h-8" />
                  <Button size="sm" onClick={() => handleLogActivity(item.id)} disabled={!actTitle.trim()}>Save</Button>
                  <Button size="sm" variant="ghost" onClick={() => setInlineActivityId(null)}>Cancel</Button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {total > 20 && (
        <div className="flex justify-center gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
          <Button variant="outline" size="sm" disabled={page >= Math.ceil(total / 20)} onClick={() => setPage(page + 1)}>Next</Button>
        </div>
      )}
    </div>
  )
}
