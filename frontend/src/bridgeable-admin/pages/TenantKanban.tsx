import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { UserCog, Play } from "lucide-react"
import { adminApi } from "../lib/admin-api"
import { adminPath } from "../lib/admin-routes"

const STATUS_COLUMNS = ["waitlist", "onboarding", "live", "churned", "staging"]
const VERTICALS = ["manufacturing", "funeral_home", "cemetery", "crematory"]

export function TenantKanban() {
  const [data, setData] = useState<any>(null)
  const [filter, setFilter] = useState<string>("all")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    adminApi
      .get("/api/platform/admin/tenants/kanban")
      .then((r) => setData(r.data))
      .catch(() => setData({}))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8 text-center text-slate-400">Loading kanban…</div>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Tenants</h1>
        <div className="flex gap-2 text-xs">
          {["all", ...VERTICALS].map((v) => (
            <button
              key={v}
              onClick={() => setFilter(v)}
              className={`px-2.5 py-1 rounded ${
                filter === v ? "bg-slate-900 text-white" : "bg-white border border-slate-200 text-slate-600"
              }`}
            >
              {v === "all" ? "All" : v.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-5 gap-3 items-start">
        {STATUS_COLUMNS.map((status) => {
          const byVertical = data?.[status] || {}
          const cards = Object.entries(byVertical)
            .filter(([v]) => filter === "all" || filter === v)
            .flatMap(([v, list]: any) => list.map((c: any) => ({ ...c, vertical: v })))
          return (
            <div key={status} className="bg-slate-100 rounded p-2 min-h-[200px]">
              <div className="text-xs font-semibold text-slate-600 uppercase tracking-wide px-1 py-1">
                {status} <span className="text-slate-400 font-normal">({cards.length})</span>
              </div>
              <div className="space-y-2 mt-2">
                {cards.map((card: any) => (
                  <TenantCard key={card.id} card={card} />
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function TenantCard({ card }: { card: any }) {
  const dotColor = {
    green: "bg-green-500",
    amber: "bg-amber-500",
    red: "bg-red-500",
    grey: "bg-slate-400",
  }[card.health?.color as string] || "bg-slate-400"

  return (
    <div className="bg-white rounded p-3 border border-slate-200 shadow-sm">
      <div className="flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${dotColor}`} title={card.health?.reason} />
        <Link to={adminPath(`/tenants/${card.id}`)} className="font-medium text-slate-900 text-sm flex-1 truncate">
          {card.name}
        </Link>
      </div>
      <div className="text-[11px] text-slate-500 mt-1">
        {card.vertical} · {card.slug}
      </div>
      <div className="text-xs text-slate-600 mt-2">{card.key_metric}</div>
      {card.health?.color === "amber" && (
        <div className="text-[11px] text-amber-700 mt-1">⚠ {card.health.reason}</div>
      )}
      <div className="flex gap-1 mt-2">
        <button
          className="flex-1 text-[11px] px-1.5 py-1 bg-slate-100 hover:bg-slate-200 rounded flex items-center justify-center gap-1"
          title="Impersonate"
        >
          <UserCog className="h-3 w-3" /> Impersonate
        </button>
        <button
          className="flex-1 text-[11px] px-1.5 py-1 bg-slate-100 hover:bg-slate-200 rounded flex items-center justify-center gap-1"
          title="Smoke test"
        >
          <Play className="h-3 w-3" /> Smoke
        </button>
      </div>
    </div>
  )
}
