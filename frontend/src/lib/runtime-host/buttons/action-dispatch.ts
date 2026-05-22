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
 *  RegisteredButton (R-4.0) or ButtonRenderer (WB-7) at click-time. */
export interface DispatchDeps {
  /** react-router useNavigate(). */
  navigate: (to: string) => void
  /** focus-context's open(). Bound to the editor or tenant
   *  FocusProvider that's nearest to the click. Optional — admin-tree
   *  previews supply a no-op (R-5.0.3 null-safe pattern). */
  openFocus: (id: string, options?: { params?: Record<string, unknown> }) => void
  /** WB-7 — peek-context's openPeek(). Optional — admin-tree previews
   *  supply a no-op. open_peek handler gracefully no-ops when this
   *  dep is absent (returns "skipped" status rather than throwing). */
  openPeek?: (args: {
    entityType: string
    entityId: string
    triggerType?: "hover" | "click"
  }) => void
  /** WB-7 — optional AbortSignal for click-during-loading dispatch
   *  cancellation. Passed through to network handlers (mutate +
   *  trigger_workflow) so a click during loading state can supersede
   *  an in-flight request without leaving the toast in a half-state.
   *  Scope distinct from WB-4a auto-save AbortController + WB-5
   *  canvas-preview AbortController per the locked separation. */
  abortSignal?: AbortSignal
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


// ─── WB-7 NEW handlers ────────────────────────────────────────────


async function handleOpenPeek(
  config: ActionConfig,
  resolved: Record<string, ResolvedValue>,
  deps: DispatchDeps,
): Promise<R4DispatchResult> {
  if (!config.peekEntityType) {
    return {
      status: "error",
      errorMessage: "open_peek action missing actionConfig.peekEntityType",
    }
  }
  // Peek expects a single entity_id. WB-7's authoring contract names
  // the resolved binding `entity_id`; if absent, fall back to the
  // first non-null resolved value (rare).
  let entityId = resolved.entity_id
  if (entityId === null || entityId === undefined) {
    for (const v of Object.values(resolved)) {
      if (v !== null && v !== undefined) {
        entityId = v
        break
      }
    }
  }
  if (entityId === null || entityId === undefined) {
    return {
      status: "error",
      errorMessage: "open_peek action missing entity_id binding",
    }
  }
  // Admin-tree previews: openPeek dep is absent. Gracefully no-op
  // with "skipped" status (mirrors the R-5.0.3 useFocusOptional
  // pattern for open_focus in admin trees).
  if (!deps.openPeek) {
    return {
      status: "skipped",
      data: {
        reason: "openPeek not available (admin preview / no provider)",
        entity_type: config.peekEntityType,
        entity_id: String(entityId),
      },
    }
  }
  deps.openPeek({
    entityType: config.peekEntityType,
    entityId: String(entityId),
    triggerType: "click",
  })
  return {
    status: "success",
    data: {
      entity_type: config.peekEntityType,
      entity_id: String(entityId),
    },
  }
}


async function handleMutate(
  config: ActionConfig,
  resolved: Record<string, ResolvedValue>,
  deps: DispatchDeps,
): Promise<R4DispatchResult> {
  // Phase 1 mutate narrowed to `anomaly_acknowledge` per §12.6a
  // bounded-state-flip discipline. Other mutate_kinds (mark_read,
  // status_flip) defer to WB-7.x.
  if (!config.mutateKind) {
    return {
      status: "error",
      errorMessage: "mutate action missing actionConfig.mutateKind",
    }
  }
  if (config.mutateKind !== "anomaly_acknowledge") {
    return {
      status: "error",
      errorMessage:
        `mutate action: unsupported mutate_kind "${config.mutateKind}" ` +
        `(Phase 1 ships anomaly_acknowledge only)`,
    }
  }
  // Anomaly acknowledge takes the resolved target_id (resolved
  // binding named `target_id` per the lift contract).
  const targetId = resolved.target_id
  if (targetId === null || targetId === undefined || targetId === "") {
    return {
      status: "error",
      errorMessage: "mutate action missing target_id binding",
    }
  }
  // Optional resolution_note bind under name `resolution_note`.
  const note =
    resolved.resolution_note !== undefined &&
    resolved.resolution_note !== null
      ? String(resolved.resolution_note)
      : undefined
  try {
    const body: Record<string, unknown> = {}
    if (note) body.resolution_note = note
    const resp = await apiClient.post(
      `/widget-data/anomalies/${encodeURIComponent(String(targetId))}/acknowledge`,
      body,
      deps.abortSignal ? { signal: deps.abortSignal } : undefined,
    )
    return {
      status: "success",
      data: {
        anomaly_id: resp.data?.id ?? String(targetId),
        resolved: resp.data?.resolved ?? true,
      },
    }
  } catch (err: unknown) {
    const msg =
      err instanceof Error ? err.message : "Anomaly acknowledge failed"
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
  open_peek: handleOpenPeek,                      // NEW WB-7
  mutate: handleMutate,                           // NEW WB-7
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
  handleOpenPeek,            // NEW WB-7
  handleMutate,              // NEW WB-7
  handleTriggerWorkflow,
  handleCreateVaultItem,
  handleRunPlaywrightWorkflow,
}
