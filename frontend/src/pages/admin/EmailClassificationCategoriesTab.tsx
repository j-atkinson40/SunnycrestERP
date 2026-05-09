/**
 * EmailClassificationCategoriesTab — Tier 2 taxonomy library.
 *
 * v1 ships flat (no parent_id tree authoring) per investigation §4.
 * Edit + delete row actions; CategoryEditor mounts in modal mode.
 */

import * as React from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { CategoryEditor } from "@/components/email-classification/CategoryEditor";
import { CategoriesTable } from "@/components/email-classification/CategoriesTable";
import * as svc from "@/services/email-classification-service";
import type {
  CategoryCreatePayload,
  CategoryUpdatePayload,
  TenantWorkflowEmailCategory,
  WorkflowSummary,
} from "@/types/email-classification";

export interface EmailClassificationCategoriesTabProps {
  categories: TenantWorkflowEmailCategory[];
  workflows: WorkflowSummary[];
  tenantVertical: string | null;
  loading: boolean;
  onReload: () => Promise<void>;
}

export function EmailClassificationCategoriesTab({
  categories,
  workflows,
  tenantVertical,
  loading,
  onReload,
}: EmailClassificationCategoriesTabProps) {
  const [editorOpen, setEditorOpen] = React.useState(false);
  const [editingCategory, setEditingCategory] =
    React.useState<TenantWorkflowEmailCategory | null>(null);
  const [deletingCategory, setDeletingCategory] =
    React.useState<TenantWorkflowEmailCategory | null>(null);
  const [deleting, setDeleting] = React.useState(false);

  function openCreate() {
    setEditingCategory(null);
    setEditorOpen(true);
  }

  function openEdit(c: TenantWorkflowEmailCategory) {
    setEditingCategory(c);
    setEditorOpen(true);
  }

  async function handleSave(
    payload: CategoryCreatePayload | CategoryUpdatePayload,
  ) {
    if (editingCategory) {
      await svc.updateCategory(
        editingCategory.id,
        payload as CategoryUpdatePayload,
      );
      toast.success(`Updated "${editingCategory.label}"`);
    } else {
      const created = await svc.createCategory(payload as CategoryCreatePayload);
      toast.success(`Created "${created.label}"`);
    }
    await onReload();
  }

  async function confirmDelete() {
    if (!deletingCategory) return;
    setDeleting(true);
    try {
      const result = await svc.deleteCategory(deletingCategory.id);
      const msg =
        result.descendants > 0
          ? `Deleted "${deletingCategory.label}" + ${result.descendants} descendant(s).`
          : `Deleted "${deletingCategory.label}".`;
      toast.success(msg);
      setDeletingCategory(null);
      await onReload();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Delete failed";
      toast.error(msg);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-h4 font-medium text-content-strong">
            Categories
          </h2>
          <p className="text-body-sm text-content-muted">
            AI Tier 2 routes emails into these categories. Each category&apos;s
            description tells Claude what kinds of messages fit.
          </p>
        </div>
        <Button
          onClick={openCreate}
          disabled={loading}
          data-testid="email-classification-new-category"
        >
          <Plus className="h-4 w-4 mr-1.5" />
          New category
        </Button>
      </div>

      <CategoriesTable
        categories={categories}
        workflows={workflows}
        loading={loading}
        onEdit={openEdit}
        onDelete={(c) => setDeletingCategory(c)}
      />

      <CategoryEditor
        open={editorOpen}
        onOpenChange={setEditorOpen}
        category={editingCategory}
        workflows={workflows}
        tenantVertical={tenantVertical}
        onSave={handleSave}
      />

      <Dialog
        open={deletingCategory !== null}
        onOpenChange={(o) => !o && setDeletingCategory(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete category?</DialogTitle>
            <DialogDescription>
              {deletingCategory
                ? `"${deletingCategory.label}" will be deactivated, and any descendants will be deactivated too. AI classification will no longer route emails into this category.`
                : null}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeletingCategory(null)}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={confirmDelete}
              disabled={deleting}
              data-testid="email-classification-confirm-delete-category"
            >
              {deleting ? "Deleting…" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
