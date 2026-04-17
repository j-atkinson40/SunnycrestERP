import { useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { ArrowLeft, Check, Loader2 } from "lucide-react"
import { fhApi } from "../lib/fh-api"

export default function VitalStatistics() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const [form, setForm] = useState<Record<string, any>>({})
  const [confidence, setConfidence] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [ssn, setSsn] = useState("")

  useEffect(() => {
    if (!caseId) return
    fhApi
      .getCase(caseId)
      .then((d) => {
        const dec = d.deceased || {}
        setForm({
          first_name: dec.first_name || "",
          middle_name: dec.middle_name || "",
          last_name: dec.last_name || "",
          suffix: dec.suffix || "",
          date_of_birth: dec.date_of_birth || "",
          date_of_death: dec.date_of_death || "",
          sex: dec.sex || "",
          religion: dec.religion || "",
          occupation: dec.occupation || "",
          marital_status: dec.marital_status || "",
          place_of_death_name: dec.place_of_death_name || "",
          residence_city: dec.residence_city || "",
          residence_state: dec.residence_state || "",
          father_name: dec.father_name || "",
          mother_maiden_name: dec.mother_maiden_name || "",
          spouse_name: dec.spouse_name || "",
        })
        // Confidence would come from field_confidence on the record — here we read the payload
        setConfidence({})
      })
      .finally(() => setLoading(false))
  }, [caseId])

  const set = (k: string, v: any) => setForm((f) => ({ ...f, [k]: v }))

  const save = async (advance = false) => {
    if (!caseId) return
    setSaving(true)
    try {
      const payload: any = {}
      for (const [k, v] of Object.entries(form)) {
        if (v !== undefined && v !== "") payload[k] = v
      }
      if (ssn) payload.ssn = ssn
      await fhApi.updateDeceased(caseId, payload)
      if (advance) {
        await fhApi.advanceStep(caseId, "vital_statistics")
        navigate(`/fh/cases/${caseId}`)
      } else {
        alert("Saved")
      }
    } catch (e: any) {
      alert(e?.response?.data?.detail || "Failed to save")
    } finally {
      setSaving(false)
    }
  }

  const requiredMissing = () => {
    const req = ["first_name", "last_name", "date_of_death"]
    return req.filter((k) => !form[k])
  }

  if (loading) return <div className="text-center text-slate-400 py-12">Loading…</div>

  const missing = requiredMissing()
  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
      <Link to={`/fh/cases/${caseId}`} className="flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900">
        <ArrowLeft className="h-4 w-4" /> Case
      </Link>
      <h1 className="text-2xl font-semibold text-slate-900">Vital Statistics</h1>
      <p className="text-sm text-slate-500">
        Review and complete the deceased's vital information. Required fields must be filled to advance.
      </p>

      <div className="bg-white border border-slate-200 rounded p-5 space-y-4">
        <h2 className="text-sm font-semibold">Name</h2>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="First name *" value={form.first_name} onChange={(v) => set("first_name", v)} confidence={confidence["first_name"]} required />
          <TextField label="Middle name" value={form.middle_name} onChange={(v) => set("middle_name", v)} />
          <TextField label="Last name *" value={form.last_name} onChange={(v) => set("last_name", v)} confidence={confidence["last_name"]} required />
          <TextField label="Suffix" value={form.suffix} onChange={(v) => set("suffix", v)} />
        </div>

        <h2 className="text-sm font-semibold pt-2 border-t border-slate-100">Demographics</h2>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Date of birth" type="date" value={form.date_of_birth} onChange={(v) => set("date_of_birth", v)} />
          <TextField label="Date of death *" type="date" value={form.date_of_death} onChange={(v) => set("date_of_death", v)} required />
          <SelectField label="Sex" value={form.sex} onChange={(v) => set("sex", v)} options={["male", "female", "other"]} />
          <SelectField label="Marital status" value={form.marital_status} onChange={(v) => set("marital_status", v)} options={["single", "married", "widowed", "divorced"]} />
          <TextField label="Religion" value={form.religion} onChange={(v) => set("religion", v)} />
          <TextField label="Occupation" value={form.occupation} onChange={(v) => set("occupation", v)} />
          <TextField label="Place of death" value={form.place_of_death_name} onChange={(v) => set("place_of_death_name", v)} />
          <TextField label="Residence city" value={form.residence_city} onChange={(v) => set("residence_city", v)} />
        </div>

        <h2 className="text-sm font-semibold pt-2 border-t border-slate-100">SSN</h2>
        <div>
          <label className="text-xs text-slate-600">SSN (encrypted at rest)</label>
          <input
            type="password"
            value={ssn}
            onChange={(e) => setSsn(e.target.value)}
            placeholder="•••-••-••••"
            className="w-48 mt-0.5 px-2 py-1.5 border border-slate-200 rounded text-sm outline-none focus:border-slate-500 font-mono"
          />
          <p className="text-xs text-slate-500 mt-1">
            Leave blank to keep the existing SSN unchanged.
          </p>
        </div>

        <h2 className="text-sm font-semibold pt-2 border-t border-slate-100">Parents / Spouse</h2>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Father's name" value={form.father_name} onChange={(v) => set("father_name", v)} />
          <TextField label="Mother's maiden name" value={form.mother_maiden_name} onChange={(v) => set("mother_maiden_name", v)} />
          <TextField label="Spouse name" value={form.spouse_name} onChange={(v) => set("spouse_name", v)} />
        </div>

        {missing.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded p-3 text-sm text-amber-900">
            Required fields missing: {missing.join(", ")}
          </div>
        )}

        <div className="flex gap-3 pt-2">
          <button
            onClick={() => save(false)}
            disabled={saving}
            className="flex-1 bg-slate-100 text-slate-900 rounded py-2 text-sm hover:bg-slate-200 disabled:opacity-60"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin inline" /> : "Save"}
          </button>
          <button
            onClick={() => save(true)}
            disabled={saving || missing.length > 0}
            className="flex-1 bg-slate-900 text-white rounded py-2 text-sm hover:bg-slate-800 disabled:opacity-60 flex items-center justify-center gap-2"
          >
            <Check className="h-4 w-4" /> Save + advance
          </button>
        </div>
      </div>
    </div>
  )
}

function TextField({
  label,
  value,
  onChange,
  type = "text",
  required,
  confidence,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  type?: string
  required?: boolean
  confidence?: number
}) {
  const dotColor =
    confidence !== undefined
      ? confidence >= 0.9
        ? "bg-green-500"
        : confidence >= 0.7
          ? "bg-amber-500"
          : "bg-slate-300"
      : value
        ? "bg-green-500"
        : required
          ? "bg-red-400"
          : "bg-slate-300"

  return (
    <div>
      <label className="text-xs text-slate-600 flex items-center gap-2">
        <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />
        {label}
      </label>
      <input
        type={type}
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        className="w-full mt-0.5 px-2 py-1.5 border border-slate-200 rounded text-sm outline-none focus:border-slate-500"
      />
    </div>
  )
}

function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  options: string[]
}) {
  return (
    <div>
      <label className="text-xs text-slate-600">{label}</label>
      <select
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        className="w-full mt-0.5 px-2 py-1.5 border border-slate-200 rounded text-sm outline-none focus:border-slate-500"
      >
        <option value="">—</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o.replace(/_/g, " ")}
          </option>
        ))}
      </select>
    </div>
  )
}
