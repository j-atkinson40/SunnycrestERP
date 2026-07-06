/**
 * Maps of Content — Tasks table (MoC-2c read; MoC-2b editable).
 *
 * A Bridgeable-native database table under the type-cards: one row per
 * vertical task (the moc_task_catalog). Descriptive columns (Task / Frequency /
 * Type / Description) + relational columns (Workflow Used / Focus's Used) whose
 * cells are deep-link pills built with the SAME mocDeepLink → adminPath path
 * the cards use — byte-identical hrefs, same brass-link treatment.
 *
 * MoC-2b — HYBRID EDITING. The constrained/text fields edit inline: Frequency +
 * Type are VocabCell quick-picks reading the editable vocabulary (with +Add-
 * value in the menu); Description edits in place. Relationships (Workflow single,
 * Focuses multi) + create-new + delete live in the TaskEditorPanel. Every write
 * goes through 2a's referentially-validated API; a rejected PATCH surfaces the
 * server's reason and the cell reverts (no silent swallow at the UI layer).
 *
 * ORPHAN-TOLERANT empty state (the §18 graceful-empty discipline): a task whose
 * workflow/focus reference isn't seeded yet renders a DELIBERATE muted em-dash,
 * never a blank that reads as a render bug.
 */
import { useState } from "react"
import { Link } from "react-router-dom"
import { ArrowUpRight, Clock, Pencil, Plus, Trash2, type LucideIcon } from "lucide-react"
import { FileText, Receipt, Sparkles } from "lucide-react"

import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import { mocDeepLink } from "@/bridgeable-admin/lib/moc-deep-link"
import { Icon } from "@/components/ui/icon"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import {
  deleteTask,
  patchTask,
  type MoCResolvedArtifact,
  type MoCTask,
  type PatchTaskInput,
} from "@/bridgeable-admin/services/moc-service"
import { VocabCell } from "./task-editing/VocabCell"
import { TaskEditorPanel, errMsg } from "./task-editing/TaskEditorPanel"
import { TriggerChips } from "./task-editing/TriggerChips"

const TASK_ICONS: Record<string, LucideIcon> = {
  receipt: Receipt,
  sparkles: Sparkles,
}

/** Free-form task_type → pill colors (DESIGN_LANGUAGE status/accent families),
 * neutral fallback for an unmapped type. */
const TYPE_PILL: Record<string, string> = {
  Accounting: "bg-status-info-muted text-status-info",
  "Funeral Service Operations": "bg-accent-subtle text-accent",
}
const TYPE_PILL_DEFAULT = "bg-surface-sunken text-content-muted"

function artifactHref(
  builder: "workflows" | "focuses",
  art: MoCResolvedArtifact,
): string | null {
  if (!art.available) return null
  const path = mocDeepLink({
    builder,
    artifact_id: art.artifact_id,
    routing: art.routing,
  })
  return path ? adminPath(path) : null
}

/** Deliberate muted empty cell — the orphan-tolerant default. */
function EmptyCell() {
  return <span className="text-content-subtle">—</span>
}

export interface MoCTaskTableProps {
  tasks: MoCTask[]
  vertical: string
  /** Tenant View: the page's selected tenant. Rows scoped to it carry a pill
   * (never confusable with the defaults); Add-task creates THAT tenant's
   * override. Null = the defaults view (today's behavior). */
  activeTenant?: { id: string; slug: string; name: string } | null
  /** Refetch after any write (the pending-then-refetch contract). */
  onChanged: () => void
  "data-testid"?: string
}

