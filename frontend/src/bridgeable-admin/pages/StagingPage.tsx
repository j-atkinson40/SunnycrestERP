import { useEffect, useState } from "react"
import { adminApi } from "../lib/admin-api"

const VERTICALS = ["manufacturing", "funeral_home", "cemetery", "crematory"]

export function StagingCreatePage() {
  const [vertical, setVertical] = useState("manufacturing")
  const [presets, setPresets] = useState<any[]>([])
  const [preset, setPreset] = useState("")
  const [companyName, setCompanyName] = useState("")
  const [creating, setCreating] = useState(false)
  const [result, setResult] = useState<any>(null)

  useEffect(() => {
    adminApi.get("/api/platform/admin/staging/presets").then((r) => {
      setPresets(r.data)
      const first = r.data.find((p: any) => p.vertical === "manufacturing")
      if (first) setPreset(first.key)
    })
  }, [])

  const presetsForVertical = presets.filter((p: any) => p.vertical === vertical)

  const create = async () => {
    setCreating(true)
    setResult(null)
    try {
      const res = await adminApi.post("/api/platform/admin/staging", {
        vertical,
        preset,
        company_name: companyName || null,
      })
      setResult(res.data)
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Failed to create staging tenant")
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="space-y-4 max-w-2xl">
      <h1 className="text-2xl font-semibold text-slate-900">Create Staging Tenant</h1>

      {!result ? (
        <div className="bg-white border border-slate-200 rounded p-6 space-y-4">
          <div>
            <label className="text-xs font-semibold text-slate-700">Vertical</label>
            <div className="flex gap-2 mt-1">
              {VERTICALS.map((v) => (
                <button
                  key={v}
                  onClick={() => {
                    setVertical(v)
                    const first = presets.find((p: any) => p.vertical === v)
                    setPreset(first?.key || "")
                  }}
                  className={`px-3 py-1.5 text-xs rounded ${
                    vertical === v ? "bg-slate-900 text-white" : "bg-slate-100"
                  }`}
                >
                  {v.replace("_", " ")}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700">Preset</label>
            <select
              value={preset}
              onChange={(e) => setPreset(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded text-sm"
            >
              {presetsForVertical.map((p: any) => (
                <option key={p.key} value={p.key}>
                  {p.label} — {p.description}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700">Company name (optional)</label>
            <input
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Auto-generated if blank"
              className="w-full px-3 py-2 border border-slate-300 rounded text-sm"
            />
          </div>

          <button
            onClick={create}
            disabled={creating || !preset}
            className="w-full py-2 bg-slate-900 text-white rounded text-sm hover:bg-slate-800 disabled:opacity-50"
          >
            {creating ? "Creating…" : "Create staging tenant →"}
          </button>
        </div>
      ) : (
        <div className="bg-emerald-50 border border-emerald-200 rounded p-6">
          <h2 className="font-semibold text-emerald-900 mb-2">✓ Staging tenant created</h2>
          <div className="text-sm space-y-1">
            <div><span className="font-medium">Company:</span> {result.company_name}</div>
            <div><span className="font-medium">Slug:</span> {result.tenant_slug}</div>
            <div><span className="font-medium">Login:</span> <a href={result.login_url} target="_blank" rel="noopener noreferrer" className="underline">{result.login_url}</a></div>
          </div>
          <div className="mt-3">
            <h3 className="font-semibold text-emerald-900 text-sm mb-1">Credentials</h3>
            <div className="bg-white border border-emerald-200 rounded p-2 text-xs font-mono space-y-1">
              {(result.users || []).map((u: any) => (
                <div key={u.email}>
                  <span className="text-slate-600">{u.role}:</span> {u.email} / {u.password}
                </div>
              ))}
            </div>
          </div>
          <button
            onClick={() => setResult(null)}
            className="mt-4 px-3 py-1.5 bg-emerald-700 text-white text-sm rounded"
          >
            Create another
          </button>
        </div>
      )}
    </div>
  )
}
