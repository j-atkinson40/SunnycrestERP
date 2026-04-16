import { useEffect, useState } from "react"
import { adminApi } from "../lib/admin-api"

export function MigrationsPanel() {
  const [status, setStatus] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    adminApi
      .get("/api/platform/admin/migrations/status")
      .then((r) => setStatus(r.data))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8 text-center text-slate-400">Loading…</div>

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-slate-900">Migrations</h1>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white border border-slate-200 rounded p-4">
          <div className="text-xs font-semibold text-slate-600 uppercase">Production</div>
          <div className="mt-2 text-lg font-mono">
            {status?.production?.current_revision || "unknown"}
          </div>
          <div className="text-xs text-slate-500 mt-1">
            Read-only. Production migrations run via Railway deploy.
          </div>
        </div>

        <div className="bg-white border border-amber-200 rounded p-4">
          <div className="text-xs font-semibold text-amber-700 uppercase">Staging</div>
          <div className="mt-2 text-lg font-mono">
            {status?.staging?.current_revision || "unknown"}
          </div>
          {status?.staging?.configured ? (
            <button
              onClick={() => {
                if (!confirm("Run `alembic upgrade head` on staging?")) return
                // WebSocket connection would go here; simplified:
                alert("WebSocket migration streaming not yet wired in UI — use Railway CLI.")
              }}
              className="mt-3 px-3 py-1.5 bg-amber-600 text-white text-xs rounded hover:bg-amber-700"
            >
              Run migrations on staging
            </button>
          ) : (
            <div className="text-xs text-amber-700 mt-1">STAGING_DATABASE_URL not configured</div>
          )}
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded p-4">
        <div className="text-xs font-semibold text-slate-600 uppercase mb-2">Alembic heads</div>
        <div className="text-sm font-mono">
          {(status?.heads || []).join(", ") || "none"}
        </div>
      </div>
    </div>
  )
}
