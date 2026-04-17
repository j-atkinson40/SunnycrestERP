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
  Lock,
  Loader2,
  MessageSquare,
  Zap,
  GitBranch,
  CheckCircle,
} from "lucide-react"
import apiClient from "@/lib/api-client"
import { StepCard, TriggerCard as TriggerCardV2 } from "@/components/workflow/StepCard"
import {
  RUN_STATUS_DISPLAY,
  TRIGGER_SOURCE_DISPLAY,
  formatRunTimestamp,
  formatRunDuration,
  formatRelativeAge,
} from "@/utils/workflowStepSummary"

// ─────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────

type StepType = "input" | "action" | "condition" | "output"

interface Step {
  step_order: number
  step_key: string
  step_type: StepType
  config: Record<string, unknown>
  is_core?: boolean
}

interface StepParam {
  step_key: string
  param_key: string
  label: string
  description: string | null
  param_type: string
  default_value: unknown
  current_value: unknown
  effective_value: unknown
  is_configurable: boolean
  validation: Record<string, unknown> | null
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
  configurable?: boolean
  params?: StepParam[]
  added_steps?: Step[]
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
  const isNew = !workflowId

  const [loading, setLoading] = useState(!isNew)
  const [saving, setSaving] = useState(false)
  const [mode, setMode] = useState<"entry" | "builder">(isNew ? "entry" : "builder")
  const [loadedMeta, setLoadedMeta] = useState<Pick<LoadedWorkflow, "tier" | "is_system" | "editable" | "recent_runs" | "configurable"> | null>(null)
  const [params, setParams] = useState<StepParam[]>([])
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
            is_core: s.is_core,
          })),
        })
        setLoadedMeta({
          tier: d.tier,
          is_system: d.is_system,
          editable: d.editable,
          configurable: d.configurable,
          recent_runs: d.recent_runs,
        })
        setParams(d.params || [])
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
        <main
          className="flex-1 overflow-y-auto p-10"
          style={{
            // Subtle dot grid background — workspace feel, not distracting
            backgroundImage:
              "radial-gradient(circle, rgb(203 213 225 / 0.6) 1px, transparent 1px)",
            backgroundSize: "20px 20px",
          }}
        >
          <div className="mx-auto max-w-[560px] space-y-6">
            {/* Paused-run banner — prominent, shown above canvas */}
            {loadedMeta?.recent_runs?.some((r) => r.status === "awaiting_input") && (
              <PausedRunBanner runs={loadedMeta.recent_runs} />
            )}

            <TriggerCardV2
              triggerType={draft.trigger_type}
              triggerConfig={draft.trigger_config}
              workflowName={draft.name}
              workflowDescription={draft.description}
              keywords={draft.keywords}
              isReadOnly={readOnly}
              onChange={(trigger_type, trigger_config) =>
                setDraft({ ...draft, trigger_type, trigger_config })
              }
            />
            <ConnectorLine />

            {loadedMeta?.tier === 1 && params.length > 0 && draft.id && (
              <>
                <ParamsPanel
                  workflowId={draft.id}
                  params={params}
                  onChange={setParams}
                />
                <ConnectorLine />
              </>
            )}

            {draft.steps.length === 0 ? (
              <div className="rounded-lg border-2 border-dashed border-slate-300 bg-white p-10 text-center">
                <div className="text-sm text-slate-500 mb-1">Your workflow starts here</div>
                <div className="text-xs text-slate-400 mb-4">
                  Add the first step below to tell Bridgeable what should happen.
                </div>
                {!readOnly && (
                  <div className="flex flex-wrap gap-2 justify-center">
                    <AddStepButton onClick={() => addStep("input")} label="Input" icon={MessageSquare} />
                    <AddStepButton onClick={() => addStep("action")} label="Action" icon={Zap} />
                    <AddStepButton onClick={() => addStep("condition")} label="Condition" icon={GitBranch} />
                    <AddStepButton onClick={() => addStep("output")} label="Output" icon={CheckCircle} />
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                {draft.steps.map((step, i) => (
                  <div key={i}>
                    <StepCard
                      step={step}
                      stepIndex={i}
                      previousSteps={draft.steps.slice(0, i)}
                      selected={selectedStepIdx === i}
                      isReadOnly={readOnly}
                      onSelect={() => setSelectedStepIdx(i)}
                      onMoveUp={() => moveStep(i, -1)}
                      onMoveDown={() => moveStep(i, 1)}
                      onRemove={() => removeStep(i)}
                      canMoveUp={i > 0}
                      canMoveDown={i < draft.steps.length - 1}
                    />
                    {i < draft.steps.length - 1 && <ConnectorLine />}
                  </div>
                ))}
                {!readOnly && (
                  <div className="pt-4">
                    <ConnectorLine />
                    <div className="flex flex-wrap gap-2 justify-center pt-2">
                      <AddStepButton onClick={() => addStep("input")} label="Add Input" icon={MessageSquare} />
                      <AddStepButton onClick={() => addStep("action")} label="Add Action" icon={Zap} />
                      <AddStepButton onClick={() => addStep("condition")} label="Add Condition" icon={GitBranch} />
                      <AddStepButton onClick={() => addStep("output")} label="Add Output" icon={CheckCircle} />
                    </div>
                  </div>
                )}
              </div>
            )}

            {loadedMeta?.recent_runs && loadedMeta.recent_runs.length > 0 && (
              <RunHistorySection runs={loadedMeta.recent_runs} />
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
// Connector line between two cards
// ─────────────────────────────────────────────────────────────────────

function ConnectorLine() {
  return (
    <div className="flex justify-center py-1" aria-hidden="true">
      <div className="h-6 w-px bg-slate-300" />
    </div>
  )
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

type RunRow = NonNullable<LoadedWorkflow["recent_runs"]>[number]

function PausedRunBanner({ runs }: { runs: RunRow[] }) {
  const navigate = useNavigate()
  const paused = runs.find((r) => r.status === "awaiting_input")
  if (!paused) return null
  return (
    <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3">
      <div className="flex items-center gap-3">
        <span className="inline-block h-2.5 w-2.5 rounded-full bg-amber-500 animate-pulse" />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-amber-900">
            You have a paused run from {formatRelativeAge(paused.started_at)}
          </div>
          {paused.error_message && (
            <div className="text-xs text-amber-800 truncate">
              Waiting for: {paused.error_message}
            </div>
          )}
        </div>
        <button
          onClick={() => navigate(`/workflows/runs/${paused.id}`)}
          className="inline-flex items-center gap-1 rounded bg-amber-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-700"
        >
          Continue now →
        </button>
      </div>
    </div>
  )
}

function RunHistorySection({ runs }: { runs: RunRow[] }) {
  const navigate = useNavigate()
  const [expandedId, setExpandedId] = useState<string | null>(null)
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">
        Recent runs
      </div>
      <div className="space-y-2.5">
        {runs.map((r) => {
          const display = RUN_STATUS_DISPLAY[r.status] || {
            icon: "●",
            colorClass: "text-slate-500",
            label: r.status,
          }
          const dur = formatRunDuration(r.started_at, r.completed_at)
          const trigLabel = TRIGGER_SOURCE_DISPLAY[r.trigger_source] || r.trigger_source
          const expanded = expandedId === r.id
          return (
            <div key={r.id} className="border-b border-slate-100 last:border-b-0 pb-2.5 last:pb-0">
              <div className="flex items-start gap-3 text-xs">
                <span className={`text-lg leading-none ${display.colorClass}`}>
                  {display.icon}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-slate-900 font-medium">
                      {formatRunTimestamp(r.started_at)}
                    </span>
                    {dur && <span className="text-slate-400">{dur}</span>}
                  </div>
                  <div className="text-slate-600 truncate">
                    <span>{display.label}</span>
                    <span className="text-slate-400"> · {trigLabel}</span>
                  </div>
                  {r.status === "failed" && r.error_message && (
                    <div className="mt-1">
                      <button
                        onClick={() => setExpandedId(expanded ? null : r.id)}
                        className="text-red-600 hover:underline"
                      >
                        {expanded ? "Hide details" : "See details →"}
                      </button>
                      {expanded && (
                        <pre className="mt-1 rounded bg-red-50 border border-red-200 p-2 text-[10px] text-red-800 whitespace-pre-wrap">
                          {r.error_message}
                        </pre>
                      )}
                    </div>
                  )}
                </div>
                {r.status === "awaiting_input" && (
                  <button
                    onClick={() => navigate(`/workflows/runs/${r.id}`)}
                    className="inline-flex items-center gap-1 rounded bg-amber-600 px-2 py-0.5 text-[10px] font-medium text-white hover:bg-amber-700"
                  >
                    Continue →
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────────
// ParamsPanel — Tier 1 configurable step params
// ─────────────────────────────────────────────────────────────────────

function ParamsPanel({
  workflowId,
  params,
  onChange,
}: {
  workflowId: string
  params: StepParam[]
  onChange: (next: StepParam[]) => void
}) {
  // Group by step_key for readability
  const byStep = useMemo(() => {
    const map = new Map<string, StepParam[]>()
    for (const p of params) {
      const arr = map.get(p.step_key) || []
      arr.push(p)
      map.set(p.step_key, arr)
    }
    return Array.from(map.entries())
  }, [params])

  const [savingKey, setSavingKey] = useState<string | null>(null)
  const [localValues, setLocalValues] = useState<Record<string, unknown>>(() => {
    const init: Record<string, unknown> = {}
    for (const p of params) {
      init[`${p.step_key}.${p.param_key}`] =
        p.current_value !== null && p.current_value !== undefined
          ? p.current_value
          : p.default_value
    }
    return init
  })

  const save = async (p: StepParam) => {
    const key = `${p.step_key}.${p.param_key}`
    setSavingKey(key)
    try {
      await apiClient.put(
        `/workflows/${workflowId}/params/${p.step_key}/${p.param_key}`,
        { current_value: localValues[key] },
      )
      // Update the outer params array so the displayed current_value refreshes
      onChange(
        params.map((pp) =>
          pp.step_key === p.step_key && pp.param_key === p.param_key
            ? { ...pp, current_value: localValues[key], effective_value: localValues[key] }
            : pp,
        ),
      )
    } finally {
      setSavingKey(null)
    }
  }

  return (
    <div className="rounded-lg border border-violet-200 bg-violet-50/40 p-4">
      <div className="flex items-center gap-2 mb-1">
        <Sparkles className="h-4 w-4 text-violet-600" />
        <div className="text-sm font-medium text-slate-900">Configure this workflow</div>
      </div>
      <div className="text-xs text-slate-500 mb-4">
        Core steps are locked, but these options let you tailor how the workflow runs.
      </div>

      <div className="space-y-5">
        {byStep.map(([stepKey, stepParams]) => (
          <div key={stepKey}>
            <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 mb-2">
              Step: <span className="font-mono">{stepKey}</span>
            </div>
            <div className="space-y-3 pl-2 border-l-2 border-violet-200">
              {stepParams.map((p) => {
                const key = `${p.step_key}.${p.param_key}`
                const val = localValues[key]
                const hasOverride = p.current_value !== null && p.current_value !== undefined
                return (
                  <div key={key} className="pl-3">
                    <div className="flex items-center gap-2">
                      <label className="text-xs font-medium text-slate-700">{p.label}</label>
                      {hasOverride && (
                        <span className="rounded bg-violet-100 px-1.5 py-0.5 text-[9px] text-violet-700">
                          Customized
                        </span>
                      )}
                    </div>
                    <ParamInput
                      param={p}
                      value={val}
                      onChange={(v) => setLocalValues((prev) => ({ ...prev, [key]: v }))}
                    />
                    {p.description && (
                      <div className="text-[10px] text-slate-500 mt-0.5">{p.description}</div>
                    )}
                    <div className="mt-1 flex items-center gap-2">
                      <button
                        onClick={() => save(p)}
                        disabled={savingKey === key}
                        className="inline-flex items-center gap-1 rounded border border-slate-300 bg-white px-2 py-0.5 text-[10px] font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                      >
                        {savingKey === key ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                        Save
                      </button>
                      {hasOverride && (
                        <button
                          onClick={async () => {
                            setLocalValues((prev) => ({ ...prev, [key]: p.default_value }))
                            setSavingKey(key)
                            try {
                              await apiClient.put(
                                `/workflows/${workflowId}/params/${p.step_key}/${p.param_key}`,
                                { current_value: null },
                              )
                              onChange(
                                params.map((pp) =>
                                  pp.step_key === p.step_key && pp.param_key === p.param_key
                                    ? { ...pp, current_value: null, effective_value: p.default_value }
                                    : pp,
                                ),
                              )
                            } finally {
                              setSavingKey(null)
                            }
                          }}
                          className="text-[10px] text-slate-500 hover:text-slate-900 underline"
                        >
                          Reset to default
                        </button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ParamInput({
  param,
  value,
  onChange,
}: {
  param: StepParam
  value: unknown
  onChange: (v: unknown) => void
}) {
  const t = param.param_type

  if (t === "toggle") {
    return (
      <label className="inline-flex items-center gap-2 text-xs mt-1">
        <input
          type="checkbox"
          checked={!!value}
          onChange={(e) => onChange(e.target.checked)}
        />
        Enabled
      </label>
    )
  }
  if (t === "number") {
    const v = param.validation as { min?: number; max?: number } | null
    return (
      <input
        type="number"
        value={(value as number | string | null) ?? ""}
        min={v?.min}
        max={v?.max}
        onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        className="mt-1 w-32 rounded border border-slate-300 px-2 py-1 text-xs"
      />
    )
  }
  if (t === "email_list" || t === "role_multi_select") {
    const list = Array.isArray(value) ? (value as string[]) : []
    const placeholder = t === "email_list" ? "email@example.com, another@example.com" : "admin, manager"
    return (
      <input
        type="text"
        value={list.join(", ")}
        placeholder={placeholder}
        onChange={(e) =>
          onChange(
            e.target.value
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean),
          )
        }
        className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-xs"
      />
    )
  }
  // text, email, select fallback: string input
  return (
    <input
      type={t === "email" ? "email" : "text"}
      value={(value as string | null) ?? ""}
      onChange={(e) => onChange(e.target.value)}
      className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-xs"
    />
  )
}
