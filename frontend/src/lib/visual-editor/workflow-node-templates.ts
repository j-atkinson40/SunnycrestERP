/**
 * workflow-node-templates — natural-language label templates for the
 * Workflow Builder cards (inline-params thread, P1, 2026-05-29).
 *
 * Each node type declares a sentence template with `{paramName}` slots
 * referencing its SEMANTIC configurableProps (a Shortcuts-style summary:
 * "Generate {templateKey} for {entityBinding} as {outputFormat}"). The
 * card renders the sentence with current param values as token-styled
 * spans (READ-ONLY in P1; P2 makes them clickable → scoped popover edit).
 *
 * Lives alongside `workflow-node-palette.ts` (the display-vocab
 * neighborhood) — NOT the registry (keeps registry render-agnostic, B-2
 * Path-A flat-category lock intact), NOT node-families.ts (that's card
 * color). Pure module: parse/interpolate are DOM-free + unit-testable
 * (mirrors simulate-trace.ts / canvas-layout.ts).
 *
 * SEMANTIC vs VESTIGIAL: every node type carries ~3 vestigial VISUAL props
 * (nodeShape / labelPosition / accentToken — A3-inert/superseded — plus the
 * 2 indicator enums). Templates slot SEMANTIC params only; the vestigial
 * set is the exclusion list (also the A3 "full nodeShape removal"
 * file-forward target). `WORKFLOW_TEMPLATE_GUARD` (test) asserts every
 * `{slot}` references a real semantic param of its type.
 */
import { getByName } from "@/lib/visual-editor/registry"
import type { ConfigPropSchema } from "@/lib/visual-editor/registry/types"

/** Visual props excluded from sentence templates (not semantic). */
export const VESTIGIAL_VISUAL_PARAMS: ReadonlySet<string> = new Set([
  "nodeShape",
  "labelPosition",
  "accentToken",
  "successIndicatorStyle",
  "failureIndicatorStyle",
])

/**
 * The 32 operator-approved templates (P1). `{x}` slots reference semantic
 * configurableProp names. Params NOT slotted here are popover-only in P2
 * (P1 simply doesn't render them). A type with no slots renders as a plain
 * label (start/input/output).
 */
export const NODE_LABEL_TEMPLATES: Record<string, string> = {
  start: "Start",
  end: "End ({terminalStatus})",
  input: "Receive input",
  output: "Output result",
  wait: "Wait {durationSeconds}",
  schedule: "Schedule {scheduleMode}",
  action: "Run action {actionType}",
  ai_prompt: "Run AI prompt {promptKey} ({model})",
  send_document: "Send {templateKey} to {recipientBinding} via {deliveryChannel}",
  send_email: "Email {templateKey} to {recipientBinding}",
  send_notification: "Notify {recipientBinding} via {channel}",
  "send-communication": "Send {templateKey} to {recipientBinding} via {channel}",
  notification: "Notify {recipientRole}: {message}",
  show_confirmation: 'Confirm "{title}"',
  open_slide_over: "Open {slideOverKey}",
  playwright_action: "Run script {scriptKey}",
  create_record: "Create {entityType}",
  update_record: "Update {entityType} {recordIdBinding}",
  log_vault_item: "Log {itemType}: {titleBinding}",
  generate_document: "Generate {templateKey} for {entityBinding} as {outputFormat}",
  call_service_method: "Call {serviceMethodKey}",
  "generation-focus-invocation": "Generate via {focusTemplateName}",
  invoke_generation_focus: "Invoke generation focus {focusTemplateName}",
  invoke_review_focus: "Invoke review focus {focusTemplateName}",
  cross_tenant_order: "Order to {targetTenantBinding}",
  cross_tenant_request: "Request {requestType} from {targetTenantBinding}",
  cross_tenant_acknowledgment: "Acknowledge {sourceRequestBinding} ({acknowledgmentStatus})",
  condition: "If {expression}",
  decision: "Decide among {branches}",
  branch: "Branch if {conditionExpression}",
  parallel_split: "Split into {branchCount} branches",
  parallel_join: "Join ({joinPolicy})",
}

/** Configurable-prop schemas for a node type (registry-backed). */
export function nodeConfigProps(
  nodeType: string,
): Record<string, ConfigPropSchema> {
  return (
    getByName("workflow-node", nodeType)?.metadata.configurableProps ?? {}
  )
}

/** Semantic params = configurableProps keys − the vestigial-visual set. */
export function semanticParams(nodeType: string): string[] {
  return Object.keys(nodeConfigProps(nodeType)).filter(
    (k) => !VESTIGIAL_VISUAL_PARAMS.has(k),
  )
}

