// WorkflowController — inline workflow execution for the command bar.
// Receives a workflow id, starts a run, and renders the current prompt
// (input step) as a micro-form. On completion, returns output via callback.

import { useEffect, useState } from "react"
import { Loader2, Check, AlertTriangle, ChevronRight, ShieldAlert, Zap } from "lucide-react"
import apiClient from "@/lib/api-client"

export interface WorkflowRunState {
  id: string
  workflow_id: string
  status: "running" | "awaiting_input" | "awaiting_approval" | "completed" | "failed" | "cancelled"
  input_data: Record<string, unknown> | null
  output_data: Record<string, unknown> | null
  current_step_id: string | null
  error_message: string | null
  steps: Array<{
    step_key: string
    status: string
    output_data: Record<string, unknown> | null
    error_message: string | null
  }>
  awaiting_prompt: {
    step_key: string
    prompt: string
    input_type: string
    options?: Array<{ value: string; label: string }>
    placeholder?: string
    record_type?: string
    crm_filter?: Record<string, unknown>
  } | null
}

interface Props {
  workflowId: string
  workflowTitle: string
  onComplete: (run: WorkflowRunState) => void
  onCancel: () => void
}

export function WorkflowController({
  workflowId,
  workflowTitle,
  onComplete,
  onCancel,
}: Props) {
  const [run, setRun] = useState<WorkflowRunState | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  // Start the run on mount
  useEffect(() => {
    setLoading(true)
    apiClient
      .post<WorkflowRunState>(`/workflows/${workflowId}/start`, {})
      .then((r) => {
        setRun(r.data)
        if (r.data.status === "completed" || r.data.status === "failed") {
          onComplete(r.data)
        }
      })
      .catch((err) => {
        setRun({
          id: "",
          workflow_id: workflowId,
          status: "failed",
          input_data: null,
          output_data: null,
          current_step_id: null,
          error_message: err?.response?.data?.detail || err?.message || "Failed to start",
          steps: [],
          awaiting_prompt: null,
        })
      })
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflowId])

  const submitStep = async (value: unknown) => {
    if (!run?.awaiting_prompt) return
    setSubmitting(true)
    try {
      const { data } = await apiClient.post<WorkflowRunState>(
        `/workflows/runs/${run.id}/advance`,
        { step_input: { [run.awaiting_prompt.step_key]: value } },
      )
      setRun(data)
      if (data.status === "completed" || data.status === "failed") {
        onComplete(data)
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Step failed"
      setRun((prev) => (prev ? { ...prev, status: "failed", error_message: msg } : prev))
    } finally {
      setSubmitting(false)
    }
  }

  const approveStep = async (approvalKey: string, approved: boolean) => {
    if (!run) return
    setSubmitting(true)
    try {
      if (!approved) {
        // User cancelled — treat as a failure
        setRun((prev) => (prev ? { ...prev, status: "failed", error_message: "Automation cancelled by user." } : prev))
        return
      }
      const { data } = await apiClient.post<WorkflowRunState>(
        `/workflows/runs/${run.id}/advance`,
        { step_input: { [approvalKey]: true } },
      )
      setRun(data)
      if (data.status === "completed" || data.status === "failed") {
        onComplete(data)
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Approval failed"
      setRun((prev) => (prev ? { ...prev, status: "failed", error_message: msg } : prev))
    } finally {
      setSubmitting(false)
    }
  }

  if (loading || !run) {
    return (
      <div className="flex items-center gap-2 p-4 text-sm text-slate-600">
        <Loader2 className="h-4 w-4 animate-spin" />
        Starting {workflowTitle}…
      </div>
    )
  }

  if (run.status === "failed") {
    return (
      <div className="p-4 text-sm">
        <div className="flex items-center gap-2 text-red-700 mb-2">
          <AlertTriangle className="h-4 w-4" />
          <span className="font-medium">Workflow failed</span>
        </div>
        <div className="text-slate-600">{run.error_message || "Unknown error"}</div>
        <button onClick={onCancel} className="mt-3 text-xs text-slate-500 hover:text-slate-900">
          Close
        </button>
      </div>
    )
  }

  if (run.status === "completed") {
    return (
      <div className="p-4 text-sm">
        <div className="flex items-center gap-2 text-emerald-700">
          <Check className="h-4 w-4" />
          <span className="font-medium">{workflowTitle} complete</span>
        </div>
      </div>
    )
  }

  // awaiting_approval — Playwright action needs user sign-off before running
  if (run.status === "awaiting_approval") {
    // Find the approval metadata from output_data
    const approvalOutput = Object.values(run.output_data || {}).find(
      (v) => (v as Record<string, unknown>)?.type === "awaiting_approval"
    ) as Record<string, unknown> | undefined

    const approvalPrompt = (approvalOutput?.approval_prompt as string) || "Proceed with automated action?"
    const approvalKey = (approvalOutput?.approval_key as string) || "_approval"
    const scriptName = (approvalOutput?.script_name as string) || "automation"

    return (
      <div className="p-4 space-y-4">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span>⚡ {workflowTitle}</span>
        </div>
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 space-y-3">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-amber-100 flex items-center justify-center flex-shrink-0 mt-0.5">
              <ShieldAlert className="h-4 w-4 text-amber-600" />
            </div>
            <div>
              <p className="text-sm font-semibold text-amber-900">Approval required</p>
              <p className="text-xs text-amber-700 mt-0.5">
                This step will open a browser and take action on an external website.
              </p>
            </div>
          </div>
          <div className="bg-white rounded-lg border border-amber-200 px-4 py-3">
            <div className="flex items-center gap-2 text-xs text-slate-500 mb-1">
              <Zap className="h-3 w-3" />
              {scriptName}
            </div>
            <p className="text-sm text-slate-800 font-medium">{approvalPrompt}</p>
          </div>
          <div className="flex gap-2 pt-1">
            <button
              onClick={() => approveStep(approvalKey, true)}
              disabled={submitting}
              className="flex-1 py-2 bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium rounded-lg disabled:opacity-50 transition"
            >
              {submitting ? (
                <span className="flex items-center justify-center gap-1.5">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Running…
                </span>
              ) : (
                "Approve & run"
              )}
            </button>
            <button
              onClick={() => approveStep(approvalKey, false)}
              disabled={submitting}
              className="px-4 py-2 border border-amber-200 text-amber-800 text-sm rounded-lg hover:bg-amber-100 disabled:opacity-50 transition"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    )
  }

  // awaiting_input
  const prompt = run.awaiting_prompt
  if (!prompt) {
    return (
      <div className="flex items-center gap-2 p-4 text-sm text-slate-600">
        <Loader2 className="h-4 w-4 animate-spin" />
        Working…
      </div>
    )
  }

  return (
    <div className="p-4 space-y-3">
      <div className="flex items-center gap-2 text-xs text-slate-500">
        <span>⚡ {workflowTitle}</span>
      </div>
      <div className="font-medium text-slate-900">{prompt.prompt}</div>
      <MicroForm prompt={prompt} onSubmit={submitStep} submitting={submitting} />
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────────
// MicroForm — renders the appropriate input UI based on prompt.input_type
// ─────────────────────────────────────────────────────────────────────

function MicroForm({
  prompt,
  onSubmit,
  submitting,
}: {
  prompt: NonNullable<WorkflowRunState["awaiting_prompt"]>
  onSubmit: (value: unknown) => void
  submitting: boolean
}) {
  switch (prompt.input_type) {
    case "select":
      return <SelectInput options={prompt.options || []} onSubmit={onSubmit} />
    case "number":
      return <NumberInput onSubmit={onSubmit} submitting={submitting} />
    case "date_picker":
      return <DateInput onSubmit={onSubmit} submitting={submitting} />
    case "datetime_picker":
      return <DateInput onSubmit={onSubmit} submitting={submitting} withTime />
    case "crm_search":
      return <CrmSearchInput placeholder={prompt.placeholder} onSubmit={onSubmit} />
    case "record_search":
      return <RecordSearchInput recordType={prompt.record_type || ""} placeholder={prompt.placeholder} onSubmit={onSubmit} />
    case "user_search":
      return <UserSearchInput onSubmit={onSubmit} />
    default:
      return <FallbackInput onSubmit={onSubmit} submitting={submitting} />
  }
}

function SelectInput({ options, onSubmit }: { options: Array<{ value: string; label: string }>; onSubmit: (v: string) => void }) {
  return (
    <div className="space-y-1">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onSubmit(o.value)}
          className="w-full flex items-center justify-between px-3 py-2 text-left text-sm border border-slate-200 rounded hover:bg-slate-50 hover:border-slate-400"
        >
          <span>{o.label}</span>
          <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
        </button>
      ))}
    </div>
  )
}

