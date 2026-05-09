/**
 * EmailClassificationTriggersTab — Tier 1 rule library.
 *
 * Composes:
 *   - Aggregate Tier 3 enrollment summary card (read-only diagnostic;
 *     edit lives at WorkflowBuilder per investigation §4 — R-6.1b.b
 *     wires that path).
 *   - "New trigger" CTA → opens TriggerConfigEditor in create mode.
 *   - RulesTable with edit + delete row actions.
 *   - Edit / delete confirm modals.
 */

import * as React from "react";
import { Plus, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { TriggerConfigEditor } from "@/components/email-classification/TriggerConfigEditor";
import { RulesTable } from "@/components/email-classification/RulesTable";
import * as svc from "@/services/email-classification-service";
import type {
  RuleCreatePayload,
  RuleUpdatePayload,
  TenantWorkflowEmailRule,
  WorkflowSummary,
} from "@/types/email-classification";

export interface EmailClassificationTriggersTabProps {
  rules: TenantWorkflowEmailRule[];
  workflows: WorkflowSummary[];
  tenantVertical: string | null;
  loading: boolean;
  onReload: () => Promise<void>;
}

export function EmailClassificationTriggersTab({
  rules,
  workflows,
  tenantVertical,
  loading,
  onReload,
}: EmailClassificationTriggersTabProps) {
  const [editorOpen, setEditorOpen] = React.useState(false);
  const [editingRule, setEditingRule] =
    React.useState<TenantWorkflowEmailRule | null>(null);
  const [deletingRule, setDeletingRule] =
    React.useState<TenantWorkflowEmailRule | null>(null);
  const [deleting, setDeleting] = React.useState(false);

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
      await svc.updateRule(editingRule.id, payload as RuleUpdatePayload);
      toast.success(`Updated "${editingRule.name}"`);
    } else {
      const created = await svc.createRule(payload as RuleCreatePayload);
      toast.success(`Created "${created.name}"`);
    }
    await onReload();
  }

  async function confirmDelete() {
    if (!deletingRule) return;
    setDeleting(true);
    try {
      await svc.deleteRule(deletingRule.id);
      toast.success(`Deleted "${deletingRule.name}"`);
      setDeletingRule(null);
      await onReload();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Delete failed";
      toast.error(msg);
    } finally {
      setDeleting(false);
    }
  }

  const tier3Count = workflows.filter((w) => w.tier3_enrolled).length;

  return (
    <div className="space-y-6">
      {/* Tier 3 summary card */}
      <Card data-testid="tier3-enrollment-summary">
        <CardContent className="flex items-start gap-4 pt-6">
          <div className="rounded-md bg-accent-muted p-2 text-content-on-accent">
            <Sparkles className="h-5 w-5" />
          </div>
          <div className="flex-1">
            <p className="text-body font-medium text-content-strong">
              {tier3Count}{" "}
              {tier3Count === 1 ? "workflow" : "workflows"} enrolled in
              AI registry selection
            </p>
            <p className="text-body-sm text-content-muted">
              When email classification can&apos;t match a rule or
              category, AI may select an enrolled workflow based on its
              description. Toggle enrollment per-workflow at{" "}
              <span className="font-plex-mono text-caption">
                /settings/workflows/&lt;id&gt;/edit
              </span>
              .
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Header + Add CTA */}
      <div className="flex items-center justify-between">
        <h2 className="text-h4 font-medium text-content-strong">
          Email triggers
        </h2>
        <Button
          onClick={openCreate}
          disabled={loading}
          data-testid="email-classification-new-trigger"
        >
          <Plus className="h-4 w-4 mr-1.5" />
          New trigger
        </Button>
      </div>

      <RulesTable
        rules={rules}
        workflows={workflows}
        loading={loading}
        onEdit={openEdit}
        onDelete={(rule) => setDeletingRule(rule)}
      />

      <TriggerConfigEditor
        open={editorOpen}
        onOpenChange={setEditorOpen}
        rule={editingRule}
        workflows={workflows}
        tenantVertical={tenantVertical}
        onSave={handleSave}
      />

      <Dialog
        open={deletingRule !== null}
        onOpenChange={(o) => !o && setDeletingRule(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete trigger?</DialogTitle>
            <DialogDescription>
              {deletingRule
                ? `"${deletingRule.name}" will be deactivated. Future incoming emails will not match this rule.`
                : null}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeletingRule(null)}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={confirmDelete}
              disabled={deleting}
              data-testid="email-classification-confirm-delete-rule"
            >
              {deleting ? "Deleting…" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
