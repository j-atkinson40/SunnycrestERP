import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { ArrowLeft, Building2, Church, Flame, Plus } from "lucide-react"
import { fhApi } from "../lib/fh-api"

export default function NetworkSettings() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fhApi
      .networkConnections()
      .then(setData)
      .catch(() => setData({ connections: [], grouped: { manufacturer: [], cemetery: [], crematory: [], other: [] } }))
      .finally(() => setLoading(false))
  }, [])

  if (loading || !data) return <div className="text-center text-slate-400 py-12">Loading…</div>

  const grouped = data.grouped || {}

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-5">
      <Link to="/fh" className="flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900">
        <ArrowLeft className="h-4 w-4" /> Home
      </Link>
      <h1 className="text-2xl font-semibold text-slate-900">Network</h1>
      <p className="text-sm text-slate-500">
        Connections to vault manufacturers, cemeteries, and crematories. Connected partners enable cross-tenant ordering and plot reservation.
      </p>

      <Section
        title="Vault Manufacturers"
        icon={<Building2 className="h-4 w-4" />}
        items={grouped.manufacturer}
      />
      <Section
        title="Cemeteries"
        icon={<Church className="h-4 w-4" />}
        items={grouped.cemetery}
      />
      <Section
        title="Crematories"
        icon={<Flame className="h-4 w-4" />}
        items={grouped.crematory}
      />
      {grouped.other?.length > 0 && (
        <Section title="Other" icon={null} items={grouped.other} />
      )}
    </div>
  )
}

function Section({
  title,
  icon,
  items,
}: {
  title: string
  icon: React.ReactNode
  items: any[]
}) {
  return (
    <section>
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-xs font-semibold text-slate-600 uppercase tracking-wide flex items-center gap-2">
          {icon} {title}
        </h2>
        <button
          onClick={() => alert("Connection requests will be available in FH-2. Demo connections are pre-seeded.")}
          className="text-xs text-slate-500 hover:text-slate-900 flex items-center gap-1"
        >
          <Plus className="h-3 w-3" /> Add
        </button>
      </div>
      {!items || items.length === 0 ? (
        <div className="bg-slate-50 border border-slate-200 rounded p-4 text-sm text-slate-500">
          No {title.toLowerCase()} connected.
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded divide-y divide-slate-100">
          {items.map((c: any) => (
            <div key={c.id} className="px-4 py-3 flex items-center justify-between">
              <div>
                <div className="font-medium text-slate-900">{c.other_company_name}</div>
                <div className="text-xs text-slate-500">
                  {c.other_company_slug && <span>{c.other_company_slug}</span>}
                  {c.other_vertical && <> · {c.other_vertical}</>}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className={`text-xs px-2 py-0.5 rounded ${
                    c.status === "active"
                      ? "bg-emerald-100 text-emerald-800"
                      : "bg-amber-100 text-amber-800"
                  }`}
                >
                  {c.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
