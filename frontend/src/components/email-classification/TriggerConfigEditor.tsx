/**
 * TriggerConfigEditor — modal form for creating + editing
 * `tenant_workflow_email_rules` rows.
 *
 * Investigation §3 locked the surface as a modal everywhere — three
 * callers (admin Triggers tab, WorkflowBuilder Triggers section in
 * R-6.1b.b, EmailUnclassifiedItemDisplay's "Author rule from email"
 * wizard in R-6.1b.b) compose it identically. R-6.1b.a wires only the
 * admin Triggers tab caller.
 *
 * Form sections:
 *   1. Identity     — name + priority + is_active
 *   2. Match conditions — composable operator stack (OR within / AND
 *      between operators) via MatchConditionsEditor.
 *   3. Fire action  — workflow picker OR suppression mode (toggle
 *      reveals suppression_reason).
 *
 * Validation gates Save:
 *   - Name non-empty
 *   - Priority integer 1-9999
 *   - At least one operator with at least one value
 *   - Either fire_action.workflow_id valid OR (workflow_id=null AND
 *     non-empty suppression_reason)
 */

import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Alert } from "@/components/ui/alert";
import { MatchConditionsEditor } from "./MatchConditionsEditor";
import { WorkflowPicker } from "./WorkflowPicker";
import type {
  MatchConditions,
  RuleCreatePayload,
  RuleUpdatePayload,
  TenantWorkflowEmailRule,
  WorkflowSummary,
} from "@/types/email-classification";

export interface TriggerConfigEditorProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** null = create mode; populated = edit mode. */
  rule: TenantWorkflowEmailRule | null;
  workflows: WorkflowSummary[];
  tenantVertical?: string | null;
  /** When set, pre-populates a new rule (Author Rule From Email path). */
  initialDraft?: Partial<RuleCreatePayload>;
  onSave: (payload: RuleCreatePayload | RuleUpdatePayload) => Promise<void>;
}

interface DraftState {
  name: string;
  priority: number;
  is_active: boolean;
  match_conditions: MatchConditions;
  /** Suppress mode toggle. When true, fire_action.workflow_id is null
   *  and suppression_reason becomes required. */
  suppress: boolean;
  fire_workflow_id: string | null;
  suppression_reason: string;
}

const PRIORITY_MIN = 1;
const PRIORITY_MAX = 9999;
const PRIORITY_DEFAULT = 100;

function fromRule(rule: TenantWorkflowEmailRule | null, initial?: Partial<RuleCreatePayload>): DraftState {
  if (rule) {
    const wfId =
      typeof rule.fire_action.workflow_id === "string"
        ? rule.fire_action.workflow_id
        : null;
    const supReason = rule.fire_action.suppression_reason ?? "";
    return {
      name: rule.name,
      priority: rule.priority,
      is_active: rule.is_active,
      match_conditions: { ...(rule.match_conditions ?? {}) },
      suppress: wfId === null,
      fire_workflow_id: wfId,
      suppression_reason: supReason,
    };
  }
  const init = initial ?? {};
  return {
    name: init.name ?? "",
    priority: init.priority ?? PRIORITY_DEFAULT,
    is_active: init.is_active ?? true,
    match_conditions: { ...(init.match_conditions ?? {}) },
    suppress: init.fire_action?.workflow_id === null,
    fire_workflow_id: init.fire_action?.workflow_id ?? null,
    suppression_reason: init.fire_action?.suppression_reason ?? "",
  };
}

interface ValidationResult {
  ok: boolean;
  errors: string[];
}

function _validate(
  d: DraftState,
  workflows: WorkflowSummary[],
): ValidationResult {
  const errs: string[] = [];
  if (d.name.trim().length === 0) errs.push("Name is required.");
  if (
    !Number.isInteger(d.priority) ||
    d.priority < PRIORITY_MIN ||
    d.priority > PRIORITY_MAX
  ) {
    errs.push(`Priority must be an integer between ${PRIORITY_MIN} and ${PRIORITY_MAX}.`);
  }
  const operatorsWithValues = Object.entries(d.match_conditions).filter(
    ([, vals]) => Array.isArray(vals) && vals.length > 0,
  );
  if (operatorsWithValues.length === 0) {
    errs.push("Add at least one match condition with at least one value.");
  }
  if (d.suppress) {
    if (d.suppression_reason.trim().length === 0) {
      errs.push("Suppression reason is required.");
    }
  } else {
    if (!d.fire_workflow_id) {
      errs.push("Pick a workflow OR turn on Suppress.");
    } else {
      const wf = workflows.find((w) => w.id === d.fire_workflow_id);
      if (!wf) errs.push("Selected workflow no longer available.");
    }
  }
  return { ok: errs.length === 0, errors: errs };
}

function _toPayload(d: DraftState): RuleCreatePayload {
  // Drop empty operators before save (defense-in-depth — validation
  // already requires ≥1, but a user could leave a stray empty list).
  const cleaned: MatchConditions = {};
  for (const [k, v] of Object.entries(d.match_conditions)) {
    if (Array.isArray(v) && v.length > 0) {
      cleaned[k as keyof MatchConditions] = v;
    }
  }
  return {
    name: d.name.trim(),
    priority: d.priority,
    is_active: d.is_active,
    match_conditions: cleaned,
    fire_action: d.suppress
      ? {
          workflow_id: null,
          suppression_reason: d.suppression_reason.trim(),
        }
      : { workflow_id: d.fire_workflow_id! },
  };
}

