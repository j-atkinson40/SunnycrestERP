import { useEffect, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import {
  AlertTriangle,
  Calendar,
  Plus,
  Search,
  Clock,
} from "lucide-react"
import { fhApi, type BriefingData } from "../lib/fh-api"
import { useAuth } from "@/contexts/auth-context"

export default function DirectionHub() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [briefing, setBriefing] = useState<BriefingData | null>(null)
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")

  useEffect(() => {
    fhApi
      .briefing()
      .then((data) => setBriefing(data))
      .catch(() => setBriefing({ active_cases: [], needs_attention: [], upcoming_services: [] }))
      .finally(() => setLoading(false))
  }, [])

  const handleCreate = async () => {
    setCreating(true)
    try {
      const result = await fhApi.createCase()
      navigate(`/fh/cases/${result.id}/arrangement`)
    } catch {
      alert("Failed to create case")
    } finally {
      setCreating(false)
    }
  }

  const firstName = (user as unknown as { first_name?: string })?.first_name || "there"
  const greeting = _greeting()

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">
          {greeting}, {firstName}.
        </h1>
      </div>

      {/* Hero: New Arrangement */}
      <button
        onClick={handleCreate}
        disabled={creating}
        className="w-full bg-slate-900 text-white rounded-lg px-6 py-5 flex items-center justify-center gap-3 text-lg font-medium hover:bg-slate-800 disabled:opacity-60"
      >
        <Plus className="h-6 w-6" />
        {creating ? "Creating…" : "New Arrangement"}
      </button>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && searchQuery.trim()) {
              navigate(`/fh/cases?search=${encodeURIComponent(searchQuery)}`)
            }
          }}
          placeholder="Search cases, families, staff..."
          className="w-full pl-10 pr-3 py-3 border border-slate-200 rounded-lg outline-none focus:border-slate-500"
        />
      </div>

      {loading ? (
        <div className="text-center text-slate-400 py-8">Loading…</div>
      ) : (
        <>
          {/* Needs Attention */}
          {briefing && briefing.needs_attention.length > 0 && (
            <section>
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
                Needs Attention
              </h2>
              <div className="space-y-2">
                {briefing.needs_attention.slice(0, 8).map((item) => (
                  <Link
                    key={item.case_id}
                    to={`/fh/cases/${item.case_id}`}
                    className="flex items-center gap-3 bg-amber-50 border border-amber-200 rounded p-3 hover:border-amber-400"
                  >
                    <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0" />
                    <div className="flex-1 text-sm">
                      <span className="font-medium text-slate-900">{item.deceased_name}</span>
                      <span className="mx-2 text-slate-400">—</span>
                      <span className="text-amber-700">{item.reasons[0]}</span>
                      {item.reasons.length > 1 && (
                        <span className="text-amber-600 text-xs ml-2">(+{item.reasons.length - 1} more)</span>
                      )}
                      <span className="text-slate-500 text-xs ml-2">· Day {item.days_open}</span>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {/* Active Cases */}
          {briefing && briefing.active_cases.length > 0 && (
            <section>
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
                Active Cases
              </h2>
              <div className="bg-white border border-slate-200 rounded divide-y divide-slate-100">
                {briefing.active_cases.slice(0, 10).map((c) => (
                  <Link
                    key={c.case_id}
                    to={`/fh/cases/${c.case_id}`}
                    className="flex items-center justify-between px-4 py-3 hover:bg-slate-50"
                  >
                    <span className="font-medium text-slate-900 text-sm flex-1">{c.deceased_name}</span>
                    <span className="text-slate-500 text-sm mx-4">{c.current_step_label}</span>
                    <span className="text-slate-400 text-xs flex items-center gap-1">
                      <Clock className="h-3 w-3" /> Day {c.days_open}
                    </span>
                  </Link>
                ))}
              </div>
              {briefing.active_cases.length > 10 && (
                <Link to="/fh/cases" className="text-sm text-slate-600 hover:text-slate-900 mt-2 inline-block">
                  See all {briefing.active_cases.length} →
                </Link>
              )}
            </section>
          )}

          {/* This Week */}
          {briefing && briefing.upcoming_services.length > 0 && (
            <section>
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
                This Week
              </h2>
              <div className="bg-white border border-slate-200 rounded divide-y divide-slate-100">
                {briefing.upcoming_services.slice(0, 5).map((s) => (
                  <Link
                    key={s.case_id}
                    to={`/fh/cases/${s.case_id}`}
                    className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50"
                  >
                    <Calendar className="h-4 w-4 text-slate-400 flex-shrink-0" />
                    <div className="flex-1 text-sm">
                      <span className="font-medium text-slate-900">
                        {_formatServiceDate(s.service_date, s.service_time)}
                      </span>
                      <span className="mx-2 text-slate-400">—</span>
                      <span className="text-slate-700">{s.deceased_name}</span>
                      {s.service_location_name && (
                        <>
                          <span className="mx-2 text-slate-400">·</span>
                          <span className="text-slate-500">{s.service_location_name}</span>
                        </>
                      )}
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {briefing &&
            briefing.active_cases.length === 0 &&
            briefing.needs_attention.length === 0 &&
            briefing.upcoming_services.length === 0 && (
              <div className="bg-white border border-slate-200 rounded p-8 text-center text-slate-500">
                No active cases yet. Click "New Arrangement" to create your first case.
              </div>
            )}
        </>
      )}
    </div>
  )
}

function _greeting(): string {
  const h = new Date().getHours()
  if (h < 12) return "Good morning"
  if (h < 17) return "Good afternoon"
  return "Good evening"
}

function _formatServiceDate(dateStr: string | null, timeStr: string | null): string {
  if (!dateStr) return "—"
  const d = new Date(dateStr + "T00:00:00")
  const dayName = d.toLocaleDateString("en-US", { weekday: "short" })
  const month = d.toLocaleDateString("en-US", { month: "short" })
  const day = d.getDate()
  const time = timeStr ? _formatTime(timeStr) : ""
  return `${dayName} ${month} ${day}${time ? " " + time : ""}`
}

function _formatTime(t: string): string {
  // "14:00:00" → "2:00pm"
  const [hh, mm] = t.split(":")
  const h = parseInt(hh, 10)
  const ampm = h >= 12 ? "pm" : "am"
  const h12 = h % 12 || 12
  return `${h12}:${mm}${ampm}`
}
