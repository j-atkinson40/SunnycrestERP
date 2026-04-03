// companies.tsx — CRM companies list page
// Route: /crm/companies

import { useState, useEffect, useCallback } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Loader2, Plus, Search } from "lucide-react"

interface CompanySummary {
  id: string
  name: string
  legal_name: string | null
  city: string | null
  state: string | null
  is_customer: boolean
  is_vendor: boolean
  is_cemetery: boolean
  is_funeral_home: boolean
  is_licensee: boolean
  primary_contact: { name: string; phone: string | null } | null
  linked_customer_id: string | null
  linked_vendor_id: string | null
  created_at: string | null
  last_activity_date: string | null
}

const ROLE_FILTERS = [
  { value: "", label: "All" },
  { value: "customer", label: "Customers" },
  { value: "vendor", label: "Vendors" },
  { value: "cemetery", label: "Cemeteries" },
  { value: "funeral_home", label: "Funeral Homes" },
  { value: "licensee", label: "Licensees" },
]

const ROLE_BADGES: Record<string, { label: string; className: string }> = {
  customer: { label: "Customer", className: "bg-blue-100 text-blue-700" },
  vendor: { label: "Vendor", className: "bg-purple-100 text-purple-700" },
  cemetery: { label: "Cemetery", className: "bg-green-100 text-green-700" },
  funeral_home: { label: "Funeral Home", className: "bg-teal-100 text-teal-700" },
  licensee: { label: "Licensee", className: "bg-amber-100 text-amber-700" },
}

