/**
 * Registry registrations — workflow node types.
 *
 * Two examples for Phase 1: a Generation Focus invocation node
 * and a Communication node. The workflow engine
 * (`workflow_engine.py`) executes step types via dispatch tables;
 * registry entries here describe each node type's editor
 * affordance.
 *
 * Phase 3 backfill: configurableProps describe visual + behavioral
 * configuration on the workflow canvas — node shape, label
 * position, indicator style, retry semantics.
 */

import { registerComponent } from "../register"
import { makePlaceholder } from "./_placeholders"


// NOTE (focus-invocation reconciliation P2, 2026-06-02): the Phase-1
// `generation-focus-invocation` registration was retired here — it was the
// redundant twin of `invoke_generation_focus` (both declared
// `extensions.workflowStepType: "invoke_generation_focus"`, one runtime
// operation). The keeper is `invoke_generation_focus` (correct runtime
// namespace: focus_id / op_id / kwargs, reconciled in P1).
registerComponent({
  type: "workflow-node",
  name: "send-communication",
  displayName: "Send Communication",
  description:
    "Channel-agnostic communication step. Wraps DeliveryService.send (D-7) — email today; SMS / phone / messaging when those primitives ship. Templates resolved via the document-template registry; recipients resolved via workflow context.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: [
    "surface-raised",
    "border-base",
    "accent",
    "status-info",
    "status-info-muted",
    "radius-base",
    "shadow-level-2",
    "text-body",
    "text-caption",
  ],
  configurableProps: {
    channel: {
      type: "enum",
      default: "email",
      bounds: ["email", "sms", "phone", "messaging"],
      displayLabel: "Channel",
      description:
        "SMS / phone / messaging are stubbed at the channel registry; email is the only fully-wired channel today (D-7).",
    },
    templateKey: {
      type: "string",
      default: "",
      displayLabel: "Template key",
      description:
        "Document template identifier (e.g., email.collections, email.fh_aftercare_7day).",
      required: true,
      bounds: { maxLength: 96 },
    },
    recipientBinding: {
      type: "string",
      default: "{customer.email}",
      displayLabel: "Recipient binding",
      description:
        "Workflow variable expression resolving to the recipient address.",
      bounds: { maxLength: 128 },
    },
    maxRetries: {
      type: "number",
      default: 3,
      bounds: [0, 10],
      displayLabel: "Max retries",
      description: "Retry attempts before marking the step failed.",
    },
    retryBackoffSeconds: {
      type: "number",
      default: 60,
      bounds: [5, 3600],
      displayLabel: "Retry backoff (seconds)",
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "envelope", "hexagon"],
      displayLabel: "Node shape on canvas",
      description:
        "'envelope' renders an envelope glyph for email; the editor uses this only when channel='email'.",
    },
    labelPosition: {
      type: "enum",
      default: "inside",
      bounds: ["inside", "above", "below"],
      displayLabel: "Label position",
    },
    accentToken: {
      type: "tokenReference",
      default: "status-info",
      tokenCategory: "status",
      displayLabel: "Node accent",
      description:
        "Token coloring the success-state accent on the workflow canvas.",
    },
  },
  schemaVersion: 1,
  componentVersion: 2,
  extensions: {
    workflowStepType: "send_document",
    serviceMethodKey: "delivery_service.send",
  },
})(makePlaceholder("Send Communication Node"))


// ─────────────────────────────────────────────────────────────────────
// Phase B sub-arc B-2 — node-type registry expansion (2 → 32).
//
// Registers the remaining 30 canonical VALID_NODE_TYPES
// (`canvas_validator.py:62-105`) so the workflow-builder palette renders
// from registry introspection (`getByType("workflow-node")`) instead of
// a hardcoded JSX tuple. Each entry mirrors the two Phase-1 registrations
// above verbatim in shape: category "workflow-nodes" (flat — Path A, no
// grouping substrate), verticals ["all"], userParadigms
// ["operator-power-user"], object-map configurableProps (>=3 genuine
// keys), extensions.workflowStepType mapping the node to its runtime
// engine vocabulary. componentVersion 1 (new this sub-arc; the two
// Phase-1 entries are at 2 from the Phase-3 backfill).
//
// Shared canvas-visual vocabulary (nodeShape / labelPosition /
// accentToken) is drawn from the established Phase-1 convention; these
// are genuine rendering config consumed by the B-1 GraphCanvas, NOT
// filler to reach the >=3 floor.
// ─────────────────────────────────────────────────────────────────────


// ─── Lifecycle (2) ──────────────────────────────────────────────────

