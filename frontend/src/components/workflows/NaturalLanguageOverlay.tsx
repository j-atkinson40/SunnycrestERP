// Natural-language overlay — replaces the sequential micro-form for
// multi-field workflows. User types a sentence; fields populate in
// real time via debounced Claude extraction; submit runs a final
// higher-fidelity pass and hands the merged inputs to the workflow
// engine's start endpoint.

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Loader2, Zap } from "lucide-react"
import apiClient from "@/lib/api-client"
import {
  flattenForSubmit,
  getConfidentFields,
  mergeExtractions,
  type ExtractedField,
  type FieldMap,
} from "@/utils/extractionMerge"
import type { WorkflowRunState } from "@/components/workflows/WorkflowController"

interface WorkflowInputStep {
  step_order: number
  step_key: string
  step_type: string
  config?: {
    prompt?: string
    input_type?: string
    required?: boolean
    options?: Array<{ value: string; label: string }>
  }
}

interface WorkflowShape {
  id: string
  name: string
  steps?: WorkflowInputStep[]
}

interface ExtractResponse {
  fields: FieldMap
  raw_input: string
}

interface Props {
  workflow: WorkflowShape
  onComplete: (run: WorkflowRunState) => void
  onCancel: () => void
}

// ─────────────────────────────────────────────────────────────────────

