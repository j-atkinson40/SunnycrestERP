/**
 * R-4.0 — action-handler dispatch table.
 *
 * Five handlers ship in R-4.0. Each takes `(actionConfig, resolvedParams,
 * deps)` and returns a Promise<R4DispatchResult>. Pure dispatch logic
 * lives here; React-hook-bound dependencies (navigate function, focus
 * open function) come in via the `deps` object so handlers stay
 * testable from vitest.
 *
 * Adding a new actionType:
 *   1. Extend `R4ActionType` in `types.ts`.
 *   2. Add a handler function below.
 *   3. Add it to `DISPATCH_HANDLERS` map.
 *   4. Register an example button using the new actionType.
 *
 * Per Spec-Override Discipline (CLAUDE.md §12): R-4.x increments add
 * new handlers as their substrate matures. Don't ship adjacent
 * capability silently. Each new handler comes with its own example
 * registration + Playwright spec.
 */

import apiClient from "@/lib/api-client"

import type {
  ActionConfig,
  R4ActionType,
  R4DispatchResult,
} from "./types"
import {
  substituteTemplate,
  type ResolvedValue,
} from "./parameter-resolver"


/** Hooks-bound dependencies handlers need. Populated by
 *  RegisteredButton at click-time and passed in. */
export interface DispatchDeps {
  /** react-router useNavigate(). */
  navigate: (to: string) => void
  /** focus-context's open(). Bound to the editor or tenant
   *  FocusProvider that's nearest to the click. */
  openFocus: (id: string, options?: { params?: Record<string, unknown> }) => void
}


/** Stringify a resolved value for URL-template substitution. Null
 *  becomes empty string (caller decides whether the template should
 *  swallow that). */
function asString(v: ResolvedValue): string {
  if (v === null || v === undefined) return ""
  return String(v)
}


/** Stringify resolved-values map for URLSearchParams (drops nulls). */
function paramsToQueryString(
  params: Record<string, ResolvedValue>,
): string {
  const usp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === null || v === undefined) continue
    usp.set(k, String(v))
  }
  const s = usp.toString()
  return s ? `?${s}` : ""
}


// ─── Five action handlers ─────────────────────────────────────────


async function handleNavigate(
  config: ActionConfig,
  resolved: Record<string, ResolvedValue>,
  deps: DispatchDeps,
): Promise<R4DispatchResult> {
  if (!config.route) {
    return {
      status: "error",
      errorMessage: "navigate action missing actionConfig.route",
    }
  }
  // Substitute {paramName} placeholders. Any unsubstituted placeholders
  // reach the URL as-is — visible bug rather than silent empty path.
  const valueMap: Record<string, ResolvedValue> = {}
  for (const [k, v] of Object.entries(resolved)) valueMap[k] = v
  const substituted = substituteTemplate(config.route, valueMap)
  deps.navigate(substituted)
  return { status: "success", data: { route: substituted } }
}


async function handleOpenFocus(
  config: ActionConfig,
  resolved: Record<string, ResolvedValue>,
  deps: DispatchDeps,
): Promise<R4DispatchResult> {
  if (!config.focusId) {
    return {
      status: "error",
      errorMessage: "open_focus action missing actionConfig.focusId",
    }
  }
  // Forward all resolved bindings as Focus params. FocusContext.open
  // accepts unknown-typed params per its registry contract.
  const params: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(resolved)) {
    if (v !== null) params[k] = v
  }
  deps.openFocus(config.focusId, { params })
  return { status: "success", data: { focusId: config.focusId } }
}


async function handleTriggerWorkflow(
  config: ActionConfig,
  resolved: Record<string, ResolvedValue>,
  _deps: DispatchDeps,
): Promise<R4DispatchResult> {
  if (!config.workflowId) {
    return {
      status: "error",
      errorMessage: "trigger_workflow action missing actionConfig.workflowId",
    }
  }
  // Workflow start endpoint expects { trigger_context: {...} }; we
  // forward all resolved bindings under that key. The workflow_engine
  // already accepts an unknown-shaped trigger_context dict.
  try {
    const resp = await apiClient.post(
      `/workflows/${encodeURIComponent(config.workflowId)}/start`,
      {
        trigger_context: { source: "r4_button", ...resolved },
      },
    )
    return {
      status: "success",
      data: { run_id: resp.data?.id ?? null, workflow_id: config.workflowId },
    }
  } catch (err: unknown) {
    const msg =
      err instanceof Error ? err.message : "Workflow trigger failed"
    return { status: "error", errorMessage: msg }
  }
}