registerComponent({
  type: "workflow-node",
  name: "start",
  displayName: "Start",
  description:
    "Workflow entry point. Every workflow has exactly one start node; the engine begins execution here. Carries no runtime action — purely the graph's source vertex.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-elevated", "border-accent", "accent", "radius-base", "text-body"],
  configurableProps: {
    nodeShape: {
      type: "enum",
      default: "circle",
      bounds: ["circle", "rounded-rect", "pill"],
      displayLabel: "Node shape on canvas",
      description: "Visual shape used when the start node renders in the graph canvas.",
    },
    labelPosition: {
      type: "enum",
      default: "below",
      bounds: ["inside", "above", "below"],
      displayLabel: "Label position",
    },
    accentToken: {
      type: "tokenReference",
      default: "status-success",
      tokenCategory: "status",
      displayLabel: "Node accent",
      description: "Token coloring the start node's accent on the workflow canvas.",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "start", serviceMethodKey: null },
})(makePlaceholder("Start Node"))


registerComponent({
  type: "workflow-node",
  name: "end",
  displayName: "End",
  description:
    "Workflow terminal node. Reaching an end node completes the run. A workflow may have multiple end nodes (one per terminal branch); terminalStatus records which outcome the branch represents.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-elevated", "border-base", "accent", "radius-base", "text-body"],
  configurableProps: {
    terminalStatus: {
      type: "enum",
      default: "success",
      bounds: ["success", "failure", "cancelled"],
      displayLabel: "Terminal status",
      description: "Which outcome reaching this end node represents for the run record.",
    },
    nodeShape: {
      type: "enum",
      default: "circle",
      bounds: ["circle", "rounded-rect", "pill"],
      displayLabel: "Node shape on canvas",
    },
    labelPosition: {
      type: "enum",
      default: "below",
      bounds: ["inside", "above", "below"],
      displayLabel: "Label position",
    },
    accentToken: {
      type: "tokenReference",
      default: "content-muted",
      tokenCategory: "status",
      displayLabel: "Node accent",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "end", serviceMethodKey: null },
})(makePlaceholder("End Node"))


// ─── Engine step types (8) ──────────────────────────────────────────

registerComponent({
  type: "workflow-node",
  name: "input",
  displayName: "Input",
  description:
    "Captures structured input into the workflow context. Downstream steps reference it via {input.*} variable bindings.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-base", "accent", "radius-base", "text-body", "text-caption"],
  configurableProps: {
    inputSchema: {
      type: "object",
      default: {},
      displayLabel: "Input schema",
      description: "Field definitions captured into {input.*} for downstream binding.",
    },
    required: {
      type: "boolean",
      default: true,
      displayLabel: "Required",
      description: "Whether the workflow blocks until input is supplied.",
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "parallelogram", "pill"],
      displayLabel: "Node shape on canvas",
    },
    labelPosition: {
      type: "enum",
      default: "inside",
      bounds: ["inside", "above", "below"],
      displayLabel: "Label position",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "input", serviceMethodKey: null },
})(makePlaceholder("Input Node"))


registerComponent({
  type: "workflow-node",
  name: "action",
  displayName: "Action",
  description:
    "Generic action step. The engine dispatches by the action's configured action_type; use a specialized node (create_record, send_email, etc.) when one exists.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "surface-elevated", "border-base", "accent", "radius-base", "text-body"],
  configurableProps: {
    actionType: {
      type: "string",
      default: "",
      displayLabel: "Action type",
      description: "Engine action_type dispatched by _execute_action.",
      required: true,
      bounds: { maxLength: 64 },
    },
    parameters: {
      type: "object",
      default: {},
      displayLabel: "Parameters",
      description: "Action parameters; values may reference workflow variables.",
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "hexagon"],
      displayLabel: "Node shape on canvas",
    },
    labelPosition: {
      type: "enum",
      default: "inside",
      bounds: ["inside", "above", "below"],
      displayLabel: "Label position",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "action", serviceMethodKey: null },
})(makePlaceholder("Action Node"))


registerComponent({
  type: "workflow-node",
  name: "ai_prompt",
  displayName: "AI Prompt",
  description:
    "Invokes Claude with a managed prompt. Output is parsed (force-JSON) into the workflow context for downstream binding.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-accent", "accent", "accent-subtle", "radius-base", "text-body", "text-caption"],
  configurableProps: {
    promptKey: {
      type: "string",
      default: "",
      displayLabel: "Managed prompt key",
      description: "Identifier of the managed prompt to invoke.",
      required: true,
      bounds: { maxLength: 96 },
    },
    model: {
      type: "enum",
      default: "haiku",
      bounds: ["haiku", "sonnet"],
      displayLabel: "Model route",
      description: "Haiku for simple/cheap extraction; Sonnet for complex reasoning.",
    },
    temperature: {
      type: "number",
      default: 0,
      bounds: [0, 1],
      displayLabel: "Temperature",
    },
    maxTokens: {
      type: "number",
      default: 1024,
      bounds: [64, 8192],
      displayLabel: "Max output tokens",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "ai_prompt", serviceMethodKey: null },
})(makePlaceholder("AI Prompt Node"))


