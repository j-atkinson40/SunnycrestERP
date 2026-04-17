// StepCard — human-readable workflow step card for the builder/viewer canvas.
//
// Consumes a step + previous steps, asks workflowStepSummary.ts to turn the
// config dict into a plain-English headline/subline/fields/result, then
// renders a card with a colored left border per step type, variable pills,
// and footer controls.

import { useState } from "react"
import {
  Zap,
  MessageSquare,
  GitBranch,
  CheckCircle,
  Lock,
  Edit3,
  Trash2,
  ChevronUp,
  ChevronDown,
  Sliders,
  ArrowUpRight,
} from "lucide-react"
import {
  generateStepSummary,
  generateWorkflowTriggerSummary,
  type StepLike,
} from "@/utils/workflowStepSummary"

export type StepType = "trigger" | "input" | "action" | "condition" | "output"

type StyleKey = StepType

const STEP_STYLES: Record<
  StyleKey,
  {
    border: string
    bg: string
    label: string
    labelColor: string
    pillBg: string
    pillText: string
    icon: typeof MessageSquare
    iconBg: string
  }
> = {
  trigger: {
    border: "border-l-slate-900",
    bg: "bg-white",
    label: "STARTS WHEN",
    labelColor: "text-slate-900",
    pillBg: "bg-slate-100",
    pillText: "text-slate-800",
    icon: Zap,
    iconBg: "bg-slate-900",
  },
  input: {
    border: "border-l-blue-500",
    bg: "bg-white",
    label: "COLLECTS INPUT",
    labelColor: "text-blue-700",
    pillBg: "bg-blue-50",
    pillText: "text-blue-700",
    icon: MessageSquare,
    iconBg: "bg-blue-600",
  },
  action: {
    border: "border-l-violet-500",
    bg: "bg-white",
    label: "TAKES ACTION",
    labelColor: "text-violet-700",
    pillBg: "bg-violet-50",
    pillText: "text-violet-700",
    icon: Zap,
    iconBg: "bg-violet-600",
  },
  condition: {
    border: "border-l-amber-500",
    bg: "bg-white",
    label: "CHECKS A CONDITION",
    labelColor: "text-amber-700",
    pillBg: "bg-amber-50",
    pillText: "text-amber-800",
    icon: GitBranch,
    iconBg: "bg-amber-500",
  },
  output: {
    border: "border-l-emerald-500",
    bg: "bg-white",
    label: "FINISHES WITH",
    labelColor: "text-emerald-700",
    pillBg: "bg-emerald-50",
    pillText: "text-emerald-700",
    icon: CheckCircle,
    iconBg: "bg-emerald-600",
  },
}

// ─────────────────────────────────────────────────────────────────────
// StepCard — for regular workflow steps (input/action/condition/output)
// ─────────────────────────────────────────────────────────────────────

export interface StepCardProps {
  step: StepLike
  stepIndex: number
  previousSteps: StepLike[]
  selected?: boolean
  isReadOnly?: boolean
  onSelect?: () => void
  onMoveUp?: () => void
  onMoveDown?: () => void
  onRemove?: () => void
  canMoveUp?: boolean
  canMoveDown?: boolean
  onConfigure?: () => void
}

