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
  product_type?: string | null
  product_type_label?: string | null
  direction?: "sales" | "purchase"
  entry_intent?: "order" | "quote"
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
  const [editingField, setEditingField] = useState<string | null>(null)
  const [editValue, setEditValue] = useState("")
  const [productTypeLabel, setProductTypeLabel] = useState<string | null>(null)
  const [direction, setDirection] = useState<"sales" | "purchase">("sales")
  const [entryIntent, setEntryIntent] = useState<"order" | "quote">("order")
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
  const unresolvedConflicts = Object.values(fields).filter(
    (f) => f?.is_conflict,
  ).length
  const canSubmit = allRequiredFilled && !submitting && unresolvedConflicts === 0

  // Click-to-edit handlers
  const startEdit = (fieldKey: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    setEditingField(fieldKey)
    setEditValue(fields[fieldKey]?.display_value ?? "")
  }
  const confirmEdit = (fieldKey: string) => {
    const trimmed = editValue.trim()
    setFields((prev) => {
      const next = { ...prev }
      if (!trimmed) {
        delete next[fieldKey]
      } else {
        next[fieldKey] = {
          value: trimmed,
          display_value: trimmed,
          confidence: 1.0,
          isManual: true,
        }
      }
      return next
    })
    setEditingField(null)
    setEditValue("")
    textareaRef.current?.focus()
  }
  const cancelEdit = () => {
    setEditingField(null)
    setEditValue("")
    textareaRef.current?.focus()
  }

  // Conflict resolution
  const acceptConflict = (fieldKey: string) => {
    setFields((prev) => {
      const f = prev[fieldKey]
      if (!f) return prev
      return {
        ...prev,
        [fieldKey]: {
          ...f,
          is_conflict: false,
          previous_value: undefined,
          // Accepted = director deliberately chose this value, treat as
          // manual so future extractions don't flip it back.
          isManual: true,
        },
      }
    })
  }
  const revertConflict = (fieldKey: string) => {
    setFields((prev) => {
      const f = prev[fieldKey]
      if (!f?.previous_value) return prev
      return {
        ...prev,
        [fieldKey]: {
          ...f,
          value: f.previous_value,
          display_value: f.previous_value,
          confidence: 0.95,
          is_conflict: false,
          previous_value: undefined,
          isManual: true,
        },
      }
    })
  }

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
        if (data.product_type_label) {
          setProductTypeLabel(data.product_type_label)
        }
        if (data.direction) {
          setDirection(data.direction)
        }
        if (data.entry_intent) {
          setEntryIntent(data.entry_intent)
        }
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
        if (canSubmit) handleSubmit()
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

      {(productTypeLabel || entryIntent === "quote") && (
        <div
          className={`mx-4 mt-1 flex items-center gap-2 rounded-md px-3 py-1.5 text-xs ${
            entryIntent === "quote"
              ? "bg-purple-50 text-purple-700"
              : direction === "purchase"
                ? "bg-blue-50 text-blue-700"
                : "bg-emerald-50 text-emerald-700"
          }`}
        >
          <span className="font-semibold">
            {entryIntent === "quote"
              ? productTypeLabel
                ? `${productTypeLabel.replace(/ Order$/i, "")} Quote`
                : "Quote"
              : productTypeLabel}
          </span>
          <span
            className={
              entryIntent === "quote"
                ? "text-purple-500/80"
                : direction === "purchase"
                  ? "text-blue-500/80"
                  : "text-emerald-600/80"
            }
          >
            {entryIntent === "quote"
              ? "· Composing a quote"
              : direction === "purchase"
                ? "· We are buying"
                : "· We are selling"}
          </span>
          <button
            onClick={() => {
              setProductTypeLabel(null)
              setDirection("sales")
              setEntryIntent("order")
            }}
            className="ml-auto text-[11px] text-slate-400 hover:text-slate-700"
          >
            wrong type?
          </button>
        </div>
      )}

      {Object.keys(fields).length > 0 && (
        <div className="mx-4 my-1 border-t border-gray-100" />
      )}

      <div className="px-4 pb-2">
        {inputSteps.map((step) => (
          <FieldRow
            key={step.step_key}
            fieldKey={step.step_key}
            label={labelFor(step, direction, !!productTypeLabel)}
            required={step.config?.required !== false}
            field={fields[step.step_key] ?? null}
            isEditing={editingField === step.step_key}
            editValue={editValue}
            onStartEdit={() => startEdit(step.step_key)}
            onEditChange={setEditValue}
            onConfirmEdit={() => confirmEdit(step.step_key)}
            onCancelEdit={cancelEdit}
            onAcceptConflict={() => acceptConflict(step.step_key)}
            onRevertConflict={() => revertConflict(step.step_key)}
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
          disabled={!canSubmit}
          className={`w-full rounded-xl py-2.5 text-sm font-semibold transition ${
            canSubmit
              ? "bg-gray-900 text-white hover:bg-gray-800 shadow-sm"
              : "cursor-not-allowed bg-gray-100 text-gray-400"
          }`}
        >
          {submitting
            ? "Creating…"
            : unresolvedConflicts > 0
              ? `Resolve ${unresolvedConflicts} conflict${unresolvedConflicts === 1 ? "" : "s"} first`
              : allRequiredFilled
                ? submitActionLabel(entryIntent, direction, productTypeLabel)
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
  fieldKey,
  label,
  required,
  field,
  isEditing,
  editValue,
  onStartEdit,
  onEditChange,
  onConfirmEdit,
  onCancelEdit,
  onAcceptConflict,
  onRevertConflict,
}: {
  fieldKey: string
  label: string
  required: boolean
  field: ExtractedField | null
  isEditing: boolean
  editValue: string
  onStartEdit: () => void
  onEditChange: (v: string) => void
  onConfirmEdit: () => void
  onCancelEdit: () => void
  onAcceptConflict: () => void
  onRevertConflict: () => void
}) {
  void fieldKey
  if (!field && !required && !isEditing) return null
  const conf = field?.confidence ?? 0
  const has = !!field && !!field.display_value

  // Editing state
  if (isEditing) {
    return (
      <div className="-mx-2 flex items-center gap-3 rounded-lg bg-blue-50 px-2 py-2 ring-1 ring-blue-200">
        <span className="w-24 flex-shrink-0 text-xs font-medium text-gray-400">
          {label}
        </span>
        <input
          type="text"
          value={editValue}
          onChange={(e) => onEditChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === "Tab") {
              e.preventDefault()
              onConfirmEdit()
            } else if (e.key === "Escape") {
              e.preventDefault()
              onCancelEdit()
            }
          }}
          autoFocus
          className="flex-1 border-none bg-transparent text-sm font-medium text-gray-900 outline-none"
        />
        <button
          onClick={onConfirmEdit}
          className="flex-shrink-0 text-xs font-medium text-blue-600 hover:text-blue-700"
        >
          Done
        </button>
      </div>
    )
  }

  // Conflict state — shows old → new with accept/revert
  if (field?.is_conflict) {
    return (
      <div className="-mx-2 flex items-center gap-3 rounded-lg bg-amber-50 px-2 py-2 ring-1 ring-amber-200">
        <span className="w-24 flex-shrink-0 text-xs font-medium text-gray-400">
          {label}
        </span>
        <div className="flex min-w-0 flex-1 items-center gap-2 text-sm">
          <span className="max-w-[35%] truncate text-gray-400 line-through">
            {field.previous_value}
          </span>
          <span className="flex-shrink-0 text-xs text-amber-500">→</span>
          <span className="truncate font-medium text-gray-900">
            {field.display_value}
          </span>
        </div>
        <div className="flex flex-shrink-0 items-center gap-1">
          <button
            onClick={(e) => {
              e.stopPropagation()
              onAcceptConflict()
            }}
            title="Use new value"
            className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-100 text-xs text-emerald-700 hover:bg-emerald-200"
          >
            ✓
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              onRevertConflict()
            }}
            title="Keep previous value"
            className="flex h-6 w-6 items-center justify-center rounded-full bg-gray-100 text-xs text-gray-600 hover:bg-gray-200"
          >
            ✕
          </button>
        </div>
      </div>
    )
  }

  // Idle — clickable (whether filled or empty required)
  return (
    <div
      onClick={onStartEdit}
      className="group -mx-2 flex cursor-pointer items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-gray-50"
    >
      <span className="w-24 flex-shrink-0 text-xs font-medium text-gray-400">
        {label}
      </span>
      <div className="min-w-0 flex-1 text-sm">
        {has ? (
          <span className="truncate font-medium text-gray-900">
            {field!.display_value}
          </span>
        ) : (
          <span className="text-gray-300 italic">
            {required ? "Required — click to add" : "Optional"}
          </span>
        )}
      </div>
      <div className="flex-shrink-0">
        {!has ? (
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              required
                ? "bg-red-300 group-hover:bg-red-400"
                : "bg-gray-200"
            }`}
          />
        ) : field?.isManual ? (
          <span className="text-sm text-slate-500" title="Manually entered">
            ✎
          </span>
        ) : conf >= 0.85 ? (
          <span className="text-sm text-emerald-500">✓</span>
        ) : conf >= 0.65 ? (
          <span className="text-sm text-amber-500">~</span>
        ) : (
          <span className="inline-block h-2 w-2 rounded-full bg-red-400" />
        )}
      </div>
      {has && (
        <span className="ml-1 text-xs text-gray-300 opacity-0 transition-opacity group-hover:opacity-100">
          ✎
        </span>
      )}
    </div>
  )
}

function labelFor(
  step: WorkflowInputStep,
  direction: "sales" | "purchase" = "sales",
  directionKnown: boolean = false,
): string {
  // The customer/vendor field adapts to the detected direction so it
  // reads correctly for POs. Before any product-type detection fires,
  // use the neutral "Account" label — it could still be either.
  if (step.step_key === "ask_customer" || step.step_key === "customer") {
    if (!directionKnown) return "Account"
    return direction === "purchase" ? "Vendor" : "Customer"
  }
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

function submitActionLabel(
  entryIntent: "order" | "quote",
  direction: "sales" | "purchase",
  productTypeLabel: string | null,
): string {
  if (entryIntent === "quote") return "Create Quote →"
  if (direction === "purchase") return "Place Purchase Order →"
  if (productTypeLabel === "Disinterment") return "Log Disinterment →"
  return "Create Order →"
}

function getPlaceholder(workflowId: string): string {
  const placeholders: Record<string, string> = {
    wf_compose:
      'e.g. "Continental for Hopkins, full equipment, deliver Friday" or "quote Murphy on a Monticello" or "PO Acme 50 bags cement"',
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