registerComponent({
  type: "workflow-node",
  name: "send_document",
  displayName: "Send Document",
  description:
    "Renders a document template and delivers it via DeliveryService (D-7). Distinct from send-communication (channel-agnostic wrapper) — this is the document-delivery step type.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-base", "accent", "status-info", "radius-base", "text-body", "text-caption"],
  configurableProps: {
    templateKey: {
      type: "string",
      default: "",
      displayLabel: "Document template key",
      required: true,
      bounds: { maxLength: 96 },
    },
    recipientBinding: {
      type: "string",
      default: "{customer.email}",
      displayLabel: "Recipient binding",
      bounds: { maxLength: 128 },
    },
    deliveryChannel: {
      type: "enum",
      default: "email",
      bounds: ["email", "download", "portal"],
      displayLabel: "Delivery channel",
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "document"],
      displayLabel: "Node shape on canvas",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "send_document", serviceMethodKey: "delivery_service.send_email_with_template" },
})(makePlaceholder("Send Document Node"))


registerComponent({
  type: "workflow-node",
  name: "playwright_action",
  displayName: "Playwright Action",
  description:
    "Runs a registered Playwright script for browser automation (e.g., portal scraping, third-party form submission).",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-base", "accent", "status-warning", "radius-base", "text-body"],
  configurableProps: {
    scriptKey: {
      type: "string",
      default: "",
      displayLabel: "Playwright script key",
      required: true,
      bounds: { maxLength: 96 },
    },
    timeoutSeconds: {
      type: "number",
      default: 120,
      bounds: [10, 1800],
      displayLabel: "Timeout (seconds)",
    },
    retryOnFailure: {
      type: "boolean",
      default: false,
      displayLabel: "Retry on failure",
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "hexagon"],
      displayLabel: "Node shape on canvas",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "playwright_action", serviceMethodKey: null },
})(makePlaceholder("Playwright Action Node"))


registerComponent({
  type: "workflow-node",
  name: "condition",
  displayName: "Condition",
  description:
    "Boolean gate. Evaluates a Jinja expression against the workflow context; the true/false outcome selects the outgoing edge.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-accent", "accent", "radius-base", "text-body", "text-caption"],
  configurableProps: {
    expression: {
      type: "string",
      default: "",
      displayLabel: "Condition expression",
      description: "Jinja expression resolving to truthy/falsy against the workflow context.",
      required: true,
      bounds: { maxLength: 256 },
    },
    trueLabel: {
      type: "string",
      default: "Yes",
      displayLabel: "True-branch label",
      bounds: { maxLength: 32 },
    },
    falseLabel: {
      type: "string",
      default: "No",
      displayLabel: "False-branch label",
      bounds: { maxLength: 32 },
    },
    nodeShape: {
      type: "enum",
      default: "diamond",
      bounds: ["diamond", "rounded-rect"],
      displayLabel: "Node shape on canvas",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "condition", serviceMethodKey: null },
})(makePlaceholder("Condition Node"))


registerComponent({
  type: "workflow-node",
  name: "output",
  displayName: "Output",
  description:
    "Publishes workflow results into {output.*} for the run record and any consuming caller.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-base", "accent", "radius-base", "text-body", "text-caption"],
  configurableProps: {
    outputBinding: {
      type: "object",
      default: {},
      displayLabel: "Output binding",
      description: "Maps workflow variables into the published {output.*} payload.",
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "parallelogram"],
      displayLabel: "Node shape on canvas",
    },
    labelPosition: {
      type: "enum",
      default: "inside",
      bounds: ["inside", "above", "below"],
      displayLabel: "Label position",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "output", serviceMethodKey: null },
})(makePlaceholder("Output Node"))


registerComponent({
  type: "workflow-node",
  name: "notification",
  displayName: "Notification",
  description:
    "Raises an in-app notification to a role or user resolved from the workflow context.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-base", "accent", "status-info", "status-info-muted", "radius-base", "text-body"],
  configurableProps: {
    message: {
      type: "string",
      default: "",
      displayLabel: "Message",
      description: "Notification body; may reference workflow variables.",
      required: true,
      bounds: { maxLength: 256 },
    },
    severity: {
      type: "enum",
      default: "info",
      bounds: ["info", "success", "warning", "error"],
      displayLabel: "Severity",
    },
    recipientRole: {
      type: "string",
      default: "",
      displayLabel: "Recipient role",
      description: "Role slug to notify (e.g., admin, production).",
      bounds: { maxLength: 48 },
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "pill"],
      displayLabel: "Node shape on canvas",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "notification", serviceMethodKey: null },
})(makePlaceholder("Notification Node"))


