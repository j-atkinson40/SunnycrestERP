/**
 * Per-verb action config forms — WB-7 Area 4 Lock 4a.
 *
 * Five small forms, one per ActionRef variant. Each renders inside
 * the ActionPicker after the verb dropdown. Forms compose
 * InspectorField + TextFieldUncontrolled + SelectField (existing
 * primitives) + ParameterBindingPicker (WB-7 new) + a "+ Add
 * parameter binding" affordance for verbs with binding lists.
 *
 * Per-verb confirm_before defaults locked in `types.ts`. Each form
 * exposes the confirm_before toggle as a checkbox-like switch so the
 * operator can override the default.
 */
import { useCallback } from "react"

import type {
  MutateActionRef,
  NavigateActionRef,
  OpenFocusActionRef,
  OpenPeekActionRef,
  ParameterBindingRef,
  PeekViewType,
  TriggerWorkflowActionRef,
} from "@/lib/widget-builder/types/composition-blob"
import {
  InspectorField,
  InspectorSection,
  SelectField,
  TextFieldUncontrolled,
} from "../inspectors/inspector-primitives"

import { ParameterBindingPicker } from "./ParameterBindingPicker"
import { makeEmptyBinding, PEEK_VIEW_TYPES } from "./types"


// ── Shared atoms ───────────────────────────────────────────────────


function ConfirmBeforeToggle({
  value,
  onChange,
  testId,
}: {
  value: boolean
  onChange: (v: boolean) => void
  testId?: string
}) {
  return (
    <InspectorField label="Require confirmation before firing">
      <label className="flex items-center gap-2 text-body-sm">
        <input
          type="checkbox"
          data-testid={testId ?? "action-confirm-before"}
          checked={value}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className="text-content-muted">Show confirmation dialog</span>
      </label>
    </InspectorField>
  )
}


function ConfirmCopyField({
  value,
  onChange,
  testId,
}: {
  value?: string
  onChange: (v: string) => void
  testId?: string
}) {
  return (
    <InspectorField label="Confirmation copy (optional)">
      <TextFieldUncontrolled
        testId={testId ?? "action-confirm-copy"}
        value={value ?? ""}
        placeholder="Are you sure?"
        onCommit={onChange}
      />
    </InspectorField>
  )
}


function BindingListEditor({
  label,
  bindings,
  onChange,
  insideRepeater,
  testId,
}: {
  label: string
  bindings: ParameterBindingRef[]
  onChange: (next: ParameterBindingRef[]) => void
  insideRepeater: boolean
  testId: string
}) {
  const add = useCallback(() => {
    onChange([...bindings, makeEmptyBinding()])
  }, [bindings, onChange])
  const updateAt = useCallback(
    (idx: number, next: ParameterBindingRef) => {
      const copy = bindings.slice()
      copy[idx] = next
      onChange(copy)
    },
    [bindings, onChange],
  )
  const removeAt = useCallback(
    (idx: number) => {
      onChange(bindings.filter((_, i) => i !== idx))
    },
    [bindings, onChange],
  )
  return (
    <InspectorSection title={label}>
      {bindings.map((b, i) => (
        <ParameterBindingPicker
          key={i}
          value={b}
          onChange={(next) => updateAt(i, next)}
          onRemove={() => removeAt(i)}
          insideRepeater={insideRepeater}
          testId={`${testId}-${i}`}
        />
      ))}
      <button
        type="button"
        data-testid={`${testId}-add`}
        onClick={add}
        className="self-start text-caption text-content-accent hover:underline"
      >
        + Add parameter binding
      </button>
    </InspectorSection>
  )
}


// ── Navigate form ──────────────────────────────────────────────────


export function NavigateActionForm({
  value,
  onChange,
  insideRepeater,
}: {
  value: NavigateActionRef
  onChange: (next: NavigateActionRef) => void
  insideRepeater: boolean
}) {
  return (
    <div data-testid="action-form-navigate" className="flex flex-col gap-2">
      <InspectorSection title="Navigate target">
        <InspectorField label="Href template">
          <TextFieldUncontrolled
            testId="action-navigate-href"
            value={value.href}
            placeholder="/cases/{case_id}"
            onCommit={(v) => onChange({ ...value, href: v })}
          />
        </InspectorField>
      </InspectorSection>
      <BindingListEditor
        label="Route parameters"
        bindings={value.params ?? []}
        onChange={(next) => onChange({ ...value, params: next })}
        insideRepeater={insideRepeater}
        testId="action-navigate-params"
      />
      <InspectorSection title="Confirmation">
        <ConfirmBeforeToggle
          value={value.confirm_before === true}
          onChange={(v) => onChange({ ...value, confirm_before: v })}
        />
        {value.confirm_before && (
          <ConfirmCopyField
            value={value.confirm_copy}
            onChange={(v) => onChange({ ...value, confirm_copy: v })}
          />
        )}
      </InspectorSection>
    </div>
  )
}


// ── Open-focus form ────────────────────────────────────────────────


