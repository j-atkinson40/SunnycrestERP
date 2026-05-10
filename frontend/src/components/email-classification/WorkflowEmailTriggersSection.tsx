/**
 * WorkflowEmailTriggersSection — R-6.1b.b Email triggers section for
 * the WorkflowBuilder canvas, mounted BELOW the canonical TriggerCardV2
 * + ABOVE the existing ParamsPanel/RunHistory blocks.
 *
 * Distinct from `Workflow.trigger_type` (which TriggerCardV2 owns):
 * email rules route inbound messages to this workflow at the email
 * classification cascade stage. They run BEFORE the trigger above. If
 * no email rule matches, cascade falls through to AI classification
 * (taxonomy + workflow registry).
 *
 * Composes:
 *   - Section header + inline copy explaining the distinction
 *   - Rule list (filtered to fire_action.workflow_id === workflowId)
 *     with edit + delete row actions
 *   - "+ Add rule" CTA opening TriggerConfigEditor pre-filled with
 *     workflow_id = currentWorkflow.id
 *   - Tier 3 enrollment toggle below the list
 *
 * The section is hidden in read-only mode (Tier 1 platform workflows
 * are locked) — no email rules can route to a platform workflow today
 * because rules are tenant-scoped and the picker filters out platform
 * verticals that don't match.
 */

import * as React from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { TriggerConfigEditor } from "@/components/email-classification/TriggerConfigEditor";
import {
  createRule,
  deleteRule,
  listRules,
  setTier3Enrollment,
  updateRule,
} from "@/services/email-classification-service";
import type {
  RuleCreatePayload,
  RuleUpdatePayload,
  TenantWorkflowEmailRule,
  WorkflowSummary,
} from "@/types/email-classification";

export interface WorkflowEmailTriggersSectionProps {
  workflowId: string;
  workflowName: string;
  /** Full workflow library (`/workflows/library/all`). Used by the
   *  TriggerConfigEditor + WorkflowPicker for the fire_action target. */
  workflows: WorkflowSummary[];
  tenantVertical: string | null;
  /** Initial Tier 3 enrollment state (looked up from workflow library
   *  by id). Defaults to false if not present. */
  initialTier3Enrolled: boolean;
  /** Hidden in read-only mode (Tier 1 / platform workflows). */
  readOnly?: boolean;
}