// ─── Action types (9) ───────────────────────────────────────────────

registerComponent({
  type: "workflow-node",
  name: "create_record",
  displayName: "Create Record",
  description:
    "Creates a new entity record (sales order, invoice, task, etc.) with fields bound from the workflow context.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-base", "accent", "status-success", "radius-base", "text-body"],
  configurableProps: {
    entityType: {
      type: "string",
      default: "",
      displayLabel: "Entity type",
      required: true,
      bounds: { maxLength: 48 },
    },
    fieldBindings: {
      type: "object",
      default: {},
      displayLabel: "Field bindings",
      description: "Maps workflow variables into the new record's fields.",
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "hexagon"],
      displayLabel: "Node shape on canvas",
    },
    labelPosition: {
      type: "enum",
      default: "inside",
      bounds: ["inside", "above", "below"],
      displayLabel: "Label position",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "create_record", serviceMethodKey: null },
})(makePlaceholder("Create Record Node"))


registerComponent({
  type: "workflow-node",
  name: "update_record",
  displayName: "Update Record",
  description:
    "Updates an existing record resolved by an id binding; patches the configured fields from the workflow context.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-base", "accent", "status-info", "radius-base", "text-body"],
  configurableProps: {
    entityType: {
      type: "string",
      default: "",
      displayLabel: "Entity type",
      required: true,
      bounds: { maxLength: 48 },
    },
    recordIdBinding: {
      type: "string",
      default: "",
      displayLabel: "Record id binding",
      description: "Workflow variable resolving to the target record id.",
      required: true,
      bounds: { maxLength: 128 },
    },
    fieldBindings: {
      type: "object",
      default: {},
      displayLabel: "Field bindings",
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "hexagon"],
      displayLabel: "Node shape on canvas",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "update_record", serviceMethodKey: null },
})(makePlaceholder("Update Record Node"))


registerComponent({
  type: "workflow-node",
  name: "open_slide_over",
  displayName: "Open Slide-Over",
  description:
    "Opens a slide-over panel for the operator (interactive workflow step). Used for human-in-the-loop data entry mid-workflow.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "surface-elevated", "border-base", "accent", "radius-base", "text-body"],
  configurableProps: {
    slideOverKey: {
      type: "string",
      default: "",
      displayLabel: "Slide-over key",
      required: true,
      bounds: { maxLength: 96 },
    },
    contextBinding: {
      type: "object",
      default: {},
      displayLabel: "Context binding",
      description: "Workflow variables passed into the slide-over.",
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "pill"],
      displayLabel: "Node shape on canvas",
    },
    labelPosition: {
      type: "enum",
      default: "inside",
      bounds: ["inside", "above", "below"],
      displayLabel: "Label position",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "open_slide_over", serviceMethodKey: null },
})(makePlaceholder("Open Slide-Over Node"))


registerComponent({
  type: "workflow-node",
  name: "show_confirmation",
  displayName: "Show Confirmation",
  description:
    "Presents a confirmation dialog to the operator; the workflow pauses until confirmed or dismissed.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-accent", "accent", "accent-subtle", "radius-base", "text-body"],
  configurableProps: {
    title: {
      type: "string",
      default: "",
      displayLabel: "Title",
      required: true,
      bounds: { maxLength: 96 },
    },
    body: {
      type: "string",
      default: "",
      displayLabel: "Body",
      bounds: { maxLength: 256 },
    },
    confirmLabel: {
      type: "string",
      default: "Confirm",
      displayLabel: "Confirm button label",
      bounds: { maxLength: 32 },
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "diamond"],
      displayLabel: "Node shape on canvas",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "show_confirmation", serviceMethodKey: null },
})(makePlaceholder("Show Confirmation Node"))


registerComponent({
  type: "workflow-node",
  name: "send_notification",
  displayName: "Send Notification",
  description:
    "Dispatches a notification through a configured channel + template; recipients resolved from the workflow context.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-base", "accent", "status-info", "status-info-muted", "radius-base", "text-body"],
  configurableProps: {
    channel: {
      type: "enum",
      default: "in_app",
      bounds: ["in_app", "email", "sms"],
      displayLabel: "Channel",
    },
    templateKey: {
      type: "string",
      default: "",
      displayLabel: "Template key",
      required: true,
      bounds: { maxLength: 96 },
    },
    recipientBinding: {
      type: "string",
      default: "",
      displayLabel: "Recipient binding",
      bounds: { maxLength: 128 },
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "pill"],
      displayLabel: "Node shape on canvas",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "send_notification", serviceMethodKey: null },
})(makePlaceholder("Send Notification Node"))


