import { useCallback, useEffect, useState } from "react";
import { CheckCircle2Icon, CircleIcon, PlusIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getApiErrorMessage } from "@/lib/api-error";
import apiClient from "@/lib/api-client";
import { toast } from "sonner";

interface ChecklistItem {
  label: string;
  completed: boolean;
}

interface OnboardingChecklist {
  id: string;
  template_id: string;
  items: string; // JSON
  created_at: string;
}

interface OnboardingTemplate {
  id: string;
  name: string;
  items: string; // JSON
  is_active: boolean;
}

interface OnboardingSectionProps {
  userId: string;
  canEdit: boolean;
}

export default function OnboardingSection({
  userId,
  canEdit,
}: OnboardingSectionProps) {
  const [checklists, setChecklists] = useState<OnboardingChecklist[]>([]);
  const [templates, setTemplates] = useState<OnboardingTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [assignDialogOpen, setAssignDialogOpen] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");

  // Create template dialog
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [newTemplateName, setNewTemplateName] = useState("");
  const [newTemplateItems, setNewTemplateItems] = useState("");
  const [creating, setCreating] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [clRes, tmplRes] = await Promise.all([
        apiClient.get<OnboardingChecklist[]>("/onboarding/checklists", {
          params: { user_id: userId },
        }),
        apiClient.get<OnboardingTemplate[]>("/onboarding/templates"),
      ]);
      setChecklists(clRes.data);
      setTemplates(tmplRes.data);
    } catch {
      // Non-critical
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleAssign() {
    if (!selectedTemplateId) return;
    try {
      await apiClient.post("/onboarding/checklists", {
        user_id: userId,
        template_id: selectedTemplateId,
      });
      toast.success("Onboarding checklist assigned");
      setAssignDialogOpen(false);
      setSelectedTemplateId("");
      await loadData();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to assign checklist"));
    }
  }

  async function handleToggleItem(
    checklistId: string,
    itemIndex: number,
    completed: boolean
  ) {
    try {
      await apiClient.patch(`/onboarding/checklists/${checklistId}/items`, {
        item_index: itemIndex,
        completed,
      });
      await loadData();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to update item"));
    }
  }

  async function handleCreateTemplate(e: React.FormEvent) {
    e.preventDefault();
    if (!newTemplateName.trim() || !newTemplateItems.trim()) return;
    setCreating(true);
    try {
      const items = newTemplateItems
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);
      await apiClient.post("/onboarding/templates", {
        name: newTemplateName.trim(),
        items,
      });
      toast.success("Template created");
      setCreateDialogOpen(false);
      setNewTemplateName("");
      setNewTemplateItems("");
      await loadData();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to create template"));
    } finally {
      setCreating(false);
    }
  }

  function getProgress(items: ChecklistItem[]): string {
    const done = items.filter((i) => i.completed).length;
    return `${done}/${items.length}`;
  }

  if (loading) {
    return (
      <p className="text-sm text-muted-foreground">Loading onboarding...</p>
    );
  }

  return (
    <div className="space-y-4">
      {canEdit && (
        <div className="flex gap-2">
          <Dialog open={assignDialogOpen} onOpenChange={setAssignDialogOpen}>
            <DialogTrigger
              render={<Button type="button" variant="outline" size="sm" />}
            >
              <PlusIcon className="mr-1.5 size-4" />
              Assign Checklist
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Assign Onboarding Checklist</DialogTitle>
                <DialogDescription>
                  Select a template to assign to this employee.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-3">
                <Label>Template</Label>
                <select
                  value={selectedTemplateId}
                  onChange={(e) => setSelectedTemplateId(e.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-[color,box-shadow] focus-visible:border-ring focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
                >
                  <option value="">Select template...</option>
                  {templates.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  onClick={handleAssign}
                  disabled={!selectedTemplateId}
                >
                  Assign
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
            <DialogTrigger
              render={<Button type="button" variant="ghost" size="sm" />}
            >
              New Template
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create Onboarding Template</DialogTitle>
                <DialogDescription>
                  Enter a name and list items (one per line).
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={handleCreateTemplate} className="space-y-4">
                <div className="space-y-2">
                  <Label>Template Name</Label>
                  <Input
                    value={newTemplateName}
                    onChange={(e) => setNewTemplateName(e.target.value)}
                    placeholder="e.g. New Hire Onboarding"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label>Checklist Items (one per line)</Label>
                  <textarea
                    value={newTemplateItems}
                    onChange={(e) => setNewTemplateItems(e.target.value)}
                    rows={5}
                    className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs transition-[color,box-shadow] focus-visible:border-ring focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
                    placeholder={"Complete W-4 form\nReview employee handbook\nIT setup"}
                    required
                  />
                </div>
                <DialogFooter>
                  <Button type="submit" disabled={creating}>
                    {creating ? "Creating..." : "Create Template"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      )}

      {checklists.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No onboarding checklists assigned.
        </p>
      ) : (
        <div className="space-y-4">
          {checklists.map((cl) => {
            const items: ChecklistItem[] = JSON.parse(cl.items);
            const templateName =
              templates.find((t) => t.id === cl.template_id)?.name ||
              "Checklist";
            return (
              <div key={cl.id} className="rounded-md border p-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-medium">{templateName}</span>
                  <span className="text-xs text-muted-foreground">
                    {getProgress(items)}
                  </span>
                </div>
                {/* Progress bar */}
                <div className="mb-3 h-1.5 rounded-full bg-muted">
                  <div
                    className="h-1.5 rounded-full bg-primary transition-all"
                    style={{
                      width: `${items.length > 0 ? (items.filter((i) => i.completed).length / items.length) * 100 : 0}%`,
                    }}
                  />
                </div>
                <div className="space-y-1.5">
                  {items.map((item, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() =>
                        canEdit &&
                        handleToggleItem(cl.id, idx, !item.completed)
                      }
                      disabled={!canEdit}
                      className="flex w-full items-center gap-2 rounded px-1 py-0.5 text-left text-sm hover:bg-muted/50 disabled:cursor-default disabled:hover:bg-transparent"
                    >
                      {item.completed ? (
                        <CheckCircle2Icon className="size-4 shrink-0 text-primary" />
                      ) : (
                        <CircleIcon className="size-4 shrink-0 text-muted-foreground" />
                      )}
                      <span
                        className={
                          item.completed
                            ? "text-muted-foreground line-through"
                            : ""
                        }
                      >
                        {item.label}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