/** The template for a node type (undefined if none — caller falls back). */
export function templateFor(nodeType: string): string | undefined {
  return NODE_LABEL_TEMPLATES[nodeType]
}

// ─── Pure engine: parse + interpolate (DOM-free) ────────────────────

/** A parsed template segment: literal prose or a `{param}` slot. */
export type TemplateSegment =
  | { kind: "literal"; text: string }
  | { kind: "slot"; param: string }

/**
 * Split a template into alternating literal + slot segments. Pure.
 * `"Wait {durationSeconds}"` → [literal "Wait ", slot durationSeconds].
 * No-slot templates → a single literal segment.
 */
export function parseTemplate(template: string): TemplateSegment[] {
  const segments: TemplateSegment[] = []
  const re = /\{(\w+)\}/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(template)) !== null) {
    if (m.index > last) {
      segments.push({ kind: "literal", text: template.slice(last, m.index) })
    }
    segments.push({ kind: "slot", param: m[1] })
    last = m.index + m[0].length
  }
  if (last < template.length) {
    segments.push({ kind: "literal", text: template.slice(last) })
  }
  return segments
}

/** A rendered token (a resolved slot): value, summary, or placeholder. */
export interface RenderedToken {
  kind: "token"
  param: string
  /** Display text. */
  text: string
  /** True when the param is unset (placeholder rendering). */
  placeholder: boolean
}

/** A render-model item: literal text or a resolved token. */
export type RenderedSegment =
  | { kind: "literal"; text: string }
  | RenderedToken

/** Humanize a param key for placeholder display: `recipientBinding` →
 *  "recipient binding". (camelCase + snake/kebab → spaced lower.) */
export function humanizeParam(param: string): string {
  return param
    .replace(/[_-]+/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .toLowerCase()
    .trim()
}

/** Summarize an object/array config value for a value-token.
 *  object → "N fields"; array → "N branches" for decision, else "N items". */
export function summarizeValue(param: string, value: unknown): string {
  if (Array.isArray(value)) {
    const n = value.length
    if (param === "branches") return `${n} branch${n === 1 ? "" : "es"}`
    return `${n} item${n === 1 ? "" : "s"}`
  }
  if (value && typeof value === "object") {
    const n = Object.keys(value as Record<string, unknown>).length
    return `${n} field${n === 1 ? "" : "s"}`
  }
  return String(value)
}

/**
 * Resolve a single slot's display text against a node's config + schema.
 *  - unset (no config value, no schema default) → placeholder token
 *    (humanized param name, e.g. "recipient binding").
 *  - object/array → summary ("3 fields" / "2 branches").
 *  - componentReference → resolved display name (focus-template lookup),
 *    raw ref if unresolvable.
 *  - enum/string/number/boolean → the value.
 */
export function resolveSlot(
  param: string,
  config: Record<string, unknown>,
  schema: ConfigPropSchema | undefined,
): RenderedToken {
  const hasConfig = config != null && param in config
  const raw = hasConfig ? config[param] : schema?.default
  const unset =
    raw === undefined || raw === null || raw === ""
  if (unset) {
    return {
      kind: "token",
      param,
      text: `[${humanizeParam(param)}]`,
      placeholder: true,
    }
  }
  const type = schema?.type
  if (type === "object" || type === "array" || Array.isArray(raw) ||
      (typeof raw === "object" && raw !== null)) {
    return { kind: "token", param, text: summarizeValue(param, raw), placeholder: false }
  }
  if (type === "componentReference" && typeof raw === "string") {
    const resolved =
      getByName("focus-template", raw)?.metadata.displayName ?? raw
    return { kind: "token", param, text: resolved, placeholder: false }
  }
  return { kind: "token", param, text: String(raw), placeholder: false }
}

/**
 * Interpolate a parsed template against a node's type + config into a
 * render model (literals + resolved tokens). Pure (registry lookups are
 * reads). The NodeLabelSentence component renders this model.
 */
export function interpolate(
  segments: TemplateSegment[],
  nodeType: string,
  config: Record<string, unknown>,
): RenderedSegment[] {
  const props = nodeConfigProps(nodeType)
  return segments.map((seg) =>
    seg.kind === "literal"
      ? seg
      : resolveSlot(seg.param, config ?? {}, props[seg.param]),
  )
}

/**
 * Convenience: type + config → render model (parse + interpolate).
 * Returns null when the type has no template (caller falls back to the
 * plain node.label render).
 */
export function renderModelFor(
  nodeType: string,
  config: Record<string, unknown>,
): RenderedSegment[] | null {
  const tmpl = templateFor(nodeType)
  if (tmpl === undefined) return null
  return interpolate(parseTemplate(tmpl), nodeType, config)
}