export default function CompaniesListPage() {
  const navigate = useNavigate()
  const [urlParams] = useSearchParams()
  const [items, setItems] = useState<CompanySummary[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [roleFilter, setRoleFilter] = useState(urlParams.get("role") || "")
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [reclassifyMode, setReclassifyMode] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [reclassifyTo, setReclassifyTo] = useState("")
  const [reclassifying, setReclassifying] = useState(false)

  const TYPE_OPTIONS = [
    { value: "funeral_home", label: "Funeral Home" },
    { value: "contractor", label: "Contractor" },
    { value: "cemetery", label: "Cemetery" },
    { value: "crematory", label: "Crematory" },
    { value: "licensee", label: "Licensee" },
    { value: "church", label: "Church" },
    { value: "government", label: "Government" },
    { value: "school", label: "School" },
    { value: "fire_department", label: "Fire Department" },
    { value: "utility", label: "Utility" },
    { value: "individual", label: "Individual" },
    { value: "other", label: "Other" },
  ]

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  function toggleSelectAll() {
    if (selected.size === items.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(items.map((i) => i.id)))
    }
  }

  async function handleReclassify() {
    if (selected.size === 0 || !reclassifyTo) { toast.error("Select companies and an action"); return }
    setReclassifying(true)
    try {
      if (reclassifyTo === "_delete") {
        if (!window.confirm(`Delete ${selected.size} selected companies? This cannot be undone.`)) { setReclassifying(false); return }
        const res = await apiClient.post("/companies/classify/delete-bulk", { company_ids: [...selected] })
        toast.success(`Deleted ${res.data.deleted} companies`)
      } else {
        const res = await apiClient.post("/companies/classify/reclassify-bulk", {
          company_ids: [...selected],
          customer_type: reclassifyTo,
        })
        toast.success(`Reclassified ${res.data.reclassified} companies`)
      }
      setSelected(new Set())
      setReclassifyMode(false)
      setReclassifyTo("")
      fetchData()
    } catch { toast.error("Failed") }
    finally { setReclassifying(false) }
  }

  const fetchData = useCallback(async () => {
    try {
      const params = new URLSearchParams()
      if (search) params.set("q", search)
      if (roleFilter) params.set("role", roleFilter)
      params.set("page", String(page))
      params.set("per_page", "20")

      const res = await apiClient.get(`/companies?${params}`)
      setItems(res.data.items || [])
      setTotal(res.data.total || 0)
    } catch {
      toast.error("Could not load companies")
    } finally {
      setLoading(false)
    }
  }, [search, roleFilter, page])

  useEffect(() => { fetchData() }, [fetchData])

  useEffect(() => {
    const t = setTimeout(() => { setPage(1); fetchData() }, 300)
    return () => clearTimeout(t)
  }, [search])

  function getRoles(item: CompanySummary): string[] {
    const roles: string[] = []
    if (item.is_customer) roles.push("customer")
    if (item.is_vendor) roles.push("vendor")
    if (item.is_cemetery) roles.push("cemetery")
    if (item.is_funeral_home) roles.push("funeral_home")
    if (item.is_licensee) roles.push("licensee")
    return roles
  }

  function timeAgo(dateStr: string | null): string {
    if (!dateStr) return "—"
    const diff = Date.now() - new Date(dateStr).getTime()
    const days = Math.floor(diff / 86400000)
    if (days === 0) return "Today"
    if (days === 1) return "Yesterday"
    if (days < 30) return `${days}d ago`
    return `${Math.floor(days / 30)}mo ago`
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Companies</h1>
          <p className="text-sm text-gray-500 mt-1">All customers, vendors, cemeteries, and partners</p>
        </div>
        <div className="flex gap-2">
          {!reclassifyMode ? (
            <>
              <Button variant="outline" onClick={() => navigate("/crm/companies/duplicates")}>
                Duplicates
              </Button>
              <Button variant="outline" onClick={() => { setReclassifyMode(true); setSelected(new Set()) }}>
                Reclassify
              </Button>
              <Button onClick={() => navigate("/crm/companies/new")}>
                <Plus className="h-4 w-4 mr-1" /> New company
              </Button>
            </>
          ) : (
            <>
              <select
                value={reclassifyTo}
                onChange={(e) => setReclassifyTo(e.target.value)}
                className="rounded-md border px-3 py-2 text-sm bg-background"
              >
                <option value="">Action...</option>
                {TYPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                <option value="_delete" className="text-red-600">Delete</option>
              </select>
              <Button onClick={handleReclassify} disabled={selected.size === 0 || !reclassifyTo || reclassifying} variant={reclassifyTo === "_delete" ? "destructive" : "default"}>
                {reclassifying ? "..." : reclassifyTo === "_delete" ? `Delete ${selected.size} selected` : `Reclassify ${selected.size} selected`}
              </Button>
              <Button variant="ghost" onClick={() => { setReclassifyMode(false); setSelected(new Set()); setReclassifyTo("") }}>
                Cancel
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Reclassify mode banner */}
      {reclassifyMode && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-700 flex items-center justify-between">
          <span>Select companies to reclassify. {selected.size} selected.</span>
          <button onClick={toggleSelectAll} className="text-blue-600 font-medium hover:underline text-xs">
            {selected.size === items.length ? "Deselect all" : "Select all on page"}
          </button>
        </div>
      )}

      {/* Search + filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, phone, email, city..."
            className="pl-9"
          />
        </div>
        <div className="flex gap-1.5 flex-wrap">
          {ROLE_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => { setRoleFilter(f.value); setPage(1) }}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                roleFilter === f.value
                  ? "bg-gray-900 text-white border-gray-900"
                  : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Results */}
      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-gray-500 mb-2">
            {search || roleFilter ? "No companies match your filters" : "No companies yet"}
          </p>
          {!search && !roleFilter && (
            <>
            <p className="text-xs text-gray-400 mb-4">
              Your customers, vendors, and cemeteries will appear here automatically.
            </p>
            <Button
              variant="outline"
              onClick={async () => {
                try {
                  const res = await apiClient.get("/companies/run-migration")
                  toast.success(`Migrated ${res.data.total_entities} companies (${res.data.customers} customers, ${res.data.vendors} vendors, ${res.data.cemeteries} cemeteries)`)
                  fetchData()
                } catch (err: unknown) {
                  const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
                  toast.error(detail || "Migration failed — check browser console")
                  console.error("Migration error:", err)
                }
              }}
            >
              Import existing customers, vendors & cemeteries
            </Button>
            </>
          )}
          {(search || roleFilter) && (
            <Button variant="outline" size="sm" onClick={() => { setSearch(""); setRoleFilter("") }}>
              Clear filters
            </Button>
          )}
        </div>
      ) : (
        <div className="rounded-md border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 uppercase tracking-wider">
              <tr>
                {reclassifyMode && <th className="px-4 py-3 w-8"></th>}
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Roles</th>
                <th className="px-4 py-3 hidden md:table-cell">Location</th>
                <th className="px-4 py-3 hidden lg:table-cell">Primary Contact</th>
                <th className="px-4 py-3 hidden lg:table-cell">Last Activity</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map((item) => {
                const roles = getRoles(item)
                return (
                  <tr key={item.id} className={`hover:bg-gray-50 cursor-pointer ${selected.has(item.id) ? "bg-blue-50" : ""}`} onClick={() => reclassifyMode ? toggleSelect(item.id) : navigate(`/crm/companies/${item.id}`)}>
                    {reclassifyMode && (
                      <td className="px-4 py-3">
                        <input type="checkbox" checked={selected.has(item.id)} onChange={() => toggleSelect(item.id)} className="rounded accent-blue-600" onClick={(e) => e.stopPropagation()} />
                      </td>
                    )}
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">{item.name}</div>
                      {item.legal_name && item.legal_name !== item.name && (
                        <div className="text-xs text-gray-400">{item.legal_name}</div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {roles.slice(0, 3).map((r) => {
                          const b = ROLE_BADGES[r]
                          return b ? <Badge key={r} className={`text-[10px] ${b.className}`}>{b.label}</Badge> : null
                        })}
                        {roles.length > 3 && <span className="text-[10px] text-gray-400">+{roles.length - 3}</span>}
                      </div>
                    </td>
                    <td className="px-4 py-3 hidden md:table-cell text-gray-500">
                      {item.city && item.state ? `${item.city}, ${item.state}` : item.city || item.state || "—"}
                    </td>
                    <td className="px-4 py-3 hidden lg:table-cell">
                      {item.primary_contact ? (
                        <div>
                          <div className="text-gray-700">{item.primary_contact.name}</div>
                          {item.primary_contact.phone && <div className="text-xs text-gray-400">{item.primary_contact.phone}</div>}
                        </div>
                      ) : (
                        <span className="text-gray-400">No contact</span>
                      )}
                    </td>
                    <td className="px-4 py-3 hidden lg:table-cell text-gray-400 text-xs">
                      {item.last_activity_date ? timeAgo(item.last_activity_date) : timeAgo(item.created_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button variant="outline" size="sm" onClick={(e) => { e.stopPropagation(); navigate(`/crm/companies/${item.id}`) }}>
                        View
                      </Button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {total > 20 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-500">
            Showing {(page - 1) * 20 + 1}–{Math.min(page * 20, total)} of {total}
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
            <Button variant="outline" size="sm" disabled={page >= Math.ceil(total / 20)} onClick={() => setPage(page + 1)}>Next</Button>
          </div>
        </div>
      )}
    </div>
  )
}
