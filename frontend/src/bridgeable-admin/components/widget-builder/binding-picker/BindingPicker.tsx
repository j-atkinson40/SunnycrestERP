/**
 * BindingPicker — WB-6 unified inspector control for atom-prop bindings.
 *
 * Composes SavedViewPicker + FieldPathPicker + IterationModePicker +
 * BindingPreviewTooltip into a single cascading authoring surface.
 * Replaces the WB-4b `BindingPlaceholderField` disabled-placeholder.
 *
 * Per-atom inspector contract: the inspector passes the current
 * `BindingRef` (looked up from `composition_blob.bindings_catalog`)
 * + an `onChange` callback that returns the next BindingRef shape.
 * Wiring of the BindingRef into the `binding_refs[propName]` map +
 * `bindings_catalog` lives at the inspector layer.
 *
 * Shape contract (Area 5d auto-inference):
 *   - When `atomType === 'repeater_atom'`: iteration_mode locked to
 *     'per_row'; SavedViewPicker filters to array-shaped views.
 *   - Otherwise: iteration_mode default 'single_record' (or
 *     'single_summary' for chart/stat views; locked).
 */
import { useCallback } from "react"

import type { BindingRef } from "@/lib/widget-builder/types/composition-blob"
import type { PresentationMode } from "@/types/saved-views"

import { BindingPreviewTooltip } from "./BindingPreviewTooltip"
import { FieldPathPicker } from "./FieldPathPicker"
import {
  IterationModePicker,
  inferIterationMode,
  type IterationMode,
} from "./IterationModePicker"
import { SavedViewPicker } from "./SavedViewPicker"
import { useBindingPicker } from "./useBindingPicker"


export interface BindingPickerProps {
  /** Which atom kind is hosting this picker (drives shape filter +
   *  iteration_mode inference). */
  atomType: string
  /** Current BindingRef for this atom prop (or null when not yet bound).
   *  The picker reads saved_view_id, field_path, iteration_mode from
   *  this ref. */
  bindingRef: BindingRef | null
  /** Called when the operator changes any picker dimension. Receives
   *  the next BindingRef (binding_type forced to 'field_path' here).
   *  When the saved_view_id is cleared, receives null (caller should
   *  remove the binding from binding_refs + bindings_catalog). */
  onChange: (next: BindingRef | null) => void
  /** Stable binding_id assigned by the inspector layer. Required to
   *  carry through onChange (the binding_id must be stable across edits
   *  so the catalog doesn't grow unbounded). */
  bindingId: string
  /** Inspector-level label (e.g. "Bound value", "Row binding"). */
  label?: string
  testId?: string
}


export function BindingPicker({
  atomType,
  bindingRef,
  onChange,
  bindingId,
  label,
  testId,
}: BindingPickerProps) {
  const { savedViews, entityTypes, loading, error } = useBindingPicker()

  const savedViewId = bindingRef?.saved_view_id ?? null
  const fieldPath = bindingRef?.field_path ?? null
  const iterationModeValue = (bindingRef?.iteration_mode ?? null) as
    | IterationMode
    | null

  const selectedSavedView = savedViewId
    ? savedViews.find((v) => v.id === savedViewId) ?? null
    : null
  const presentationMode: PresentationMode | null =
    selectedSavedView?.config.presentation.mode ?? null

  const requiresArrayShape = atomType === "repeater_atom"

  const inferred = inferIterationMode({ atomType, presentationMode })
  const effectiveIterationMode: IterationMode =
    inferred.locked
      ? inferred.mode
      : iterationModeValue ?? inferred.mode

  const handleSavedViewChange = useCallback(
    (nextId: string | null) => {
      if (nextId === null) {
        onChange(null)
        return
      }
      const nextView = savedViews.find((v) => v.id === nextId)
      const nextInferred = inferIterationMode({
        atomType,
        presentationMode: nextView?.config.presentation.mode ?? null,
      })
      onChange({
        binding_id: bindingId,
        binding_type: "field_path",
        saved_view_id: nextId,
        // Preserve field_path if the entity type is unchanged.
        field_path:
          nextView &&
          selectedSavedView &&
          nextView.config.query.entity_type ===
            selectedSavedView.config.query.entity_type
            ? fieldPath ?? undefined
            : undefined,
        iteration_mode: nextInferred.mode,
      })
    },
    [
      atomType,
      bindingId,
      fieldPath,
      onChange,
      savedViews,
      selectedSavedView,
    ],
  )

  const handleFieldPathChange = useCallback(
    (nextPath: string | null) => {
      if (!savedViewId) return
      onChange({
        binding_id: bindingId,
        binding_type: "field_path",
        saved_view_id: savedViewId,
        field_path: nextPath ?? undefined,
        iteration_mode: effectiveIterationMode,
      })
    },
    [bindingId, effectiveIterationMode, onChange, savedViewId],
  )

  const handleIterationModeChange = useCallback(
    (next: IterationMode) => {
      if (!savedViewId) return
      onChange({
        binding_id: bindingId,
        binding_type: "field_path",
        saved_view_id: savedViewId,
        field_path: fieldPath ?? undefined,
        iteration_mode: next,
      })
    },
    [bindingId, fieldPath, onChange, savedViewId],
  )

  if (loading) {
    return (
      <div
        data-testid={testId ? `${testId}-loading` : "binding-picker-loading"}
        className="rounded-md border border-dashed border-border-subtle bg-surface-sunken px-2 py-1.5 text-caption text-content-subtle"
      >
        Loading saved views…
      </div>
    )
  }

  if (error) {
    return (
      <div
        data-testid={testId ? `${testId}-error` : "binding-picker-error"}
        className="rounded-md border border-status-error/30 bg-status-error-muted px-2 py-1.5 text-caption text-status-error"
      >
        Failed to load saved views: {error}
      </div>
    )
  }

  return (
    <div
      data-testid={testId ?? "binding-picker"}
      className="flex flex-col gap-2"
    >
      {label && (
        <span className="text-caption font-medium text-content-muted">
          {label}
        </span>
      )}
      <div className="flex flex-col gap-1">
        <span className="text-caption text-content-muted">Saved view</span>
        <SavedViewPicker
          testId={testId ? `${testId}-saved-view` : "binding-picker-saved-view"}
          savedViews={savedViews}
          value={savedViewId}
          onChange={handleSavedViewChange}
          requiresArrayShape={requiresArrayShape}
        />
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-caption text-content-muted">Field path</span>
        <FieldPathPicker
          testId={testId ? `${testId}-field-path` : "binding-picker-field-path"}
          entityType={selectedSavedView?.config.query.entity_type ?? null}
          entityTypes={entityTypes}
          value={fieldPath}
          onChange={handleFieldPathChange}
        />
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-caption text-content-muted">Iteration mode</span>
        <IterationModePicker
          testId={
            testId
              ? `${testId}-iteration-mode`
              : "binding-picker-iteration-mode"
          }
          atomType={atomType}
          presentationMode={presentationMode}
          value={effectiveIterationMode}
          onChange={handleIterationModeChange}
        />
      </div>
      {savedViewId && fieldPath && (
        <BindingPreviewTooltip
          testId={testId ? `${testId}-preview` : "binding-picker-preview"}
          savedViewId={savedViewId}
          fieldPath={fieldPath}
          iterationMode={effectiveIterationMode}
        />
      )}
    </div>
  )
}
