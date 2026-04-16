import { useEffect, useState } from "react"
import { adminApi } from "../lib/admin-api"

const VERTICALS = ["manufacturing", "funeral_home", "cemetery", "crematory", "all"]

export function DeploymentsPage() {
  const [deployments, setDeployments] = useState<any[]>([])
  const [showLog, setShowLog] = useState(false)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    adminApi
      .get("/api/platform/admin/deployments?limit=50")
      .then((r) => setDeployments(r.data))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Deployments</h1>
        <button
          onClick={() => setShowLog(true)}
          className="px-3 py-1.5 bg-slate-900 text-white text-sm rounded hover:bg-slate-800"
        >
          Log deployment
        </button>
      </div>

      {showLog && <LogDeploymentModal onClose={() => setShowLog(false)} onSaved={load} />}

      <div className="bg-white border border-slate-200 rounded overflow-hidden">
        {loading ? (
          <div className="p-6 text-center text-slate-400">Loading…</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs text-slate-600">
              <tr>
                <th className="text-left px-4 py-2">Description</th>
                <th className="text-left px-4 py-2">Verticals</th>
                <th className="text-left px-4 py-2">Commit</th>
                <th className="text-left px-4 py-2">Deployed</th>
                <th className="text-left px-4 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {deployments.map((d) => (
                <tr key={d.id} className="border-t border-slate-100">
                  <td className="px-4 py-2">{d.description}</td>
                  <td className="px-4 py-2 text-slate-600">{(d.affected_verticals || []).join(", ")}</td>
                  <td className="px-4 py-2 font-mono text-xs text-slate-500">{d.git_commit?.slice(0, 7) || "—"}</td>
                  <td className="px-4 py-2 text-slate-500">{d.deployed_at?.slice(0, 19).replace("T", " ")}</td>
                  <td className="px-4 py-2">
                    {d.is_tested ? (
                      <span className="text-xs text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">✓ Tested</span>
                    ) : (
                      <span className="text-xs text-amber-700 bg-amber-50 px-2 py-0.5 rounded">⚠ Untested</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function LogDeploymentModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [description, setDescription] = useState("")
  const [verticals, setVerticals] = useState<string[]>(["manufacturing"])
  const [gitCommit, setGitCommit] = useState("")
  const [saving, setSaving] = useState(false)

  const save = async () => {
    setSaving(true)
    try {
      await adminApi.post("/api/platform/admin/deployments", {
        description,
        affected_verticals: verticals,
        git_commit: gitCommit || null,
      })
      onSaved()
      onClose()
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Failed to log deployment")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold mb-4">Log deployment</h2>
        <div className="space-y-3">
          <div>
            <label className="text-xs font-semibold text-slate-700">Description</label>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Vault migration + Core UI"
              className="w-full px-3 py-2 border border-slate-300 rounded text-sm"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-700">Affected verticals</label>
            <div className="flex flex-wrap gap-2 mt-1">
              {VERTICALS.map((v) => (
                <label key={v} className="flex items-center gap-1 text-xs">
                  <input
                    type="checkbox"
                    checked={verticals.includes(v)}
                    onChange={(e) => {
                      if (e.target.checked) setVerticals([...verticals, v])
                      else setVerticals(verticals.filter((x) => x !== v))
                    }}
                  />
                  {v}
                </label>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-700">Git commit (optional)</label>
            <input
              value={gitCommit}
              onChange={(e) => setGitCommit(e.target.value)}
              placeholder="abc1234"
              className="w-full px-3 py-2 border border-slate-300 rounded text-sm font-mono"
            />
          </div>
          <div className="flex gap-2 justify-end">
            <button onClick={onClose} className="px-3 py-1.5 text-sm text-slate-600">Cancel</button>
            <button
              onClick={save}
              disabled={saving || !description || verticals.length === 0}
              className="px-3 py-1.5 bg-slate-900 text-white text-sm rounded disabled:opacity-50"
            >
              {saving ? "Saving…" : "Log deployment"}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
