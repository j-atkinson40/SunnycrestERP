import { useEffect, useState } from "react"
import { adminApi } from "../lib/admin-api"

export function FeatureFlagsPage() {
  const [flags, setFlags] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    adminApi
      .get("/api/platform/admin/feature-flags")
      .then((r) => setFlags(r.data))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const toggle = async (flag_key: string, current: boolean) => {
    await adminApi.patch(`/api/platform/admin/feature-flags/${flag_key}`, {
      default_enabled: !current,
    })
    load()
  }

  if (loading) return <div className="p-8 text-center text-slate-400">Loading…</div>

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-slate-900">Feature Flags</h1>

      <div className="bg-white border border-slate-200 rounded overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs text-slate-600">
            <tr>
              <th className="text-left px-4 py-2">Flag</th>
              <th className="text-left px-4 py-2">Category</th>
              <th className="text-left px-4 py-2">Default</th>
              <th className="text-left px-4 py-2">Overrides</th>
            </tr>
          </thead>
          <tbody>
            {flags.map((f) => (
              <tr key={f.flag_key} className="border-t border-slate-100">
                <td className="px-4 py-2">
                  <div className="font-medium text-slate-900">{f.flag_key}</div>
                  <div className="text-xs text-slate-500">{f.description}</div>
                </td>
                <td className="px-4 py-2 text-slate-600">{f.category}</td>
                <td className="px-4 py-2">
                  <button
                    onClick={() => toggle(f.flag_key, f.default_enabled)}
                    className={`px-2 py-1 text-xs rounded ${
                      f.default_enabled ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {f.default_enabled ? "ON" : "OFF"}
                  </button>
                </td>
                <td className="px-4 py-2 text-xs text-slate-500">
                  {f.overrides?.length ? `${f.overrides.length} tenant overrides` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
