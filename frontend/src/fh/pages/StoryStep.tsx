import { useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { ArrowLeft, Check, Loader2, Sparkles, X } from "lucide-react"
import { fhApi } from "../lib/fh-api"

export default function StoryStep() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const [detail, setDetail] = useState<any>(null)
  const [narrative, setNarrative] = useState<string | null>(null)
  const [compiling, setCompiling] = useState(true)
  const [approving, setApproving] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [showConfirm, setShowConfirm] = useState(false)

  const reload = async () => {
    if (!caseId) return
    const d = await fhApi.getCase(caseId)
    setDetail(d)
    setNarrative(d.case?.story_thread_narrative || null)
    if (!d.case?.story_thread_narrative && d.case?.story_thread_status !== "approved") {
      // Auto-compile on open
      try {
        const r = await fhApi.compileStory(caseId)
        setNarrative(r.narrative)
      } catch {
        /* no key or failure — leave blank */
      }
    }
    setCompiling(false)
  }

  useEffect(() => {
    setCompiling(true)
    reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId])

  const handleApprove = async () => {
    if (!caseId) return
    setApproving(true)
    try {
      const r = await fhApi.approveAll(caseId)
      setResult(r)
    } catch (e: any) {
      alert(e?.response?.data?.detail || "Approval failed")
    } finally {
      setApproving(false)
      setShowConfirm(false)
    }
  }

  if (!detail) return <div className="text-center text-slate-400 py-12">Loading…</div>

  const dec = detail.deceased || {}
  const svc = detail.service || {}
  const merch = detail.merchandise || {}
  const cem = detail.cemetery || {}
  const alreadyApproved = detail.case?.story_thread_status === "approved"
  const deceasedName = [dec.first_name, dec.middle_name, dec.last_name].filter(Boolean).join(" ") || "—"

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-5">
      <Link to={`/fh/cases/${caseId}`} className="flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900">
        <ArrowLeft className="h-4 w-4" /> Case
      </Link>
      <h1 className="text-2xl font-semibold text-slate-900">The Story</h1>
      <p className="text-sm text-slate-500">
        Here is how {dec.first_name || "your loved one"} will be remembered. Review the compiled picture and approve all selections when ready.
      </p>

      {/* Narrative */}
      <div className="bg-gradient-to-br from-amber-50 to-slate-50 border border-amber-200 rounded p-6">
        <div className="flex items-center gap-2 text-xs font-semibold text-amber-700 uppercase tracking-wide mb-3">
          <Sparkles className="h-4 w-4" />
          Narrative
        </div>
        {compiling ? (
          <div className="flex items-center gap-2 text-slate-500 text-sm">
            <Loader2 className="h-4 w-4 animate-spin" />
            Compiling your story...
          </div>
        ) : narrative ? (
          <p className="text-lg text-slate-900 leading-relaxed italic">"{narrative}"</p>
        ) : (
          <p className="text-slate-500 text-sm italic">Narrative not yet compiled.</p>
        )}
      </div>

      {/* Visual compilation */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <SelectionCard
          title="Vault"
          present={!!merch.vault_product_name}
          value={merch.vault_product_name}
          subtitle={merch.vault_approved_at ? "Approved" : "Selected"}
          onChange={() => navigate(`/fh/cases/${caseId}/vault-selection`)}
        />
        <SelectionCard
          title="Casket"
          present={!!merch.casket_product_name}
          value={merch.casket_product_name}
          subtitle={merch.casket_approved_at ? "Approved" : "Selected"}
          onChange={() => navigate(`/fh/cases/${caseId}/casket-selection`)}
        />
        <SelectionCard
          title="Monument"
          present={!!merch.monument_shape}
          value={merch.monument_shape ? `${_title(merch.monument_shape)} in ${_title(merch.monument_stone || "standard")}` : null}
          subtitle={merch.monument_approved_at ? "Approved" : "Selected"}
          onChange={() => navigate(`/fh/cases/${caseId}/monument-selection`)}
        />
        <SelectionCard
          title="Cemetery"
          present={!!cem?.cemetery_name || !!cem?.plot_number}
          value={cem?.cemetery_name ? `${cem.cemetery_name}${cem.plot_number ? ` · ${cem.section}-${cem.row}-${cem.plot_number}` : ""}` : null}
          onChange={() => navigate(`/fh/cases/${caseId}/cemetery`)}
        />
        <SelectionCard
          title="Service"
          present={!!svc.service_date}
          value={svc.service_date ? _formatDate(svc.service_date) + (svc.service_location_name ? ` · ${svc.service_location_name}` : "") : null}
          onChange={() => navigate(`/fh/cases/${caseId}/service-planning`)}
        />
        <SelectionCard
          title="For"
          present={!!dec.first_name}
          value={deceasedName}
          subtitle={dec.religion || (detail.veteran?.ever_in_armed_forces ? "Veteran" : undefined)}
          onChange={() => navigate(`/fh/cases/${caseId}/vital-statistics`)}
        />
      </div>

      {/* Approve All */}
      {!alreadyApproved && !result ? (
        <button
          onClick={() => setShowConfirm(true)}
          className="w-full bg-slate-900 text-white rounded-lg py-4 text-base font-medium hover:bg-slate-800 disabled:opacity-60"
          disabled={approving}
        >
          Approve all selections →
        </button>
      ) : null}

      {alreadyApproved && !result && (
        <div className="bg-emerald-50 border border-emerald-200 rounded p-4 text-sm">
          <div className="flex items-center gap-2 text-emerald-900 font-medium">
            <Check className="h-4 w-4" /> All selections approved
          </div>
          <div className="text-emerald-800 mt-1">
            Approved at {detail.case?.all_selections_approved_at ? new Date(detail.case.all_selections_approved_at).toLocaleString() : "—"}
          </div>
        </div>
      )}

      {/* Confirmation dialog */}
      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold">Approve all selections</h2>
              <button onClick={() => setShowConfirm(false)}>
                <X className="h-4 w-4 text-slate-400" />
              </button>
            </div>
            <p className="text-sm text-slate-600 mb-3">When you approve, the following will happen:</p>
            <ul className="text-sm text-slate-700 space-y-1.5 mb-4">
              {merch.vault_product_name && detail.case?.vault_manufacturer_company_id && (
                <li>✓ Vault order sent to manufacturer</li>
              )}
              {cem?.plot_id && <li>✓ Cemetery plot reserved + paid</li>}
              {merch.monument_shape && <li>✓ Monument order logged</li>}
              <li>✓ Legacy Vault Print generated</li>
            </ul>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowConfirm(false)} className="px-3 py-1.5 text-slate-600 text-sm">
                Cancel
              </button>
              <button
                onClick={handleApprove}
                disabled={approving}
                className="px-4 py-2 bg-slate-900 text-white text-sm rounded disabled:opacity-60 flex items-center gap-2"
              >
                {approving && <Loader2 className="h-4 w-4 animate-spin" />}
                Approve all
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Result summary */}
      {result && <ApprovalResult result={result} caseId={caseId!} />}
    </div>
  )
}

