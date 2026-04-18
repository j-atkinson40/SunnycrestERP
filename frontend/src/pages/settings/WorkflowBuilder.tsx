// Workflow Builder — canvas + block editor + AI describe entry
//
// Routes:
//   /settings/workflows/new                  — blank or AI-describe entry
//   /settings/workflows/:workflowId/edit     — edit custom workflow
//   /settings/workflows/:workflowId/view     — read-only (Tier 1)

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import {
  ArrowLeft,
  Save,
  Play,
  Sparkles,
  Lock,
  Loader2,
  Trash2,
  ChevronDown,
  Bot,
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  Plus,
  X,
} from "lucide-react"
import apiClient from "@/lib/api-client"
import { StepCard, TriggerCard as TriggerCardV2 } from "@/components/workflow/StepCard"
import {
  BlockLibrary,
  stepDraftFromBlock,
  type BlockDefinition,
} from "@/components/workflow/BlockLibrary"
import { InterStepDropZone, EndDropZone } from "@/components/workflow/DropZones"
import { PlaceholderCard } from "@/components/workflow/PlaceholderCard"
import VariablePicker, { type StepSummary as PickerStepSummary } from "@/components/workflow/VariablePicker"
import CredentialModal from "@/components/workflow/CredentialModal"
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

type StepType = "input" | "action" | "playwright_action" | "condition" | "output"

interface Step {
  step_order: number
  step_key: string
  step_type: StepType
  config: Record<string, unknown>
  is_core?: boolean
  display_name?: string | null
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
  const [placeholderIndex, setPlaceholderIndex] = useState<number | null>(null)

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
            display_name: (s as Step).display_name ?? null,
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

