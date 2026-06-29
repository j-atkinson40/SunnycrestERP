/**
 * Maps of Content — Tasks table (MoC-2c).
 *
 * A Bridgeable-native database table under the type-cards: one row per
 * vertical task (the moc_task_catalog). Descriptive columns (Task / Frequency /
 * Type / Description) + relational columns (Workflow Used / Focus's Used) whose
 * cells are deep-link pills built with the SAME mocDeepLink → adminPath path
 * the cards use — byte-identical hrefs, same brass-link treatment.
 *
 * ORPHAN-TOLERANT empty state (the §18 graceful-empty discipline, getting its
 * first real render): a task whose workflow/focus reference isn't seeded yet
 * (the queued option-3 artifacts) renders a DELIBERATE muted em-dash, never a
 * blank that reads as a render bug. Read-only this phase (authoring deferred).
 */
import { Link } from "react-router-dom"
import { ArrowUpRight, type LucideIcon } from "lucide-react"
import { FileText, Receipt, Sparkles } from "lucide-react"

import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import { mocDeepLink } from "@/bridgeable-admin/lib/moc-deep-link"
import { Icon } from "@/components/ui/icon"
import type {
  MoCResolvedArtifact,
  MoCTask,
} from "@/bridgeable-admin/services/moc-service"

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
  "data-testid"?: string
}

export function MoCTaskTable({ tasks, "data-testid": testId }: MoCTaskTableProps) {
  if (tasks.length === 0) return null

  return (
    <section data-testid={testId} className="space-y-3">
      <h2 className="text-h4 font-semibold text-content-strong">Tasks</h2>
      <div className="overflow-hidden rounded-lg border border-border-subtle bg-surface-elevated">
        <table className="w-full border-collapse text-body-sm">
          <thead>
            <tr className="border-b border-border-subtle bg-surface-sunken text-left">
              {["Task", "Frequency", "Workflow Used", "Focus's Used", "Type", "Description"].map(
                (h) => (
                  <th
                    key={h}
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
              <TaskRow key={task.id} task={task} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function TaskRow({ task }: { task: MoCTask }) {
  const TaskIcon = (task.icon && TASK_ICONS[task.icon]) || FileText
  const wfHref = task.workflow ? artifactHref("workflows", task.workflow) : null

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
        </span>
      </td>
      {/* Frequency */}
      <td className="px-3 py-2 text-content-muted">
        {task.frequency || <EmptyCell />}
      </td>
      {/* Workflow Used — deep-link or deliberate em-dash */}
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
      {/* Type — colored pill */}
      <td className="px-3 py-2">
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
      </td>
      {/* Description */}
      <td className="px-3 py-2 text-content-muted">
        {task.description || <EmptyCell />}
      </td>
    </tr>
  )
}