async function handleCreateVaultItem(
  config: ActionConfig,
  resolved: Record<string, ResolvedValue>,
  _deps: DispatchDeps,
): Promise<R4DispatchResult> {
  if (!config.itemType) {
    return {
      status: "error",
      errorMessage: "create_vault_item action missing actionConfig.itemType",
    }
  }
  // Vault items take an item_type + an arbitrary fields dict. Resolved
  // bindings flatten directly onto the body. The API filters unknown
  // fields server-side.
  const body: Record<string, unknown> = {
    item_type: config.itemType,
  }
  for (const [k, v] of Object.entries(resolved)) {
    if (v !== null) body[k] = v
  }
  try {
    const resp = await apiClient.post("/vault/items", body)
    return {
      status: "success",
      data: { item_id: resp.data?.id ?? null, item_type: config.itemType },
    }
  } catch (err: unknown) {
    const msg =
      err instanceof Error ? err.message : "Vault item create failed"
    return { status: "error", errorMessage: msg }
  }
}


async function handleRunPlaywrightWorkflow(
  config: ActionConfig,
  resolved: Record<string, ResolvedValue>,
  _deps: DispatchDeps,
): Promise<R4DispatchResult> {
  if (!config.scriptName) {
    return {
      status: "error",
      errorMessage:
        "run_playwright_workflow action missing actionConfig.scriptName",
    }
  }
  // Existing operational Playwright path: POST inputs to the script
  // execution endpoint. The endpoint resolves credentials per-tenant
  // and returns the execution log id + output.
  try {
    const resp = await apiClient.post(
      `/playwright-scripts/${encodeURIComponent(config.scriptName)}/run`,
      { inputs: resolved },
    )
    return {
      status: "success",
      data: {
        log_id: resp.data?.log_id ?? null,
        script_name: config.scriptName,
      },
    }
  } catch (err: unknown) {
    const msg =
      err instanceof Error ? err.message : "Playwright run failed"
    return { status: "error", errorMessage: msg }
  }
}


// ─── Dispatch table ───────────────────────────────────────────────


type Handler = (
  config: ActionConfig,
  resolved: Record<string, ResolvedValue>,
  deps: DispatchDeps,
) => Promise<R4DispatchResult>


export const DISPATCH_HANDLERS: Readonly<Record<R4ActionType, Handler>> = {
  navigate: handleNavigate,
  open_focus: handleOpenFocus,
  trigger_workflow: handleTriggerWorkflow,
  create_vault_item: handleCreateVaultItem,
  run_playwright_workflow: handleRunPlaywrightWorkflow,
}


/** Single entry point for RegisteredButton. Resolves the handler
 *  for the action type, runs it. Unknown action types return an
 *  error result rather than throwing. */
export async function dispatchAction(
  actionType: R4ActionType,
  config: ActionConfig,
  resolved: Record<string, ResolvedValue>,
  deps: DispatchDeps,
): Promise<R4DispatchResult> {
  const handler = DISPATCH_HANDLERS[actionType]
  if (!handler) {
    return {
      status: "error",
      errorMessage: `Unknown action type: ${String(actionType)}`,
    }
  }
  try {
    return await handler(config, resolved, deps)
  } catch (err: unknown) {
    const msg =
      err instanceof Error ? err.message : "Action handler threw"
    return { status: "error", errorMessage: msg }
  }
}


// Internal helpers exposed for vitest. Not part of the public API.
export const __internals = {
  asString,
  paramsToQueryString,
  handleNavigate,
  handleOpenFocus,
  handleTriggerWorkflow,
  handleCreateVaultItem,
  handleRunPlaywrightWorkflow,
}
