import { useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { ArrowLeft, MapPin, Check } from "lucide-react"
import { fhApi } from "../lib/fh-api"
import { CemeteryPlotMap, type PlotData } from "../components/CemeteryPlotMap"

export default function CemeteryStep() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const [detail, setDetail] = useState<any>(null)
  const [selectedPlot, setSelectedPlot] = useState<PlotData | null>(null)
  const [reserving, setReserving] = useState(false)
  const [reserved, setReserved] = useState(false)

  useEffect(() => {
    if (!caseId) return
    fhApi.getCase(caseId).then(setDetail)
  }, [caseId])

  if (!caseId || !detail) {
    return <div className="text-center text-slate-400 py-12">Loading…</div>
  }

  const cemeteryCompanyId = detail.case?.cemetery_company_id
  const existingPlot = detail.cemetery?.plot_number

  const handleReserve = async () => {
    if (!selectedPlot) return
    if (!confirm(`Reserve ${selectedPlot.plot_label} and process payment?\n\nThis simulates a demo payment in Phase 1.`)) return
    setReserving(true)
    try {
      // Reserve first, then complete the payment (Phase 1 demo flow)
      await fhApi.reservePlot(selectedPlot.id, caseId)
      await fhApi.completePlotPayment(selectedPlot.id, caseId)
      setReserved(true)
      // Advance staircase
      await fhApi.advanceStep(caseId, "cemetery")
    } catch (e: any) {
      alert(e?.response?.data?.detail || "Reservation failed")
    } finally {
      setReserving(false)
    }
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-4">
      <Link to={`/fh/cases/${caseId}`} className="flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900">
        <ArrowLeft className="h-4 w-4" /> Case
      </Link>
      <h1 className="text-2xl font-semibold text-slate-900">Cemetery</h1>

      {reserved && (
        <div className="bg-emerald-50 border border-emerald-200 rounded p-4 flex items-start gap-2">
          <Check className="h-5 w-5 text-emerald-700 flex-shrink-0" />
          <div>
            <div className="font-medium text-emerald-900">Plot reserved</div>
            <div className="text-sm text-emerald-800">
              {selectedPlot?.plot_label} is now reserved for this case. Payment processed (demo).
            </div>
            <button
              onClick={() => navigate(`/fh/cases/${caseId}`)}
              className="mt-2 px-3 py-1.5 bg-emerald-700 text-white text-sm rounded"
            >
              Back to case →
            </button>
          </div>
        </div>
      )}

      {existingPlot && !reserved && (
        <div className="bg-slate-100 border border-slate-200 rounded p-3 text-sm">
          <span className="text-slate-600">Current plot:</span>{" "}
          <span className="font-medium">
            {detail.cemetery.section}-{detail.cemetery.row}-{existingPlot}
          </span>
          {detail.cemetery.cemetery_name && (
            <>
              {" · "}
              <span>{detail.cemetery.cemetery_name}</span>
            </>
          )}
        </div>
      )}

      {cemeteryCompanyId ? (
        <>
          <p className="text-sm text-slate-600">
            Interactive plot map. Click an available (green) plot to select it.
          </p>
          <CemeteryPlotMap
            cemeteryCompanyId={cemeteryCompanyId}
            mode="select"
            caseId={caseId}
            onPlotSelected={(p) => setSelectedPlot(p)}
          />

          {selectedPlot && !reserved && (
            <div className="bg-white border-2 border-slate-900 rounded p-4 flex items-center justify-between">
              <div>
                <div className="text-xs text-slate-500 uppercase">Selected plot</div>
                <div className="text-lg font-semibold">{selectedPlot.plot_label}</div>
                <div className="text-sm text-slate-600">
                  {selectedPlot.plot_type.replace(/_/g, " ")}
                  {selectedPlot.price ? ` · $${(selectedPlot.price + (selectedPlot.opening_closing_fee || 0)).toLocaleString()} total` : ""}
                </div>
              </div>
              <button
                onClick={handleReserve}
                disabled={reserving}
                className="bg-slate-900 text-white rounded px-5 py-2.5 font-medium hover:bg-slate-800 disabled:opacity-60"
              >
                {reserving ? "Reserving…" : "Reserve and pay"}
              </button>
            </div>
          )}
        </>
      ) : (
        <ManualEntryFallback caseId={caseId} detail={detail} onSaved={() => window.location.reload()} />
      )}
    </div>
  )
}

function ManualEntryFallback({ caseId, detail, onSaved }: { caseId: string; detail: any; onSaved: () => void }) {
  const [form, setForm] = useState({
    cemetery_name: detail.cemetery?.cemetery_name || "",
    section: detail.cemetery?.section || "",
    row: detail.cemetery?.row || "",
    plot_number: detail.cemetery?.plot_number || "",
  })
  const [saving, setSaving] = useState(false)

  const save = async () => {
    setSaving(true)
    try {
      // case_cemetery doesn't have a direct PATCH endpoint yet — store via notes for now
      await fhApi.addNote(
        caseId,
        `Cemetery info (manual entry): ${form.cemetery_name}, Section ${form.section}-${form.row}-${form.plot_number}`,
        "general",
      )
      await fhApi.advanceStep(caseId, "cemetery")
      onSaved()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="bg-amber-50 border border-amber-200 rounded p-4 space-y-3">
      <div className="flex items-start gap-2">
        <MapPin className="h-5 w-5 text-amber-700 mt-0.5" />
        <div>
          <div className="font-medium text-amber-900">No cemetery connection</div>
          <div className="text-sm text-amber-800">
            Enter the cemetery details manually, or connect to a cemetery in Settings → Network.
          </div>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <input
          value={form.cemetery_name}
          onChange={(e) => setForm({ ...form, cemetery_name: e.target.value })}
          placeholder="Cemetery name"
          className="px-2 py-1.5 border border-amber-200 rounded text-sm"
        />
        <input
          value={form.section}
          onChange={(e) => setForm({ ...form, section: e.target.value })}
          placeholder="Section"
          className="px-2 py-1.5 border border-amber-200 rounded text-sm"
        />
        <input
          value={form.row}
          onChange={(e) => setForm({ ...form, row: e.target.value })}
          placeholder="Row"
          className="px-2 py-1.5 border border-amber-200 rounded text-sm"
        />
        <input
          value={form.plot_number}
          onChange={(e) => setForm({ ...form, plot_number: e.target.value })}
          placeholder="Plot #"
          className="px-2 py-1.5 border border-amber-200 rounded text-sm"
        />
      </div>
      <button
        onClick={save}
        disabled={saving || !form.cemetery_name}
        className="bg-slate-900 text-white rounded px-4 py-2 text-sm hover:bg-slate-800 disabled:opacity-60"
      >
        {saving ? "Saving…" : "Save and advance"}
      </button>
    </div>
  )
}
