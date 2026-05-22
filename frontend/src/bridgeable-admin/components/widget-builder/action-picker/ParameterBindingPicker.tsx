/**
 * ParameterBindingPicker — 8-source picker per WB-7 Area 6 Lock 6a.
 *
 * Renders source dropdown + per-source extras (literal value / param
 * name / row field). `current_row` is contextually gated when the
 * button is NOT inside a repeater — the option appears in the
 * dropdown with explanatory copy + the picker surfaces a warning if
 * selected outside that context.
 *
 * Operator-observable shape: NameInput + SourceSelect + per-source
 * field render below. Add / Remove handled by the parent list editor.
 */
import { useCallback } from "react"

import type {
  ParameterBindingRef,
  ParameterBindingSource,
} from "@/lib/widget-builder/types/composition-blob"
import {
  SelectField,
  TextFieldUncontrolled,
  InspectorField,
} from "../inspectors/inspector-primitives"

import { BINDING_SOURCE_OPTIONS } from "./types"


export interface ParameterBindingPickerProps {
  value: ParameterBindingRef
  onChange: (next: ParameterBindingRef) => void
  onRemove?: () => void
  /** When false, `current_row` source is grayed out with an
   *  explanation that the button is not inside a repeater_atom. */
  insideRepeater: boolean
  testId?: string
  /** Optional — hide the name input when the binding's name is
   *  controlled by a single-binding slot (e.g. mutate's
   *  target_id_binding). */
  hideName?: boolean
}


export function ParameterBindingPicker({
  value,
  onChange,
  onRemove,
  insideRepeater,
  testId,
  hideName,
}: ParameterBindingPickerProps) {
  const updateField = useCallback(
    <K extends keyof ParameterBindingRef>(
      key: K,
      v: ParameterBindingRef[K],
    ) => {
      onChange({ ...value, [key]: v })
    },
    [onChange, value],
  )

  const sourceWarning =
    value.source === "current_row" && !insideRepeater
      ? "current_row not available outside repeater — bindings will resolve to null at runtime."
      : null

  return (
    <div
      data-testid={testId ?? "action-binding-picker"}
      className="flex flex-col gap-1.5 rounded-md border border-border-subtle bg-surface-raised p-2"
    >
      {!hideName && (
        <InspectorField label="Parameter name">
          <TextFieldUncontrolled
            testId={`${testId ?? "action-binding"}-name`}
            value={value.name}
            placeholder="e.g. entity_id"
            onCommit={(v) => updateField("name", v)}
          />
        </InspectorField>
      )}
      <InspectorField label="Source">
        <SelectField<ParameterBindingSource>
          testId={`${testId ?? "action-binding"}-source`}
          value={value.source}
          onChange={(v) => onChange({ ...value, source: v })}
          options={BINDING_SOURCE_OPTIONS}
        />
      </InspectorField>
      {sourceWarning && (
        <div
          data-testid={`${testId ?? "action-binding"}-warning`}
          className="text-caption text-status-warning"
        >
          {sourceWarning}
        </div>
      )}
      {(value.source === "literal" || value.source === "static") && (
        <InspectorField label="Value">
          <TextFieldUncontrolled
            testId={`${testId ?? "action-binding"}-value`}
            value={
              typeof value.value === "string" ||
              typeof value.value === "number" ||
              typeof value.value === "boolean"
                ? String(value.value)
                : ""
            }
            placeholder="value"
            onCommit={(v) => updateField("value", v)}
          />
        </InspectorField>
      )}
      {(value.source === "route_param" || value.source === "query_param") && (
        <InspectorField label="Param name">
          <TextFieldUncontrolled
            testId={`${testId ?? "action-binding"}-param-name`}
            value={value.param_name ?? ""}
            placeholder="e.g. id"
            onCommit={(v) => updateField("param_name", v)}
          />
        </InspectorField>
      )}
      {(value.source === "tenant_context" ||
        value.source === "operator_context" ||
        value.source === "focus_context") && (
        <InspectorField label="Field name">
          <TextFieldUncontrolled
            testId={`${testId ?? "action-binding"}-field-name`}
            value={value.field_name ?? ""}
            placeholder="e.g. id / slug / role"
            onCommit={(v) => updateField("field_name", v)}
          />
        </InspectorField>
      )}
      {value.source === "current_row" && (
        <InspectorField label="Row field">
          <TextFieldUncontrolled
            testId={`${testId ?? "action-binding"}-row-field`}
            value={value.row_field ?? ""}
            placeholder="e.g. id"
            onCommit={(v) => updateField("row_field", v)}
          />
        </InspectorField>
      )}
      {onRemove && (
        <button
          type="button"
          data-testid={`${testId ?? "action-binding"}-remove`}
          onClick={onRemove}
          className="self-end text-caption text-status-error hover:underline"
        >
          Remove
        </button>
      )}
    </div>
  )
}
