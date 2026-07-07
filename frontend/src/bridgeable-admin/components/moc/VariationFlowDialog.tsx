/**
 * Guided variation flow (Focus Variations V-1) — name → verticals (MULTI) →
 * task wiring → create. One dialog, ordered steps; submit is ONE call
 * (`createFocusVariation`) that creates the Tier 2 variation (core-version
 * pinned), writes the multi-vertical join, wires the chosen tasks, and
 * auto-authors the refs onto each chosen vertical's map — then the caller
 * lands the operator in the editor on the new variation.
 *
 * The task list follows the vertical selection (a variation is wired to
 * tasks that live where it lives) — checking a vertical fetches its catalog
 * lazily; unchecking drops its tasks (and their selections).
 */

import * as React from "react"
import { toast } from "sonner"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  createFocusVariation,
  readTaskCatalog,
  type FocusVariationResult,
  type MoCTask,
} from "@/bridgeable-admin/services/moc-service"
import { KNOWN_VERTICALS } from "@/bridgeable-admin/components/moc/MoCVerticalsRail"
import type { MoCTypeCardEntry } from "@/bridgeable-admin/components/moc/MoCTypeCards"

export interface VariationFlowDialogProps {
  /** The default (a focus-cores entry; artifact_id = the ACTIVE core id). */
  source: MoCTypeCardEntry
  onClose: () => void
  onCreated: (result: FocusVariationResult) => void
}

export function VariationFlowDialog({
  source,
  onClose,
  onCreated,
}: VariationFlowDialogProps) {
  const [name, setName] = React.useState("")
  const [verticals, setVerticals] = React.useState<string[]>([])
  const [tasksByVertical, setTasksByVertical] = React.useState<
    Record<string, MoCTask[]>
  >({})
  const [taskIds, setTaskIds] = React.useState<string[]>([])
  const [saving, setSaving] = React.useState(false)

  function toggleVertical(slug: string) {
    setVerticals((prev) => {
      const next = prev.includes(slug)
        ? prev.filter((v) => v !== slug)
        : [...prev, slug]
      if (!prev.includes(slug) && !(slug in tasksByVertical)) {
        readTaskCatalog({ vertical: slug })
          .then((tasks) =>
            setTasksByVertical((m) => ({ ...m, [slug]: tasks })),
          )
          .catch(() =>
            setTasksByVertical((m) => ({ ...m, [slug]: [] })),
          )
      }
      if (prev.includes(slug)) {
        // Unchecking a vertical drops its tasks' selections.
        const dropped = new Set(
          (tasksByVertical[slug] ?? []).map((t) => t.id),
        )
        setTaskIds((ids) => ids.filter((id) => !dropped.has(id)))
      }
      return next
    })
  }

  function toggleTask(id: string) {
    setTaskIds((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id],
    )
  }

  async function submit() {
    if (!source.artifact_id) return
    setSaving(true)
    try {
      const result = await createFocusVariation({
        core_id: source.artifact_id,
        display_name: name.trim(),
        verticals,
        task_ids: taskIds,
      })
      onCreated(result)
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : "Creating the variation failed",
      )
      setSaving(false)
    }
  }

  const canSubmit = name.trim().length > 0 && verticals.length > 0 && !saving

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="max-w-lg" data-testid="variation-flow-dialog">
        <DialogHeader>
          <DialogTitle>Create a variation of {source.label}</DialogTitle>
          <DialogDescription>
            A new template on this shape — name it, pick the verticals it
            serves, wire the tasks that use it. It appears on each chosen
            vertical's map.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="variation-name">Name</Label>
            <Input
              id="variation-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Cemetery Scheduling"
              data-testid="variation-name-input"
            />
          </div>

          <div className="space-y-1.5">
            <Label>Verticals</Label>
            <div className="grid grid-cols-2 gap-1.5">
              {KNOWN_VERTICALS.map((v) => (
                <label
                  key={v.slug}
                  className="flex cursor-pointer items-center gap-2 rounded-md border border-border-subtle bg-surface-elevated px-2.5 py-1.5 text-body-sm text-content-base has-[:checked]:border-accent"
                >
                  <input
                    type="checkbox"
                    checked={verticals.includes(v.slug)}
                    onChange={() => toggleVertical(v.slug)}
                    data-testid={`variation-vertical-${v.slug}`}
                  />
                  {v.label}
                </label>
              ))}
            </div>
            <p className="text-caption text-content-subtle">
              The first checked vertical is the variation's home; it surfaces
              on every checked vertical's map.
            </p>
          </div>

          {verticals.length > 0 ? (
            <div className="space-y-1.5">
              <Label>Wire to tasks (optional)</Label>
              <div className="max-h-40 space-y-1 overflow-y-auto rounded-md border border-border-subtle p-1.5">
                {verticals.flatMap((slug) =>
                  (tasksByVertical[slug] ?? []).map((t) => (
                    <label
                      key={t.id}
                      className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1 text-body-sm text-content-base hover:bg-surface-sunken"
                    >
                      <input
                        type="checkbox"
                        checked={taskIds.includes(t.id)}
                        onChange={() => toggleTask(t.id)}
                        data-testid={`variation-task-${t.id}`}
                      />
                      {t.name}
                      <span className="text-caption text-content-subtle">
                        · {slug}
                      </span>
                    </label>
                  )),
                )}
                {verticals.every(
                  (slug) => (tasksByVertical[slug] ?? []).length === 0,
                ) ? (
                  <p className="px-2 py-1 text-caption text-content-subtle">
                    No tasks in the chosen verticals yet — wiring can happen
                    later from any task's editor.
                  </p>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button
            onClick={() => void submit()}
            disabled={!canSubmit}
            data-testid="variation-create-button"
          >
            {saving ? "Creating…" : "Create variation"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
