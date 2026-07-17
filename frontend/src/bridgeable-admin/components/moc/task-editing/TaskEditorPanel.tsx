/**
 * TaskEditorPanel — create a task / edit its relationships (MoC Task Editing 2b).
 *
 * The descriptive cells edit inline in the table; the relationship-heavy fields
 * (Workflow Used single + Focuses multi) are awkward inline, so they live here
 * alongside create-new. Pickers list REAL templates (the workflow_templates incl.
 * the 18 mirrors; the focus_templates) — the same artifacts the resolver
 * deep-links. Submit POSTs/PATCHes via 2a's API; delete removes the task.
 */
import { useEffect, useState } from "react"
import { Check, Play, Plus, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { SlideOver } from "@/components/ui/SlideOver"
import {
  liveCapableForTask,
  addTaskTrigger,
  createTask,
  deleteTask,
  deleteTrigger,
  listFocusTemplateOptions,
  listTriggerEvents,
  listWorkflowTemplateOptions,
  patchTask,
  patchTrigger,
  type MoCArtifactOption,
  type MoCTask,
  type MoCTrigger,
  type MoCTriggerEvent,
  type MoCTriggerKind,
} from "@/bridgeable-admin/services/moc-service"
import { VocabCell } from "./VocabCell"
import { TriggerChips } from "./TriggerChips"
import { TriggerEditor } from "./TriggerEditor"
import { GoLiveConfirm } from "./GoLiveConfirm"

export function errMsg(e: unknown): string {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === "string") return detail
  return e instanceof Error ? e.message : "Something went wrong"
}

function ArtifactPicker({
  options, selected, multi, onChange, placeholder, testId,
}: {
  options: MoCArtifactOption[]
  selected: string[]
  multi: boolean
  onChange: (ids: string[]) => void
  placeholder?: string
  testId?: string
}) {
  const [q, setQ] = useState("")
  const filtered = options.filter((o) =>
    o.display_name.toLowerCase().includes(q.toLowerCase()),
  )
  function toggle(id: string) {
    if (multi) {
      onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id])
    } else {
      onChange(selected.includes(id) ? [] : [id])
    }
  }
  return (
    <div className="rounded-md border border-border-base" data-testid={testId}>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={placeholder ?? "Search…"}
        className="w-full border-b border-border-subtle bg-transparent px-2.5 py-1.5 text-body-sm text-content-base placeholder:text-content-subtle focus-visible:outline-none"
      />
      <div className="max-h-44 overflow-auto p-1">
        {filtered.map((o) => (
          <button
            key={o.id}
            type="button"
            onClick={() => toggle(o.id)}
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1 text-left text-body-sm text-content-base hover:bg-accent-subtle"
          >
            <span
              className={`flex h-4 w-4 flex-none items-center justify-center rounded-${multi ? "sm" : "full"} border ${
                selected.includes(o.id)
                  ? "border-accent bg-accent text-content-on-accent"
                  : "border-border-strong"
              }`}
            >
              {selected.includes(o.id) ? <Check size={11} /> : null}
            </span>
            {o.display_name}
          </button>
        ))}
        {filtered.length === 0 ? (
          <div className="px-2 py-2 text-body-sm text-content-subtle">No matches</div>
        ) : null}
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="text-body-sm font-medium text-content-base">{label}</label>
      {children}
    </div>
  )
}

