import { useEffect, useState } from "react"
import apiClient from "@/lib/api-client"

export default function ProductLines() {
  const [lines, setLines] = useState<any[]>([])
  const [available, setAvailable] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    Promise.all([
      apiClient.get("/product-lines"),
      apiClient.get("/product-lines/available"),
    ])
      .then(([l, a]) => {
        setLines(l.data)
        setAvailable(a.data || {})
      })
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const toggle = async (lineKey: string, isEnabled: boolean) => {
    if (isEnabled) {
      await apiClient.post(`/product-lines/disable/${lineKey}`)
    } else {
      await apiClient.post("/product-lines/enable", { line_key: lineKey })
    }
    load()
  }

  if (loading) return <div className="p-8 text-center text-slate-400">Loading…</div>

  const enabledKeys = new Set(lines.filter((l) => l.is_enabled).map((l) => l.line_key))

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Product Lines</h1>
        <p className="text-sm text-slate-500 mt-1">
          Configure what your business sells. Turning on a product line enables related catalog,
          ordering, and reporting features across the platform.
        </p>
      </div>

      <div className="bg-white border border-slate-200 rounded overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs text-slate-600">
            <tr>
              <th className="text-left px-4 py-2">Product line</th>
              <th className="text-left px-4 py-2">Status</th>
              <th className="text-right px-4 py-2 w-24">Enabled</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(available).map(([key, meta]: any) => {
              const isEnabled = enabledKeys.has(key)
              return (
                <tr key={key} className="border-t border-slate-100">
                  <td className="px-4 py-2">
                    <div className="font-medium text-slate-900">{meta.display_name}</div>
                    {meta.replaces_extension && (
                      <div className="text-xs text-slate-400">
                        (replaces extension "{meta.replaces_extension}")
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-2 text-slate-500 text-xs">
                    {isEnabled ? "Active" : "Not enabled"}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() => toggle(key, isEnabled)}
                      className={`px-3 py-1 text-xs rounded ${
                        isEnabled
                          ? "bg-green-100 text-green-700 hover:bg-green-200"
                          : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                      }`}
                    >
                      {isEnabled ? "ON" : "OFF"}
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
