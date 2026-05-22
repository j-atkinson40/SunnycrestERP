/**
 * BindingPreviewTooltip — WB-6 in-inspector preview-value display.
 *
 * Renders a small inline card beneath the picker showing the resolved
 * preview value. Bridges WB-6 → WB-5 — operators verify their binding
 * selections during authoring without waiting for canvas-preview
 * wiring.
 *
 * The "tooltip" framing in the prompt + investigation is rendered as
 * an inline card (always-visible when a binding is set) rather than a
 * hover tooltip; operator-validation-sensitive per Area 5 — visible
 * inline is more discoverable than hover-revealed for authoring.
 */
import { useBindingPreview, type BindingPreviewState } from "./useBindingPreview"


export interface BindingPreviewTooltipProps {
  savedViewId: string | null
  fieldPath: string | null
  iterationMode: "per_row" | "single_summary" | "single_record" | null
  testId?: string
}


export function BindingPreviewTooltip({
  savedViewId,
  fieldPath,
  iterationMode,
  testId,
}: BindingPreviewTooltipProps) {
  const state = useBindingPreview({ savedViewId, fieldPath, iterationMode })
  return <BindingPreviewTooltipDisplay state={state} testId={testId} />
}


/** Display-only inner — separate so tests can drive state directly. */
export function BindingPreviewTooltipDisplay({
  state,
  testId,
}: {
  state: BindingPreviewState
  testId?: string
}) {
  if (state.kind === "idle") return null

  if (state.kind === "loading") {
    return (
      <div
        data-testid={testId}
        data-preview-state="loading"
        className="rounded-md border border-dashed border-border-subtle bg-surface-sunken px-2 py-1.5 text-caption text-content-muted"
      >
        Resolving preview…
      </div>
    )
  }

  if (state.kind === "empty") {
    return (
      <div
        data-testid={testId}
        data-preview-state="empty"
        className="rounded-md border border-dashed border-border-subtle bg-surface-sunken px-2 py-1.5 text-caption text-content-muted"
      >
        Preview: {state.reason}
      </div>
    )
  }

  if (state.kind === "error") {
    return (
      <div
        data-testid={testId}
        data-preview-state="error"
        className="rounded-md border border-status-error/30 bg-status-error-muted px-2 py-1.5 text-caption text-status-error"
      >
        Preview error: {state.message}
      </div>
    )
  }

  // value
  return (
    <div
      data-testid={testId}
      data-preview-state="value"
      className="rounded-md border border-border-subtle bg-surface-sunken px-2 py-1.5"
    >
      <div className="text-caption text-content-muted">Preview</div>
      <div className="font-plex-mono text-body-sm text-content-strong">
        {state.preview}
      </div>
      {state.description && (
        <div className="mt-0.5 text-caption text-content-muted">
          {state.description}
        </div>
      )}
    </div>
  )
}