export function WorkflowEmailTriggersSection({
  workflowId,
  workflowName,
  workflows,
  tenantVertical,
  initialTier3Enrolled,
  readOnly,
}: WorkflowEmailTriggersSectionProps) {
  const [rules, setRules] = React.useState<TenantWorkflowEmailRule[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [editorOpen, setEditorOpen] = React.useState(false);
  const [editingRule, setEditingRule] =
    React.useState<TenantWorkflowEmailRule | null>(null);
  const [tier3Enrolled, setTier3EnrolledState] = React.useState(
    initialTier3Enrolled,
  );
  const [tier3Toggling, setTier3Toggling] = React.useState(false);

  // Re-sync Tier 3 if parent reloads with a fresh value.
  React.useEffect(() => {
    setTier3EnrolledState(initialTier3Enrolled);
  }, [initialTier3Enrolled]);

  const loadRules = React.useCallback(async () => {
    setLoading(true);
    try {
      const list = await listRules({ workflow_id: workflowId });
      setRules(list);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load rules";
      toast.error(msg);
      setRules([]);
    } finally {
      setLoading(false);
    }
  }, [workflowId]);

  React.useEffect(() => {
    void loadRules();
  }, [loadRules]);

  function openCreate() {
    setEditingRule(null);
    setEditorOpen(true);
  }

  function openEdit(rule: TenantWorkflowEmailRule) {
    setEditingRule(rule);
    setEditorOpen(true);
  }

  async function handleSave(
    payload: RuleCreatePayload | RuleUpdatePayload,
  ) {
    if (editingRule) {
      await updateRule(editingRule.id, payload as RuleUpdatePayload);
      toast.success(`Updated "${editingRule.name}"`);
    } else {
      // Force fire_action.workflow_id to this workflow on create
      // (TriggerConfigEditor allows any workflow in the picker; we
      // pin it here so the rule lands on this workflow).
      const pinned: RuleCreatePayload = {
        ...(payload as RuleCreatePayload),
        fire_action: { workflow_id: workflowId },
      };
      const created = await createRule(pinned);
      toast.success(`Created "${created.name}"`);
    }
    await loadRules();
  }

  async function handleDelete(rule: TenantWorkflowEmailRule) {
    if (
      !window.confirm(
        `Delete trigger "${rule.name}"? It will be deactivated.`,
      )
    ) {
      return;
    }
    try {
      await deleteRule(rule.id);
      toast.success(`Deleted "${rule.name}"`);
      await loadRules();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Delete failed";
      toast.error(msg);
    }
  }

  async function handleTier3Toggle(next: boolean) {
    setTier3Toggling(true);
    setTier3EnrolledState(next); // optimistic
    try {
      await setTier3Enrollment(workflowId, next);
      toast.success(
        next
          ? "Enrolled in AI registry selection"
          : "Removed from AI registry selection",
      );
    } catch (err) {
      // Revert on failure.
      setTier3EnrolledState(!next);
      const msg =
        err instanceof Error ? err.message : "Failed to update enrollment";
      toast.error(msg);
    } finally {
      setTier3Toggling(false);
    }
  }

  // Pre-pin the fire_action workflow_id when the editor opens to author a new
  // rule, so the picker pre-selects this workflow.
  const initialDraft = React.useMemo(
    () =>
      editingRule === null
        ? { fire_action: { workflow_id: workflowId } }
        : undefined,
    [editingRule, workflowId],
  );

  return (
    <Card
      className="p-4 space-y-3"
      data-testid="workflow-email-triggers-section"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-content-strong">
            Email triggers
          </h3>
          <p className="text-caption text-content-muted">
            Email triggers route inbound messages to this workflow.
            They run BEFORE the trigger above. If no email rule
            matches, cascade falls through to AI classification
            (taxonomy + workflow registry).
          </p>
        </div>
        {!readOnly ? (
          <Button
            size="sm"
            onClick={openCreate}
            data-testid="workflow-email-triggers-add"
          >
            <Plus className="h-3.5 w-3.5 mr-1" />
            Add rule
          </Button>
        ) : null}
      </div>

      {loading ? (
        <p className="text-caption text-content-muted">Loading rules…</p>
      ) : rules.length === 0 ? (
        <p
          className="text-caption text-content-muted"
          data-testid="workflow-email-triggers-empty"
        >
          No email rules route to this workflow yet.
        </p>
      ) : (
        <ul
          className="space-y-1.5"
          data-testid="workflow-email-triggers-list"
        >
          {rules.map((r) => (
            <li
              key={r.id}
              className="flex items-center gap-2 rounded-md border border-border-subtle bg-surface-elevated px-3 py-2"
              data-testid={`workflow-email-triggers-row-${r.id}`}
            >
              <button
                type="button"
                onClick={() => !readOnly && openEdit(r)}
                disabled={readOnly}
                className="flex-1 min-w-0 text-left disabled:cursor-default"
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-content-strong truncate">
                    {r.name}
                  </span>
                  {r.is_active ? null : (
                    <Badge variant="outline">Inactive</Badge>
                  )}
                  <Badge variant="outline" className="font-plex-mono text-caption">
                    p{r.priority}
                  </Badge>
                </div>
              </button>
              {!readOnly ? (
                <div className="flex items-center gap-1">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => openEdit(r)}
                    aria-label={`Edit ${r.name}`}
                    data-testid={`workflow-email-triggers-edit-${r.id}`}
                  >
                    <Pencil className="h-3 w-3" />
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleDelete(r)}
                    aria-label={`Delete ${r.name}`}
                    data-testid={`workflow-email-triggers-delete-${r.id}`}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {/* Tier 3 enrollment toggle */}
      <div
        className="flex items-start gap-3 rounded-md border border-border-subtle bg-surface-sunken p-3"
        data-testid="workflow-email-triggers-tier3"
      >
        <Switch
          id={`tier3-toggle-${workflowId}`}
          checked={tier3Enrolled}
          onCheckedChange={handleTier3Toggle}
          disabled={readOnly || tier3Toggling}
          data-testid="workflow-email-triggers-tier3-switch"
        />
        <label
          htmlFor={`tier3-toggle-${workflowId}`}
          className="flex-1 min-w-0 cursor-pointer text-sm"
        >
          <div className="font-medium text-content-strong">
            Enable AI registry selection
          </div>
          <p className="text-caption text-content-muted">
            When email classification can&apos;t match a rule or
            category, AI may select this workflow based on its
            description. Default: off. Make sure your workflow&apos;s
            description above describes when this workflow should fire
            — Claude reads it.
          </p>
        </label>
      </div>

      <TriggerConfigEditor
        open={editorOpen}
        onOpenChange={setEditorOpen}
        rule={editingRule}
        workflows={workflows}
        tenantVertical={tenantVertical}
        initialDraft={initialDraft}
        onSave={handleSave}
      />

      {/* Hidden but DOM-rendered name marker so tests can verify
          the section recognized which workflow it's mounted under. */}
      <span className="sr-only" data-testid="workflow-email-triggers-name">
        {workflowName}
      </span>
    </Card>
  );
}
