import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { AlertTriangle, Activity, Users, DollarSign } from "lucide-react"
import { adminApi } from "../lib/admin-api"

interface KanbanData {
  [status: string]: { [vertical: string]: any[] }
}

export function HealthDashboard() {
  const [kanban, setKanban] = useState<KanbanData | null>(null)
  const [untested, setUntested] = useState<Record<string, any[]>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      adminApi.get("/api/platform/admin/tenants/kanban"),
      adminApi.get("/api/platform/admin/deployments/untested"),
    ])
      .then(([k, u]) => {
        setKanban(k.data)
        setUntested(u.data || {})
      })
      .catch(() => {
        setKanban({})
        setUntested({})
      })
      .finally(() => setLoading(false))
  }, [])

  const allTenants = Object.values(kanban || {}).flatMap((byVertical) =>
    Object.values(byVertical).flat()
  )
  const liveCount = (kanban?.live ? Object.values(kanban.live).flat() : []).length
  const onboardingCount = (kanban?.onboarding ? Object.values(kanban.onboarding).flat() : []).length
  const errorCount = allTenants.filter((t: any) => t.health?.color === "red").length

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Platform Health</h1>

      {/* Quick stats */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard icon={<Activity className="h-5 w-5" />} label="Live tenants" value={liveCount} />
        <StatCard icon={<Users className="h-5 w-5" />} label="Onboarding" value={onboardingCount} />
        <StatCard
          icon={<DollarSign className="h-5 w-5" />}
          label="MRR (est)"
          value={`$${(liveCount * 800).toLocaleString()}`}
        />
        <StatCard
          icon={<AlertTriangle className="h-5 w-5" />}
          label="Errors today"
          value={errorCount}
          alert={errorCount > 0}
        />
      </div>

      {/* Untested deployments alert */}
      {Object.keys(untested).length > 0 && (
        <div className="bg-amber-50 border-2 border-amber-300 rounded p-4">
          <div className="flex items-center gap-2 font-semibold text-amber-900 mb-2">
            <AlertTriangle className="h-5 w-5" />
            Untested deployments
          </div>
          <div className="space-y-2">
            {Object.entries(untested).map(([vertical, deps]) => (
              <div key={vertical} className="text-sm text-amber-900">
                <span className="font-medium">{vertical}:</span>{" "}
                {deps.length} untested deployment{deps.length !== 1 && "s"}
                <Link
                  to={`/bridgeable-admin/audit?scope=vertical&scope_value=${vertical}`}
                  className="ml-3 px-2 py-0.5 bg-amber-700 text-white text-xs rounded hover:bg-amber-800"
                >
                  Run audit →
                </Link>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tenant health table */}
      <div className="bg-white border border-slate-200 rounded overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-200 font-semibold text-slate-900">
          Per-tenant health
        </div>
        {loading ? (
          <div className="p-6 text-center text-slate-400">Loading…</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-left px-4 py-2">Tenant</th>
                <th className="text-left px-4 py-2">Vertical</th>
                <th className="text-left px-4 py-2">Metric</th>
                <th className="text-left px-4 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {allTenants.sort((a: any, b: any) => {
                const order = { red: 0, amber: 1, grey: 2, green: 3 }
                return (order[a.health?.color as keyof typeof order] ?? 4) -
                       (order[b.health?.color as keyof typeof order] ?? 4)
              }).map((t: any) => (
                <tr key={t.id} className="border-t border-slate-100">
                  <td className="px-4 py-2">
                    <Link to={`/bridgeable-admin/tenants/${t.id}`} className="text-slate-900 hover:text-amber-600 font-medium">
                      {t.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-slate-600">{t.vertical}</td>
                  <td className="px-4 py-2 text-slate-600">{t.key_metric}</td>
                  <td className="px-4 py-2">
                    <HealthDot color={t.health?.color || "grey"} label={t.health?.reason} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="flex gap-4">
        <Link
          to="/bridgeable-admin/audit"
          className="flex-1 bg-white border border-slate-200 rounded p-4 hover:border-slate-400"
        >
          <div className="font-semibold text-slate-900">Run audit</div>
          <div className="text-xs text-slate-500 mt-1">Full Playwright E2E on staging</div>
        </Link>
        <Link
          to="/bridgeable-admin/deployments"
          className="flex-1 bg-white border border-slate-200 rounded p-4 hover:border-slate-400"
        >
          <div className="font-semibold text-slate-900">Log deployment</div>
          <div className="text-xs text-slate-500 mt-1">Track test coverage of a push</div>
        </Link>
        <Link
          to="/bridgeable-admin/staging/create"
          className="flex-1 bg-white border border-slate-200 rounded p-4 hover:border-slate-400"
        >
          <div className="font-semibold text-slate-900">Create staging tenant</div>
          <div className="text-xs text-slate-500 mt-1">Seeded tenant for any vertical</div>
        </Link>
      </div>
    </div>
  )
}

function StatCard({
  icon,
  label,
  value,
  alert,
}: {
  icon: React.ReactNode
  label: string
  value: string | number
  alert?: boolean
}) {
  return (
    <div
      className={`bg-white border rounded p-4 ${alert ? "border-red-300 bg-red-50" : "border-slate-200"}`}
    >
      <div className="flex items-center gap-2 text-slate-500 text-xs">
        {icon}
        <span>{label}</span>
      </div>
      <div className="text-2xl font-semibold text-slate-900 mt-1">{value}</div>
    </div>
  )
}

function HealthDot({ color, label }: { color: string; label?: string }) {
  const bg = {
    green: "bg-green-500",
    amber: "bg-amber-500",
    red: "bg-red-500",
    grey: "bg-slate-400",
  }[color] || "bg-slate-400"
  return (
    <span className="flex items-center gap-2">
      <span className={`h-2.5 w-2.5 rounded-full ${bg}`} />
      <span className="text-xs text-slate-600">{label || color}</span>
    </span>
  )
}