export function MoCTaskTable({
  tasks, vertical, activeTenant = null, onChanged, "data-testid": testId,
}: MoCTaskTableProps) {
  const [error, setError] = useState<string | null>(null)
  const [panelOpen, setPanelOpen] = useState(false)
  const [editingTask, setEditingTask] = useState<MoCTask | null>(null)

  function openCreate() {
    setEditingTask(null)
    setPanelOpen(true)
  }
  function openEdit(task: MoCTask) {
    setEditingTask(task)
    setPanelOpen(true)
  }

  // The section self-hid pre-2b when empty; now it always renders so the
  // "Add task" affordance is reachable on an empty vertical.
  return (
    <section data-testid={testId} className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-h4 font-semibold text-content-strong">Tasks</h2>
        <Button size="sm" variant="outline" onClick={openCreate} data-testid="moc-task-add">
          <Plus size={15} /> Add task
        </Button>
      </div>

      {error ? (
        <div
          className="flex items-start justify-between gap-3 rounded-md border border-status-error/30 bg-status-error-muted px-3 py-2 text-body-sm text-status-error"
          data-testid="moc-task-error"
        >
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)} className="font-medium underline">
            Dismiss
          </button>
        </div>
      ) : null}

      {tasks.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border-base bg-surface-elevated px-4 py-8 text-center text-body-sm text-content-subtle">
          No tasks yet. Add one to start mapping this vertical's work.
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-border-subtle bg-surface-elevated">
          <table className="w-full border-collapse text-body-sm">
            <thead>
              <tr className="border-b border-border-subtle bg-surface-sunken text-left">
                {["Task", "Frequency", "Workflow Used", "Focus's Used", "Type", "Description", "Triggers", ""].map(
                  (h, i) => (
                    <th
                      key={h || `actions-${i}`}
                      className="px-3 py-2 font-medium text-content-muted"
                    >
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <TaskRow
                  key={task.id}
                  task={task}
                  vertical={vertical}
                  tenantLabel={
                    task.scope === "tenant_override" ? activeTenant?.name ?? "Tenant" : null
                  }
                  onChanged={onChanged}
                  onError={setError}
                  onEdit={() => openEdit(task)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <TaskEditorPanel
        isOpen={panelOpen}
        onClose={() => setPanelOpen(false)}
        vertical={vertical}
        activeTenant={activeTenant}
        task={editingTask}
        onSaved={onChanged}
        onError={setError}
      />
    </section>
  )
}

function TaskRow({
  task, vertical, tenantLabel, onChanged, onError, onEdit,
}: {
  task: MoCTask
  vertical: string
  /** Non-null = a tenant_override row in the tenant view; renders the scope
   * pill so it's never confused with a vertical default. */
  tenantLabel: string | null
  onChanged: () => void
  onError: (msg: string) => void
  onEdit: () => void
}) {
  const TaskIcon = (task.icon && TASK_ICONS[task.icon]) || FileText
  const wfHref = task.workflow ? artifactHref("workflows", task.workflow) : null
  const [deleting, setDeleting] = useState(false)

  /** Pending-then-refetch: PATCH, then refetch on success; on failure surface
   * the server's reason — no refetch, so the cell keeps showing the old value
   * (the revert). */
  async function patchField(input: PatchTaskInput) {
    try {
      await patchTask(task.id, input)
      onChanged()
    } catch (e) {
      onError(errMsg(e))
    }
  }

  async function remove() {
    if (!window.confirm(`Delete task "${task.name}"? This can't be undone.`)) return
    setDeleting(true)
    try {
      await deleteTask(task.id)
      onChanged()
    } catch (e) {
      onError(errMsg(e))
    } finally {
      setDeleting(false)
    }
  }

  return (
    <tr
      className="border-b border-border-subtle last:border-0 align-top"
      data-testid={`moc-task-row-${task.id}`}
    >
      {/* Task */}
      <td className="px-3 py-2">
        <span className="flex items-center gap-2 font-medium text-content-base">
          <Icon icon={TaskIcon} size={15} className="text-content-muted" />
          {task.name}
          {tenantLabel ? (
            <span
              className="inline-flex items-center rounded-full bg-accent-subtle px-1.5 py-0.5 text-caption font-medium text-accent"
              data-testid={`moc-task-tenant-pill-${task.id}`}
              title="This task belongs to the selected tenant (a tenant override), not the vertical defaults."
            >
              {tenantLabel}
            </span>
          ) : null}
        </span>
      </td>
      {/* Frequency — DERIVED from a schedule-trigger when present (read-only,
          marked "from schedule"); otherwise the manual 2a quick-pick stands +
          stays editable (the non-destructive coexistence). */}
      <td className="px-3 py-2 text-content-muted" data-testid={`moc-task-frequency-${task.id}`}>
        {task.derived_frequency ? (
          <span
            className="inline-flex items-center gap-1 text-content-base"
            title="Derived from this task's schedule trigger"
            data-testid={`moc-task-frequency-derived-${task.id}`}
          >
            <Clock size={12} className="text-status-info" />
            {task.derived_frequency}
          </span>
        ) : (
          <VocabCell
            kind="frequency"
            value={task.frequency ?? null}
            vertical={vertical}
            onSelect={(v) => void patchField({ frequency: v })}
          >
            {task.frequency || <EmptyCell />}
          </VocabCell>
        )}
      </td>
      {/* Workflow Used — deep-link or deliberate em-dash (edit via panel) */}
      <td className="px-3 py-2" data-testid={`moc-task-workflow-${task.id}`}>
        {!task.workflow ? (
          <EmptyCell />
        ) : wfHref ? (
          <Link
            to={wfHref}
            className="focus-ring-accent inline-flex items-center gap-1 rounded-sm text-content-base hover:text-accent"
          >
            {task.workflow.label}
            <ArrowUpRight size={12} className="text-content-subtle" />
          </Link>
        ) : (
          <span className="text-content-subtle">{task.workflow.label}</span>
        )}
      </td>
      {/* Focus's Used — deep-link pills, or deliberate em-dash when none */}
      <td className="px-3 py-2" data-testid={`moc-task-focuses-${task.id}`}>
        {task.focuses.length === 0 ? (
          <EmptyCell />
        ) : (
          <span className="flex flex-wrap gap-1">
            {task.focuses.map((f) => {
              const href = artifactHref("focuses", f)
              const base =
                "inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-caption"
              return href ? (
                <Link
                  key={f.artifact_id}
                  to={href}
                  className={`${base} focus-ring-accent bg-accent-subtle text-accent hover:bg-accent-muted`}
                >
                  {f.label}
                  <ArrowUpRight size={10} />
                </Link>
              ) : (
                <span
                  key={f.artifact_id}
                  className={`${base} bg-surface-sunken text-content-subtle`}
                >
                  {f.label}
                </span>
              )
            })}
          </span>
        )}
      </td>
      {/* Type — inline quick-pick rendering the colored pill */}
      <td className="px-3 py-2">
        <VocabCell
          kind="type"
          value={task.task_type ?? null}
          vertical={vertical}
          onSelect={(v) => void patchField({ task_type: v })}
        >
          {task.task_type ? (
            <span
              className={`inline-block rounded-full px-2 py-0.5 text-caption font-medium ${
                TYPE_PILL[task.task_type] ?? TYPE_PILL_DEFAULT
              }`}
            >
              {task.task_type}
            </span>
          ) : (
            <EmptyCell />
          )}
        </VocabCell>
      </td>
      {/* Description — inline text edit */}
      <td className="px-3 py-2 text-content-muted">
        <DescriptionCell
          value={task.description ?? null}
          onCommit={(v) => patchField({ description: v })}
        />
      </td>
      {/* Triggers — chips (summary) + Live/Dry-run badge; editing + the live
          toggle happen in the panel. liveCapable keeps a mirror task's badge
          honest (a mirror never fires live — §6). */}
      <td className="px-3 py-2" data-testid={`moc-task-triggers-${task.id}`}>
        <TriggerChips
          triggers={task.triggers ?? []}
          liveCapable={!(task.workflow?.is_mirror ?? false)}
        />
      </td>
      {/* Row actions — edit relationships / delete */}
      <td className="px-3 py-2">
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onEdit}
            title="Edit relationships"
            data-testid={`moc-task-edit-${task.id}`}
            className="focus-ring-accent rounded-sm p-1 text-content-subtle hover:bg-surface-sunken hover:text-content-base"
          >
            <Pencil size={14} />
          </button>
          <button
            type="button"
            onClick={() => void remove()}
            disabled={deleting}
            title="Delete task"
            data-testid={`moc-task-delete-${task.id}`}
            className="focus-ring-accent rounded-sm p-1 text-content-subtle hover:bg-status-error-muted hover:text-status-error disabled:opacity-40"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </td>
    </tr>
  )
}

/** Click-to-edit description: shows text (or em-dash), becomes a textarea on
 * click, commits on blur / Enter, cancels on Escape. */
function DescriptionCell({
  value, onCommit,
}: {
  value: string | null
  onCommit: (v: string | null) => Promise<void> | void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState("")

  function start() {
    setDraft(value ?? "")
    setEditing(true)
  }
  function commit() {
    setEditing(false)
    const next = draft.trim() || null
    if (next !== (value ?? null)) void onCommit(next)
  }

  if (editing) {
    return (
      <Textarea
        autoFocus
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault()
            commit()
          }
          if (e.key === "Escape") setEditing(false)
        }}
        rows={2}
        className="min-w-[180px] text-body-sm"
        data-testid="moc-task-description-input"
      />
    )
  }
  return (
    <button
      type="button"
      onClick={start}
      data-testid="moc-task-description-cell"
      className="-mx-1 block w-full rounded-sm px-1 text-left hover:bg-surface-sunken"
    >
      {value || <EmptyCell />}
    </button>
  )
}