registerComponent({
  type: "workflow-node",
  name: "send_email",
  displayName: "Send Email",
  description:
    "Sends an email via a managed template (D-7 delivery). Distinct from send_document — body-only email without a rendered document attachment.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-base", "accent", "status-info", "radius-base", "text-body", "text-caption"],
  configurableProps: {
    templateKey: {
      type: "string",
      default: "",
      displayLabel: "Email template key",
      required: true,
      bounds: { maxLength: 96 },
    },
    recipientBinding: {
      type: "string",
      default: "{customer.email}",
      displayLabel: "Recipient binding",
      bounds: { maxLength: 128 },
    },
    subjectBinding: {
      type: "string",
      default: "",
      displayLabel: "Subject binding",
      bounds: { maxLength: 128 },
    },
    maxRetries: {
      type: "number",
      default: 3,
      bounds: [0, 10],
      displayLabel: "Max retries",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "send_email", serviceMethodKey: "delivery_service.send_email_with_template" },
})(makePlaceholder("Send Email Node"))


registerComponent({
  type: "workflow-node",
  name: "notify_via_contact_preference",
  displayName: "Notify via Contact Preference",
  description:
    "Notifies a target customer via THEIR preferred channel (email or sms, per the customer's preferred_delivery_method). Raises on channels with no automated send path — never silently falls back to email. The reusable contact-preference primitive (3a.1).",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-base", "accent", "status-info", "radius-base", "text-body", "text-caption"],
  configurableProps: {
    customerBinding: {
      type: "string",
      default: "{customer.id}",
      displayLabel: "Target customer binding",
      required: true,
      bounds: { maxLength: 128 },
    },
    bodyBinding: {
      type: "string",
      default: "",
      displayLabel: "Message body binding",
      required: true,
      bounds: { maxLength: 512 },
    },
    subjectBinding: {
      type: "string",
      default: "",
      displayLabel: "Subject binding (email only)",
      bounds: { maxLength: 128 },
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "notify_via_contact_preference" },
})(makePlaceholder("Notify via Contact Preference Node"))


registerComponent({
  type: "workflow-node",
  name: "log_vault_item",
  displayName: "Log Vault Item",
  description:
    "Writes a VaultItem (audit trail, note, generated artifact) into the Vault from the workflow context.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-base", "accent", "radius-base", "text-body", "text-caption"],
  configurableProps: {
    itemType: {
      type: "string",
      default: "",
      displayLabel: "Vault item type",
      required: true,
      bounds: { maxLength: 48 },
    },
    titleBinding: {
      type: "string",
      default: "",
      displayLabel: "Title binding",
      bounds: { maxLength: 128 },
    },
    bodyBinding: {
      type: "string",
      default: "",
      displayLabel: "Body binding",
      bounds: { maxLength: 256 },
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "document"],
      displayLabel: "Node shape on canvas",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "log_vault_item", serviceMethodKey: null },
})(makePlaceholder("Log Vault Item Node"))


registerComponent({
  type: "workflow-node",
  name: "generate_document",
  displayName: "Generate Document",
  description:
    "Renders a document template to a stored artifact (PDF/HTML) bound to an entity, without delivering it.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-base", "accent", "radius-base", "text-body", "text-caption"],
  configurableProps: {
    templateKey: {
      type: "string",
      default: "",
      displayLabel: "Document template key",
      required: true,
      bounds: { maxLength: 96 },
    },
    outputFormat: {
      type: "enum",
      default: "pdf",
      bounds: ["pdf", "html"],
      displayLabel: "Output format",
    },
    entityBinding: {
      type: "string",
      default: "",
      displayLabel: "Entity binding",
      description: "Workflow variable resolving to the entity the document is generated for.",
      bounds: { maxLength: 128 },
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "document"],
      displayLabel: "Node shape on canvas",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "generate_document", serviceMethodKey: null },
})(makePlaceholder("Generate Document Node"))


