/**
 * AddTaskDialog — tenant-side ADD (The Sunnycrest Workshop).
 *
 * A tenant admin authors a NEW task on THEIR map. Minimal, honest fields:
 * name (required), what it does, its type (the vocabulary visible to the
 * vertical — a per-section add arrives pre-filled). The scope is the
 * SERVER'S decision (forced tenant_override — the coherence guard); the
 * dialog never even mentions scope. Born bare: schedules, captions, and a
 * workflow arrive later, where those live.
 */
import { useEffect, useState } from "react"
import { Plus } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  createMapTask, getMapVocabulary, type MapTask,
} from "@/services/moc-map-service"

export function AddTaskDialog({
  presetType, companyName, onCreated, onClose,
}: {
  /** Pre-filled from the section whose Add was clicked; null = general. */
  presetType: string | null
  companyName: string
  onCreated: (task: MapTask) => void
  onClose: () => void
}) {
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [taskType, setTaskType] = useState<string>(presetType ?? "")
  const [types, setTypes] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getMapVocabulary("type")
      .then((vals) => {
        if (!cancelled) setTypes(vals.map((v) => v.value))
      })
      .catch(() => { /* the type stays free-optional */ })
    return () => { cancelled = true }
  }, [])

  async function submit() {
    if (!name.trim()) {
      setError("Give the task a name.")
      return
    }
    setBusy(true)
    setError(null)
    try {
      const task = await createMapTask({
        name: name.trim(),
        description: description.trim() || null,
        task_type: taskType || null,
      })
      onCreated(task)
    } catch (e) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail
      setError(detail ?? "Couldn't create the task.")
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open && !busy) onClose() }}>
      <DialogContent className="max-w-md" data-testid="map-add-task">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Plus size={16} className="flex-none text-accent" />
            Add a task to {companyName}'s map
          </DialogTitle>
          <DialogDescription>
            Yours from the start — it appears on your map only, ready for a
            schedule and a walkthrough.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div>
            <label className="text-body-sm font-medium text-content-base" htmlFor="add-task-name">
              Name
            </label>
            <Input
              id="add-task-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Weekly yard walk-through"
              autoFocus
              className="mt-1"
              data-testid="map-add-name"
            />
          </div>
          <div>
            <label className="text-body-sm font-medium text-content-base" htmlFor="add-task-desc">
              What it does <span className="font-normal text-content-subtle">(optional)</span>
            </label>
            <Textarea
              id="add-task-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              placeholder="One or two sentences — this is what the card teaches."
              className="mt-1"
              data-testid="map-add-description"
            />
          </div>
          {types.length > 0 ? (
            <div>
              <label className="text-body-sm font-medium text-content-base" htmlFor="add-task-type">
                Section
              </label>
              <select
                id="add-task-type"
                value={taskType}
                onChange={(e) => setTaskType(e.target.value)}
                className="mt-1 w-full rounded-md border border-border-base bg-surface-raised px-2.5 py-1.5 text-body-sm text-content-base focus-ring-accent"
                data-testid="map-add-type"
              >
                <option value="">General</option>
                {types.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
          ) : null}
          {error ? (
            <p className="text-body-sm text-status-error" data-testid="map-add-error">
              {error}
            </p>
          ) : null}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy}
            data-testid="map-add-cancel">
            Cancel
          </Button>
          <Button onClick={() => void submit()} disabled={busy}
            data-testid="map-add-submit">
            {busy ? "Adding…" : "Add task"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