  // Insert a step built from a BlockDefinition at the given index.
  // If index is null/undefined → append at end.
  const insertBlock = useCallback(
    (block: BlockDefinition, atIndex?: number) => {
      setDraft((prev) => {
        const insertAt = atIndex ?? prev.steps.length
        const base = stepDraftFromBlock(block, insertAt)
        const next = [...prev.steps]
        next.splice(insertAt, 0, base as Step)
        // Renumber step_order
        return {
          ...prev,
          steps: next.map((s, i) => ({ ...s, step_order: i + 1 })),
        }
      })
      setSelectedStepIdx(atIndex ?? draft.steps.length)
    },
    [draft.steps.length],
  )

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
        {/* Canvas — takes all remaining width */}
        <main
          className="flex-1 overflow-y-auto p-10"
          style={{
            backgroundImage:
              "radial-gradient(circle, rgb(203 213 225 / 0.6) 1px, transparent 1px)",
            backgroundSize: "20px 20px",
          }}
          onDragOver={(e) => {
            if (e.dataTransfer.types.includes("application/x-workflow-block")) {
              e.preventDefault()
              e.dataTransfer.dropEffect = "copy"
            }
          }}
          onDrop={(e) => {
            const data = e.dataTransfer.getData("application/x-workflow-block")
            if (!data) return
            e.preventDefault()
            try {
              const block = JSON.parse(data) as BlockDefinition
              insertBlock(block)
            } catch { /* ignore */ }
          }}
        >
          <div className="mx-auto max-w-[560px] space-y-6">
            {/* Paused-run banner */}
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
              placeholderIndex === 0 && !readOnly ? (
                <PlaceholderCard
                  onSelect={(block) => {
                    setPlaceholderIndex(null)
                    insertBlock(block, 0)
                  }}
                  onCancel={() => setPlaceholderIndex(null)}
                />
              ) : readOnly ? (
                <EmptyCanvasStep
                  readOnly={readOnly}
                  onDrop={(block) => insertBlock(block)}
                />
              ) : (
                <EndDropZone
                  onDrop={(block) => insertBlock(block, 0)}
                  onClickAdd={() => setPlaceholderIndex(0)}
                />
              )
            ) : (
              <div className="space-y-2">
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
                    {i < draft.steps.length - 1 && !readOnly && (
                      placeholderIndex === i + 1 ? (
                        <div className="my-2">
                          <PlaceholderCard
                            onSelect={(block) => {
                              setPlaceholderIndex(null)
                              insertBlock(block, i + 1)
                            }}
                            onCancel={() => setPlaceholderIndex(null)}
                          />
                        </div>
                      ) : (
                        <InterStepDropZone
                          onDrop={(block) => insertBlock(block, i + 1)}
                          onClickAdd={() => setPlaceholderIndex(i + 1)}
                        />
                      )
                    )}
                    {i < draft.steps.length - 1 && readOnly && <ConnectorLine />}
                  </div>
                ))}
                {!readOnly && (
                  placeholderIndex === draft.steps.length ? (
                    <div className="my-2">
                      <PlaceholderCard
                        onSelect={(block) => {
                          setPlaceholderIndex(null)
                          insertBlock(block, draft.steps.length)
                        }}
                        onCancel={() => setPlaceholderIndex(null)}
                      />
                    </div>
                  ) : (
                    <EndDropZone
                      onDrop={(block) => insertBlock(block)}
                      onClickAdd={() => setPlaceholderIndex(draft.steps.length)}
                    />
                  )
                )}
              </div>
            )}

            {loadedMeta?.recent_runs && loadedMeta.recent_runs.length > 0 && (
              <RunHistorySection runs={loadedMeta.recent_runs} />
            )}
          </div>
        </main>

        {/* Persistent right sidebar — double-wide flex container that
            slides between the library (left half) and the editor (right
            half). Both panels are always mounted so the library keeps
            its scroll position and there's no mount flash. */}
        <aside className="w-80 flex-shrink-0 border-l border-slate-200 bg-white overflow-hidden">
          <div
            className="flex h-full transition-transform duration-200 ease-in-out"
            style={{
              width: "200%",
              transform: selectedStep ? "translateX(-50%)" : "translateX(0%)",
            }}
          >
            {/* Left pane — library */}
            <div className="flex flex-col h-full overflow-hidden" style={{ width: "50%" }}>
              <WorkflowDetailsPanel
                triggerType={draft.trigger_type}
                vertical={draft.vertical}
                keywords={draft.keywords}
              />
              {readOnly && <TemplateBanner tier={loadedMeta?.tier} />}
              <BlockLibrary
                onDragStart={() => {}}
                onClick={(block) => insertBlock(block)}
                workflowId={draft.id}
              />
            </div>

            {/* Right pane — editor (always mounted; empty when nothing selected) */}
            <div className="flex flex-col h-full overflow-hidden" style={{ width: "50%" }}>
              {selectedStep ? (
                <SidebarEditorHeader
                  step={selectedStep}
                  onBack={() => setSelectedStepIdx(null)}
                  onDelete={
                    readOnly
                      ? undefined
                      : () => {
                          if (selectedStepIdx !== null) removeStep(selectedStepIdx)
                        }
                  }
                  onRename={
                    readOnly
                      ? undefined
                      : (name) => updateStep(selectedStepIdx!, { display_name: name || null })
                  }
                >
                  <BlockEditor
                    step={selectedStep}
                    priorSteps={draft.steps.slice(0, selectedStepIdx!)}
                    readOnly={readOnly}
                    onChange={(update) => updateStep(selectedStepIdx!, update)}
                    onConfigChange={(configUpdate) =>
                      updateStepConfig(selectedStepIdx!, configUpdate)
                    }
                    onClose={() => setSelectedStepIdx(null)}
                  />
                </SidebarEditorHeader>
              ) : (
                <div className="flex-1" />
              )}
            </div>
          </div>
        </aside>

      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────
// Sidebar editor header (sits above BlockEditor inside the right sidebar)
// ─────────────────────────────────────────────────────────────────────

