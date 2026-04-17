// Workflow Builder — canvas + block editor + AI describe entry
//
// Routes:
//   /settings/workflows/new                  — blank or AI-describe entry
//   /settings/workflows/:workflowId/edit     — edit custom workflow
//   /settings/workflows/:workflowId/view     — read-only (Tier 1)

import { useCallback, useEffect, useMemo, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import {
  ArrowLeft,
  Save,
  Play,
  Sparkles,
  Plus,
  Trash2,
  Lock,
  Loader2,
  MessageSquare,
  Zap,
  GitBranch,
  CheckCircle,
  ChevronDown,
  ChevronUp,
} from "lucide-react"
import apiClient from "@/lib/api-client"

// ─────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────

type StepType = "input" | "action" | "condition" | "output"

interface Step {
  step_order: number
  step_key: string
  step_type: StepType
  config: Record<string, unknown>
}

interface WorkflowDraft {
  id?: string
  name: string
  description: string
  keywords: string[]
  vertical: string | null
  trigger_type: string
  trigger_config: Record<string, unknown> | null
  icon: string | null
  command_bar_priority: number
  is_active: boolean
  steps: Step[]
}

interface LoadedWorkflow extends WorkflowDraft {
  tier: number
  is_system: boolean
  editable: boolean
  recent_runs?: Array<{
    id: string
    status: string
    trigger_source: string
    started_at: string | null
    completed_at: string | null
    error_message: string | null
  }>
}

// ─────────────────────────────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────────────────────────────

export default function WorkflowBuilderPage() {
  const { workflowId } = useParams<{ workflowId: string }>()
  const navigate = useNavigate()
  const isViewMode = location.pathname.endsWith("/view")
  const isEditMode = location.pathname.endsWith("/edit")
  const isNew = !workflowId

  const [loading, setLoading] = useState(!isNew)
  const [saving, setSaving] = useState(false)
  const [mode, setMode] = useState<"entry" | "builder">(isNew ? "entry" : "builder")
  const [loadedMeta, setLoadedMeta] = useState<Pick<LoadedWorkflow, "tier" | "is_system" | "editable" | "recent_runs"> | null>(null)
  const [draft, setDraft] = useState<WorkflowDraft>({
    name: "",
    description: "",
    keywords: [],
    vertical: null,
    trigger_type: "manual",
    trigger_config: null,
    icon: null,
    command_bar_priority: 50,
    is_active: false,
    steps: [],
  })
  const [selectedStepIdx, setSelectedStepIdx] = useState<number | null>(null)

  // Load existing workflow
  useEffect(() => {
    if (isNew) return
    setLoading(true)
    apiClient
      .get<LoadedWorkflow>(`/workflows/${workflowId}`)
      .then((r) => {
        const d = r.data
        setDraft({
          id: d.id,
          name: d.name,
          description: d.description || "",
          keywords: d.keywords || [],
          vertical: d.vertical,
          trigger_type: d.trigger_type,
          trigger_config: d.trigger_config,
          icon: d.icon,
          command_bar_priority: d.command_bar_priority,
          is_active: d.is_active,
          steps: (d.steps || []).map((s, i) => ({
            step_order: s.step_order || i + 1,
            step_key: s.step_key,
            step_type: s.step_type as StepType,
            config: (s.config as Record<string, unknown>) || {},
          })),
        })
        setLoadedMeta({
          tier: d.tier,
          is_system: d.is_system,
          editable: d.editable,
          recent_runs: d.recent_runs,
        })
      })
      .finally(() => setLoading(false))
  }, [workflowId, isNew])

  const readOnly = isViewMode || (loadedMeta ? !loadedMeta.editable : false)

  const updateStep = useCallback((idx: number, update: Partial<Step>) => {
    setDraft((prev) => ({
      ...prev,
      steps: prev.steps.map((s, i) => (i === idx ? { ...s, ...update } : s)),
    }))
  }, [])

  const updateStepConfig = useCallback((idx: number, configUpdate: Record<string, unknown>) => {
    setDraft((prev) => ({
      ...prev,
      steps: prev.steps.map((s, i) =>
        i === idx ? { ...s, config: { ...s.config, ...configUpdate } } : s,
      ),
    }))
  }, [])

  const addStep = useCallback((type: StepType) => {
    setDraft((prev) => {
      const order = prev.steps.length + 1
      const newStep: Step = {
        step_order: order,
        step_key: `step_${order}`,
        step_type: type,
        config: defaultConfigForType(type),
      }
      return { ...prev, steps: [...prev.steps, newStep] }
    })
    setSelectedStepIdx(draft.steps.length)
  }, [draft.steps.length])

  const removeStep = useCallback((idx: number) => {
    setDraft((prev) => ({
      ...prev,
      steps: prev.steps
        .filter((_, i) => i !== idx)
        .map((s, i) => ({ ...s, step_order: i + 1 })),
    }))
    setSelectedStepIdx(null)
  }, [])

  const moveStep = useCallback((idx: number, direction: -1 | 1) => {
    setDraft((prev) => {
      const newIdx = idx + direction
      if (newIdx < 0 || newIdx >= prev.steps.length) return prev
      const steps = [...prev.steps]
      const [s] = steps.splice(idx, 1)
      steps.splice(newIdx, 0, s)
      return {
        ...prev,
        steps: steps.map((s2, i) => ({ ...s2, step_order: i + 1 })),
      }
    })
  }, [])

  const save = async (activate: boolean) => {
    if (!draft.name.trim()) {
      alert("Name is required.")
      return
    }
    setSaving(true)
    try {
      const payload = {
        ...draft,
        is_active: activate,
      }
      if (draft.id) {
        await apiClient.patch(`/workflows/${draft.id}`, payload)
      } else {
        const r = await apiClient.post("/workflows", payload)
        navigate(`/settings/workflows/${r.data.id}/edit`, { replace: true })
      }
      setDraft((d) => ({ ...d, is_active: activate }))
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Save failed"
      alert(msg)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="p-8 text-center text-slate-400">Loading…</div>
  }

  // Entry screen for new workflows: blank or AI
  if (mode === "entry" && isNew) {
    return <EntryScreen onPick={(d) => { setDraft((prev) => ({ ...prev, ...d })); setMode("builder") }} />
  }

  const selectedStep = selectedStepIdx !== null ? draft.steps[selectedStepIdx] : null

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col bg-slate-50">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white px-6 py-3 flex items-center gap-3">
        <Link
          to="/settings/workflows"
          className="text-slate-500 hover:text-slate-900"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="flex-1 min-w-0">
          {readOnly ? (
            <div className="flex items-center gap-2">
              <h1 className="text-base font-semibold text-slate-900 truncate">{draft.name}</h1>
              {loadedMeta?.tier === 1 && (
                <span className="inline-flex items-center gap-1 rounded bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800">
                  <Lock className="h-3 w-3" />
                  Platform-locked
                </span>
              )}
            </div>
          ) : (
            <input
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              placeholder="Workflow name"
              className="w-full text-base font-semibold text-slate-900 bg-transparent outline-none placeholder:text-slate-400"
            />
          )}
          {readOnly ? (
            <div className="text-xs text-slate-500 mt-0.5 truncate">{draft.description}</div>
          ) : (
            <input
              value={draft.description}
              onChange={(e) => setDraft({ ...draft, description: e.target.value })}
              placeholder="Short description"
              className="w-full text-xs text-slate-500 mt-0.5 bg-transparent outline-none placeholder:text-slate-400"
            />
          )}
        </div>
        {!readOnly && (
          <>
            <button
              onClick={() => save(false)}
              disabled={saving}
              className="inline-flex items-center gap-1.5 rounded border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
            >
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
              Save draft
            </button>
            <button
              onClick={() => save(true)}
              disabled={saving}
              className="inline-flex items-center gap-1.5 rounded bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-60"
            >
              <Play className="h-3.5 w-3.5" />
              Activate
            </button>
          </>
        )}
      </header>

      <div className="flex flex-1 min-h-0">
        {/* Canvas */}
        <main className="flex-1 overflow-y-auto p-6">
          <div className="mx-auto max-w-2xl space-y-6">
            <TriggerCard
              triggerType={draft.trigger_type}
              triggerConfig={draft.trigger_config}
              readOnly={readOnly}
              onChange={(trigger_type, trigger_config) =>
                setDraft({ ...draft, trigger_type, trigger_config })
              }
            />

            {draft.steps.length === 0 ? (
              <div className="rounded border-2 border-dashed border-slate-300 bg-white p-8 text-center">
                <div className="text-sm text-slate-500">No steps yet.</div>
                {!readOnly && (
                  <div className="mt-3 flex flex-wrap gap-2 justify-center">
                    <AddStepButton onClick={() => addStep("input")} label="Input" icon={MessageSquare} />
                    <AddStepButton onClick={() => addStep("action")} label="Action" icon={Zap} />
                    <AddStepButton onClick={() => addStep("condition")} label="Condition" icon={GitBranch} />
                    <AddStepButton onClick={() => addStep("output")} label="Output" icon={CheckCircle} />
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                {draft.steps.map((step, i) => (
                  <StepBlock
                    key={i}
                    step={step}
                    index={i}
                    selected={selectedStepIdx === i}
                    readOnly={readOnly}
                    onSelect={() => setSelectedStepIdx(i)}
                    onMoveUp={() => moveStep(i, -1)}
                    onMoveDown={() => moveStep(i, 1)}
                    onRemove={() => removeStep(i)}
                    canMoveUp={i > 0}
                    canMoveDown={i < draft.steps.length - 1}
                  />
                ))}
                {!readOnly && (
                  <div className="flex gap-2 pt-2">
                    <AddStepButton onClick={() => addStep("input")} label="Add Input" icon={MessageSquare} />
                    <AddStepButton onClick={() => addStep("action")} label="Add Action" icon={Zap} />
                    <AddStepButton onClick={() => addStep("condition")} label="Add Condition" icon={GitBranch} />
                    <AddStepButton onClick={() => addStep("output")} label="Add Output" icon={CheckCircle} />
                  </div>
                )}
              </div>
            )}

            {readOnly && loadedMeta?.recent_runs && loadedMeta.recent_runs.length > 0 && (
              <RecentRuns runs={loadedMeta.recent_runs} />
            )}
          </div>
        </main>

        {/* Block editor (right panel) */}
        {selectedStep !== null && !readOnly && (
          <aside className="w-96 flex-shrink-0 border-l border-slate-200 bg-white overflow-y-auto">
            <BlockEditor
              step={selectedStep}
              onChange={(update) => updateStep(selectedStepIdx!, update)}
              onConfigChange={(configUpdate) => updateStepConfig(selectedStepIdx!, configUpdate)}
              onClose={() => setSelectedStepIdx(null)}
            />
          </aside>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────
// Entry screen (blank vs AI)
// ─────────────────────────────────────────────────────────────────────

function EntryScreen({ onPick }: { onPick: (draft: Partial<WorkflowDraft>) => void }) {
  const [aiDescription, setAiDescription] = useState("")
  const [generating, setGenerating] = useState(false)
  const [aiError, setAiError] = useState<string | null>(null)

  const generate = async () => {
    if (aiDescription.trim().length < 10) {
      setAiError("Please provide at least 10 characters.")
      return
    }
    setGenerating(true)
    setAiError(null)
    try {
      const r = await apiClient.post("/workflows/generate", {
        description: aiDescription,
      })
      const d = r.data
      onPick({
        name: d.name || "Untitled Workflow",
        description: d.description || aiDescription.slice(0, 140),
        keywords: d.keywords || [],
        vertical: d.vertical,
        trigger_type: d.trigger_type || "manual",
        trigger_config: d.trigger_config || null,
        icon: d.icon || null,
        steps: (d.steps || []).map((s: Step, i: number) => ({
          step_order: s.step_order || i + 1,
          step_key: s.step_key || `step_${i + 1}`,
          step_type: s.step_type || "action",
          config: s.config || {},
        })),
      })
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Generation failed"
      setAiError(msg)
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-12">
      <div className="mb-4">
        <Link to="/settings/workflows" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900">
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to library
        </Link>
      </div>
      <h1 className="text-2xl font-semibold text-slate-900">New Workflow</h1>
      <p className="mt-1 text-sm text-slate-500">
        Describe the process in plain English, or start from scratch.
      </p>

      <div className="mt-8 rounded-lg border border-slate-200 bg-white p-6">
        <div className="flex items-center gap-2 text-slate-900 font-medium">
          <Sparkles className="h-4 w-4 text-violet-600" />
          Describe your process
        </div>
        <textarea
          value={aiDescription}
          onChange={(e) => setAiDescription(e.target.value)}
          placeholder="E.g. When a funeral home calls to cancel an order, ask for the reason, log it to the case vault, and notify the assigned director."
          rows={5}
          className="mt-3 w-full rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-900"
        />
        {aiError && (
          <div className="mt-2 rounded bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-700">
            {aiError}
          </div>
        )}
        <button
          onClick={generate}
          disabled={generating || aiDescription.trim().length < 10}
          className="mt-3 inline-flex items-center gap-2 rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60"
        >
          {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          Generate draft
        </button>
      </div>

      <div className="mt-4 text-center">
        <button
          onClick={() => onPick({ name: "Untitled Workflow" })}
          className="text-sm text-slate-500 hover:text-slate-900 underline"
        >
          or start from a blank canvas
        </button>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────
// Trigger card
// ─────────────────────────────────────────────────────────────────────

function TriggerCard({
  triggerType,
  triggerConfig,
  readOnly,
  onChange,
}: {
  triggerType: string
  triggerConfig: Record<string, unknown> | null
  readOnly: boolean
  onChange: (type: string, config: Record<string, unknown> | null) => void
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-2 mb-2">
        <div className="h-6 w-6 rounded bg-slate-900 text-white grid place-items-center text-[10px] font-bold">
          TRIG
        </div>
        <div className="text-sm font-medium text-slate-900">Trigger</div>
      </div>
      {readOnly ? (
        <div className="text-xs text-slate-500 capitalize">
          {triggerType.replace(/_/g, " ")}
          {triggerConfig && Object.keys(triggerConfig).length > 0 && (
            <pre className="mt-2 bg-slate-50 rounded p-2 text-[10px] overflow-x-auto">
              {JSON.stringify(triggerConfig, null, 2)}
            </pre>
          )}
        </div>
      ) : (
        <select
          value={triggerType}
          onChange={(e) => onChange(e.target.value, null)}
          className="rounded border border-slate-300 px-2 py-1 text-sm"
        >
          <option value="manual">Manual (command bar)</option>
          <option value="scheduled">Scheduled (cron)</option>
          <option value="event">Event</option>
          <option value="time_of_day">Time of day</option>
          <option value="time_after_event">Time after event</option>
        </select>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────
// Step block (canvas)
// ─────────────────────────────────────────────────────────────────────

function StepBlock({
  step,
  index,
  selected,
  readOnly,
  onSelect,
  onMoveUp,
  onMoveDown,
  onRemove,
  canMoveUp,
  canMoveDown,
}: {
  step: Step
  index: number
  selected: boolean
  readOnly: boolean
  onSelect: () => void
  onMoveUp: () => void
  onMoveDown: () => void
  onRemove: () => void
  canMoveUp: boolean
  canMoveDown: boolean
}) {
  const { icon: Icon, color } = stepVisual(step.step_type)
  return (
    <div
      onClick={onSelect}
      className={`group relative cursor-pointer rounded-lg border bg-white p-4 transition ${
        selected ? "border-slate-900 ring-1 ring-slate-900" : "border-slate-200 hover:border-slate-400"
      }`}
    >
      <div className="flex items-center gap-3">
        <div className={`h-8 w-8 rounded grid place-items-center ${color}`}>
          <Icon className="h-4 w-4 text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
              Step {index + 1} · {step.step_type}
            </span>
          </div>
          <div className="text-sm font-medium text-slate-900 truncate">
            {stepSummary(step)}
          </div>
          <div className="text-[10px] text-slate-400 font-mono truncate">{step.step_key}</div>
        </div>
        {!readOnly && (
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition">
            <button
              onClick={(e) => { e.stopPropagation(); onMoveUp() }}
              disabled={!canMoveUp}
              className="p-1 text-slate-400 hover:text-slate-900 disabled:opacity-30"
              aria-label="Move up"
            >
              <ChevronUp className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onMoveDown() }}
              disabled={!canMoveDown}
              className="p-1 text-slate-400 hover:text-slate-900 disabled:opacity-30"
              aria-label="Move down"
            >
              <ChevronDown className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onRemove() }}
              className="p-1 text-slate-400 hover:text-red-600"
              aria-label="Delete step"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function stepVisual(type: StepType): { icon: typeof MessageSquare; color: string } {
  switch (type) {
    case "input":
      return { icon: MessageSquare, color: "bg-blue-600" }
    case "action":
      return { icon: Zap, color: "bg-violet-600" }
    case "condition":
      return { icon: GitBranch, color: "bg-amber-600" }
    case "output":
      return { icon: CheckCircle, color: "bg-emerald-600" }
  }
}

function stepSummary(step: Step): string {
  const cfg = step.config as Record<string, unknown>
  if (step.step_type === "input") return (cfg.prompt as string) || "Input"
  if (step.step_type === "action") return (cfg.action_type as string) || "Action"
  if (step.step_type === "condition") return (cfg.expression as string) || "Condition"
  if (step.step_type === "output") return (cfg.message as string) || (cfg.action_type as string) || "Output"
  return step.step_key
}

function defaultConfigForType(type: StepType): Record<string, unknown> {
  switch (type) {
    case "input":
      return { prompt: "", input_type: "text", required: true }
    case "action":
      return { action_type: "show_confirmation", message: "" }
    case "condition":
      return { expression: "" }
    case "output":
      return { action_type: "show_confirmation", message: "" }
  }
}

function AddStepButton({
  onClick,
  label,
  icon: Icon,
}: {
  onClick: () => void
  label: string
  icon: typeof MessageSquare
}) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded border border-dashed border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:border-slate-900 hover:text-slate-900"
    >
      <Plus className="h-3.5 w-3.5" />
      <Icon className="h-3.5 w-3.5" />
      {label}
    </button>
  )
}

// ─────────────────────────────────────────────────────────────────────
// Block editor (right panel)
// ─────────────────────────────────────────────────────────────────────

function BlockEditor({
  step,
  onChange,
  onConfigChange,
  onClose,
}: {
  step: Step
  onChange: (update: Partial<Step>) => void
  onConfigChange: (update: Record<string, unknown>) => void
  onClose: () => void
}) {
  const cfg = step.config as Record<string, unknown>

  return (
    <div className="p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
          Step editor
        </div>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-900 text-xs">
          Close
        </button>
      </div>

      <Field label="Step key">
        <input
          value={step.step_key}
          onChange={(e) => onChange({ step_key: e.target.value.replace(/[^a-z0-9_]/gi, "_").toLowerCase() })}
          className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm font-mono"
        />
      </Field>

      <Field label="Type">
        <select
          value={step.step_type}
          onChange={(e) => onChange({ step_type: e.target.value as StepType, config: defaultConfigForType(e.target.value as StepType) })}
          className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
        >
          <option value="input">Input — ask the user</option>
          <option value="action">Action — do something</option>
          <option value="condition">Condition — branch</option>
          <option value="output">Output — final result</option>
        </select>
      </Field>

      <div className="border-t border-slate-100 pt-4 space-y-4">
        {step.step_type === "input" && (
          <>
            <Field label="Prompt (shown to user)">
              <input
                value={(cfg.prompt as string) || ""}
                onChange={(e) => onConfigChange({ prompt: e.target.value })}
                placeholder="Which customer?"
                className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              />
            </Field>
            <Field label="Input type">
              <select
                value={(cfg.input_type as string) || "text"}
                onChange={(e) => onConfigChange({ input_type: e.target.value })}
                className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              >
                <option value="text">Text</option>
                <option value="number">Number</option>
                <option value="select">Select (dropdown)</option>
                <option value="date_picker">Date picker</option>
                <option value="datetime_picker">Date + time picker</option>
                <option value="crm_search">Search companies</option>
                <option value="record_search">Search records</option>
                <option value="user_search">Search users</option>
              </select>
            </Field>
            <Field label="Required">
              <label className="inline-flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={cfg.required !== false}
                  onChange={(e) => onConfigChange({ required: e.target.checked })}
                />
                Required
              </label>
            </Field>
          </>
        )}

        {step.step_type === "action" && (
          <>
            <Field label="Action type">
              <select
                value={(cfg.action_type as string) || "show_confirmation"}
                onChange={(e) => onConfigChange({ action_type: e.target.value })}
                className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              >
                <option value="create_record">Create record</option>
                <option value="send_email">Send email</option>
                <option value="send_notification">Send notification</option>
                <option value="log_vault_item">Log vault item</option>
                <option value="generate_document">Generate document</option>
                <option value="open_slide_over">Open slide-over</option>
                <option value="show_confirmation">Show confirmation</option>
              </select>
            </Field>
            <Field label="Config (JSON)">
              <JsonEditor
                value={cfg}
                onChange={(v) => onChange({ config: v })}
              />
            </Field>
          </>
        )}

        {step.step_type === "condition" && (
          <Field label="Expression">
            <input
              value={(cfg.expression as string) || ""}
              onChange={(e) => onConfigChange({ expression: e.target.value })}
              placeholder="{input.ask_amount} > 1000"
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm font-mono"
            />
          </Field>
        )}

        {step.step_type === "output" && (
          <Field label="Message">
            <input
              value={(cfg.message as string) || ""}
              onChange={(e) => onConfigChange({ message: e.target.value })}
              placeholder="Order created!"
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
            />
          </Field>
        )}
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 mb-1">{label}</div>
      {children}
    </div>
  )
}

function JsonEditor({
  value,
  onChange,
}: {
  value: Record<string, unknown>
  onChange: (v: Record<string, unknown>) => void
}) {
  const [text, setText] = useState(() => JSON.stringify(value, null, 2))
  const [error, setError] = useState<string | null>(null)

  // Re-sync if outer value changes (e.g. action type switch)
  const outerSerialized = useMemo(() => JSON.stringify(value, null, 2), [value])
  useEffect(() => {
    setText(outerSerialized)
  }, [outerSerialized])

  return (
    <div>
      <textarea
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          try {
            const parsed = JSON.parse(e.target.value)
            onChange(parsed)
            setError(null)
          } catch {
            setError("Invalid JSON")
          }
        }}
        rows={10}
        className="w-full rounded border border-slate-300 px-2 py-1.5 text-xs font-mono"
      />
      {error && <div className="text-[10px] text-red-600 mt-1">{error}</div>}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────
// Recent runs (read-only view for Tier 1)
// ─────────────────────────────────────────────────────────────────────

function RecentRuns({
  runs,
}: {
  runs: NonNullable<LoadedWorkflow["recent_runs"]>
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">
        Recent runs
      </div>
      <div className="space-y-1.5">
        {runs.map((r) => (
          <div key={r.id} className="flex items-center gap-3 text-xs">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                r.status === "completed"
                  ? "bg-emerald-500"
                  : r.status === "failed"
                    ? "bg-red-500"
                    : r.status === "running"
                      ? "bg-blue-500"
                      : "bg-slate-400"
              }`}
            />
            <span className="text-slate-500">{r.started_at?.slice(0, 16).replace("T", " ")}</span>
            <span className="text-slate-700 capitalize">{r.status}</span>
            <span className="text-slate-400">· {r.trigger_source}</span>
            {r.error_message && (
              <span className="text-red-600 truncate">{r.error_message}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
