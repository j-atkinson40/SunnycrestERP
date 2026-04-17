import { useEffect, useState } from "react"
import { Link, useSearchParams, useNavigate } from "react-router-dom"
import { Plus, Search } from "lucide-react"
import { fhApi, type CaseSummary } from "../lib/fh-api"

export default function CaseList() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const [cases, setCases] = useState<CaseSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string>(searchParams.get("status") || "active")
  const [query, setQuery] = useState(searchParams.get("search") || "")

  useEffect(() => {
    setLoading(true)
    fhApi
      .listCases({ status: statusFilter === "all" ? undefined : statusFilter, search: query || undefined })
      .then((data) => setCases(data))
      .finally(() => setLoading(false))
  }, [statusFilter, query])

  const createCase = async () => {
    try {
      const c = await fhApi.createCase()
      navigate(`/fh/cases/${c.id}/arrangement`)
    } catch {
      alert("Failed to create case")
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Cases</h1>
        <button
          onClick={createCase}
          className="bg-slate-900 text-white rounded px-4 py-2 text-sm flex items-center gap-2 hover:bg-slate-800"
        >
          <Plus className="h-4 w-4" /> New Arrangement
        </button>
      </div>

      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search name, case number…"
            className="w-full pl-10 pr-3 py-2 border border-slate-200 rounded outline-none focus:border-slate-500"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value)
            setSearchParams((p) => {
              p.set("status", e.target.value)
              return p
            })
          }}
          className="border border-slate-200 rounded px-3 py-2 text-sm"
        >
          <option value="active">Active</option>
          <option value="completed">Completed</option>
          <option value="on_hold">On hold</option>
          <option value="cancelled">Cancelled</option>
          <option value="all">All</option>
        </select>
      </div>

      {loading ? (
        <div className="text-center text-slate-400 py-8">Loading…</div>
      ) : cases.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded p-8 text-center text-slate-500">
          {query ? "No cases match your search." : "No cases yet. Create your first one."}
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs text-slate-600">
              <tr>
                <th className="text-left px-4 py-2">Case #</th>
                <th className="text-left px-4 py-2">Deceased</th>
                <th className="text-left px-4 py-2">Current step</th>
                <th className="text-left px-4 py-2">Status</th>
                <th className="text-left px-4 py-2">Opened</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-2">
                    <Link to={`/fh/cases/${c.id}`} className="font-mono text-xs text-slate-700">
                      {c.case_number}
                    </Link>
                  </td>
                  <td className="px-4 py-2">
                    <Link to={`/fh/cases/${c.id}`} className="font-medium text-slate-900 hover:text-slate-700">
                      {c.deceased_name}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-slate-600">{c.current_step.replace(/_/g, " ")}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">{c.status}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">
                    {c.opened_at ? new Date(c.opened_at).toLocaleDateString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