export function NaturalLanguageOverlay({
  workflow,
  onComplete,
  onCancel,
}: Props) {
  const [text, setText] = useState("")
  const [fields, setFields] = useState<FieldMap>({})
  const [extracting, setExtracting] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    textareaRef.current?.focus()
  }, [])

  const inputSteps = useMemo<WorkflowInputStep[]>(
    () =>
      (workflow.steps ?? [])
        .filter((s) => s.step_type === "input")
        .sort((a, b) => a.step_order - b.step_order),
    [workflow.steps],
  )

  const requiredKeys = useMemo(
    () =>
      inputSteps
        .filter((s) => s.config?.required !== false)
        .map((s) => s.step_key),
    [inputSteps],
  )

  const missingCount = requiredKeys.filter(
    (k) => !fields[k] || (fields[k]?.confidence ?? 0) < 0.7,
  ).length
  const allRequiredFilled = missingCount === 0 && requiredKeys.length > 0

  const runExtraction = useCallback(
    async (input: string, isFinal: boolean): Promise<FieldMap | null> => {
      if (!input || input.trim().length < 3) return null
      try {
        const { data } = await apiClient.post<ExtractResponse>(
          "/core/command-bar/extract",
          {
            workflow_id: workflow.id,
            input_text: input,
            existing_fields: getConfidentFields(fields),
            is_final: isFinal,
          },
        )
        return data.fields || {}
      } catch {
        return null
      }
    },
    [workflow.id, fields],
  )

  const scheduleLiveExtraction = useCallback(
    (input: string) => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(async () => {
        setExtracting(true)
        const incoming = await runExtraction(input, false)
        setExtracting(false)
        if (incoming) {
          setFields((prev) => mergeExtractions(prev, incoming))
        }
      }, 600)
    },
    [runExtraction],
  )

  const onTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const next = e.target.value
    setText(next)
    scheduleLiveExtraction(next)
  }

  const handleSubmit = async () => {
    if (!allRequiredFilled || submitting) return
    setSubmitting(true)
    setError(null)
    // Final higher-fidelity extraction pass, if the user typed anything
    let merged: FieldMap = fields
    if (text.trim()) {
      const finalFields = await runExtraction(text, true)
      if (finalFields) {
        merged = mergeExtractions(fields, finalFields)
      }
    }
    try {
      const { data } = await apiClient.post<WorkflowRunState>(
        `/workflows/${workflow.id}/start`,
        { initial_inputs: flattenForSubmit(merged) },
      )
      onComplete(data)
    } catch (e) {
      const detail = (
        e as { response?: { data?: { detail?: string } }; message?: string }
      )?.response?.data?.detail
      setError(detail || "Failed to create record")
    } finally {
      setSubmitting(false)
    }
  }

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault()
        if (allRequiredFilled) handleSubmit()
      } else if (e.key === "Escape") {
        e.preventDefault()
        onCancel()
      }
    }
    document.addEventListener("keydown", h, { capture: true })
    return () => document.removeEventListener("keydown", h, { capture: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allRequiredFilled, text, fields])

  const placeholder = useMemo(() => getPlaceholder(workflow.id), [workflow.id])

  return (
    <div className="flex flex-col min-w-[480px]">
      <div className="flex items-center gap-2 border-b border-gray-100 px-4 py-3">
        <Zap className="h-4 w-4 text-violet-600" />
        <span className="text-sm font-semibold text-gray-900">
          {workflow.name}
        </span>
        <div className="ml-auto flex items-center gap-2 text-xs">
          {extracting && (
            <span className="flex items-center gap-1 text-blue-500">
              <Loader2 className="h-3 w-3 animate-spin" />
              Reading…
            </span>
          )}
          <button
            onClick={onCancel}
            className="text-gray-400 hover:text-gray-700"
          >
            Cancel
          </button>
        </div>
      </div>

      <div className="px-4 pt-4 pb-2">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={onTextChange}
          placeholder={placeholder}
          rows={2}
          className="w-full resize-none rounded-xl border border-gray-200 px-3 py-2.5 text-sm leading-relaxed text-gray-900 placeholder:text-gray-400 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-500"
          style={{ minHeight: 64 }}
        />
        <div className="mt-1.5 flex items-center justify-between">
          <span className="text-xs text-gray-400">
            Describe in your own words
          </span>
          <span className="text-xs text-gray-400">⌘↵ to create</span>
        </div>
      </div>

      {Object.keys(fields).length > 0 && (
        <div className="mx-4 my-1 border-t border-gray-100" />
      )}

      <div className="px-4 pb-2">
        {inputSteps.map((step) => (
          <FieldRow
            key={step.step_key}
            label={labelFor(step)}
            required={step.config?.required !== false}
            field={fields[step.step_key] ?? null}
          />
        ))}
      </div>

      {error && (
        <div className="mx-4 mb-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      )}

      <div className="border-t border-gray-100 bg-gray-50/50 px-4 py-3">
        <button
          onClick={handleSubmit}
          disabled={!allRequiredFilled || submitting}
          className={`w-full rounded-xl py-2.5 text-sm font-semibold transition ${
            allRequiredFilled && !submitting
              ? "bg-gray-900 text-white hover:bg-gray-800 shadow-sm"
              : "cursor-not-allowed bg-gray-100 text-gray-400"
          }`}
        >
          {submitting
            ? "Creating…"
            : allRequiredFilled
              ? "Create →"
              : `Fill in ${missingCount} more field${missingCount === 1 ? "" : "s"}`}
        </button>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────
// Sub-components + helpers
// ─────────────────────────────────────────────────────────────────────

function FieldRow({
  label,
  required,
  field,
}: {
  label: string
  required: boolean
  field: ExtractedField | null
}) {
  if (!field && !required) return null
  const conf = field?.confidence ?? 0
  const has = !!field && !!field.display_value

  return (
    <div
      className={`-mx-2 flex items-center gap-3 rounded-lg px-2 py-2 ${
        field?.is_conflict ? "bg-amber-50" : ""
      }`}
    >
      <span className="w-24 flex-shrink-0 text-xs font-medium text-gray-400">
        {label}
      </span>
      <div className="min-w-0 flex-1 text-sm">
        {has ? (
          field?.is_conflict ? (
            <span className="flex items-center gap-2">
              <span className="text-gray-400 line-through">
                {field.previous_value}
              </span>
              <span className="text-amber-600">→</span>
              <span className="font-medium text-gray-900">
                {field.display_value}
              </span>
            </span>
          ) : (
            <span className="truncate font-medium text-gray-900">
              {field.display_value}
            </span>
          )
        ) : (
          <span className="text-gray-300">
            {required ? "Required" : "Optional"}
          </span>
        )}
      </div>
      <div className="flex-shrink-0">
        {!has ? (
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              required ? "bg-red-400" : "bg-gray-200"
            }`}
          />
        ) : conf >= 0.85 ? (
          <span className="text-sm text-emerald-500">✓</span>
        ) : conf >= 0.65 ? (
          <span className="text-sm text-amber-500">~</span>
        ) : (
          <span className="inline-block h-2 w-2 rounded-full bg-red-400" />
        )}
      </div>
    </div>
  )
}

function labelFor(step: WorkflowInputStep): string {
  const p = step.config?.prompt
  if (p) {
    return p
      .replace(/^which /i, "")
      .replace(/^what /i, "")
      .replace(/^enter /i, "")
      .replace(/^select /i, "")
      .replace(/\?$/, "")
      .trim()
  }
  return step.step_key.replace(/_/g, " ").replace(/^ask /, "")
}

function getPlaceholder(workflowId: string): string {
  const placeholders: Record<string, string> = {
    wf_mfg_create_order:
      "e.g. Continental standard for Hopkins, deliver Friday, full equipment",
    wf_mfg_disinterment:
      "e.g. Hopkins FH, removal from Greenwood Cemetery, need this Thursday",
    wf_mfg_schedule_delivery:
      "e.g. Order 1234 for Murphy FH, deliver next Wednesday morning",
    wf_fh_first_call:
      "e.g. Burial, Johnson family, Hopkins directing, tomorrow 2pm",
    wf_fh_schedule_arrangement:
      "e.g. Johnson case, arrangement Monday at 10am, Director Torres",
  }
  return placeholders[workflowId] || "Describe in your own words…"
}
