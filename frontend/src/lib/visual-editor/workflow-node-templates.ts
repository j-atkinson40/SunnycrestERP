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
import type {
  ConfigPropSchema,
  ConfigPropType,
} from "@/lib/visual-editor/registry/types"

/**
 * RETIRED visual props — superseded by A3 (uniform cards + family tone +
 * per-type icon). No render reads them; the sentence engine excludes them
 * from tokenization. Registry declarations REMAIN — true removal is
 * canon-gated by the ≥3-configurableProps rule + the backend snapshot.
 */
export const VESTIGIAL_VISUAL_PARAMS: ReadonlySet<string> = new Set([
  "nodeShape",
  "labelPosition",
  "accentToken",
])

/**
 * NOT-YET-IMPLEMENTED props — a future per-node success/failure status
 * indicator (successIndicatorStyle / failureIndicatorStyle): no render yet,
 * reserved. (These were declared on the now-retired generation-focus-invocation
 * node — focus-invocation reconciliation P2; no registration declares them
 * today. The set persists as a forward-looking exclusion for when the
 * status-indicator feature lands — DISTINCT from the retired-visual set above.)
 */
export const NOT_YET_IMPLEMENTED_PARAMS: ReadonlySet<string> = new Set([
  "successIndicatorStyle",
  "failureIndicatorStyle",
])

/**
 * Params hidden from the node INSPECTOR (RegistryDrivenConfig render):
 * the retired-visual set ∪ the not-yet-implemented set. Two reasons, one
 * inspector filter. This is the INSPECTOR's concern ONLY — the sentence
 * engine (`semanticParams`) excludes just the RETIRED set
 * (VESTIGIAL_VISUAL_PARAMS), NOT this union: the not-yet-built indicators
 * are inspector-hidden but stay semantic so a future feature can token
 * them. The props stay DECLARED in the registry (≥3 rule + backend
 * snapshot untouched); only their inspector controls are suppressed.
 */
