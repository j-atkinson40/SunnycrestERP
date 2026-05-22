/**
 * ActionPicker types — narrow types + per-verb defaults shared across
 * the picker forms, preview card, and hooks.
 *
 * Per WB-7 Area 2 Lock 2a + Area 4 Lock 4c (verb-switch wipe).
 */
import type {
  ActionRef,
  ParameterBindingRef,
  ParameterBindingSource,
} from "@/lib/widget-builder/types/composition-blob"


export type ActionKind = ActionRef["action_kind"]


export const ACTION_KIND_LABELS: Record<ActionKind, string> = {
  navigate: "Navigate to route",
  open_focus: "Open Focus",
  open_peek: "Open Peek",
  trigger_workflow: "Trigger workflow",
  mutate: "Acknowledge / mutate",
}


export const PEEK_VIEW_TYPES = [
  "fh_case",
  "invoice",
  "sales_order",
  "task",
  "contact",
  "saved_view",
] as const


/** Per-verb confirm_before defaults per WB-7 Area 5 Lock 5b.
 *  trigger_workflow + mutate default to true; others default to false. */
export const CONFIRM_BEFORE_DEFAULTS: Record<ActionKind, boolean> = {
  navigate: false,
  open_focus: false,
  open_peek: false,
  trigger_workflow: true,
  mutate: true,
}


/** Build a fresh ActionRef of the given kind with per-verb defaults.
 *  Used when the operator first picks a verb (Lock 4d empty-state) +
 *  when switching verbs after wipe-confirm (Lock 4c). */
export function makeDefaultAction(kind: ActionKind): ActionRef {
  const confirm_before = CONFIRM_BEFORE_DEFAULTS[kind]
  switch (kind) {
    case "navigate":
      return { action_kind: "navigate", href: "", params: [], confirm_before }
    case "open_focus":
      return {
        action_kind: "open_focus",
        focus_template_slug: "",
        initial_context: [],
        confirm_before,
      }
    case "open_peek":
      return {
        action_kind: "open_peek",
        peek_view_type: "fh_case",
        initial_context: [],
        confirm_before,
      }
    case "trigger_workflow":
      return {
        action_kind: "trigger_workflow",
        workflow_slug: "",
        workflow_input: [],
        confirm_before,
      }
    case "mutate":
      return {
        action_kind: "mutate",
        mutate_kind: "anomaly_acknowledge",
        target_id_binding: {
          name: "anomaly_id",
          source: "current_row",
          row_field: "id",
        },
        confirm_before,
      }
  }
}


/** Detect whether an ActionRef has any "non-default" fields populated
 *  beyond the verb-defaults shape. Used by the verb-switch confirm
 *  modal (Lock 4c) — if everything is default, no confirm needed. */
export function hasNonDefaultContent(action: ActionRef): boolean {
  switch (action.action_kind) {
    case "navigate":
      return Boolean(
        action.href ||
          (action.params && action.params.length > 0) ||
          action.href_binding,
      )
    case "open_focus":
      return Boolean(
        action.focus_template_slug ||
          (action.initial_context && action.initial_context.length > 0),
      )
    case "open_peek":
      return Boolean(
        (action.initial_context && action.initial_context.length > 0) ||
          // peek_view_type defaults to fh_case; non-default = anything else
          (action.peek_view_type && action.peek_view_type !== "fh_case"),
      )
    case "trigger_workflow":
      return Boolean(
        action.workflow_slug ||
          (action.workflow_input && action.workflow_input.length > 0),
      )
    case "mutate":
      return Boolean(
        action.target_id_binding && action.target_id_binding.row_field
          ? action.target_id_binding.row_field !== "id"
          : false,
      )
  }
}


/** The 8 ParameterBindingPicker sources + labels.
 *  current_row is contextually gated outside a repeater per Area 6 +
 *  Risk 5 mitigation. */
export const BINDING_SOURCE_OPTIONS: ReadonlyArray<{
  value: ParameterBindingSource
  label: string
}> = [
  { value: "literal", label: "Literal value" },
  { value: "static", label: "Static (alias)" },
  { value: "route_param", label: "Route param" },
  { value: "query_param", label: "Query param" },
  { value: "focus_context", label: "Current Focus context" },
  { value: "tenant_context", label: "Current tenant" },
  { value: "operator_context", label: "Current operator" },
  { value: "current_row", label: "Current row (repeater)" },
]


/** Build an empty ParameterBindingRef for the picker's "Add binding"
 *  button. Defaults source to "literal" — operator picks the real
 *  source via the source dropdown. */
export function makeEmptyBinding(name = ""): ParameterBindingRef {
  return { name, source: "literal" }
}
