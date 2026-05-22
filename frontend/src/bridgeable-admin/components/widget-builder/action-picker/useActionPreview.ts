/**
 * useActionPreview — pure-function preview text computation.
 *
 * NON-DISPATCHING per WB-7 Area 4 Lock 4b. Does NOT call the R-4
 * dispatcher; returns a human-readable summary string per verb. The
 * resolved-binding sample-record-derived preview is deferred to a
 * Phase 2 enrichment — Phase 1 ships verb + slug + binding shape
 * descriptions.
 */
import type {
  ActionRef,
  ParameterBindingRef,
} from "@/lib/widget-builder/types/composition-blob"


function describeBinding(b: ParameterBindingRef): string {
  switch (b.source) {
    case "literal":
    case "static":
      return `literal ${JSON.stringify(b.value ?? b.static_value ?? "")}`
    case "route_param":
      return `route param "${b.param_name ?? ""}"`
    case "query_param":
      return `query param "${b.param_name ?? ""}"`
    case "focus_context":
      return `focus.${b.field_name ?? ""}`
    case "tenant_context":
      return `tenant.${b.field_name ?? "id"}`
    case "operator_context":
      return `operator.${b.field_name ?? "id"}`
    case "current_row":
      return `row.${b.row_field ?? ""}`
    default:
      return "unknown source"
  }
}


export function computeActionPreviewText(action: ActionRef | null): string {
  if (!action) return "Pick an action verb to wire this button."
  switch (action.action_kind) {
    case "navigate":
      return action.href
        ? `Navigate to ${action.href}`
        : "Navigate (target route not set)"
    case "open_focus":
      return action.focus_template_slug
        ? `Open Focus "${action.focus_template_slug}"`
        : "Open Focus (slug not set)"
    case "open_peek":
      return `Open ${action.peek_view_type.replace(/_/g, " ")} peek panel`
    case "trigger_workflow":
      return action.workflow_slug
        ? `Trigger workflow "${action.workflow_slug}"`
        : "Trigger workflow (slug not set)"
    case "mutate": {
      const target = action.target_id_binding
      return `${action.mutate_kind} bound to ${describeBinding(target)}`
    }
  }
}


/** Hook entry point. Phase 1: returns the pure text. Phase 2 may
 *  enrich with resolved sample-record values. */
export function useActionPreview(action: ActionRef | null): {
  text: string
} {
  return { text: computeActionPreviewText(action) }
}