function SelectionCard({
  title,
  present,
  value,
  subtitle,
  onChange,
}: {
  title: string
  present: boolean
  value: string | null | undefined
  subtitle?: string
  onChange: () => void
}) {
  return (
    <div className={`bg-white border rounded p-4 ${present ? "border-slate-200" : "border-dashed border-slate-300"}`}>
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-xs font-semibold text-slate-600 uppercase tracking-wide">{title}</h3>
        <button onClick={onChange} className="text-xs text-slate-500 hover:text-slate-900">
          Change
        </button>
      </div>
      <div className={`text-sm ${present ? "font-medium text-slate-900" : "text-slate-400 italic"}`}>
        {value || "Not selected"}
      </div>
      {subtitle && <div className="text-xs text-slate-500 mt-0.5">{subtitle}</div>}
    </div>
  )
}

function ApprovalResult({ result, caseId }: { result: any; caseId: string }) {
  return (
    <div className="bg-white border border-slate-200 rounded p-5 space-y-3">
      <h3 className="font-semibold text-slate-900">Approval complete</h3>
      <ResultRow label="Vault order" data={result.vault_order} />
      <ResultRow label="Cemetery reservation" data={result.cemetery_reservation} />
      <ResultRow label="Monument order" data={result.monument_order} />
      <ResultRow label="Legacy Vault Print" data={result.legacy_print} />

      {result.legacy_print?.url && (
        <a
          href={result.legacy_print.url}
          target="_blank"
          rel="noopener noreferrer"
          className="block text-sm text-blue-600 underline mt-2"
        >
          View Legacy Vault Print PDF →
        </a>
      )}

      <div className="pt-2 border-t border-slate-100">
        <Link
          to={`/fh/cases/${caseId}`}
          className="text-sm text-slate-700 hover:text-slate-900"
        >
          ← Back to case
        </Link>
      </div>
    </div>
  )
}

function ResultRow({ label, data }: { label: string; data: any }) {
  if (!data) return null
  const status = data.status
  const color =
    status === "ordered" || status === "sold" || status === "generated" || status === "logged"
      ? "text-emerald-700"
      : status === "manual" || status === "not_applicable"
        ? "text-slate-500"
        : "text-red-600"
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="font-medium w-48">{label}:</span>
      <span className={color}>{status}</span>
      {data.order_number && <span className="text-xs text-slate-500">({data.order_number})</span>}
      {data.manufacturer_name && <span className="text-xs text-slate-500">→ {data.manufacturer_name}</span>}
      {data.error && <span className="text-xs text-red-500">{data.error}</span>}
    </div>
  )
}

function _formatDate(iso: string): string {
  try {
    return new Date(iso + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
  } catch {
    return iso
  }
}

function _title(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}