export function TaskEditorPanel({
  isOpen, onClose, vertical, platformScope = false, activeTenant = null, task, onSaved, onError, onPonder,
}: {
  isOpen: boolean
  onClose: () => void
  vertical: string
  /** H-2: the platform page's panel — CREATE authors a platform_default
   * (vertical-less) task. Mutually exclusive with activeTenant. */
  platformScope?: boolean
  /** Tenant View: non-null = the page is tenant-scoped, so CREATE authors that
   * tenant's override (scope="tenant_override" + tenant_id) — never silently a
   * vertical-wide default. Edits are unaffected (they PATCH the existing row,
   * whatever its scope). */
  activeTenant?: { id: string; slug: string; name: string } | null
  /** null = create mode. */
  task: MoCTask | null
  /** The ponder affordance (P1) — the second surface per the investigation.
   * Present only when editing a task that has a workflow to walk through. */
  onPonder?: () => void
  onSaved: () => void
  onError: (msg: string) => void
}) {
  const editing = task !== null
  const [name, setName] = useState("")
  const [frequency, setFrequency] = useState<string | null>(null)
  const [taskType, setTaskType] = useState<string | null>(null)
  const [description, setDescription] = useState("")
  const [workflowId, setWorkflowId] = useState<string | null>(null)
  const [focusIds, setFocusIds] = useState<string[]>([])
  const [workflows, setWorkflows] = useState<MoCArtifactOption[]>([])
  const [focuses, setFocuses] = useState<MoCArtifactOption[]>([])
  const [saving, setSaving] = useState(false)
  // Triggers (edit mode only — they attach to an existing task_catalog_id).
  const [triggers, setTriggers] = useState<MoCTrigger[]>([])
  const [triggerEvents, setTriggerEvents] = useState<MoCTriggerEvent[]>([])
  const [addingTrigger, setAddingTrigger] = useState(false)
  // T-2.1c: the trigger awaiting the go-live confirm (null = no confirm open).
  const [confirmingLive, setConfirmingLive] = useState<MoCTrigger | null>(null)

  useEffect(() => {
    if (!isOpen) return
    listWorkflowTemplateOptions().then(setWorkflows).catch(() => setWorkflows([]))
    listFocusTemplateOptions().then(setFocuses).catch(() => setFocuses([]))
    listTriggerEvents(platformScope ? undefined : vertical).then(setTriggerEvents).catch(() => setTriggerEvents([]))
    setName(task?.name ?? "")
    setFrequency(task?.frequency ?? null)
    setTaskType(task?.task_type ?? null)
    setDescription(task?.description ?? "")
    setWorkflowId(task?.workflow?.artifact_id ?? null)
    setFocusIds(task ? task.focuses.map((f) => f.artifact_id) : [])
    setTriggers(task?.triggers ?? [])
    setAddingTrigger(false)
  }, [isOpen, task, vertical])

  // Add/remove ride T-1a's trigger CRUD; local state updates immediately (the
  // POST response carries `summary`, no TS drift), and onSaved refreshes the
  // table's read shape (derived Frequency + chips). Errors propagate to the
  // TriggerEditor (which shows the validator's reason) — never swallowed.
  async function addTrigger(kind: MoCTriggerKind, config: Record<string, unknown>) {
    const created = await addTaskTrigger(task!.id, { kind, config })
    setTriggers((cur) => [...cur, created])
    setAddingTrigger(false)
    onSaved()
  }

  async function removeTrigger(triggerId: string) {
    try {
      await deleteTrigger(triggerId)
      setTriggers((cur) => cur.filter((t) => t.id !== triggerId))
      onSaved()
    } catch (e) {
      onError(errMsg(e))
    }
  }

  // T-2.1c live toggle. TO live → the evidence-backed confirm (a beat of
  // gravity). BACK to dry-run → immediate, no confirm (the safe direction is
  // friction-free — a live fire can always be killed fast).
  async function setTriggerLive(triggerId: string, isLive: boolean) {
    try {
      const updated = await patchTrigger(triggerId, { is_live: isLive })
      setTriggers((cur) =>
        cur.map((t) => (t.id === triggerId ? { ...t, is_live: updated.is_live } : t)),
      )
      onSaved()
    } catch (e) {
      onError(errMsg(e))
    }
  }

  function requestLiveToggle(trigger: MoCTrigger, next: boolean) {
    if (next) setConfirmingLive(trigger) // going live → confirm first
    else void setTriggerLive(trigger.id, false) // back to dry-run → immediate
  }

  async function save() {
    if (!name.trim()) { onError("Name is required"); return }
    setSaving(true)
    try {
      const body = {
        name: name.trim(), frequency, task_type: taskType,
        description: description.trim() || null,
        workflow_template_id: workflowId, focus_template_ids: focusIds,
      }
      if (editing) await patchTask(task!.id, body)
      else if (platformScope)
        // H-2: the platform page authors a platform_default (vertical-less)
        // task — the coherence guard at platform scope.
        await createTask({
          vertical: null,
          scope: "platform_default",
          icon: "workflow",
          ...body,
        })
      else
        await createTask({
          vertical,
          icon: "workflow",
          // Tenant View: creating while a tenant is selected authors THAT
          // tenant's override — never silently a vertical-wide default.
          ...(activeTenant
            ? { scope: "tenant_override" as const, tenant_id: activeTenant.id }
            : {}),
          ...body,
        })
      onSaved()
      onClose()
    } catch (e) {
      onError(errMsg(e))
    } finally {
      setSaving(false)
    }
  }

  async function remove() {
    if (!editing) return
    if (!window.confirm(`Delete task "${task!.name}"? This can't be undone.`)) return
    setSaving(true)
    try {
      await deleteTask(task!.id)
      onSaved()
      onClose()
    } catch (e) {
      onError(errMsg(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <SlideOver
      isOpen={isOpen}
      onClose={onClose}
      title={
        editing
          ? "Edit automation"
          : platformScope
            ? "Add platform task"
            : activeTenant
              ? `Add automation for ${activeTenant.name}`
              : "Add automation"
      }
      footer={
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1">
            {editing ? (
              <Button variant="ghost" onClick={remove} disabled={saving}
                className="text-status-error hover:bg-status-error-muted">
                <Trash2 size={15} /> Delete
              </Button>
            ) : null}
            {editing && onPonder ? (
              <Button variant="ghost" onClick={onPonder} disabled={saving}
                data-testid="task-panel-ponder">
                <Play size={15} /> How this works
              </Button>
            ) : null}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
            <Button onClick={save} disabled={saving} data-testid="task-panel-save">
              {saving ? "Saving…" : editing ? "Save" : "Create task"}
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        <Field label="Name">
          <Input value={name} onChange={(e) => setName(e.target.value)}
            placeholder="Funeral Home Billing" data-testid="task-panel-name" />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Frequency">
            <div className="rounded-md border border-border-base px-2.5 py-1.5">
              <VocabCell kind="frequency" value={frequency} vertical={platformScope ? undefined : vertical}
                onSelect={setFrequency}>
                <span className={frequency ? "text-content-base" : "text-content-subtle"}>
                  {frequency ?? "Select…"}
                </span>
              </VocabCell>
            </div>
          </Field>
          <Field label="Type">
            <div className="rounded-md border border-border-base px-2.5 py-1.5">
              <VocabCell kind="type" value={taskType} vertical={platformScope ? undefined : vertical}
                onSelect={setTaskType}>
                <span className={taskType ? "text-content-base" : "text-content-subtle"}>
                  {taskType ?? "Select…"}
                </span>
              </VocabCell>
            </div>
          </Field>
        </div>
        <Field label="Description">
          <Textarea value={description} onChange={(e) => setDescription(e.target.value)}
            rows={3} placeholder="What this task does…" />
        </Field>
        <Field label="Workflow Used">
          <ArtifactPicker options={workflows} selected={workflowId ? [workflowId] : []}
            multi={false} onChange={(ids) => setWorkflowId(ids[0] ?? null)}
            placeholder="Search workflows…" testId="task-panel-workflow" />
        </Field>
        <Field label="Focuses Used">
          <ArtifactPicker options={focuses} selected={focusIds} multi
            onChange={setFocusIds} placeholder="Search focuses…"
            testId="task-panel-focuses" />
        </Field>

        {/* Triggers — descriptive (do NOT fire). Edit mode only: a trigger
            attaches to a saved task. */}
        {editing ? (
          <div className="space-y-2 border-t border-border-subtle pt-4" data-testid="task-panel-triggers">
            <div className="flex items-center justify-between">
              <label className="text-body-sm font-medium text-content-base">Triggers</label>
              {!addingTrigger ? (
                <Button size="sm" variant="outline" onClick={() => setAddingTrigger(true)}
                  data-testid="trigger-add-open">
                  <Plus size={14} /> Add trigger
                </Button>
              ) : null}
            </div>
            <p className="text-caption text-content-subtle">
              Schedule triggers fire dry-run by default; going Live fires real
              effects on schedule.
            </p>
            {triggers.length > 0 ? (
              <TriggerChips
                triggers={triggers}
                onRemove={removeTrigger}
                liveCapable={task ? liveCapableForTask(task) : true}
                onToggleLive={requestLiveToggle}
              />
            ) : !addingTrigger ? (
              <p className="text-body-sm text-content-subtle">No triggers — this task is run manually.</p>
            ) : null}
            {addingTrigger ? (
              <TriggerEditor
                events={triggerEvents}
                onAdd={addTrigger}
                onCancel={() => setAddingTrigger(false)}
              />
            ) : null}
          </div>
        ) : (
          <p className="border-t border-border-subtle pt-4 text-caption text-content-subtle">
            Save the task first to add triggers.
          </p>
        )}
      </div>

      {/* T-2.1c: the evidence-backed go-live confirm (shows the latest dry-run
          preview; the no-preview fallback nudges dry-run-first). */}
      {confirmingLive ? (
        <GoLiveConfirm
          trigger={confirmingLive}
          taskName={task?.name ?? ""}
          onConfirm={() => {
            const id = confirmingLive.id
            setConfirmingLive(null)
            void setTriggerLive(id, true)
          }}
          onCancel={() => setConfirmingLive(null)}
        />
      ) : null}
    </SlideOver>
  )
}