registerComponent({
  type: "workflow-node",
  name: "call_service_method",
  displayName: "Call Service Method",
  description:
    "Invokes a whitelisted service-layer method via the engine's _SERVICE_METHOD_REGISTRY (Phase 8b pattern). The method key is operator-selected from the registry.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-accent", "accent", "accent-subtle", "radius-base", "text-body"],
  configurableProps: {
    serviceMethodKey: {
      type: "string",
      default: "",
      displayLabel: "Service method key",
      description: "Whitelisted '{agent}.{method}' key from _SERVICE_METHOD_REGISTRY.",
      required: true,
      bounds: { maxLength: 96 },
    },
    kwargsBinding: {
      type: "object",
      default: {},
      displayLabel: "Kwargs binding",
      description: "Maps workflow variables into the method's allowed kwargs.",
    },
    timeoutSeconds: {
      type: "number",
      default: 300,
      bounds: [10, 3600],
      displayLabel: "Timeout (seconds)",
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "hexagon"],
      displayLabel: "Node shape on canvas",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "call_service_method", serviceMethodKey: null },
})(makePlaceholder("Call Service Method Node"))


// ─── Focus invocations (2) ──────────────────────────────────────────

registerComponent({
  type: "workflow-node",
  name: "invoke_generation_focus",
  displayName: "Invoke Generation Focus",
  description:
    "Engine action_type that invokes a Generation Focus headless. The sole generation-focus canvas node (the redundant Phase-1 'generation-focus-invocation' twin was retired in focus-invocation reconciliation P2). Config: focus_id / op_id / kwargs (the runtime + bespoke-config shape).",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-accent", "accent", "accent-subtle", "radius-base", "text-body", "text-caption"],
  // Inline-params reconciliation P1 (2026-06-02): configurableProps now
  // declare the REAL keys the bespoke InvokeGenerationFocusConfig writes +
  // the backend `_handle_invoke_generation_focus` reads (focus_id / op_id /
  // kwargs) — replacing the stranded Phase-1 props (focusTemplateName /
  // inputBinding / reviewMode / timeoutSeconds, which nothing wrote or read).
  // focus_id is a HEADLESS_DISPATCH id (not a focus-template name); op_id's
  // options depend on focus_id + kwargs is a binding-row list, which is why
  // this type stays bespoke-edited (P3, gated on the editor shape, ungates it
  // from BESPOKE_NAMESPACE_TYPES).
  configurableProps: {
    focus_id: {
      type: "string",
      default: "",
      displayLabel: "Generation Focus id",
      description:
        "HEADLESS_DISPATCH focus id (e.g. burial_vault_personalization_studio). Authored via the bespoke InvokeGenerationFocusConfig.",
      required: true,
    },
    op_id: {
      type: "string",
      default: "",
      displayLabel: "Operation id",
      description:
        "Operation on the focus (e.g. extract_decedent_info); valid options depend on focus_id.",
    },
    kwargs: {
      type: "object",
      default: {},
      displayLabel: "Operation kwargs",
      description: "Source-binding rows passed to the dispatch callable.",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "invoke_generation_focus", serviceMethodKey: null },
})(makePlaceholder("Invoke Generation Focus Node"))


registerComponent({
  type: "workflow-node",
  name: "invoke_review_focus",
  displayName: "Invoke Review Focus",
  description:
    "Invokes a Review Focus, pausing the workflow until the review item reaches a terminal outcome; the outcome routes the outgoing edge.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-accent", "accent", "accent-subtle", "radius-base", "text-body"],
  // Inline-params reconciliation P1 (2026-06-02): configurableProps now
  // declare the REAL keys the bespoke InvokeReviewFocusConfig writes
  // (review_focus_id / input_data_binding / reviewer_role / decision_actions)
  // — replacing the stranded Phase-1 props (focusTemplateName / inputBinding /
  // routingMode / nodeShape). `review_focus_id` matches the backend handler;
  // `input_data_binding` is the {prefix.path} binding the editor authors —
  // the binding→resolved-`input_data` step is the DEFERRED #7 sub-divergence
  // (a future-runtime layer, not this rename). Still bespoke-edited (P3).
  configurableProps: {
    review_focus_id: {
      type: "string",
      default: "",
      displayLabel: "Review Focus id",
      required: true,
    },
    input_data_binding: {
      type: "string",
      default: "",
      displayLabel: "Input data binding",
      description:
        "A {prefix.path} binding the engine resolves to input_data at runtime (the binding→dict resolution is the deferred #7 concern).",
    },
    reviewer_role: {
      type: "enum",
      default: "",
      bounds: [
        "admin",
        "office",
        "fh_director",
        "production_manager",
        "production",
        "accountant",
        "support",
      ],
      displayLabel: "Reviewer role",
    },
    decision_actions: {
      type: "array",
      default: ["approve", "edit_and_approve", "reject"],
      displayLabel: "Decision actions",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "invoke_review_focus", serviceMethodKey: null },
})(makePlaceholder("Invoke Review Focus Node"))


// ─── Cross-tenant primitives (3) ────────────────────────────────────

registerComponent({
  type: "workflow-node",
  name: "cross_tenant_order",
  displayName: "Cross-Tenant Order",
  description:
    "Places an order against a connected tenant (e.g., FH → manufacturer). Routed through the cross-tenant connection substrate.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-accent", "accent", "radius-base", "text-body", "text-caption"],
  configurableProps: {
    targetTenantBinding: {
      type: "string",
      default: "",
      displayLabel: "Target tenant binding",
      description: "Workflow variable resolving to the connected tenant id.",
      required: true,
      bounds: { maxLength: 128 },
    },
    orderPayloadBinding: {
      type: "object",
      default: {},
      displayLabel: "Order payload binding",
    },
    acknowledgmentRequired: {
      type: "boolean",
      default: true,
      displayLabel: "Acknowledgment required",
      description: "Whether the workflow waits for a cross_tenant_acknowledgment before proceeding.",
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "hexagon"],
      displayLabel: "Node shape on canvas",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "cross_tenant_order", serviceMethodKey: null },
})(makePlaceholder("Cross-Tenant Order Node"))


