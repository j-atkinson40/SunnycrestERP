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


registerComponent({
  type: "workflow-node",
  name: "generation-focus-invocation",
  displayName: "Generation Focus Invocation",
  description:
    "Workflow step that invokes a Generation Focus in headless mode. Input: extraction context + target entity. Output: drafted vault item routed to the Focus's review queue.",
  category: "workflow-nodes",
  verticals: ["all"],
  userParadigms: ["operator-power-user"],
  consumedTokens: [
    "surface-raised",
    "surface-elevated",
    "border-base",
    "border-accent",
    "accent",
    "accent-subtle",
    "radius-base",
    "shadow-level-2",
    "text-body",
    "text-caption",
  ],
  configurableProps: {
    focusTemplateName: {
      type: "componentReference",
      default: "arrangement-scribe",
      componentTypes: ["focus-template"],
      displayLabel: "Generation Focus template",
      description:
        "Which Generation Focus template to invoke. Editor picker filtered to focus-template entries with extensions.focusType === 'generation'.",
      required: true,
    },
    inputBinding: {
      type: "object",
      default: {},
      displayLabel: "Input binding",
      description:
        "Map workflow variables ({input.*}, {output.*}) into the Focus's extraction context.",
    },
    reviewMode: {
      type: "enum",
      default: "review-by-default",
      bounds: ["review-by-default", "auto-commit-on-high-confidence"],
      displayLabel: "Review mode",
      description:
        "Review-by-default queues the output for human review. Auto-commit (deferred to 2028+ per arc canon) requires per-tenant configurability + audit transparency.",
    },
    nodeShape: {
      type: "enum",
      default: "rounded-rect",
      bounds: ["rounded-rect", "diamond", "hexagon"],
      displayLabel: "Node shape on canvas",
      description: "Visual shape used when this node renders in workflow builder.",
    },
    labelPosition: {
      type: "enum",
      default: "inside",
      bounds: ["inside", "above", "below"],
      displayLabel: "Label position",
    },
    successIndicatorStyle: {
      type: "enum",
      default: "checkmark-badge",
      bounds: ["checkmark-badge", "color-fill", "border-glow"],
      displayLabel: "Success indicator style",
    },
    failureIndicatorStyle: {
      type: "enum",
      default: "warning-badge",
      bounds: ["warning-badge", "color-fill", "border-glow"],
      displayLabel: "Failure indicator style",
    },
    timeoutSeconds: {
      type: "number",
      default: 600,
      bounds: [30, 7200],
      displayLabel: "Timeout (seconds)",
      description:
        "Max time the headless generation can run before the workflow marks the step failed.",
    },
  },
  schemaVersion: 1,
  componentVersion: 2,
  extensions: {
    workflowStepType: "invoke_generation_focus",
    serviceMethodKey: null,
  },
})(makePlaceholder("Generation Focus Invocation Node"))


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