export const INSPECTOR_HIDDEN_PARAMS: ReadonlySet<string> = new Set([
  ...VESTIGIAL_VISUAL_PARAMS,
  ...NOT_YET_IMPLEMENTED_PARAMS,
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
  invoke_generation_focus: "Invoke generation focus {focus_id}",
  invoke_review_focus: "Invoke review focus {review_focus_id}",
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
  // Excludes ONLY the RETIRED-visual props (VESTIGIAL_VISUAL_PARAMS) — the
  // sentence engine's permanent tokenization-exclusion. NOT the union: the
  // not-yet-built indicator enums are hidden from the INSPECTOR
  // (INSPECTOR_HIDDEN_PARAMS, RegistryDrivenConfig) but stay SEMANTIC here,
  // so a future status-indicator feature can token them without fighting
  // the engine. Keeping the two reasons distinct (retired ≠ not-yet-built).
  return Object.keys(nodeConfigProps(nodeType)).filter(
    (k) => !VESTIGIAL_VISUAL_PARAMS.has(k),
  )
}

/** The template for a node type (undefined if none — caller falls back). */
export function templateFor(nodeType: string): string | undefined {
  return NODE_LABEL_TEMPLATES[nodeType]
}

/**
 * UN-SLOTTED params (inline-params P3a) — a node type's configurableProp
 * keys that are NEITHER inspector-hidden NOR already slotted in its sentence
 * template. These edit ONLY in the inspector today; the card's expand panel
 * surfaces them as editable rows so every config param has an inline home
 * (the precondition for retiring the inspector in P3c). Pure, registry-backed
 * (mirrors `semanticParams`). Returns `[]` for the 6 fully-slotted types
 * (start, end, send_document, generate_document, cross_tenant_acknowledgment,
 * branch).
 *
 * TWO-TIER discipline: this DELIBERATELY excludes the template-slotted params
 * (which edit via their sentence tokens) so each param is editable in exactly
 * ONE place — no duplication between the sentence and the panel. It reuses the
 * SAME `INSPECTOR_HIDDEN_PARAMS` set the inspector filters
 * (RegistryDrivenConfig), so the retired-visual + not-yet-built indicator
 * params stay out of the panel too.
 */
export function unslottedParams(nodeType: string): string[] {
  const tmpl = templateFor(nodeType)
  const slotted = new Set(
    tmpl === undefined
      ? []
      : parseTemplate(tmpl)
          .filter((s): s is { kind: "slot"; param: string } => s.kind === "slot")
          .map((s) => s.param),
  )
  return Object.keys(nodeConfigProps(nodeType)).filter(
    (k) => !INSPECTOR_HIDDEN_PARAMS.has(k) && !slotted.has(k),
  )
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
  /**
   * The param's ConfigPropType (P2a). Gates editability: simple types
   * (string/enum/number/boolean) render as clickable popover-editor
   * tokens; complex types (object/array/componentReference) + an absent
   * schema stay read-only. The editor re-fetches the full schema via
   * `nodeConfigProps`; only the type is carried here for the gate.
   */
  propType?: ConfigPropType
}

/**
 * ConfigPropTypes whose tokens are inline-editable. P2a (2026-05-29)
 * shipped the four SIMPLE types; P2b adds the three COMPLEX types — each
 * renders the EXISTING PropControlDispatcher control in the popover
 * (object → ObjectControl JSON textarea, array → ArrayControl,
 * componentReference → ComponentReferenceControl picker). No new control
 * bodies — the dispatcher already handles all seven as controlled
 * {schema,value,onChange} components. (Renamed from SIMPLE_EDITABLE_TYPES
 * — no longer simple-only.)
 *
 * NOTE on `object`: no current template SLOTS an object param (the 32
 * templates slot only `branches`:array + `focusTemplateName`:
 * componentReference among the complex types). object is included here
 * so the gate is forward-compatible — the instant a future template
 * slots an object param, it edits inline with zero further work.
 */
export const EDITABLE_TOKEN_TYPES: ReadonlySet<string> = new Set([
  "string",
  "enum",
  "number",
  "boolean",
  "object",
  "array",
  "componentReference",
])

/**
 * Node types whose tokens are NEVER inline-editable, regardless of propType.
 * Both use bespoke inspector configs (InvokeGenerationFocusConfig /
 * InvokeReviewFocusConfig).
 *
 * The namespace divergence that originally motivated this set was RESOLVED in
 * the focus-invocation reconciliation arc: P1 reshaped the registry + template
 * to the real keys (focus_id / op_id / kwargs ; review_focus_id /
 * input_data_binding / …), so registry/template/config/backend now agree —
 * there is no longer a phantom-key risk. These two types stay read-only for a
 * DIFFERENT reason: their editor SHAPE is genuinely bespoke (op_id's options
 * depend on focus_id; kwargs is a dynamic binding-row list) — a plain inline
 * token / expand-panel control can't express it. P3 (E-3: host the bespoke
 * config in the card's expand panel) ungates them from this set.
 *
 * (The redundant hyphenated `generation-focus-invocation` twin was retired in
 * reconciliation P2; `invoke_generation_focus` is now the sole generation
 * focus node.)
 */
export const BESPOKE_NAMESPACE_TYPES: ReadonlySet<string> = new Set([
  "invoke_generation_focus",
  "invoke_review_focus",
])

/** True when a token's PROP TYPE is one of the inline-editable kinds.
 *  Pure propType gate — the namespace exclusion is applied separately by
 *  `isTokenInlineEditable` (the gate NodeLabelSentence consults). */
export function isEditableToken(token: RenderedToken): boolean {
  return token.propType !== undefined && EDITABLE_TOKEN_TYPES.has(token.propType)
}

/** True when a token is inline-editable IN CONTEXT: its propType is
 *  editable AND its node type is not a bespoke-namespace type (whose
 *  template tokens map to keys the authoring path never writes). This is
 *  the gate NodeLabelSentence consults to decide clickable vs read-only. */
export function isTokenInlineEditable(
  nodeType: string,
  token: RenderedToken,
): boolean {
  return isEditableToken(token) && !BESPOKE_NAMESPACE_TYPES.has(nodeType)
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
  const propType = schema?.type
  const unset =
    raw === undefined || raw === null || raw === ""
  if (unset) {
    return {
      kind: "token",
      param,
      text: `[${humanizeParam(param)}]`,
      placeholder: true,
      propType,
    }
  }
  if (propType === "object" || propType === "array" || Array.isArray(raw) ||
      (typeof raw === "object" && raw !== null)) {
    return { kind: "token", param, text: summarizeValue(param, raw), placeholder: false, propType }
  }
  if (propType === "componentReference" && typeof raw === "string") {
    const resolved =
      getByName("focus-template", raw)?.metadata.displayName ?? raw
    return { kind: "token", param, text: resolved, placeholder: false, propType }
  }
  return { kind: "token", param, text: String(raw), placeholder: false, propType }
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
