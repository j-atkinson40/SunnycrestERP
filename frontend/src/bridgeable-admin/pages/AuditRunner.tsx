import { useEffect, useRef, useState } from "react"
import { Play, CheckCircle2, XCircle } from "lucide-react"
import { adminApi } from "../lib/admin-api"

const VERTICALS = ["manufacturing", "funeral_home", "cemetery", "crematory"]
const FEATURES = [
  "vault_migration",
  "core_ui",
  "multi_location",
  "manufacturing_onboarding",
  "wilbert_programs",
  "personalization_config",
  "authentication",
  "order_management",
  "crm",
  "scheduling_board",
  "compliance_hub",
  "invoicing",
  "vault_api",
]

export function AuditRunner() {
  const [scope, setScope] = useState<"all" | "vertical" | "feature" | "tenant">("all")
  const [scopeValue, setScopeValue] = useState<string>("")
  const [environment, setEnvironment] = useState<"staging" | "production">("staging")
  const [running, setRunning] = useState(false)
  const [lines, setLines] = useState<string[]>([])
  const [result, setResult] = useState<any>(null)
  const [history, setHistory] = useState<any[]>([])
  const outputRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    adminApi.get("/api/platform/admin/audit/history").then((r) => setHistory(r.data))
  }, [result])

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight
    }
  }, [lines])

  const runAudit = async () => {
    setRunning(true)
    setLines([])
    setResult(null)
    try {
      const res = await adminApi.post("/api/platform/admin/audit/run", {
        scope,
        scope_value: scopeValue || null,
        environment,
      })
      setResult(res.data)
      setLines((prev) => [...prev, `\n=== COMPLETE: ${res.data.status} ===`])
    } catch (err: any) {
      setLines((prev) => [...prev, `ERROR: ${err.message}`])
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-slate-900">Audit Runner</h1>

      <div className="bg-white border border-slate-200 rounded p-4 space-y-4">
        <div>
          <label className="text-xs font-semibold text-slate-700">Scope</label>
          <div className="flex gap-2 mt-1">
            {(["all", "vertical", "feature", "tenant"] as const).map((s) => (
              <button
                key={s}
                onClick={() => {
                  setScope(s)
                  setScopeValue("")
                }}
                className={`px-3 py-1.5 text-xs rounded ${
                  scope === s ? "bg-slate-900 text-white" : "bg-slate-100"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {scope === "vertical" && (
          <select
            value={scopeValue}
            onChange={(e) => setScopeValue(e.target.value)}
            className="w-full px-3 py-2 border border-slate-300 rounded text-sm"
          >
            <option value="">Select vertical…</option>
            {VERTICALS.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        )}
        {scope === "feature" && (
          <select
            value={scopeValue}
            onChange={(e) => setScopeValue(e.target.value)}
            className="w-full px-3 py-2 border border-slate-300 rounded text-sm"
          >
            <option value="">Select feature…</option>
            {FEATURES.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        )}
        {scope === "tenant" && (
          <input
            value={scopeValue}
            onChange={(e) => setScopeValue(e.target.value)}
            placeholder="Tenant company_id"
            className="w-full px-3 py-2 border border-slate-300 rounded text-sm"
          />
        )}

        <div>
          <label className="text-xs font-semibold text-slate-700">Environment</label>
          <div className="flex gap-2 mt-1">
            {(["staging", "production"] as const).map((e) => (
              <button
                key={e}
                onClick={() => setEnvironment(e)}
                className={`px-3 py-1.5 text-xs rounded ${
                  environment === e ? (e === "staging" ? "bg-amber-600 text-white" : "bg-slate-900 text-white") : "bg-slate-100"
                }`}
              >
                {e}
              </button>
            ))}
          </div>
          {environment === "production" && (
            <p className="text-xs text-amber-700 mt-1">Production: only @readonly tests will run.</p>
          )}
        </div>

        <button
          onClick={runAudit}
          disabled={running || (scope !== "all" && !scopeValue)}
          className="w-full py-2 bg-slate-900 text-white rounded text-sm hover:bg-slate-800 disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {running ? "Running…" : <><Play className="h-4 w-4" /> Run audit</>}
        </button>
      </div>

      {(lines.length > 0 || result) && (
        <div className="bg-slate-900 text-slate-100 rounded p-4 font-mono text-xs max-h-[400px] overflow-y-auto" ref={outputRef}>
          {lines.length === 0 ? <div className="text-slate-500">Running…</div> : lines.map((l, i) => <div key={i}>{l}</div>)}
          {result && (
            <div className="mt-4 border-t border-slate-700 pt-3">
              <div className={result.status === "passed" ? "text-emerald-300" : "text-red-300"}>
                {result.status === "passed" ? "✓" : "✗"} {result.status} — {result.passed} passed, {result.failed} failed, {result.skipped} skipped ({result.duration_seconds?.toFixed(1)}s)
              </div>
            </div>
          )}
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded overflow-hidden">
        <div className="px-4 py-2 border-b border-slate-200 font-semibold text-sm">Recent audit runs</div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs text-slate-600">
            <tr>
              <th className="text-left px-4 py-2">Scope</th>
              <th className="text-left px-4 py-2">Environment</th>
              <th className="text-left px-4 py-2">Result</th>
              <th className="text-left px-4 py-2">Started</th>
            </tr>
          </thead>
          <tbody>
            {history.map((h) => (
              <tr key={h.id} className="border-t border-slate-100">
                <td className="px-4 py-2">{h.scope}{h.scope_value ? ` / ${h.scope_value}` : ""}</td>
                <td className="px-4 py-2">{h.environment}</td>
                <td className="px-4 py-2 flex items-center gap-1">
                  {h.status === "passed" ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> : <XCircle className="h-3.5 w-3.5 text-red-500" />}
                  {h.passed || 0}/{h.total_tests || 0}
                </td>
                <td className="px-4 py-2 text-slate-500">{h.started_at?.slice(0, 19).replace("T", " ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
