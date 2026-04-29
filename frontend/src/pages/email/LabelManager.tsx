/**
 * LabelManager — popover with existing labels list + create-new
 * affordance + per-label toggle on the current thread.
 *
 * Phase W-4b Layer 1 Step 4b. Per canon §3.26.15.13 + §14.9.1
 * label chips (per-tenant accent-palette assignment; rounded-sm).
 *
 * Named export so vitest renders directly.
 */

import { useEffect, useState } from "react";
import { Check, Plus, Tag } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  addLabelToThread,
  createLabel,
  listLabels,
  removeLabelFromThread,
} from "@/services/email-inbox-service";
import type { EmailLabel } from "@/types/email-inbox";


export interface LabelManagerProps {
  threadId: string;
  currentLabelIds: string[];
  onLabelsChanged: (labelIds: string[]) => void;
  onClose: () => void;
}


// Step 4b ships 6 canonical accent colors aligned with DESIGN_LANGUAGE
// Aesthetic Arc Session 2 single-value cross-mode accent palette.
const PRESET_COLORS = [
  "#9C5640", // accent (terracotta)
  "#4D7C5A", // sage (success-aligned)
  "#9C7A2C", // warm amber (warning-aligned)
  "#5C5C8E", // dusk lavender
  "#7C5040", // muted brown
  "#5A5A5A", // slate
];


export function LabelManager({
  threadId,
  currentLabelIds,
  onLabelsChanged,
  onClose,
}: LabelManagerProps) {
  const [labels, setLabels] = useState<EmailLabel[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newColor, setNewColor] = useState(PRESET_COLORS[0]);
  const [appliedIds, setAppliedIds] = useState<Set<string>>(
    new Set(currentLabelIds),
  );

  useEffect(() => {
    void listLabels()
      .then(setLabels)
      .catch(() => toast.error("Failed to load labels"))
      .finally(() => setLoading(false));
  }, []);

  async function toggleLabel(label: EmailLabel) {
    const isApplied = appliedIds.has(label.id);
    const next = new Set(appliedIds);
    try {
      if (isApplied) {
        next.delete(label.id);
        setAppliedIds(next);
        await removeLabelFromThread(threadId, label.id);
      } else {
        next.add(label.id);
        setAppliedIds(next);
        await addLabelToThread(threadId, label.id);
      }
      onLabelsChanged(Array.from(next));
    } catch {
      // Rollback
      if (isApplied) {
        next.add(label.id);
      } else {
        next.delete(label.id);
      }
      setAppliedIds(next);
      toast.error("Label change failed");
    }
  }

  async function handleCreate() {
    if (!newName.trim()) return;
    try {
      const created = await createLabel(newName.trim(), newColor);
      setLabels([...labels, created]);
      // Auto-apply the new label to the thread
      await addLabelToThread(threadId, created.id);
      const next = new Set(appliedIds);
      next.add(created.id);
      setAppliedIds(next);
      onLabelsChanged(Array.from(next));
      setNewName("");
      setCreating(false);
      toast.success("Label created and applied");
    } catch {
      toast.error("Failed to create label");
    }
  }

  return (
    <div
      className="rounded-lg bg-surface-raised shadow-level-3 p-3 w-72 max-h-96 overflow-y-auto space-y-2"
      data-testid="label-manager"
    >
      <div className="flex items-center gap-2 mb-1">
        <Tag className="h-4 w-4 text-accent" />
        <span className="font-medium text-content-strong">Labels</span>
      </div>

      {loading ? (
        <div className="text-body-sm text-content-muted text-center py-4">
          Loading…
        </div>
      ) : (
        <>
          {labels.length === 0 && !creating && (
            <div className="text-body-sm text-content-muted text-center py-2">
              No labels yet
            </div>
          )}
          <div className="space-y-1">
            {labels.map((label) => {
              const isApplied = appliedIds.has(label.id);
              return (
                <button
                  key={label.id}
                  type="button"
                  onClick={() => toggleLabel(label)}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-accent-subtle text-body-sm"
                  data-testid={`label-toggle-${label.id}`}
                >
                  {label.color && (
                    <span
                      className="w-3 h-3 rounded-full shrink-0"
                      style={{ backgroundColor: label.color }}
                    />
                  )}
                  <span className="flex-1 truncate text-left">
                    {label.name}
                  </span>
                  {isApplied && (
                    <Check className="h-3 w-3 text-accent" data-testid={`label-applied-${label.id}`} />
                  )}
                </button>
              );
            })}
          </div>

          {creating ? (
            <div className="border-t border-border-subtle pt-2 space-y-2">
              <Input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Label name"
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleCreate();
                }}
                data-testid="label-new-name"
                autoFocus
              />
              <div className="flex gap-1">
                {PRESET_COLORS.map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setNewColor(c)}
                    className={
                      "w-6 h-6 rounded-full border-2 " +
                      (newColor === c
                        ? "border-content-strong"
                        : "border-transparent")
                    }
                    style={{ backgroundColor: c }}
                    aria-label={`Color ${c}`}
                  />
                ))}
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setCreating(false);
                    setNewName("");
                  }}
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  onClick={handleCreate}
                  disabled={!newName.trim()}
                  data-testid="label-create-submit"
                  className="flex-1"
                >
                  Create
                </Button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setCreating(true)}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-accent-subtle text-body-sm border-t border-border-subtle pt-2 mt-2"
              data-testid="label-create-btn"
            >
              <Plus className="h-3 w-3" />
              <span>Create new label</span>
            </button>
          )}

          <Button
            variant="outline"
            size="sm"
            onClick={onClose}
            className="w-full mt-2"
          >
            Done
          </Button>
        </>
      )}
    </div>
  );
}