function NumberInput({ onSubmit, submitting }: { onSubmit: (v: number) => void; submitting: boolean }) {
  const [val, setVal] = useState("")
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        const n = Number(val)
        if (!Number.isNaN(n)) onSubmit(n)
      }}
      className="flex gap-2"
    >
      <input
        type="number"
        value={val}
        onChange={(e) => setVal(e.target.value)}
        autoFocus
        className="flex-1 px-3 py-2 border border-slate-200 rounded text-sm outline-none focus:border-slate-500"
      />
      <button
        type="submit"
        disabled={submitting || !val}
        className="px-4 py-2 bg-slate-900 text-white text-sm rounded disabled:opacity-60"
      >
        Confirm
      </button>
    </form>
  )
}

function DateInput({ onSubmit, submitting, withTime }: { onSubmit: (v: string) => void; submitting: boolean; withTime?: boolean }) {
  const [val, setVal] = useState("")
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (val) onSubmit(val)
      }}
      className="flex gap-2"
    >
      <input
        type={withTime ? "datetime-local" : "date"}
        value={val}
        onChange={(e) => setVal(e.target.value)}
        autoFocus
        className="flex-1 px-3 py-2 border border-slate-200 rounded text-sm outline-none focus:border-slate-500"
      />
      <button
        type="submit"
        disabled={submitting || !val}
        className="px-4 py-2 bg-slate-900 text-white text-sm rounded disabled:opacity-60"
      >
        Confirm
      </button>
    </form>
  )
}

