/**
 * R-4.0 — button substrate type definitions.
 *
 * Buttons are first-class composable components in the visual editor
 * registry. Each button registration declares an action contract via
 * the registry's `extensions` field — actionType, actionConfig,
 * parameterBindings, and per-button confirm/success behavior.
 *
 * Five action types ship in R-4.0 dispatch:
 *   - navigate              (react-router useNavigate)
 *   - open_focus            (FocusContext.open())
 *   - trigger_workflow      (POST /workflows/{id}/start)
 *   - create_vault_item     (POST /vault/items)
 *   - run_playwright_workflow (existing operational path)
 *
 * Other ActionKind values from `services/actions/` (search_result,
 * answer, ask_ai, view, document, saved_view, triage, ...) deferred
 * to R-4.x increments per Spec-Override Discipline. Each lands when
 * its underlying action substrate is stable.
 *
 * Seven parameter binding sources cover R-4.0:
 *   - literal               (config-time string/number/boolean)
 *   - current_user          (useAuth().user)
 *   - current_tenant        (useAuth().company)
 *   - current_date          (Date.now())
 *   - current_route_param   (useParams() by name)
 *   - current_query_param   (useSearchParams() by name)
 *   - current_focus_id      (useFocus().currentFocus?.id)
 *
 * Resolver runs at click-time. Missing context returns null/undefined
 * gracefully so partial bindings don't crash the dispatch.
 */


/** Five action types R-4.0 dispatches. R-4.x adds new entries
 *  alongside as substrate matures. */
export type R4ActionType =
  | "navigate"
  | "open_focus"
  | "trigger_workflow"
  | "create_vault_item"
  | "run_playwright_workflow"


/** Per-action-type configuration. Keys not under the active
 *  `actionType` are ignored at dispatch time. */
export interface ActionConfig {
  /** navigate: route to navigate to. May contain {paramName}
   *  placeholders that resolve from `parameterBindings`. */
  route?: string
  /** open_focus: focus id to invoke (matches `id` in
   *  `focus-registry.ts`). */
  focusId?: string
  /** trigger_workflow: workflow id to start. */
  workflowId?: string
  /** create_vault_item: vault item type discriminator. */
  itemType?: string
  /** run_playwright_workflow: registered Playwright script name. */
  scriptName?: string
}


/** Seven binding sources R-4.0 supports. Each resolves to a single
 *  value at click-time. */
export type ParameterBindingSource =
  | "literal"
  | "current_user"
  | "current_tenant"
  | "current_date"
  | "current_route_param"
  | "current_query_param"
  | "current_focus_id"


/** A single named parameter binding. The resolver returns
 *  `{[name]: resolvedValue}` for the dispatch handler. */
export interface ParameterBinding {
  /** Parameter name as the dispatch handler expects it (e.g. "case_id"
   *  for create_vault_item, "date" for open_focus). */
  name: string
  /** Where the value comes from. */
  source: ParameterBindingSource
  /** literal: the literal value. */
  value?: string | number | boolean
  /** current_user: which field to extract ("id" / "email" / "role"). */
  userField?: "id" | "email" | "role"
  /** current_tenant: which field to extract. */
  tenantField?: "id" | "slug" | "vertical"
  /** current_date: format. Defaults to "iso-date" (YYYY-MM-DD). */
  dateFormat?: "iso" | "iso-date" | "epoch-ms"
  /** current_route_param / current_query_param: param key. */
  paramName?: string
}


/** Per-button success behavior. The dispatch handler returns a
 *  result; this field tells RegisteredButton what to do next. */
export type SuccessBehavior = "stay" | "navigate" | "toast"


/** R-4.0 action contract — declared on each button registration's
 *  `extensions.r4` field. */
export interface R4ButtonContract {
  actionType: R4ActionType
  actionConfig: ActionConfig
  parameterBindings: ParameterBinding[]
  /** When true, click opens a confirmation Dialog before dispatch. */
  confirmBeforeFire?: boolean
  /** Dialog body copy when `confirmBeforeFire`. */
  confirmCopy?: string
  /** What to do after successful dispatch. */
  successBehavior?: SuccessBehavior
  /** successBehavior="navigate": route to navigate to post-success. */
  successNavigateRoute?: string
  /** successBehavior="toast": message text. */
  successToastMessage?: string
}


/** Registry `extensions` slot for R-4.0 buttons. Stored as
 *  `extensions: { r4: { ... } }` so future R-4.x increments can
 *  evolve the contract under a versioned key without disturbing
 *  the rest of the `extensions` namespace. */
export interface R4ButtonExtensions {
  r4: R4ButtonContract
}


/** Result returned by an R-4 action handler. RegisteredButton uses
 *  it to drive successBehavior. */
export interface R4DispatchResult {
  status: "success" | "error" | "skipped"
  /** Optional payload (e.g. created vault item id, workflow run id). */
  data?: Record<string, unknown>
  /** Human-readable error message when status="error". */
  errorMessage?: string
}
