import { useEffect, useRef, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { ArrowLeft, Mic, MicOff, Square, Loader2 } from "lucide-react"
import { fhApi } from "../lib/fh-api"

type Method = "menu" | "scribe" | "natural" | "form"

export default function ArrangementConference() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const [method, setMethod] = useState<Method>("menu")

  if (!caseId) return null

  const finish = () => {
    navigate(`/fh/cases/${caseId}`)
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-4">
      <div className="flex items-center justify-between text-sm">
        <Link to={`/fh/cases/${caseId}`} className="flex items-center gap-1 text-slate-600 hover:text-slate-900">
          <ArrowLeft className="h-4 w-4" /> Case
        </Link>
        {method !== "menu" && (
          <button onClick={finish} className="text-sm text-slate-600 hover:text-slate-900">
            Done → Case Dashboard
          </button>
        )}
      </div>

      <h1 className="text-2xl font-semibold text-slate-900">Arrangement Conference</h1>

      {method === "menu" && <MethodMenu onChoose={setMethod} />}
      {method !== "menu" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            {method === "scribe" && <ScribePanel caseId={caseId} />}
            {method === "natural" && <NaturalLanguagePanel caseId={caseId} />}
            {method === "form" && <FormPanel caseId={caseId} />}
          </div>
          <div className="lg:col-span-1">
            <CompletionPanel caseId={caseId} />
          </div>
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────
// Method selection
// ─────────────────────────────────────────────────────────────────────
function MethodMenu({ onChoose }: { onChoose: (m: Method) => void }) {
  return (
    <div className="space-y-4">
      <p className="text-slate-600">How would you like to capture arrangement details?</p>

      <button
        onClick={() => onChoose("scribe")}
        className="w-full bg-white border-2 border-slate-200 rounded-lg p-6 hover:border-slate-900 text-left flex items-start gap-4"
      >
        <div className="text-3xl">🎙️</div>
        <div>
          <div className="font-semibold text-lg text-slate-900">Record Arrangement Conference</div>
          <div className="text-sm text-slate-500 mt-1">
            Start recording — Scribe captures everything automatically
          </div>
        </div>
      </button>

      <button
        onClick={() => onChoose("natural")}
        className="w-full bg-white border-2 border-slate-200 rounded-lg p-5 hover:border-slate-700 text-left flex items-start gap-4"
      >
        <div className="text-2xl">💬</div>
        <div>
          <div className="font-semibold text-slate-900">Type or speak as you go</div>
          <div className="text-sm text-slate-500 mt-1">
            Enter notes naturally as you learn them
          </div>
        </div>
      </button>

      <div className="text-center pt-2">
        <button onClick={() => onChoose("form")} className="text-sm text-slate-500 hover:text-slate-900 underline">
          Fill out manually ↓
        </button>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────
// Method 1: Scribe (recording + review)
// ─────────────────────────────────────────────────────────────────────
function ScribePanel({ caseId }: { caseId: string }) {
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [processing, setProcessing] = useState(false)
  const [transcript, setTranscript] = useState("")
  const [result, setResult] = useState<{ auto_applied: number; needs_review: number; skipped: number } | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<number | null>(null)

  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        // Phase 1 note: audio recorded, but upload+transcription wiring is Phase 2.
        // For Phase 1 we collect and leave the transcript input open for the director to paste/type the transcript.
      }
      recorder.start()
      mediaRecorderRef.current = recorder
      setRecording(true)
      setSeconds(0)
      timerRef.current = window.setInterval(() => setSeconds((s) => s + 1), 1000)
    } catch {
      alert("Microphone access was denied. You can paste a transcript instead.")
    }
  }

  const stop = () => {
    mediaRecorderRef.current?.stop()
    mediaRecorderRef.current = null
    setRecording(false)
    if (timerRef.current) window.clearInterval(timerRef.current)
  }

  const process = async () => {
    if (!transcript.trim()) return
    setProcessing(true)
    try {
      const data = await fhApi.scribeProcess(caseId, transcript)
      setResult({ auto_applied: data.auto_applied, needs_review: data.needs_review, skipped: data.skipped })
    } catch (e: any) {
      alert(e?.response?.data?.detail || "Failed to process transcript")
    } finally {
      setProcessing(false)
    }
  }

  return (
    <div className="bg-white border border-slate-200 rounded p-5 space-y-4">
      <h2 className="text-sm font-semibold text-slate-900">Recording</h2>
      <div className="flex items-center gap-4">
        {!recording ? (
          <button
            onClick={start}
            className="bg-red-600 text-white rounded-full px-5 py-2 flex items-center gap-2 hover:bg-red-700"
          >
            <Mic className="h-4 w-4" /> Start recording
          </button>
        ) : (
          <button
            onClick={stop}
            className="bg-slate-900 text-white rounded-full px-5 py-2 flex items-center gap-2"
          >
            <Square className="h-3 w-3 fill-current" /> Stop ({_fmtSec(seconds)})
          </button>
        )}
        {recording && (
          <span className="flex items-center gap-2 text-red-600 text-sm">
            <span className="h-2 w-2 bg-red-600 rounded-full animate-pulse" />
            Recording…
          </span>
        )}
      </div>

      <div>
        <label className="text-xs font-semibold text-slate-700">
          Transcript (paste or type after stopping, then process)
        </label>
        <textarea
          value={transcript}
          onChange={(e) => setTranscript(e.target.value)}
          placeholder="Transcript of the conversation…"
          rows={8}
          className="w-full mt-1 px-3 py-2 border border-slate-200 rounded text-sm outline-none focus:border-slate-500"
        />
      </div>

      <button
        onClick={process}
        disabled={processing || !transcript.trim()}
        className="w-full bg-slate-900 text-white rounded py-2 text-sm hover:bg-slate-800 disabled:opacity-60 flex items-center justify-center gap-2"
      >
        {processing ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        {processing ? "Processing transcript…" : "Process with Scribe"}
      </button>

      {result && (
        <div className="bg-emerald-50 border border-emerald-200 rounded p-3 text-sm">
          <div className="font-medium text-emerald-900 mb-1">Extraction complete</div>
          <div className="text-emerald-800">
            ✓ {result.auto_applied} auto-applied ·{" "}
            ⚠ {result.needs_review} need review ·{" "}
            {result.skipped} skipped
          </div>
          <div className="text-xs text-emerald-700 mt-2">
            Open each step page to confirm amber fields.
          </div>
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────
// Method 2: Natural language
// ─────────────────────────────────────────────────────────────────────
function NaturalLanguagePanel({ caseId }: { caseId: string }) {
  const [input, setInput] = useState("")
  const [processing, setProcessing] = useState(false)
  const [history, setHistory] = useState<{ auto_applied: number; needs_review: number; skipped: number }[]>([])
  const [speechActive, setSpeechActive] = useState(false)

  const submit = async () => {
    if (!input.trim()) return
    setProcessing(true)
    try {
      const data = await fhApi.scribeExtract(caseId, input)
      setHistory((h) => [
        { auto_applied: data.auto_applied, needs_review: data.needs_review, skipped: data.skipped },
        ...h,
      ])
      setInput("")
    } catch (e: any) {
      alert(e?.response?.data?.detail || "Failed to extract")
    } finally {
      setProcessing(false)
    }
  }

  const toggleSpeech = () => {
    const Speech = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition
    if (!Speech) {
      alert("Speech recognition not available in this browser.")
      return
    }
    if (speechActive) {
      setSpeechActive(false)
      return
    }
    const rec = new Speech()
    rec.continuous = true
    rec.interimResults = true
    rec.onresult = (e: any) => {
      const transcript = Array.from(e.results)
        .map((r: any) => r[0].transcript)
        .join(" ")
      setInput((prev) => prev + " " + transcript)
    }
    rec.onend = () => setSpeechActive(false)
    rec.start()
    setSpeechActive(true)
  }

  return (
    <div className="bg-white border border-slate-200 rounded p-5 space-y-4">
      <h2 className="text-sm font-semibold text-slate-900">Notes</h2>
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit()
        }}
        placeholder='Type notes as you go — "His name is John Smith, born March 3, 1942. Catholic. Retired steelworker. His wife Mary will be the primary contact."'
        rows={6}
        className="w-full px-3 py-2 border border-slate-200 rounded text-sm outline-none focus:border-slate-500"
      />
      <div className="flex gap-2">
        <button
          onClick={toggleSpeech}
          className={`rounded px-3 py-2 text-sm flex items-center gap-2 ${
            speechActive ? "bg-red-600 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
          title="Voice input"
        >
          {speechActive ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
          {speechActive ? "Listening…" : "Voice"}
        </button>
        <button
          onClick={submit}
          disabled={processing || !input.trim()}
          className="flex-1 bg-slate-900 text-white rounded py-2 text-sm hover:bg-slate-800 disabled:opacity-60 flex items-center justify-center gap-2"
        >
          {processing ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Extract (⌘⏎)
        </button>
      </div>

      {history.length > 0 && (
        <div className="space-y-1 pt-2 border-t border-slate-100">
          <div className="text-xs font-semibold text-slate-500 mb-2">Extraction history</div>
          {history.map((h, i) => (
            <div key={i} className="text-xs text-slate-600 flex gap-3">
              <span>✓ {h.auto_applied}</span>
              <span>⚠ {h.needs_review}</span>
              <span>skipped {h.skipped}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────
// Method 3: Form
// ─────────────────────────────────────────────────────────────────────
function FormPanel({ caseId }: { caseId: string }) {
  const [form, setForm] = useState<Record<string, any>>({})
  const [saving, setSaving] = useState(false)

  const set = (k: string, v: any) => setForm((f) => ({ ...f, [k]: v }))

  const save = async () => {
    setSaving(true)
    try {
      const deceasedPayload: any = {}
      const servicePayload: any = {}
      for (const k of ["first_name", "middle_name", "last_name", "suffix", "date_of_birth", "date_of_death", "sex", "religion", "occupation", "marital_status", "place_of_death_name", "residence_city", "residence_state"]) {
        if (form[k] !== undefined && form[k] !== "") deceasedPayload[k] = form[k]
      }
      for (const k of ["service_type", "service_date", "service_location_name", "officiant_name"]) {
        if (form[k] !== undefined && form[k] !== "") servicePayload[k] = form[k]
      }
      if (Object.keys(deceasedPayload).length > 0) {
        await fhApi.updateDeceased(caseId, deceasedPayload)
      }
      if (Object.keys(servicePayload).length > 0) {
        await fhApi.updateService(caseId, servicePayload)
      }
      alert("Saved")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="bg-white border border-slate-200 rounded p-5 space-y-5">
      <h2 className="text-sm font-semibold text-slate-900">Deceased Information</h2>
      <div className="grid grid-cols-2 gap-3">
        <Field label="First name" value={form.first_name || ""} onChange={(v) => set("first_name", v)} />
        <Field label="Middle name" value={form.middle_name || ""} onChange={(v) => set("middle_name", v)} />
        <Field label="Last name" value={form.last_name || ""} onChange={(v) => set("last_name", v)} />
        <Field label="Suffix" value={form.suffix || ""} onChange={(v) => set("suffix", v)} />
        <Field label="Date of birth" type="date" value={form.date_of_birth || ""} onChange={(v) => set("date_of_birth", v)} />
        <Field label="Date of death" type="date" value={form.date_of_death || ""} onChange={(v) => set("date_of_death", v)} />
        <Select label="Sex" value={form.sex || ""} onChange={(v) => set("sex", v)} options={["male", "female", "other"]} />
        <Field label="Religion" value={form.religion || ""} onChange={(v) => set("religion", v)} />
        <Field label="Occupation" value={form.occupation || ""} onChange={(v) => set("occupation", v)} />
        <Select label="Marital status" value={form.marital_status || ""} onChange={(v) => set("marital_status", v)} options={["single", "married", "widowed", "divorced"]} />
        <Field label="Place of death" value={form.place_of_death_name || ""} onChange={(v) => set("place_of_death_name", v)} />
        <Field label="Residence city" value={form.residence_city || ""} onChange={(v) => set("residence_city", v)} />
      </div>

      <h2 className="text-sm font-semibold text-slate-900 pt-2 border-t border-slate-100">Service</h2>
      <div className="grid grid-cols-2 gap-3">
        <Select
          label="Type"
          value={form.service_type || ""}
          onChange={(v) => set("service_type", v)}
          options={["graveside", "chapel", "church", "memorial", "celebration_of_life", "no_service"]}
        />
        <Field label="Date" type="date" value={form.service_date || ""} onChange={(v) => set("service_date", v)} />
        <Field label="Location" value={form.service_location_name || ""} onChange={(v) => set("service_location_name", v)} />
        <Field label="Officiant" value={form.officiant_name || ""} onChange={(v) => set("officiant_name", v)} />
      </div>

      <button
        onClick={save}
        disabled={saving}
        className="w-full bg-slate-900 text-white rounded py-2 text-sm hover:bg-slate-800 disabled:opacity-60"
      >
        {saving ? "Saving…" : "Save"}
      </button>
    </div>
  )
}

function Field({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (v: string) => void; type?: string }) {
  return (
    <div>
      <label className="text-xs text-slate-600">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full mt-0.5 px-2 py-1.5 border border-slate-200 rounded text-sm outline-none focus:border-slate-500"
      />
    </div>
  )
}

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: string[] }) {
  return (
    <div>
      <label className="text-xs text-slate-600">{label}</label>
      <select
        value={value}
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

// ─────────────────────────────────────────────────────────────────────
// Live completion panel (right side)
// ─────────────────────────────────────────────────────────────────────
function CompletionPanel({ caseId }: { caseId: string }) {
  const [detail, setDetail] = useState<any>(null)

  useEffect(() => {
    const load = () =>
      fhApi
        .getCase(caseId)
        .then(setDetail)
        .catch(() => setDetail(null))
    load()
    const t = window.setInterval(load, 5000)
    return () => window.clearInterval(t)
  }, [caseId])

  if (!detail) return null
  const dec = detail.deceased || {}
  const svc = detail.service || {}
  const disp = detail.disposition || {}
  const vet = detail.veteran || {}

  const deceasedFields: [string, any][] = [
    ["first_name", dec.first_name],
    ["last_name", dec.last_name],
    ["date_of_birth", dec.date_of_birth],
    ["date_of_death", dec.date_of_death],
    ["sex", dec.sex],
    ["religion", dec.religion],
    ["occupation", dec.occupation],
  ]
  const serviceFields: [string, any][] = [
    ["service_type", svc.service_type],
    ["service_date", svc.service_date],
    ["service_location_name", svc.service_location_name],
    ["officiant_name", svc.officiant_name],
  ]
  const dispositionFields: [string, any][] = [["disposition_type", disp.disposition_type]]
  const veteranFields: [string, any][] = [
    ["ever_in_armed_forces", vet.ever_in_armed_forces],
    ["branch", vet.branch],
  ]

  return (
    <div className="bg-white border border-slate-200 rounded p-4 space-y-3 sticky top-4">
      <h3 className="text-sm font-semibold text-slate-900">Case Completion</h3>
      <div className="text-xs text-slate-500 mb-2">Updates every 5 seconds</div>
      <Section title="Deceased" fields={deceasedFields} />
      <Section title="Service" fields={serviceFields} />
      <Section title="Disposition" fields={dispositionFields} />
      <Section title="Veteran" fields={veteranFields} />
    </div>
  )
}

function Section({ title, fields }: { title: string; fields: [string, any][] }) {
  const captured = fields.filter(([, v]) => v !== null && v !== undefined && v !== "").length
  return (
    <div>
      <div className="text-xs font-semibold text-slate-600 uppercase mb-1">
        {title} <span className="text-slate-400 font-normal">{captured}/{fields.length}</span>
      </div>
      <div className="space-y-0.5">
        {fields.map(([k, v]) => (
          <div key={k} className="text-xs flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${v ? "bg-green-500" : "bg-slate-300"}`} />
            <span className="text-slate-500 flex-1">{k.replace(/_/g, " ")}</span>
            {v && <span className="text-slate-700 truncate max-w-[120px]">{String(v)}</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

function _fmtSec(s: number): string {
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m}:${String(r).padStart(2, "0")}`
}