export function OpenFocusActionForm({
  value,
  onChange,
  insideRepeater,
}: {
  value: OpenFocusActionRef
  onChange: (next: OpenFocusActionRef) => void
  insideRepeater: boolean
}) {
  return (
    <div data-testid="action-form-open_focus" className="flex flex-col gap-2">
      <InspectorSection title="Focus target">
        <InspectorField label="Focus template slug">
          <TextFieldUncontrolled
            testId="action-open-focus-slug"
            value={value.focus_template_slug}
            placeholder="funeral-scheduling"
            onCommit={(v) =>
              onChange({ ...value, focus_template_slug: v })
            }
          />
        </InspectorField>
      </InspectorSection>
      <BindingListEditor
        label="Initial context"
        bindings={value.initial_context ?? []}
        onChange={(next) => onChange({ ...value, initial_context: next })}
        insideRepeater={insideRepeater}
        testId="action-open-focus-ctx"
      />
      <InspectorSection title="Confirmation">
        <ConfirmBeforeToggle
          value={value.confirm_before === true}
          onChange={(v) => onChange({ ...value, confirm_before: v })}
        />
        {value.confirm_before && (
          <ConfirmCopyField
            value={value.confirm_copy}
            onChange={(v) => onChange({ ...value, confirm_copy: v })}
          />
        )}
      </InspectorSection>
    </div>
  )
}


// ── Open-peek form ─────────────────────────────────────────────────


export function OpenPeekActionForm({
  value,
  onChange,
  insideRepeater,
}: {
  value: OpenPeekActionRef
  onChange: (next: OpenPeekActionRef) => void
  insideRepeater: boolean
}) {
  return (
    <div data-testid="action-form-open_peek" className="flex flex-col gap-2">
      <InspectorSection title="Peek target">
        <InspectorField label="Entity type">
          <SelectField<PeekViewType>
            testId="action-open-peek-type"
            value={value.peek_view_type}
            onChange={(v) => onChange({ ...value, peek_view_type: v })}
            options={PEEK_VIEW_TYPES.map((v) => ({
              value: v,
              label: v.replace(/_/g, " "),
            }))}
          />
        </InspectorField>
      </InspectorSection>
      <BindingListEditor
        label="Initial context"
        bindings={value.initial_context ?? []}
        onChange={(next) => onChange({ ...value, initial_context: next })}
        insideRepeater={insideRepeater}
        testId="action-open-peek-ctx"
      />
      <InspectorSection title="Confirmation">
        <ConfirmBeforeToggle
          value={value.confirm_before === true}
          onChange={(v) => onChange({ ...value, confirm_before: v })}
        />
        {value.confirm_before && (
          <ConfirmCopyField
            value={value.confirm_copy}
            onChange={(v) => onChange({ ...value, confirm_copy: v })}
          />
        )}
      </InspectorSection>
    </div>
  )
}


// ── Trigger-workflow form ──────────────────────────────────────────


export function TriggerWorkflowActionForm({
  value,
  onChange,
  insideRepeater,
}: {
  value: TriggerWorkflowActionRef
  onChange: (next: TriggerWorkflowActionRef) => void
  insideRepeater: boolean
}) {
  return (
    <div
      data-testid="action-form-trigger_workflow"
      className="flex flex-col gap-2"
    >
      <InspectorSection title="Workflow target">
        <InspectorField label="Workflow slug">
          <TextFieldUncontrolled
            testId="action-trigger-workflow-slug"
            value={value.workflow_slug}
            placeholder="wf_sys_month_end_close"
            onCommit={(v) => onChange({ ...value, workflow_slug: v })}
          />
        </InspectorField>
      </InspectorSection>
      <BindingListEditor
        label="Workflow input"
        bindings={value.workflow_input ?? []}
        onChange={(next) => onChange({ ...value, workflow_input: next })}
        insideRepeater={insideRepeater}
        testId="action-trigger-workflow-input"
      />
      <InspectorSection title="Confirmation">
        <ConfirmBeforeToggle
          value={value.confirm_before !== false}
          onChange={(v) => onChange({ ...value, confirm_before: v })}
        />
        {value.confirm_before !== false && (
          <ConfirmCopyField
            value={value.confirm_copy}
            onChange={(v) => onChange({ ...value, confirm_copy: v })}
          />
        )}
      </InspectorSection>
    </div>
  )
}


// ── Mutate form ────────────────────────────────────────────────────


export function MutateActionForm({
  value,
  onChange,
  insideRepeater,
}: {
  value: MutateActionRef
  onChange: (next: MutateActionRef) => void
  insideRepeater: boolean
}) {
  return (
    <div data-testid="action-form-mutate" className="flex flex-col gap-2">
      <InspectorSection title="Mutate target">
        <InspectorField label="Mutate kind">
          <SelectField
            testId="action-mutate-kind"
            value={value.mutate_kind}
            onChange={() => {
              // Phase 1 narrowed to anomaly_acknowledge — no-op
            }}
            options={[
              {
                value: "anomaly_acknowledge",
                label: "Anomaly acknowledge",
              },
            ]}
          />
        </InspectorField>
        <div className="text-caption text-content-subtle">
          Phase 1 narrowed to anomaly_acknowledge per §12.6a discipline.
        </div>
      </InspectorSection>
      <InspectorSection title="Target id binding">
        <ParameterBindingPicker
          value={value.target_id_binding}
          onChange={(next) =>
            onChange({ ...value, target_id_binding: next })
          }
          insideRepeater={insideRepeater}
          testId="action-mutate-target"
          hideName
        />
      </InspectorSection>
      <InspectorSection title="Confirmation">
        <ConfirmBeforeToggle
          value={value.confirm_before !== false}
          onChange={(v) => onChange({ ...value, confirm_before: v })}
        />
        {value.confirm_before !== false && (
          <ConfirmCopyField
            value={value.confirm_copy}
            onChange={(v) => onChange({ ...value, confirm_copy: v })}
          />
        )}
      </InspectorSection>
    </div>
  )
}