interface GenericRecord {
  id: string
  name: string
  subtitle?: string
}

function CrmSearchInput({ placeholder, onSubmit }: { placeholder?: string; onSubmit: (v: GenericRecord) => void }) {
  return <GenericRecordSearch endpoint="/companies" placeholder={placeholder || "Search..."} onSubmit={onSubmit} labelField="name" />
}

function RecordSearchInput({ recordType, placeholder, onSubmit }: { recordType: string; placeholder?: string; onSubmit: (v: GenericRecord) => void }) {
  const endpoint = {
    order: "/sales/orders",
    delivery: "/scheduling/deliveries",
    funeral_case: "/fh/cases",
    product: "/products",
  }[recordType] || "/companies"
  return <GenericRecordSearch endpoint={endpoint} placeholder={placeholder || "Search..."} onSubmit={onSubmit} labelField="name" />
}

function UserSearchInput({ onSubmit }: { onSubmit: (v: GenericRecord) => void }) {
  return <GenericRecordSearch endpoint="/users/list" placeholder="Search team members..." onSubmit={onSubmit} labelField="email" />
}

function GenericRecordSearch({
  endpoint,
  placeholder,
  onSubmit,
  labelField,
}: {
  endpoint: string
  placeholder: string
  onSubmit: (v: GenericRecord) => void
  labelField: string
}) {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<Array<Record<string, unknown>>>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    const t = setTimeout(async () => {
      setLoading(true)
      try {
        const { data } = await apiClient.get(endpoint, { params: { search: query, limit: 5 } })
        if (!cancelled) {
          const list = Array.isArray(data) ? data : (data?.items || data?.results || [])
          setResults(list.slice(0, 5))
        }
      } catch {
        if (!cancelled) setResults([])
      } finally {
        if (!cancelled) setLoading(false)
      }
    }, 250)
    return () => {
      cancelled = true
      clearTimeout(t)
    }
  }, [query, endpoint])

  return (
    <div className="space-y-2">
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        autoFocus
        placeholder={placeholder}
        className="w-full px-3 py-2 border border-slate-200 rounded text-sm outline-none focus:border-slate-500"
      />
      <div className="space-y-1">
        {loading && results.length === 0 && (
          <div className="text-xs text-slate-400 px-1 py-2">Searching…</div>
        )}
        {!loading && results.length === 0 && query.length > 0 && (
          <div className="text-xs text-slate-400 px-1 py-2">No matches</div>
        )}
        {results.map((r, i) => {
          const rec = r as Record<string, unknown>
          const id = (rec.id || rec.case_id || `${i}`) as string
          const label = (rec[labelField] || rec.name || rec.deceased_name || rec.case_number || rec.email || "—") as string
          const subtitle = (rec.subtitle || rec.email || rec.status || "") as string
          return (
            <button
              key={id}
              onClick={() => onSubmit({ id, name: label, subtitle, ...rec } as GenericRecord)}
              className="w-full flex items-center justify-between px-3 py-2 text-left text-sm border border-slate-200 rounded hover:bg-slate-50 hover:border-slate-400"
            >
              <div>
                <div className="font-medium">{label}</div>
                {subtitle && <div className="text-xs text-slate-500">{subtitle}</div>}
              </div>
              <span className="text-xs text-slate-500">Select →</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function FallbackInput({ onSubmit, submitting }: { onSubmit: (v: string) => void; submitting: boolean }) {
  const [val, setVal] = useState("")
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (val.trim()) onSubmit(val)
      }}
      className="flex gap-2"
    >
      <input
        value={val}
        onChange={(e) => setVal(e.target.value)}
        autoFocus
        className="flex-1 px-3 py-2 border border-slate-200 rounded text-sm outline-none focus:border-slate-500"
      />
      <button
        type="submit"
        disabled={submitting || !val.trim()}
        className="px-4 py-2 bg-slate-900 text-white text-sm rounded disabled:opacity-60"
      >
        Submit
      </button>
    </form>
  )
}

export default WorkflowController
