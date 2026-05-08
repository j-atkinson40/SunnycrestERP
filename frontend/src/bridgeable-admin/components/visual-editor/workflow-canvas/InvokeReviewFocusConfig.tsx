/**
 * InvokeReviewFocusConfig — R-6.0b workflow editor inspector pane.
 *
 * Renders inside WorkflowEditorPage's right-rail when the selected
 * canvas node has `type === "invoke_review_focus"`. Mirrors the shape
 * the backend `_handle_invoke_review_focus` consumes:
 *
 *   {
 *     review_focus_id: "decedent_info_review",
 *     input_data:      { ... }           # binding-resolved payload
 *   }
 *
 * `input_data` is authored as a single source-binding (typically
 * `workflow_input.line_items` referring to the prior
 * `invoke_generation_focus` step's output). The input binding produces
 * a `{<prefix>.<path>}` template string the engine resolves at
 * execution time via `resolve_variables`.
 *
 * `reviewer_role` and `decision_actions` are AUTHORING-LAYER hints —
 * the canonical TriageQueueConfig (workflow_review_triage) governs
 * runtime decision actions + reviewer routing in R-6.0. These fields
 * round-trip through `config` so future R-6.x phases (multi-reviewer
 * routing, per-step decision-action overrides) can adopt them without
 * a config-shape migration.
 */

import { useState } from "react"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"


// ── Catalogs ────────────────────────────────────────────────────────


/** Reviewer role catalog. Matches role slugs commonly present in
 *  tenants today. R-6.x replaces with a tenant-scoped role lookup. */
export const REVIEWER_ROLES = [
  { value: "admin", display: "Admin" },
  { value: "office", display: "Office" },
  { value: "fh_director", display: "Funeral home director" },
  { value: "production_manager", display: "Production manager" },
  { value: "production", display: "Production" },
  { value: "accountant", display: "Accountant" },
  { value: "support", display: "Support" },
] as const


/** Source-prefix vocabulary for input_data binding. Subset of the
 *  Generation Focus catalog — review focuses typically read prior step
 *  output, not raw trigger context. Full vocabulary still permitted. */
export const REVIEW_INPUT_SOURCE_TYPES = [
  { value: "workflow_input", display: "workflow_input.X" },
  { value: "current_record", display: "current_record.X" },
  { value: "incoming_email", display: "incoming_email.X" },
  { value: "incoming_transcription", display: "incoming_transcription.X" },
  { value: "vault_item", display: "vault_item.X" },
] as const


type ReviewSourceType = (typeof REVIEW_INPUT_SOURCE_TYPES)[number]["value"]


/** Decision action catalog. Matches `workflow_review_triage` queue's
 *  action_palette. R-6.0 ships all three by default. */
export const DECISION_ACTIONS = [
  { id: "approve", display: "Approve" },
  { id: "edit_and_approve", display: "Edit & Approve" },
  { id: "reject", display: "Reject" },
] as const


// ── Input data binding helpers ──────────────────────────────────────


interface ParsedInputBinding {
  source_type: ReviewSourceType
  path: string
}


function parseInputBinding(value: unknown): ParsedInputBinding {
  if (typeof value === "string") {
    const m = value.match(/^\{([a-z_]+)\.(.+)\}$/)
    if (m) {
      const prefix = m[1] as ReviewSourceType
      if (REVIEW_INPUT_SOURCE_TYPES.some((t) => t.value === prefix)) {
        return { source_type: prefix, path: m[2] }
      }
    }
  }
  return { source_type: "workflow_input", path: "line_items" }
}


function inputBindingToTemplate(binding: ParsedInputBinding): string {
  return `{${binding.source_type}.${binding.path.trim() || "line_items"}}`
}


// ── Component ───────────────────────────────────────────────────────


export interface InvokeReviewFocusConfigProps {
  config: Record<string, unknown>
  onChange: (next: Record<string, unknown>) => void
}