registerComponent({
  type: "workflow-node",
  name: "cross_tenant_request",
  displayName: "Cross-Tenant Request",
  description:
    "Sends a typed request to a connected tenant (transfer, quote, info). The target tenant's workflow may produce an acknowledgment.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-accent", "accent", "radius-base", "text-body", "text-caption"],
  configurableProps: {
    targetTenantBinding: {
      type: "string",
      default: "",
      displayLabel: "Target tenant binding",
      required: true,
      bounds: { maxLength: 128 },
    },
    requestType: {
      type: "string",
      default: "",
      displayLabel: "Request type",
      required: true,
      bounds: { maxLength: 48 },
    },
    payloadBinding: {
      type: "object",
      default: {},
      displayLabel: "Payload binding",
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "hexagon"],
      displayLabel: "Node shape on canvas",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "cross_tenant_request", serviceMethodKey: null },
})(makePlaceholder("Cross-Tenant Request Node"))


registerComponent({
  type: "workflow-node",
  name: "cross_tenant_acknowledgment",
  displayName: "Cross-Tenant Acknowledgment",
  description:
    "Acknowledges a received cross-tenant order/request, closing the loop on the originating tenant's pending step.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-base", "accent", "status-success", "radius-base", "text-body"],
  configurableProps: {
    sourceRequestBinding: {
      type: "string",
      default: "",
      displayLabel: "Source request binding",
      description: "Workflow variable resolving to the originating request/order id.",
      required: true,
      bounds: { maxLength: 128 },
    },
    acknowledgmentStatus: {
      type: "enum",
      default: "accepted",
      bounds: ["accepted", "rejected", "deferred"],
      displayLabel: "Acknowledgment status",
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "pill"],
      displayLabel: "Node shape on canvas",
    },
    labelPosition: {
      type: "enum",
      default: "inside",
      bounds: ["inside", "above", "below"],
      displayLabel: "Label position",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "cross_tenant_acknowledgment", serviceMethodKey: null },
})(makePlaceholder("Cross-Tenant Acknowledgment Node"))


// ─── Composition primitives (6) ─────────────────────────────────────

registerComponent({
  type: "workflow-node",
  name: "decision",
  displayName: "Decision",
  description:
    "Multi-way branch. Evaluates ordered branch conditions; the first match selects the outgoing edge, falling through to the default branch.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-accent", "accent", "radius-base", "text-body", "text-caption"],
  configurableProps: {
    branches: {
      type: "array",
      default: [],
      displayLabel: "Branches",
      description: "Ordered (condition, edge-label) pairs evaluated top-down.",
      itemSchema: {
        type: "string",
        default: "",
        displayLabel: "Branch condition",
      },
    },
    defaultBranch: {
      type: "string",
      default: "",
      displayLabel: "Default branch label",
      bounds: { maxLength: 48 },
    },
    nodeShape: {
      type: "enum",
      default: "diamond",
      bounds: ["diamond", "rounded-rect"],
      displayLabel: "Node shape on canvas",
    },
    labelPosition: {
      type: "enum",
      default: "above",
      bounds: ["inside", "above", "below"],
      displayLabel: "Label position",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "decision", serviceMethodKey: null },
})(makePlaceholder("Decision Node"))


registerComponent({
  type: "workflow-node",
  name: "branch",
  displayName: "Branch",
  description:
    "Single conditional fork. Evaluates one expression; the truthy outcome takes the conditional edge.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-accent", "accent", "radius-base", "text-body"],
  configurableProps: {
    conditionExpression: {
      type: "string",
      default: "",
      displayLabel: "Condition expression",
      description: "Jinja expression selecting the conditional edge.",
      required: true,
      bounds: { maxLength: 256 },
    },
    nodeShape: {
      type: "enum",
      default: "diamond",
      bounds: ["diamond", "rounded-rect"],
      displayLabel: "Node shape on canvas",
    },
    labelPosition: {
      type: "enum",
      default: "above",
      bounds: ["inside", "above", "below"],
      displayLabel: "Label position",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "branch", serviceMethodKey: null },
})(makePlaceholder("Branch Node"))