export function TriggerConfigEditor({
  open,
  onOpenChange,
  rule,
  workflows,
  tenantVertical,
  initialDraft,
  onSave,
}: TriggerConfigEditorProps) {
  const [draft, setDraft] = React.useState<DraftState>(() =>
    fromRule(rule, initialDraft),
  );
  const [saving, setSaving] = React.useState(false);
  const [serverError, setServerError] = React.useState<string | null>(null);
  const [touched, setTouched] = React.useState(false);

  // Reset draft when the editor opens or the editing rule changes.
  React.useEffect(() => {
    if (open) {
      setDraft(fromRule(rule, initialDraft));
      setSaving(false);
      setServerError(null);
      setTouched(false);
    }
  }, [open, rule, initialDraft]);

  const validation = React.useMemo(
    () => _validate(draft, workflows),
    [draft, workflows],
  );

  function update<K extends keyof DraftState>(key: K, value: DraftState[K]) {
    setDraft((prev) => ({ ...prev, [key]: value }));
    setTouched(true);
  }

  async function handleSave() {
    setTouched(true);
    if (!validation.ok) return;
    setSaving(true);
    setServerError(null);
    try {
      await onSave(_toPayload(draft));
      onOpenChange(false);
    } catch (err) {
      const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string };
      const detail = axiosErr.response?.data?.detail;
      setServerError(
        (typeof detail === "string" && detail) ||
          axiosErr.message ||
          "Save failed",
      );
    } finally {
      setSaving(false);
    }
  }

  const showErrors = touched && !validation.ok;
  const isEdit = rule !== null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "Edit email trigger" : "New email trigger"}
          </DialogTitle>
          <DialogDescription>
            Email triggers route incoming messages to a workflow before
            AI classification runs. Lower priority numbers fire first.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Identity */}
          <section className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="trigger-name">Name</Label>
              <Input
                id="trigger-name"
                value={draft.name}
                onChange={(e) => update("name", e.target.value)}
                disabled={saving}
                placeholder="e.g., Hopkins FH service-day requests"
                data-testid="trigger-name-input"
                aria-invalid={showErrors && draft.name.trim() === ""}
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
              <div className="space-y-1.5">
                <Label htmlFor="trigger-priority">Priority</Label>
                <Input
                  id="trigger-priority"
                  type="number"
                  min={PRIORITY_MIN}
                  max={PRIORITY_MAX}
                  step={1}
                  value={draft.priority}
                  onChange={(e) =>
                    update("priority", Number.parseInt(e.target.value, 10) || 0)
                  }
                  disabled={saving}
                  data-testid="trigger-priority-input"
                />
                <p className="text-caption text-content-muted">
                  Lower fires first. Default 100.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  checked={draft.is_active}
                  onCheckedChange={(v) => update("is_active", Boolean(v))}
                  disabled={saving}
                  id="trigger-is-active"
                  data-testid="trigger-is-active-switch"
                />
                <Label htmlFor="trigger-is-active">Active</Label>
              </div>
            </div>
          </section>

          {/* Match conditions */}
          <section className="space-y-2">
            <h3 className="text-body-sm font-medium text-content-strong">
              Match conditions
            </h3>
            <MatchConditionsEditor
              conditions={draft.match_conditions}
              onChange={(v) => update("match_conditions", v)}
              disabled={saving}
            />
          </section>

          {/* Fire action */}
          <section className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-body-sm font-medium text-content-strong">
                  When this rule matches…
                </h3>
                <p className="text-caption text-content-muted">
                  Fire a workflow OR suppress (drop the message without
                  surfacing it for triage).
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  checked={draft.suppress}
                  onCheckedChange={(v) => update("suppress", Boolean(v))}
                  disabled={saving}
                  id="trigger-suppress-switch"
                  data-testid="trigger-suppress-switch"
                />
                <Label htmlFor="trigger-suppress-switch">Suppress</Label>
              </div>
            </div>

            {draft.suppress ? (
              <div className="space-y-1.5">
                <Label htmlFor="trigger-suppression-reason">
                  Suppression reason
                </Label>
                <Textarea
                  id="trigger-suppression-reason"
                  value={draft.suppression_reason}
                  onChange={(e) =>
                    update("suppression_reason", e.target.value)
                  }
                  disabled={saving}
                  placeholder="e.g., Recurring vendor newsletter — known noise."
                  data-testid="trigger-suppression-reason"
                />
              </div>
            ) : (
              <div className="space-y-1.5">
                <Label>Workflow</Label>
                <WorkflowPicker
                  workflows={workflows}
                  value={draft.fire_workflow_id}
                  onChange={(id) => update("fire_workflow_id", id)}
                  tenantVertical={tenantVertical}
                  data-testid="trigger-workflow-picker"
                />
              </div>
            )}
          </section>

          {/* Validation surface */}
          {showErrors ? (
            <Alert variant="warning" data-testid="trigger-validation-alert">
              <ul className="list-disc pl-5">
                {validation.errors.map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            </Alert>
          ) : null}

          {serverError ? (
            <Alert variant="error" data-testid="trigger-server-error">
              {serverError}
            </Alert>
          ) : null}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={saving}
            data-testid="trigger-cancel"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving || (touched && !validation.ok)}
            data-testid="trigger-save"
          >
            {saving ? "Saving…" : isEdit ? "Save changes" : "Create rule"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
