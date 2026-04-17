import { useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { ArrowLeft, Check, Eye, EyeOff } from "lucide-react"
import { fhApi, type StaircaseStep } from "../lib/fh-api"

export default function CaseDashboard() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const [detail, setDetail] = useState<any>(null)
  const [staircase, setStaircase] = useState<StaircaseStep[]>([])
  const [loading, setLoading] = useState(true)
  const [showSsn, setShowSsn] = useState(false)

  useEffect(() => {
    if (!caseId) return
    Promise.all([fhApi.getCase(caseId, showSsn), fhApi.getStaircase(caseId)])
      .then(([d, s]) => {
        setDetail(d)
        setStaircase(s)
      })
      .finally(() => setLoading(false))
  }, [caseId, showSsn])

  // Auto-mask SSN after 10s
  useEffect(() => {
    if (!showSsn) return
    const t = setTimeout(() => setShowSsn(false), 10000)
    return () => clearTimeout(t)
  }, [showSsn])

  if (loading || !detail) {
    return <div className="text-center text-slate-400 py-12">Loading case…</div>
  }

  const { case: caseData, deceased, service, disposition, cemetery, veteran, merchandise, financials, informants } = detail
  const currentStep = staircase.find((s) => s.is_current)

  const continueToCurrentStep = () => {
    if (!currentStep) return
    const stepToRoute: Record<string, string> = {
      arrangement_conference: `/fh/cases/${caseId}/arrangement`,
      vital_statistics: `/fh/cases/${caseId}/vital-statistics`,
      authorization: `/fh/cases/${caseId}/authorization`,
      service_planning: `/fh/cases/${caseId}/service-planning`,
      obituary: `/fh/cases/${caseId}/service-planning`,
      merchandise_vault: `/fh/cases/${caseId}/vault-selection`,
      merchandise_casket: `/fh/cases/${caseId}/casket-selection`,
      merchandise_monument: `/fh/cases/${caseId}/monument-selection`,
      merchandise_urn: `/fh/cases/${caseId}/urn-selection`,
      story: `/fh/cases/${caseId}/story`,
      cemetery: `/fh/cases/${caseId}/cemetery`,
      cremation: `/fh/cases/${caseId}/cremation`,
      veterans_benefits: `/fh/cases/${caseId}/veterans`,
      death_certificate: `/fh/cases/${caseId}/death-certificate`,
      financials: `/fh/cases/${caseId}/financials`,
      aftercare: `/fh/cases/${caseId}/aftercare`,
    }
    navigate(stepToRoute[currentStep.key] || `/fh/cases/${caseId}`)
  }

  const deceasedFullName = deceased
    ? [deceased.first_name, deceased.middle_name, deceased.last_name, deceased.suffix].filter(Boolean).join(" ")
    : caseData.case_number

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-5">
      <div className="flex items-center justify-between text-sm">
        <Link to="/fh/cases" className="flex items-center gap-1 text-slate-600 hover:text-slate-900">
          <ArrowLeft className="h-4 w-4" /> Cases
        </Link>
        <span className="font-mono text-slate-500">{caseData.case_number}</span>
      </div>

      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 uppercase">{deceasedFullName}</h1>
        {deceased && (
          <div className="text-sm text-slate-600 mt-1">
            {deceased.date_of_birth && `Born ${_formatDate(deceased.date_of_birth)}`}
            {deceased.date_of_death && ` — Died ${_formatDate(deceased.date_of_death)}`}
          </div>
        )}
        <div className="text-sm text-slate-500 mt-1">
          Day {caseData.days_open} of arrangement
        </div>
      </div>

      {/* Staircase */}
      <div className="bg-white border border-slate-200 rounded p-4">
        <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">The Staircase</h2>
        <div className="flex flex-wrap items-center gap-1 text-xs mb-4">
          {staircase.map((s, i) => (
            <div key={s.key} className="flex items-center">
              <span
                className={`px-2 py-1 rounded ${
                  s.status === "completed"
                    ? "bg-green-100 text-green-800"
                    : s.is_current
                      ? "bg-slate-900 text-white font-medium"
                      : "bg-slate-100 text-slate-500"
                }`}
              >
                {s.status === "completed" && <Check className="inline h-3 w-3 mr-1" />}
                {s.is_current && "→ "}
                {s.name}
              </span>
              {i < staircase.length - 1 && <span className="text-slate-300 mx-0.5">·</span>}
            </div>
          ))}
        </div>
        {currentStep && (
          <button
            onClick={continueToCurrentStep}
            className="w-full bg-slate-900 text-white rounded py-3 text-base font-medium hover:bg-slate-800"
          >
            Continue: {currentStep.name} →
          </button>
        )}
      </div>

      {/* Domain Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {/* Deceased */}
        {deceased && (
          <DomainCard
            title="Deceased"
            linkTo={`/fh/cases/${caseId}/vital-statistics`}
          >
            <Field label="Name" value={deceasedFullName} />
            {deceased.date_of_birth && <Field label="DOB" value={_formatDate(deceased.date_of_birth)} />}
            <div className="text-sm flex items-center gap-2">
              <span className="text-slate-500">SSN:</span>
              <span className="font-mono">{showSsn && deceased.ssn_plaintext ? _formatSsn(deceased.ssn_plaintext) : deceased.ssn_display}</span>
              <button
                onClick={() => setShowSsn(!showSsn)}
                className="text-slate-400 hover:text-slate-700"
                title={showSsn ? "Hide SSN" : "Show SSN (10s)"}
              >
                {showSsn ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </button>
            </div>
            {veteran?.ever_in_armed_forces && (
              <Field label="Veteran" value="Yes ✓" valueClass="text-green-700" />
            )}
          </DomainCard>
        )}

        {/* Service */}
        {service && (
          <DomainCard title="Service" linkTo={`/fh/cases/${caseId}/service-planning`}>
            {service.service_date ? (
              <Field label="Date" value={_formatDate(service.service_date) + (service.service_time ? ` ${_formatTime(service.service_time)}` : "")} />
            ) : (
              <div className="text-sm text-slate-400">Not scheduled</div>
            )}
            {service.service_location_name && <Field label="Where" value={service.service_location_name} />}
            {service.officiant_name && <Field label="Officiant" value={service.officiant_name} />}
          </DomainCard>
        )}

        {/* Informants / Family */}
        <DomainCard title="Family" linkTo={`/fh/cases/${caseId}/authorization`}>
          {informants && informants.length > 0 ? (
            <>
              {informants.slice(0, 2).map((i: any) => (
                <Field
                  key={i.id}
                  label={i.relationship || "Informant"}
                  value={i.name + (i.phone ? ` · ${i.phone}` : "")}
                />
              ))}
              {informants.some((i: any) => i.is_authorizing) && (
                <Field
                  label="Auth"
                  value={informants.find((i: any) => i.is_authorizing)?.authorization_signed_at ? "Signed ✓" : "Not signed"}
                  valueClass={
                    informants.find((i: any) => i.is_authorizing)?.authorization_signed_at
                      ? "text-green-700"
                      : "text-amber-700"
                  }
                />
              )}
            </>
          ) : (
            <div className="text-sm text-slate-400">No informants yet</div>
          )}
        </DomainCard>

        {/* Merchandise */}
        {merchandise && (
          <DomainCard title="Merchandise" linkTo={`/fh/cases/${caseId}/vault-selection`}>
            {merchandise.vault_product_name && (
              <Field
                label="Vault"
                value={merchandise.vault_product_name + (merchandise.vault_approved_at ? " ✓" : " · Pending")}
              />
            )}
            {merchandise.casket_product_name && (
              <Field
                label="Casket"
                value={merchandise.casket_product_name + (merchandise.casket_approved_at ? " ✓" : " · Pending")}
              />
            )}
            {merchandise.monument_shape && (
              <Field
                label="Monument"
                value={`${merchandise.monument_shape}${merchandise.monument_approved_at ? " ✓" : ""}`}
              />
            )}
            {!merchandise.vault_product_name && !merchandise.casket_product_name && !merchandise.monument_shape && (
              <div className="text-sm text-slate-400">Not yet selected</div>
            )}
          </DomainCard>
        )}

        {/* Disposition */}
        {disposition && (
          <DomainCard title="Disposition" linkTo={`/fh/cases/${caseId}/cemetery`}>
            {disposition.disposition_type ? (
              <>
                <Field label="Type" value={_titleCase(disposition.disposition_type)} />
                {cemetery?.cemetery_name && <Field label="Cemetery" value={cemetery.cemetery_name} />}
                <Field
                  label="DC"
                  value={disposition.death_certificate_status === "filed" ? "Filed ✓" : "Not filed"}
                  valueClass={disposition.death_certificate_status === "filed" ? "text-green-700" : "text-amber-700"}
                />
              </>
            ) : (
              <div className="text-sm text-slate-400">Not yet set</div>
            )}
          </DomainCard>
        )}

        {/* Financials */}
        {financials && (
          <DomainCard title="Financials" linkTo={`/fh/cases/${caseId}/financials`}>
            <Field label="Total" value={`$${Number(financials.total || 0).toLocaleString()}`} />
            <Field label="Paid" value={`$${Number(financials.amount_paid || 0).toLocaleString()}`} />
            <Field label="Balance" value={`$${Number(financials.balance_due || 0).toLocaleString()}`} />
          </DomainCard>
        )}

        {/* Veteran (only if veteran) */}
        {veteran?.ever_in_armed_forces && (
          <DomainCard title="Veteran" linkTo={`/fh/cases/${caseId}/veterans`}>
            {veteran.branch && <Field label="Branch" value={_titleCase(veteran.branch)} />}
            <Field
              label="VA Flag"
              value={veteran.va_flag_requested ? "Requested" : "—"}
              valueClass={veteran.va_flag_requested ? "text-slate-900" : "text-slate-400"}
            />
            <Field
              label="DD-214"
              value={veteran.dd214_on_file ? "On file ✓" : "Missing"}
              valueClass={veteran.dd214_on_file ? "text-green-700" : "text-amber-700"}
            />
          </DomainCard>
        )}
      </div>
    </div>
  )
}