function SidebarEditorHeader({
  step,
  onBack,
  onDelete,
  onRename,
  children,
}: {
  step: Step
  onBack: () => void
  onDelete?: () => void
  onRename?: (name: string) => void
  children: React.ReactNode
}) {
  const TYPE_LABELS: Record<string, string> = {
    input: "Collect Input",
    action: "Action",
    playwright_action: "Automation",
    condition: "Condition",
    output: "Output",
    trigger: "Trigger",
  }
  const typeLabel = TYPE_LABELS[step.step_type] ?? step.step_type

  // Two-click delete: first click arms, second click fires; auto-disarms after 3s
  const [deleteArmed, setDeleteArmed] = useState(false)
  const disarmRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  function handleDeleteClick() {
    if (!deleteArmed) {
      setDeleteArmed(true)
      disarmRef.current = setTimeout(() => setDeleteArmed(false), 3000)
    } else {
      if (disarmRef.current) clearTimeout(disarmRef.current)
      setDeleteArmed(false)
      onDelete?.()
    }
  }

  const displayValue = step.display_name ?? ""

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 pt-3 pb-2 border-b border-slate-100 flex-shrink-0">
        {/* Top row: back + delete */}
        <div className="flex items-center gap-2 mb-2">
          <button
            onClick={onBack}
            className="group inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-900"
          >
            <ArrowLeft className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5" />
            Back
          </button>
          <div className="flex-1" />
          {!step.is_core && onDelete && (
            <button
              onClick={handleDeleteClick}
              className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-medium transition-colors ${
                deleteArmed
                  ? "bg-red-600 text-white hover:bg-red-700"
                  : "text-slate-400 hover:text-red-600"
              }`}
              aria-label="Delete step"
            >
              <Trash2 className="h-3 w-3" />
              {deleteArmed ? "Confirm delete" : ""}
            </button>
          )}
          {step.is_core && (
            <span className="inline-flex items-center gap-1 text-[10px] text-slate-400">
              <Lock className="h-3 w-3" />
              Core
            </span>
          )}
        </div>

        {/* Step type badge + rename input */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 whitespace-nowrap">
            {typeLabel}
          </span>
          <span className="text-slate-300">·</span>
          {onRename ? (
            <input
              type="text"
              value={displayValue}
              onChange={(e) => onRename(e.target.value)}
              placeholder={`Name this step…`}
              className="flex-1 min-w-0 text-sm font-medium text-slate-900 bg-transparent outline-none placeholder:text-slate-300 border-b border-transparent focus:border-slate-300 transition-colors"
            />
          ) : (
            <span className="text-sm font-medium text-slate-900 truncate">
              {displayValue || step.step_key}
            </span>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-4">{children}</div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────
// WorkflowDetailsPanel — collapsed by default, sits at the top of the
// sidebar above the BlockLibrary. Exposes trigger/vertical/keywords
// without stealing the sidebar's main real estate.
// ─────────────────────────────────────────────────────────────────────

function WorkflowDetailsPanel({
  triggerType,
  vertical,
  keywords,
}: {
  triggerType: string
  vertical?: string | null
  keywords?: string[]
}) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border-b border-slate-100 flex-shrink-0">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-slate-50 transition"
      >
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Workflow details
        </span>
        <ChevronDown
          className={`h-3.5 w-3.5 text-slate-400 transition-transform ${
            open ? "" : "-rotate-90"
          }`}
        />
      </button>
      {open && (
        <div className="px-4 pb-3 space-y-2.5">
          <div>
            <div className="text-[10px] text-slate-400">Trigger</div>
            <div className="text-xs text-slate-700 capitalize">
              {triggerType.replace(/_/g, " ")}
            </div>
          </div>
          {vertical && (
            <div>
              <div className="text-[10px] text-slate-400">Vertical</div>
              <div className="text-xs text-slate-700 capitalize">
                {vertical.replace(/_/g, " ")}
              </div>
            </div>
          )}
          {keywords && keywords.length > 0 && (
            <div>
              <div className="text-[10px] text-slate-400 mb-1">Keywords</div>
              <div className="flex flex-wrap gap-1">
                {keywords.map((kw) => (
                  <span
                    key={kw}
                    className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-700"
                  >
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────
// TemplateBanner — small amber banner explaining lock state on read-only
// workflows. Shown above the library so users see why core steps can't
// be removed.
// ─────────────────────────────────────────────────────────────────────

function TemplateBanner({ tier }: { tier?: number }) {
  if (tier === 1) {
    return (
      <div className="mx-3 mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 flex-shrink-0">
        <div className="text-[11px] font-medium text-amber-800 mb-0.5">
          🔒 Platform-locked
        </div>
        <div className="text-[10px] text-amber-700 leading-snug">
          Core steps can't be removed. You can configure options and add your
          own follow-up steps.
        </div>
      </div>
    )
  }
  if (tier === 2 || tier === 3) {
    return (
      <div className="mx-3 mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 flex-shrink-0">
        <div className="text-[11px] font-medium text-slate-800 mb-0.5">
          📋 Template
        </div>
        <div className="text-[10px] text-slate-600 leading-snug">
          This is a template. Customize it by starting a new workflow from
          this one.
        </div>
      </div>
    )
  }
  return null
}

// ─────────────────────────────────────────────────────────────────────
// Empty canvas card — shown when no steps exist yet
// ─────────────────────────────────────────────────────────────────────

function EmptyCanvasStep({
  readOnly,
  onDrop,
}: {
  readOnly: boolean
  onDrop: (block: BlockDefinition) => void
}) {
  const [dragOver, setDragOver] = useState(false)

  return (
    <div
      onDragOver={(e) => {
        if (!readOnly && e.dataTransfer.types.includes("application/x-workflow-block")) {
          e.preventDefault()
          setDragOver(true)
        }
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        if (readOnly) return
        const data = e.dataTransfer.getData("application/x-workflow-block")
        if (!data) return
        e.preventDefault()
        setDragOver(false)
        try {
          onDrop(JSON.parse(data) as BlockDefinition)
        } catch { /* noop */ }
      }}
      className={`rounded-xl border-2 border-dashed p-8 text-center transition ${
        dragOver
          ? "border-blue-400 bg-blue-50"
          : "border-slate-300 bg-slate-50/50"
      }`}
    >
      <div className="mx-auto w-12 h-12 rounded-xl grid place-items-center text-2xl text-slate-400 bg-white border border-slate-200">
        +
      </div>
      <div className="mt-3 text-sm font-medium text-slate-700">
        Add your first step
      </div>
      <div className="mt-1 text-xs text-slate-500">
        {readOnly
          ? "This workflow has no steps yet."
          : "Drag a block from the sidebar or click one to add it."}
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
    <div className="flex flex-col items-center py-0.5" aria-hidden="true">
      <div className="h-7 w-0.5 bg-slate-400" />
      <div
        className="h-0 w-0 border-l-[5px] border-r-[5px] border-t-[6px] border-l-transparent border-r-transparent border-t-slate-400"
      />
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

// ─────────────────────────────────────────────────────────────────────
// Block editor (right panel)
// ─────────────────────────────────────────────────────────────────────

function BlockEditor({
  step,
  priorSteps = [],
  onChange,
  onConfigChange,
  readOnly = false,
}: {
  step: Step
  priorSteps?: Step[]
  onChange: (update: Partial<Step>) => void
  onConfigChange: (update: Record<string, unknown>) => void
  onClose?: () => void  // kept for parent call-site compatibility
  readOnly?: boolean
}) {
  const cfg = step.config as Record<string, unknown>
  // Core means "can't remove" — params are still editable
  const locked = readOnly

  return (
    <div className="space-y-4">
      {readOnly && (
        <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-900">
          🔒 View-only — this workflow is read-only in this view.
        </div>
      )}

      <Field label="Step key">
        <input
          value={step.step_key}
          onChange={(e) => onChange({ step_key: e.target.value.replace(/[^a-z0-9_]/gi, "_").toLowerCase() })}
          disabled={locked}
          className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm font-mono disabled:bg-slate-50 disabled:text-slate-500"
        />
      </Field>

      {step.step_type !== "playwright_action" && (
        <Field label="Type">
          <select
            value={step.step_type}
            onChange={(e) => onChange({ step_type: e.target.value as StepType, config: defaultConfigForType(e.target.value as StepType) })}
            disabled={locked}
            className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm disabled:bg-slate-50 disabled:text-slate-500"
          >
            <option value="input">Input — ask the user</option>
            <option value="action">Action — do something</option>
            <option value="condition">Condition — branch</option>
            <option value="output">Output — final result</option>
          </select>
        </Field>
      )}

      <div
        className={`border-t border-slate-100 pt-4 space-y-4 ${
          locked ? "opacity-70 pointer-events-none select-none" : ""
        }`}
      >
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

        {step.step_type === "playwright_action" && (
          <PlaywrightActionConfig
            cfg={cfg}
            priorSteps={priorSteps}
            onConfigChange={onConfigChange}
          />
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

// ─────────────────────────────────────────────────────────────────────
// PlaywrightActionConfig — type-specific configurator for automation steps
// ─────────────────────────────────────────────────────────────────────

interface ScriptMeta {
  name: string
  description: string
  service_key: string
  input_schema: string[]
  output_schema: string[]
}

function PlaywrightActionConfig({
  cfg,
  priorSteps,
  onConfigChange,
}: {
  cfg: Record<string, unknown>
  priorSteps: Step[]
  onConfigChange: (update: Record<string, unknown>) => void
}) {
  const scriptName = (cfg.script_name as string) || ""
  const [scripts, setScripts] = useState<ScriptMeta[]>([])
  const [accountStatus, setAccountStatus] = useState<{
    connected: boolean
    last_verified_at?: string | null
  } | null>(null)
  const [credModalOpen, setCredModalOpen] = useState(false)

  // Load available scripts once
  useEffect(() => {
    apiClient.get<ScriptMeta[]>("/external-accounts/available-scripts")
      .then((r) => setScripts(r.data))
      .catch(() => {})
  }, [])

  // Load account status whenever script changes
  useEffect(() => {
    if (!scriptName) { setAccountStatus(null); return }
    const s = scripts.find((s) => s.name === scriptName)
    if (!s?.service_key) { setAccountStatus(null); return }
    apiClient.get<{ connected: boolean; last_verified_at?: string | null }>(
      `/external-accounts/${s.service_key}/status`
    )
      .then((r) => setAccountStatus(r.data))
      .catch(() => setAccountStatus(null))
  }, [scriptName, scripts])

  const selectedScript = scripts.find((s) => s.name === scriptName)
  const serviceKey = selectedScript?.service_key ?? ""
  const inputMapping = (cfg.input_mapping as Record<string, string>) || {}
  const outputMapping = (cfg.output_mapping as Record<string, string>) || {}
  const requiresApproval = !!(cfg.requires_approval)
  const approvalPrompt = (cfg.approval_prompt as string) || ""

  // Helpers
  const pickerSteps: PickerStepSummary[] = priorSteps.map((s) => ({
    step_key: s.step_key,
    step_type: s.step_type,
    display_name: s.display_name,
    config: s.config as Record<string, unknown>,
  }))

  function setInputMapping(key: string, value: string) {
    onConfigChange({ input_mapping: { ...inputMapping, [key]: value } })
  }
  function removeInputMapping(key: string) {
    const next = { ...inputMapping }
    delete next[key]
    onConfigChange({ input_mapping: next })
  }
  function setOutputMapping(key: string, value: string) {
    onConfigChange({ output_mapping: { ...outputMapping, [key]: value } })
  }
  function removeOutputMapping(key: string) {
    const next = { ...outputMapping }
    delete next[key]
    onConfigChange({ output_mapping: next })
  }

  return (
    <div className="space-y-5">
      {/* Script selector */}
      <div>
        <div className="flex items-center gap-1.5 mb-1">
          <Bot className="h-3.5 w-3.5 text-slate-500" />
          <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            Script
          </span>
        </div>
        <select
          value={scriptName}
          onChange={(e) => onConfigChange({ script_name: e.target.value })}
          className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
        >
          <option value="">— choose script —</option>
          {scripts.map((s) => (
            <option key={s.name} value={s.name}>
              {s.name}
            </option>
          ))}
        </select>
        {selectedScript && (
          <div className="mt-1 text-[10px] text-slate-400">
            {selectedScript.description}
          </div>
        )}
      </div>

      {/* Account connection status */}
      {selectedScript && (
        <div className="rounded border border-slate-200 px-3 py-2.5 flex items-center gap-3">
          {accountStatus === null ? (
            <Loader2 className="h-4 w-4 text-slate-300 animate-spin flex-shrink-0" />
          ) : accountStatus.connected ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-500 flex-shrink-0" />
          ) : (
            <AlertCircle className="h-4 w-4 text-amber-500 flex-shrink-0" />
          )}
          <div className="flex-1 min-w-0">
            <div className="text-xs font-medium text-slate-700">
              {selectedScript.service_key || "External account"}
            </div>
            {accountStatus?.connected ? (
              <div className="text-[10px] text-slate-400">
                Connected
                {accountStatus.last_verified_at
                  ? ` · verified ${new Date(accountStatus.last_verified_at).toLocaleDateString()}`
                  : ""}
              </div>
            ) : (
              <div className="text-[10px] text-amber-600">Not connected</div>
            )}
          </div>
          <button
            type="button"
            onClick={() => setCredModalOpen(true)}
            className="text-[10px] text-blue-600 hover:underline whitespace-nowrap"
          >
            {accountStatus?.connected ? "Update" : "Connect"}
          </button>
          <a
            href="/settings/external-accounts"
            target="_blank"
            rel="noopener"
            className="text-slate-400 hover:text-slate-600"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </div>
      )}

      {/* Input mapping */}
      <div>
        <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 mb-2">
          Input mapping
          <span className="ml-1 font-normal normal-case text-slate-400">
            (pass workflow data into the script)
          </span>
        </div>
        <div className="space-y-2">
          {/* Known inputs from script schema */}
          {(selectedScript?.input_schema ?? []).map((key) => (
            <div key={key} className="flex items-center gap-2">
              <span className="w-28 flex-shrink-0 text-xs font-mono text-slate-600 truncate">
                {key}
              </span>
              <div className="flex-1 flex items-center gap-1">
                <input
                  value={inputMapping[key] ?? ""}
                  onChange={(e) => setInputMapping(key, e.target.value)}
                  placeholder="{output.step.field}"
                  className="flex-1 rounded border border-slate-300 px-2 py-1 text-xs font-mono"
                />
                <VariablePicker
                  priorSteps={pickerSteps}
                  onSelect={(v) => setInputMapping(key, v)}
                />
              </div>
            </div>
          ))}
          {/* Free-form additional mappings */}
          {Object.entries(inputMapping)
            .filter(([k]) => !(selectedScript?.input_schema ?? []).includes(k))
            .map(([key, val]) => (
              <div key={key} className="flex items-center gap-2">
                <input
                  value={key}
                  onChange={(e) => {
                    removeInputMapping(key)
                    setInputMapping(e.target.value, val)
                  }}
                  className="w-28 flex-shrink-0 rounded border border-slate-300 px-2 py-1 text-xs font-mono"
                />
                <div className="flex-1 flex items-center gap-1">
                  <input
                    value={val}
                    onChange={(e) => setInputMapping(key, e.target.value)}
                    placeholder="{output.step.field}"
                    className="flex-1 rounded border border-slate-300 px-2 py-1 text-xs font-mono"
                  />
                  <VariablePicker
                    priorSteps={pickerSteps}
                    onSelect={(v) => setInputMapping(key, v)}
                  />
                  <button
                    type="button"
                    onClick={() => removeInputMapping(key)}
                    className="text-slate-400 hover:text-red-500"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))}
          <button
            type="button"
            onClick={() => setInputMapping(`input_${Date.now()}`, "")}
            className="inline-flex items-center gap-1 text-[10px] text-blue-600 hover:underline"
          >
            <Plus className="h-3 w-3" />
            Add input
          </button>
        </div>
      </div>

      {/* Output mapping */}
      <div>
        <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 mb-2">
          Output mapping
          <span className="ml-1 font-normal normal-case text-slate-400">
            (capture results from the script)
          </span>
        </div>
        <div className="space-y-2">
          {(selectedScript?.output_schema ?? []).map((key) => (
            <div key={key} className="flex items-center gap-2">
              <span className="w-28 flex-shrink-0 text-xs font-mono text-slate-600 truncate">
                {key}
              </span>
              <input
                value={outputMapping[key] ?? key}
                onChange={(e) => setOutputMapping(key, e.target.value)}
                placeholder={key}
                className="flex-1 rounded border border-slate-300 px-2 py-1 text-xs font-mono"
              />
            </div>
          ))}
          {Object.entries(outputMapping)
            .filter(([k]) => !(selectedScript?.output_schema ?? []).includes(k))
            .map(([key, val]) => (
              <div key={key} className="flex items-center gap-2">
                <input
                  value={key}
                  onChange={(e) => {
                    removeOutputMapping(key)
                    setOutputMapping(e.target.value, val)
                  }}
                  className="w-28 flex-shrink-0 rounded border border-slate-300 px-2 py-1 text-xs font-mono"
                />
                <input
                  value={val}
                  onChange={(e) => setOutputMapping(key, e.target.value)}
                  className="flex-1 rounded border border-slate-300 px-2 py-1 text-xs font-mono"
                />
                <button
                  type="button"
                  onClick={() => removeOutputMapping(key)}
                  className="text-slate-400 hover:text-red-500"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          <button
            type="button"
            onClick={() => setOutputMapping(`output_${Date.now()}`, "")}
            className="inline-flex items-center gap-1 text-[10px] text-blue-600 hover:underline"
          >
            <Plus className="h-3 w-3" />
            Add output
          </button>
        </div>
      </div>

      {/* Approval gate toggle */}
      <div className="rounded border border-slate-200 p-3 space-y-2">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={requiresApproval}
            onChange={(e) => onConfigChange({ requires_approval: e.target.checked })}
            className="rounded"
          />
          <span className="text-xs font-medium text-slate-700">
            Require human approval before running
          </span>
        </label>
        {requiresApproval && (
          <Field label="Approval prompt">
            <input
              value={approvalPrompt}
              onChange={(e) => onConfigChange({ approval_prompt: e.target.value })}
              placeholder="Review the order before placing it on Uline…"
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
            />
          </Field>
        )}
      </div>

      {credModalOpen && serviceKey && (
        <CredentialModal
          serviceKey={serviceKey}
          onClose={() => setCredModalOpen(false)}
          onSaved={() => {
            setAccountStatus({ connected: true })
          }}
        />
      )}
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