export function StepCard({
  step,
  stepIndex,
  previousSteps,
  selected,
  isReadOnly,
  onSelect,
  onMoveUp,
  onMoveDown,
  onRemove,
  canMoveUp,
  canMoveDown,
  onConfigure,
}: StepCardProps) {
  const isCore = !!step.is_core
  const typ = step.step_type as StepType
  const style = STEP_STYLES[typ] || STEP_STYLES.action
  const summary = generateStepSummary(step, previousSteps)
  const Icon = style.icon

  return (
    <div
      onClick={onSelect}
      className={`group relative w-full cursor-pointer rounded-lg border border-slate-200 border-l-4 ${style.border} ${style.bg} shadow-sm transition hover:shadow ${
        selected ? "ring-2 ring-offset-1 ring-slate-900" : ""
      }`}
    >
      {/* Top row: type label + core/tenant badge */}
      <div className="flex items-center justify-between px-5 pt-4">
        <div className="flex items-center gap-2">
          <div className={`h-6 w-6 rounded grid place-items-center ${style.iconBg}`}>
            <Icon className="h-3.5 w-3.5 text-white" />
          </div>
          <span className={`text-[10px] font-semibold tracking-wide uppercase ${style.labelColor}`}>
            {style.label}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {isCore ? (
            <span className="inline-flex items-center gap-1 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-700">
              <Lock className="h-3 w-3" />
              CORE
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded bg-violet-50 px-1.5 py-0.5 text-[10px] font-medium text-violet-700">
              <Edit3 className="h-3 w-3" />
              YOUR STEP
            </span>
          )}
        </div>
      </div>

      {/* Headline + subline */}
      <div className="px-5 pt-2">
        <div className="text-base font-semibold text-slate-900 leading-snug">
          {summary.headline}
        </div>
        {summary.subline && (
          <div className="text-xs text-slate-500 mt-1">{summary.subline}</div>
        )}
      </div>

      {/* Fields */}
      {summary.fields.length > 0 && (
        <div className="px-5 pt-3 space-y-1">
          {summary.fields.map((f, i) => (
            <div key={i} className="flex items-baseline gap-2 text-xs">
              <span className="text-slate-500 flex-shrink-0">{f.label}:</span>
              {f.isVariable ? (
                <VariablePill value={f.value} path={f.variablePath} />
              ) : (
                <span className="text-slate-900 truncate">{f.value}</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Result variable */}
      {summary.resultVariable && (
        <div className="px-5 pt-3">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-500">Result saved as:</span>
            <span
              className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium ${style.pillBg} ${style.pillText}`}
            >
              {summary.resultVariable}
            </span>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="mt-4 flex items-center justify-between border-t border-slate-100 px-5 py-2">
        <div className="text-[10px] text-slate-400">
          Step {stepIndex + 1} · <span className="font-mono">{step.step_key}</span>
        </div>
        {!isReadOnly && (
          <div className="flex items-center gap-1">
            {isCore && onConfigure && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onConfigure()
                }}
                className="inline-flex items-center gap-1 rounded border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-medium text-slate-700 hover:bg-slate-50"
              >
                <Sliders className="h-3 w-3" />
                Options
              </button>
            )}
            {!isCore && (
              <>
                {onMoveUp && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onMoveUp()
                    }}
                    disabled={!canMoveUp}
                    className="p-1 text-slate-400 hover:text-slate-900 disabled:opacity-30"
                    aria-label="Move up"
                  >
                    <ChevronUp className="h-3.5 w-3.5" />
                  </button>
                )}
                {onMoveDown && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onMoveDown()
                    }}
                    disabled={!canMoveDown}
                    className="p-1 text-slate-400 hover:text-slate-900 disabled:opacity-30"
                    aria-label="Move down"
                  >
                    <ChevronDown className="h-3.5 w-3.5" />
                  </button>
                )}
                {onRemove && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onRemove()
                    }}
                    className="p-1 text-slate-400 hover:text-red-600"
                    aria-label="Delete step"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────
// TriggerCard — synthetic card representing the workflow's entry trigger
// ─────────────────────────────────────────────────────────────────────

export interface TriggerCardProps {
  triggerType: string
  triggerConfig: Record<string, unknown> | null
  workflowName?: string
  workflowDescription?: string
  keywords?: string[]
  isReadOnly?: boolean
  onChange?: (type: string, config: Record<string, unknown> | null) => void
}

export function TriggerCard({
  triggerType,
  triggerConfig,
  workflowName,
  workflowDescription,
  keywords,
  isReadOnly,
  onChange,
}: TriggerCardProps) {
  const style = STEP_STYLES.trigger
  const Icon = style.icon
  const summary = generateWorkflowTriggerSummary(triggerType, triggerConfig)

  return (
    <div
      className={`relative w-full rounded-lg border border-slate-200 border-l-4 ${style.border} ${style.bg} shadow-sm`}
    >
      <div className="flex items-center gap-2 px-5 pt-4">
        <div className={`h-6 w-6 rounded grid place-items-center ${style.iconBg}`}>
          <Icon className="h-3.5 w-3.5 text-white" />
        </div>
        <span className={`text-[10px] font-semibold tracking-wide uppercase ${style.labelColor}`}>
          {style.label}
        </span>
      </div>

      <div className="px-5 pt-2">
        <div className="text-base font-semibold text-slate-900 leading-snug">
          {summary.headline}
        </div>
        {summary.subline && (
          <div className="text-xs text-slate-500 mt-1">{summary.subline}</div>
        )}
      </div>

      {/* Manual triggers: show command-bar keywords + preview */}
      {triggerType === "manual" && (
        <div className="px-5 pt-3 space-y-2">
          {keywords && keywords.length > 0 && (
            <div className="flex items-start gap-2 text-xs">
              <span className="text-slate-500 flex-shrink-0 mt-0.5">Keywords:</span>
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
          {workflowName && (
            <div className="rounded border border-slate-200 bg-slate-50 px-3 py-2">
              <div className="text-[10px] uppercase tracking-wide text-slate-400">
                Appears as
              </div>
              <div className="text-sm font-medium text-slate-900">{workflowName}</div>
              {workflowDescription && (
                <div className="text-xs text-slate-500 line-clamp-1">
                  {workflowDescription}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <div className="mt-4 flex items-center justify-between border-t border-slate-100 px-5 py-2">
        <div className="text-[10px] text-slate-400">
          Trigger · <span className="font-mono">{triggerType}</span>
        </div>
        {!isReadOnly && onChange && (
          <select
            value={triggerType}
            onChange={(e) => onChange(e.target.value, null)}
            className="rounded border border-slate-300 px-2 py-0.5 text-[11px]"
          >
            <option value="manual">Manual (command bar)</option>
            <option value="scheduled">Scheduled (cron)</option>
            <option value="event">Event</option>
            <option value="time_of_day">Time of day</option>
            <option value="time_after_event">Time after event</option>
          </select>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────
// VariablePill — shows a variable-resolved label with hover tooltip
// ─────────────────────────────────────────────────────────────────────

function VariablePill({ value, path }: { value: string; path?: string }) {
  const [hover, setHover] = useState(false)
  return (
    <span
      className="relative inline-flex items-center gap-1 rounded bg-blue-50 px-1.5 py-0.5 text-xs font-medium text-blue-700"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      {value}
      <ArrowUpRight className="h-3 w-3" />
      {hover && path && (
        <span className="absolute left-0 top-full mt-1 z-10 whitespace-nowrap rounded bg-slate-900 px-2 py-1 text-[10px] font-mono text-white">
          {path}
        </span>
      )}
    </span>
  )
}
