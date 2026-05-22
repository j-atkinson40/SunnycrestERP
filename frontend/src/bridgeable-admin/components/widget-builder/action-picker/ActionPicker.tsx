/**
 * ActionPicker — WB-7 first admin-authored action substrate.
 *
 * Composes the verb dropdown + per-verb config form + action preview
 * card + verb-switch wipe-confirm Dialog. Replaces the WB-4b disabled
 * BindingPlaceholderField at the inspector slot.
 *
 * Per WB-7 Area 4 Locks 4a / 4b / 4c / 4d:
 *   • Flat verb dropdown (5 verbs) — no categorization (Lock 4a).
 *   • Per-verb config form below (Lock 4a) — see verb-forms.tsx.
 *   • Action preview card surfaces "Clicking will: ..." (Lock 4b) —
 *     NON-DISPATCHING.
 *   • Verb switch wipes prior config behind a confirm modal (Lock 4c).
 *   • Empty state surfaces "Pick a verb" CTA (Lock 4d).
 *
 * Per Area 5 Lock 5b — per-verb confirm_before defaults locked in
 * types.ts; the form exposes the toggle so the operator can override.
 */
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button as UIButton } from "@/components/ui/button"

import type { ActionRef } from "@/lib/widget-builder/types/composition-blob"
import {
  InspectorField,
  InspectorSection,
  SelectField,
} from "../inspectors/inspector-primitives"

import { ActionPreviewCard } from "./ActionPreviewCard"
import {
  MutateActionForm,
  NavigateActionForm,
  OpenFocusActionForm,
  OpenPeekActionForm,
  TriggerWorkflowActionForm,
} from "./verb-forms"
import {
  ACTION_KIND_LABELS,
  type ActionKind,
} from "./types"
import { useActionPicker } from "./useActionPicker"


const VERB_OPTIONS: ReadonlyArray<{ value: ActionKind; label: string }> = [
  { value: "navigate", label: ACTION_KIND_LABELS.navigate },
  { value: "open_focus", label: ACTION_KIND_LABELS.open_focus },
  { value: "open_peek", label: ACTION_KIND_LABELS.open_peek },
  { value: "trigger_workflow", label: ACTION_KIND_LABELS.trigger_workflow },
  { value: "mutate", label: ACTION_KIND_LABELS.mutate },
]


export interface ActionPickerProps {
  value: ActionRef | null
  onChange: (next: ActionRef | null) => void
  /** Whether this button atom is inside a repeater_atom — passed
   *  through to ParameterBindingPicker for current_row context
   *  gating. */
  insideRepeater: boolean
  testId?: string
}


export function ActionPicker({
  value,
  onChange,
  insideRepeater,
  testId,
}: ActionPickerProps) {
  const {
    selectVerb,
    pendingVerb,
    commitPendingVerb,
    cancelPendingVerb,
  } = useActionPicker({ value, onChange })

  return (
    <div data-testid={testId ?? "action-picker"} className="flex flex-col gap-2">
      <InspectorSection title="Action">
        <InspectorField label="Verb">
          <SelectField<ActionKind | "">
            testId="action-picker-verb"
            value={value?.action_kind ?? ""}
            onChange={(v) => selectVerb(v as ActionKind | "")}
            options={VERB_OPTIONS}
            placeholder="Pick a verb to wire this button"
          />
        </InspectorField>
        {!value && (
          <div
            data-testid="action-picker-empty"
            className="rounded-md border border-dashed border-border-subtle bg-surface-sunken px-2 py-1.5 text-caption text-content-subtle"
          >
            Pick an action verb to wire this button.
          </div>
        )}
      </InspectorSection>

      {value?.action_kind === "navigate" && (
        <NavigateActionForm
          value={value}
          onChange={onChange}
          insideRepeater={insideRepeater}
        />
      )}
      {value?.action_kind === "open_focus" && (
        <OpenFocusActionForm
          value={value}
          onChange={onChange}
          insideRepeater={insideRepeater}
        />
      )}
      {value?.action_kind === "open_peek" && (
        <OpenPeekActionForm
          value={value}
          onChange={onChange}
          insideRepeater={insideRepeater}
        />
      )}
      {value?.action_kind === "trigger_workflow" && (
        <TriggerWorkflowActionForm
          value={value}
          onChange={onChange}
          insideRepeater={insideRepeater}
        />
      )}
      {value?.action_kind === "mutate" && (
        <MutateActionForm
          value={value}
          onChange={onChange}
          insideRepeater={insideRepeater}
        />
      )}

      <ActionPreviewCard action={value} />

      {/* Verb-switch wipe-confirm modal (Lock 4c). */}
      {pendingVerb !== null && (
        <Dialog open={true} onOpenChange={(o) => !o && cancelPendingVerb()}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Switch action verb?</DialogTitle>
              <DialogDescription>
                Switching from{" "}
                <strong>
                  {value ? ACTION_KIND_LABELS[value.action_kind] : ""}
                </strong>{" "}
                to <strong>{ACTION_KIND_LABELS[pendingVerb]}</strong> will
                clear the current action settings. Continue?
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <UIButton
                variant="outline"
                data-testid="action-picker-confirm-cancel"
                onClick={cancelPendingVerb}
              >
                Cancel
              </UIButton>
              <UIButton
                variant="default"
                data-testid="action-picker-confirm-switch"
                onClick={commitPendingVerb}
              >
                Switch & clear
              </UIButton>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}
