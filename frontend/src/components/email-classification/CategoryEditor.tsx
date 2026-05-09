/**
 * CategoryEditor — modal form for `tenant_workflow_email_categories`
 * (UI vocabulary "categories"; URL surface `/taxonomy/nodes/*`).
 *
 * Investigation §4 locked v1 ships flat (no parent_id tree authoring).
 * The schema's parent_id self-FK is preserved for R-6.x nested-category
 * UX; v1 only allows top-level categories.
 *
 * Fields:
 *   - label (required, unique within tenant)
 *   - description (load-bearing for AI Tier 2 classification — guides
 *     Claude when it categorizes emails)
 *   - mapped_workflow_id (optional; null means "Don't auto-route")
 *   - is_active (toggle)
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
import { WorkflowPicker } from "./WorkflowPicker";
import type {
  CategoryCreatePayload,
  CategoryUpdatePayload,
  TenantWorkflowEmailCategory,
  WorkflowSummary,
} from "@/types/email-classification";

export interface CategoryEditorProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** null = create mode; populated = edit mode. */
  category: TenantWorkflowEmailCategory | null;
  workflows: WorkflowSummary[];
  tenantVertical?: string | null;
  onSave: (
    payload: CategoryCreatePayload | CategoryUpdatePayload,
  ) => Promise<void>;
}

interface DraftState {
  label: string;
  description: string;
  mapped_workflow_id: string | null;
  is_active: boolean;
}

function fromCategory(c: TenantWorkflowEmailCategory | null): DraftState {
  if (c) {
    return {
      label: c.label,
      description: c.description ?? "",
      mapped_workflow_id: c.mapped_workflow_id,
      is_active: c.is_active,
    };
  }
  return {
    label: "",
    description: "",
    mapped_workflow_id: null,
    is_active: true,
  };
}

export function CategoryEditor({
  open,
  onOpenChange,
  category,
  workflows,
  tenantVertical,
  onSave,
}: CategoryEditorProps) {
  const [draft, setDraft] = React.useState<DraftState>(() =>
    fromCategory(category),
  );
  const [saving, setSaving] = React.useState(false);
  const [serverError, setServerError] = React.useState<string | null>(null);
  const [touched, setTouched] = React.useState(false);

  React.useEffect(() => {
    if (open) {
      setDraft(fromCategory(category));
      setSaving(false);
      setServerError(null);
      setTouched(false);
    }
  }, [open, category]);

  const isEdit = category !== null;
  const labelEmpty = draft.label.trim().length === 0;
  const validationError = touched && labelEmpty ? "Label is required." : null;

  function update<K extends keyof DraftState>(key: K, value: DraftState[K]) {
    setDraft((prev) => ({ ...prev, [key]: value }));
    setTouched(true);
  }

  async function handleSave() {
    setTouched(true);
    if (labelEmpty) return;
    setSaving(true);
    setServerError(null);
    try {
      const payload: CategoryCreatePayload = {
        label: draft.label.trim(),
        description: draft.description.trim() || null,
        mapped_workflow_id: draft.mapped_workflow_id,
        is_active: draft.is_active,
      };
      await onSave(payload);
      onOpenChange(false);
    } catch (err) {
      const axiosErr = err as {
        response?: { data?: { detail?: string } };
        message?: string;
      };
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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "Edit category" : "New category"}
          </DialogTitle>
          <DialogDescription>
            Categories guide AI Tier 2 classification. The description
            is what Claude reads when it decides which category an email
            fits — be specific.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="category-label">Label</Label>
            <Input
              id="category-label"
              value={draft.label}
              onChange={(e) => update("label", e.target.value)}
              disabled={saving}
              placeholder="e.g., Pricing inquiries"
              data-testid="category-label-input"
              aria-invalid={validationError !== null}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="category-description">Description</Label>
            <Textarea
              id="category-description"
              value={draft.description}
              onChange={(e) => update("description", e.target.value)}
              disabled={saving}
              placeholder="e.g., Customer questions about pricing, quotes, or product comparisons. NOT for service-day scheduling or order status."
              data-testid="category-description-input"
            />
            <p className="text-caption text-content-muted">
              This text guides Claude when it categorizes emails. Describe
              what kinds of messages fit this category.
            </p>
          </div>

          <div className="space-y-1.5">
            <Label>Mapped workflow</Label>
            <WorkflowPicker
              workflows={workflows}
              value={draft.mapped_workflow_id}
              onChange={(id) => update("mapped_workflow_id", id)}
              tenantVertical={tenantVertical}
              allowNone
              data-testid="category-workflow-picker"
            />
            <p className="text-caption text-content-muted">
              When AI classifies an email into this category, fire this
              workflow. Leave unset to surface for manual review only.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Switch
              checked={draft.is_active}
              onCheckedChange={(v) => update("is_active", Boolean(v))}
              disabled={saving}
              id="category-is-active"
              data-testid="category-is-active-switch"
            />
            <Label htmlFor="category-is-active">Active</Label>
          </div>

          {validationError ? (
            <Alert variant="warning" data-testid="category-validation-alert">
              {validationError}
            </Alert>
          ) : null}

          {serverError ? (
            <Alert variant="error" data-testid="category-server-error">
              {serverError}
            </Alert>
          ) : null}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={saving}
            data-testid="category-cancel"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving || (touched && labelEmpty)}
            data-testid="category-save"
          >
            {saving
              ? "Saving…"
              : isEdit
                ? "Save changes"
                : "Create category"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