export function InvokeReviewFocusConfig({
  config,
  onChange,
}: InvokeReviewFocusConfigProps) {
  const review_focus_id =
    typeof config.review_focus_id === "string" ? config.review_focus_id : ""
  const reviewer_role =
    typeof config.reviewer_role === "string" ? config.reviewer_role : ""
  const decision_actions: string[] = Array.isArray(config.decision_actions)
    ? (config.decision_actions as string[])
    : DECISION_ACTIONS.map((a) => a.id)

  // R-6.0a backend stores the resolved value at exec time — but during
  // authoring we represent input_data via a string template binding.
  const inputBindingRaw =
    typeof config.input_data_binding === "string"
      ? config.input_data_binding
      : null
  const [parsedBinding, setParsedBinding] = useState<ParsedInputBinding>(() =>
    parseInputBinding(inputBindingRaw),
  )

  const handleReviewFocusIdChange = (value: string) => {
    onChange({ ...config, review_focus_id: value })
  }

  const handleReviewerRoleChange = (value: string | null) => {
    onChange({ ...config, reviewer_role: value ?? "" })
  }

  const handleBindingChange = (next: Partial<ParsedInputBinding>) => {
    const merged = { ...parsedBinding, ...next }
    setParsedBinding(merged)
    const template = inputBindingToTemplate(merged)
    // Persist both the raw template (for legacy consumers) AND the
    // canonical input_data preview shape — at workflow execution time
    // the engine substitutes `input_data` from the resolved template.
    onChange({
      ...config,
      input_data_binding: template,
    })
  }

  const handleDecisionToggle = (actionId: string) => {
    const set = new Set(decision_actions)
    if (set.has(actionId)) {
      set.delete(actionId)
    } else {
      set.add(actionId)
    }
    const ordered = DECISION_ACTIONS.map((a) => a.id).filter((id) =>
      set.has(id),
    )
    onChange({ ...config, decision_actions: ordered })
  }

  return (
    <div
      className="flex flex-col gap-3"
      data-testid="wf-invoke-review-focus-config"
    >
      <div>
        <Label
          htmlFor="wf-invoke-review-focus-slug"
          className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted"
        >
          Review focus id
        </Label>
        <Input
          id="wf-invoke-review-focus-slug"
          value={review_focus_id}
          onChange={(e) => handleReviewFocusIdChange(e.target.value)}
          placeholder="e.g. decedent_info_review"
          data-testid="wf-invoke-review-focus-slug"
          className="font-plex-mono text-caption"
        />
        <p className="mt-1 text-caption text-content-muted">
          Slug surfaces in the workflow_review_triage queue header.
        </p>
      </div>

      <div>
        <Label className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted">
          Reviewer role
        </Label>
        <Select
          value={reviewer_role || undefined}
          onValueChange={handleReviewerRoleChange}
        >
          <SelectTrigger
            data-testid="wf-invoke-review-focus-reviewer-role"
            className="text-caption"
          >
            <SelectValue placeholder="Select reviewer role" />
          </SelectTrigger>
          <SelectContent>
            {REVIEWER_ROLES.map((role) => (
              <SelectItem key={role.value} value={role.value}>
                {role.display}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="mt-1 text-caption text-content-muted">
          R-6.0 routes to first active user with this role; multi-reviewer
          routing lands in R-6.x.
        </p>
      </div>

      <div>
        <Label className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted">
          Input binding
        </Label>
        <div className="flex items-center gap-1.5">
          <Select
            value={parsedBinding.source_type}
            onValueChange={(v) => {
              if (v) {
                handleBindingChange({ source_type: v as ReviewSourceType })
              }
            }}
          >
            <SelectTrigger
              className="h-9 w-44 text-caption"
              data-testid="wf-invoke-review-focus-input-source"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {REVIEW_INPUT_SOURCE_TYPES.map((t) => (
                <SelectItem key={t.value} value={t.value}>
                  {t.display}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            value={parsedBinding.path}
            onChange={(e) => handleBindingChange({ path: e.target.value })}
            placeholder="line_items"
            className="h-9 flex-1 font-plex-mono text-caption"
            data-testid="wf-invoke-review-focus-input-path"
          />
        </div>
      </div>

      <div>
        <Label className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted">
          Decision actions
        </Label>
        <div className="flex flex-col gap-1.5">
          {DECISION_ACTIONS.map((action) => {
            const checked = decision_actions.includes(action.id)
            return (
              <label
                key={action.id}
                className="flex items-center gap-2 text-caption"
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => handleDecisionToggle(action.id)}
                  data-testid={`wf-invoke-review-focus-decision-${action.id}`}
                />
                <span className="text-content-base">{action.display}</span>
              </label>
            )
          })}
        </div>
        <p className="mt-1 text-caption text-content-muted">
          R-6.0 runtime: workflow_review_triage queue applies all three;
          per-step overrides land in R-6.x.
        </p>
      </div>
    </div>
  )
}