registerComponent({
  type: "workflow-node",
  name: "parallel_split",
  displayName: "Parallel Split",
  description:
    "Fans out to multiple concurrent branches. All outgoing edges activate simultaneously; a parallel_join rejoins them.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-accent", "accent", "radius-base", "text-body"],
  configurableProps: {
    branchCount: {
      type: "number",
      default: 2,
      bounds: [2, 8],
      displayLabel: "Branch count",
      description: "Number of concurrent outgoing branches.",
    },
    waitForAll: {
      type: "boolean",
      default: true,
      displayLabel: "Wait for all",
      description: "Whether the matching join waits for every branch (vs first-N).",
    },
    nodeShape: {
      type: "enum",
      default: "bar",
      bounds: ["bar", "rounded-rect"],
      displayLabel: "Node shape on canvas",
    },
    labelPosition: {
      type: "enum",
      default: "above",
      bounds: ["inside", "above", "below"],
      displayLabel: "Label position",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "parallel_split", serviceMethodKey: null },
})(makePlaceholder("Parallel Split Node"))


registerComponent({
  type: "workflow-node",
  name: "parallel_join",
  displayName: "Parallel Join",
  description:
    "Rejoins concurrent branches from a parallel_split. The join policy determines when the workflow proceeds.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-accent", "accent", "radius-base", "text-body"],
  configurableProps: {
    joinPolicy: {
      type: "enum",
      default: "all",
      bounds: ["all", "any", "n-of-m"],
      displayLabel: "Join policy",
      description: "all = wait for every branch; any = first to finish; n-of-m = threshold.",
    },
    threshold: {
      type: "number",
      default: 1,
      bounds: [1, 8],
      displayLabel: "Threshold (n-of-m)",
      description: "Branches required to complete when joinPolicy = n-of-m.",
    },
    nodeShape: {
      type: "enum",
      default: "bar",
      bounds: ["bar", "rounded-rect"],
      displayLabel: "Node shape on canvas",
    },
    labelPosition: {
      type: "enum",
      default: "below",
      bounds: ["inside", "above", "below"],
      displayLabel: "Label position",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "parallel_join", serviceMethodKey: null },
})(makePlaceholder("Parallel Join Node"))


registerComponent({
  type: "workflow-node",
  name: "wait",
  displayName: "Wait",
  description:
    "Pauses the workflow for a duration, until an event, or until a task completes. The engine resumes the run when the wait condition clears.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-base", "accent", "status-warning", "radius-base", "text-body"],
  configurableProps: {
    waitMode: {
      type: "enum",
      default: "duration",
      bounds: ["duration", "until-event", "until-task"],
      displayLabel: "Wait mode",
    },
    durationSeconds: {
      type: "number",
      default: 3600,
      bounds: [1, 2592000],
      displayLabel: "Duration (seconds)",
      description: "Used when waitMode = duration.",
    },
    eventBinding: {
      type: "string",
      default: "",
      displayLabel: "Event / task binding",
      description: "Event name or task id binding for until-event / until-task modes.",
      bounds: { maxLength: 128 },
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "pill"],
      displayLabel: "Node shape on canvas",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "wait", serviceMethodKey: null },
})(makePlaceholder("Wait Node"))


registerComponent({
  type: "workflow-node",
  name: "schedule",
  displayName: "Schedule",
  description:
    "Time-based trigger marker for scheduled workflows (cron or delay). Authored on the canvas; the workflow_scheduler dispatches the run.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: ["surface-raised", "border-base", "accent", "radius-base", "text-body", "text-caption"],
  configurableProps: {
    scheduleMode: {
      type: "enum",
      default: "cron",
      bounds: ["cron", "delay"],
      displayLabel: "Schedule mode",
    },
    cronExpression: {
      type: "string",
      default: "0 0 * * *",
      displayLabel: "Cron expression",
      description: "Tenant-local cron when scheduleMode = cron.",
      bounds: { maxLength: 64 },
    },
    delaySeconds: {
      type: "number",
      default: 86400,
      bounds: [1, 31536000],
      displayLabel: "Delay (seconds)",
      description: "Used when scheduleMode = delay.",
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "pill"],
      displayLabel: "Node shape on canvas",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: { workflowStepType: "schedule", serviceMethodKey: null },
})(makePlaceholder("Schedule Node"))