function DomainCard({
  title,
  linkTo,
  children,
}: {
  title: string
  linkTo?: string
  children: React.ReactNode
}) {
  return (
    <div className="bg-white border border-slate-200 rounded p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-semibold text-slate-600 uppercase tracking-wide">{title}</h3>
        {linkTo && (
          <Link to={linkTo} className="text-xs text-slate-500 hover:text-slate-900">
            Edit
          </Link>
        )}
      </div>
      <div className="space-y-1">{children}</div>
    </div>
  )
}

function Field({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="text-sm flex items-baseline gap-2">
      <span className="text-slate-500 text-xs w-20 flex-shrink-0">{label}:</span>
      <span className={valueClass || "text-slate-900"}>{value}</span>
    </div>
  )
}

function _formatDate(iso: string): string {
  try {
    return new Date(iso + "T00:00:00").toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    })
  } catch {
    return iso
  }
}

function _formatTime(t: string): string {
  const [hh, mm] = t.split(":")
  const h = parseInt(hh, 10)
  const ampm = h >= 12 ? "pm" : "am"
  const h12 = h % 12 || 12
  return `${h12}:${mm}${ampm}`
}

function _formatSsn(s: string): string {
  const d = s.replace(/\D/g, "")
  if (d.length !== 9) return s
  return `${d.slice(0, 3)}-${d.slice(3, 5)}-${d.slice(5)}`
}

function _titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}
