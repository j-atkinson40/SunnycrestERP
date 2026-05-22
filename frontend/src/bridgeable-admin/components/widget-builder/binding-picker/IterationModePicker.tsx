/**
 * IterationModePicker — WB-6 auto-inferred iteration_mode display.
 *
 * Per Area 5 Lock 6d: iteration_mode is auto-inferred from atom type
 * + saved-view presentation mode. Read-only display (no operator
 * control); the value is rendered + the rule is explained inline.
 *
 *   repeater_atom → 'per_row' (forced).
 *   chart/stat view → 'single_summary' (forced).
 *   list/table/kanban/cards/calendar + non-repeater → 'single_record'
 *     by default (operator MAY toggle to 'single_summary' via this
 *     picker; minimal toggle exposure surfaces author intent).
 */
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { PresentationMode } from "@/types/saved-views"


export type IterationMode = "per_row" | "single_summary" | "single_record"


export interface InferredIteration {
  mode: IterationMode
  locked: boolean
  reason: string
}


export function inferIterationMode(args: {
  atomType: string
  presentationMode: PresentationMode | null
}): InferredIteration {
  const { atomType, presentationMode } = args

  if (atomType === "repeater_atom") {
    return {
      mode: "per_row",
      locked: true,
      reason: "Repeater atoms always iterate per row.",
    }
  }

  if (presentationMode === "chart" || presentationMode === "stat") {
    return {
      mode: "single_summary",
      locked: true,
      reason: "Chart and stat views emit aggregated summaries.",
    }
  }

  // List / table / kanban / cards / calendar / null → default to
  // single_record. The picker permits toggle to single_summary so the
  // operator can bind to total_count summary mode.
  return {
    mode: "single_record",
    locked: false,
    reason: "Defaults to first record; switch to Summary for count.",
  }
}


export interface IterationModePickerProps {
  atomType: string
  presentationMode: PresentationMode | null
  value: IterationMode | null
  onChange: (mode: IterationMode) => void
  testId?: string
}


export function IterationModePicker({
  atomType,
  presentationMode,
  value,
  onChange,
  testId,
}: IterationModePickerProps) {
  const inferred = inferIterationMode({ atomType, presentationMode })

  // If the value drifts from the locked inference, the parent should
  // sync. We render the inferred value when locked, regardless.
  const displayValue = inferred.locked ? inferred.mode : (value ?? inferred.mode)

  if (inferred.locked) {
    return (
      <div
        data-testid={testId}
        className="rounded-md border border-border-subtle bg-surface-sunken px-2 py-1.5"
      >
        <div className="flex items-center justify-between text-body-sm">
          <span className="font-medium text-content-base">
            {displayValue.replace("_", " ")}
          </span>
          <span className="text-caption text-content-muted">auto</span>
        </div>
        <div className="mt-1 text-caption text-content-muted">
          {inferred.reason}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1">
      <Select
        value={displayValue}
        onValueChange={(v) => onChange(v as IterationMode)}
      >
        <SelectTrigger data-testid={testId} className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="single_record">Single record</SelectItem>
          <SelectItem value="single_summary">Summary (count)</SelectItem>
        </SelectContent>
      </Select>
      <span className="text-caption text-content-muted">{inferred.reason}</span>
    </div>
  )
}
