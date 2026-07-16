/**
 * THE BRIDGEABLE MAP — the tenant's map of what their platform does
 * (Tenant Ponder-Editor P2; the settings-replacement home, growing into
 * the full vision).
 *
 * THE FRAME IS THE VISION'S: a map page with deliberate room for future
 * cards (capability ponders, monitoring). Today the task section is the
 * first populated card — the page is honest about being young, and the
 * coming sections read as room, not shrug.
 *
 * VIEW for all tenant users (hold P on a task to ponder it — the full
 * walkthrough with THEIR fires and THEIR people). EDIT for tenant admins:
 * entering edit mode on a SHARED task raises THE PROMPTED FORK — "create
 * your own version" — a tenant task row + enrollment; the workflow stays
 * shared, the vertical default untouched for everyone else, and their
 * version appears pilled "yours". Forked triggers are born unpromoted
 * (Dry-run) — liveness never inherits.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  ChevronLeft, ChevronRight, Clock, FileText, GitBranch, Map as MapIcon,
  Play, Radio, Sparkles, Zap,
} from "lucide-react"

import { useAuth } from "@/contexts/auth-context"
import { Button } from "@/components/ui/button"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import {
  PonderServiceContext,
} from "@/bridgeable-admin/components/moc/ponder-service-context"
import { PonderOverlay } from "@/bridgeable-admin/components/moc/PonderOverlay"
import {
  HoldRing, useHoldToPonder,
} from "@/bridgeable-admin/components/moc/MoCTaskTable"
import {
  forkTask, getMapTasks, tenantPonderService, type MapTask,
} from "@/services/moc-map-service"
import { TaskOfferDialog } from "@/components/moc-map/TaskOfferDialog"

const KIND_ICON = { schedule: Clock, event: Zap, manual: Play } as const

function TaskRow({
  task, onPonder, onOpenOffer,
}: {
  task: MapTask
  onPonder: (task: MapTask) => void
  onOpenOffer: (task: MapTask) => void
}) {
  const ponderable = Boolean(task.workflow?.exists)
  // Stable identity: the hook's effect deps include onComplete — an inline
  // arrow would re-arm (and cancel) the hold timer on every holding
  // re-render, killing the gesture.
  const complete = useCallback(() => onPonder(task), [onPonder, task])
  const { hovered, holding, reduced, hoverProps } = useHoldToPonder(
    ponderable, complete,
  )
  const when = task.derived_frequency || task.frequency

  return (
    <tr className="border-b border-border-subtle last:border-b-0">
      <td className="py-3 pl-4 pr-3 align-top">
        <div
          className="relative inline-flex items-center gap-2"
          {...hoverProps}
          data-testid={`map-task-${task.id}`}
        >
          <span className="text-body font-medium text-content-strong">
            {task.name}
          </span>
          {task.scope === "tenant_override" ? (
            <span
              className="rounded-full bg-accent-subtle px-2 py-0.5 text-micro font-medium text-accent"
              data-testid={`map-task-yours-${task.id}`}
            >
              yours
            </span>
          ) : null}
          {task.offer_state?.offer_status === "pending" ? (
            <button
              type="button"
              onClick={() => onOpenOffer(task)}
              className="focus-ring-accent rounded-full bg-accent px-2 py-0.5 text-micro font-medium text-content-on-accent"
              data-testid={`map-task-offer-${task.id}`}
            >
              standard updated
            </button>
          ) : task.offer_state?.offer_status === "declined" ? (
            <button
              type="button"
              onClick={() => onOpenOffer(task)}
              className="focus-ring-accent rounded-full border border-border-base bg-surface-sunken px-2 py-0.5 text-micro text-content-subtle"
              data-testid={`map-task-offer-gap-${task.id}`}
              title="The standard version updated — you passed earlier; still available"
            >
              yours · standard updated
            </button>
          ) : null}
          {ponderable && hovered ? (
            <span
              className="absolute left-full top-1/2 ml-2 flex -translate-y-1/2 items-center gap-1.5 whitespace-nowrap rounded-md bg-surface-sunken px-2 py-1 text-caption text-content-muted shadow-level-1"
              data-testid="map-hold-hint"
            >
              <HoldRing holding={holding} reduced={reduced} />
              Hold <kbd className="rounded-sm border border-border-base px-1 font-plex-mono text-micro">P</kbd> to ponder
            </span>
          ) : null}
        </div>
        {task.description ? (
          <p className="mt-0.5 max-w-md text-body-sm text-content-muted">
            {task.description}
          </p>
        ) : null}
      </td>
      <td className="px-3 py-3 align-top text-body-sm text-content-muted">
        {when ?? "—"}
      </td>
      <td className="px-3 py-3 align-top text-body-sm text-content-muted">
        {task.workflow?.label ?? "—"}
      </td>
      <td className="px-3 py-3 align-top">
        <div className="flex flex-wrap gap-1.5">
          {task.triggers.length === 0 ? (
            <span className="text-body-sm text-content-subtle">—</span>
          ) : (
            task.triggers.map((t) => {
              const Icon = KIND_ICON[t.kind]
              return (
                <span
                  key={t.id}
                  className="inline-flex items-center gap-1 rounded-full border border-border-subtle bg-surface-sunken px-2 py-0.5 text-caption text-content-muted"
                >
                  <Icon size={10} />
                  {t.summary ?? t.kind}
                  {t.is_live ? (
                    <span className="inline-flex items-center gap-0.5 text-accent">
                      <Radio size={9} /> live
                    </span>
                  ) : (
                    <span className="text-content-subtle">dry-run</span>
                  )}
                </span>
              )
            })
          )}
        </div>
      </td>
    </tr>
  )
}

export default function BridgeableMapPage() {
  const { company, isAdmin } = useAuth()
  const [tasks, setTasks] = useState<MapTask[]>([])
  const [vertical, setVertical] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [group, setGroup] = useState<string | null>(null)
  const [ponderTaskId, setPonderTaskId] = useState<string | null>(null)
  const [forkPrompt, setForkPrompt] = useState<{
    task: MapTask
    resolve: (ok: boolean) => void
  } | null>(null)
  const [forking, setForking] = useState(false)
  const tasksRef = useRef<MapTask[]>([])

  const reload = useCallback(async () => {
    const data = await getMapTasks()
    setTasks(data.tasks)
    tasksRef.current = data.tasks
    setVertical(data.vertical)
  }, [])

  useEffect(() => {
    reload().finally(() => setLoading(false))
  }, [reload])

  // Group tabs — derived from task_type, empty groups hidden (self-maintaining).
  const groups = useMemo(() => {
    const counts = new Map<string, number>()
    for (const t of tasks) {
      if (t.task_type) counts.set(t.task_type, (counts.get(t.task_type) ?? 0) + 1)
    }
    return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  }, [tasks])
  const visible = useMemo(
    () => (group ? tasks.filter((t) => t.task_type === group) : tasks),
    [tasks, group],
  )

  // Pages, not a wall: 10 tasks at a time, chevrons underneath. The page
  // clamps when the filter shrinks the list; switching tabs starts at 1.
  const PAGE_SIZE = 10
  const [page, setPage] = useState(0)
  const pageCount = Math.max(1, Math.ceil(visible.length / PAGE_SIZE))
  const safePage = Math.min(page, pageCount - 1)
  const paged = useMemo(
    () => visible.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE),
    [visible, safePage],
  )

  const ponder = useCallback((task: MapTask) => setPonderTaskId(task.id), [])
  const [offerFor, setOfferFor] = useState<MapTask | null>(null)
  const openOffer = useCallback((task: MapTask) => setOfferFor(task), [])

  /** THE PROMPTED FORK — asked when an admin enters edit mode on a SHARED
   * task. Accept → fork server-side → the overlay retargets to THEIR row. */
  const onRequestEdit = useCallback(async (): Promise<boolean> => {
    const task = tasksRef.current.find((t) => t.id === ponderTaskId)
    if (!task) return false
    if (task.scope === "tenant_override") return true // already theirs
    const ok = await new Promise<boolean>((resolve) =>
      setForkPrompt({ task, resolve }),
    )
    if (!ok) return false
    setForking(true)
    try {
      const fork = await forkTask(task.id)
      await reload()
      setPonderTaskId(fork.id) // the overlay refetches — now editing THEIRS
      return true
    } catch {
      return false
    } finally {
      setForking(false)
      setForkPrompt(null)
    }
  }, [ponderTaskId, reload])

  return (
    <PonderServiceContext.Provider value={tenantPonderService}>
      <div className="space-y-6 p-6" data-testid="bridgeable-map-page">
        <div>
          <h1 className="flex items-center gap-2.5 text-h1 font-semibold text-content-strong">
            <MapIcon size={26} className="text-accent" strokeWidth={1.8} />
            Bridgeable Map
          </h1>
          <p className="mt-1 max-w-2xl text-body text-content-muted">
            The map of what your platform does — every automated task, when it
            runs, and how it works. Hold <kbd className="rounded-sm border border-border-base px-1 font-plex-mono text-caption">P</kbd> on
            a task to walk through it{isAdmin ? "; edit it right where it teaches" : ""}.
          </p>
        </div>

        {/* THE FIRST CARD — the task map */}
        <section
          className="rounded-lg bg-surface-elevated shadow-level-1"
          data-testid="map-tasks-card"
        >
          <div className="flex items-center justify-between border-b border-border-subtle px-4 py-3">
            <h2 className="text-h4 font-medium text-content-strong">Tasks</h2>
            {groups.length > 0 ? (
              <div className="flex gap-1" role="tablist">
                <button
                  type="button" role="tab" aria-selected={group === null}
                  onClick={() => { setGroup(null); setPage(0) }}
                  className={`rounded-md px-2.5 py-1 text-body-sm ${group === null ? "bg-accent-subtle font-medium text-accent" : "text-content-muted hover:bg-surface-sunken"}`}
                >
                  All <span className="text-caption text-content-subtle">{tasks.length}</span>
                </button>
                {groups.map(([g, n]) => (
                  <button
                    key={g} type="button" role="tab" aria-selected={group === g}
                    onClick={() => { setGroup(group === g ? null : g); setPage(0) }}
                    className={`rounded-md px-2.5 py-1 text-body-sm capitalize ${group === g ? "bg-accent-subtle font-medium text-accent" : "text-content-muted hover:bg-surface-sunken"}`}
                    data-testid={`map-group-${g}`}
                  >
                    {g} <span className="text-caption text-content-subtle">{n}</span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          {loading ? (
            <p className="px-4 py-8 text-center text-body-sm text-content-muted">
              Loading the map…
            </p>
          ) : visible.length === 0 ? (
            <p className="px-4 py-8 text-center text-body-sm text-content-muted">
              No tasks yet — your vertical's defaults appear here as they ship.
            </p>
          ) : (
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-border-subtle text-caption uppercase tracking-wide text-content-subtle">
                  <th className="py-2 pl-4 pr-3 font-medium">Task</th>
                  <th className="px-3 py-2 font-medium">When</th>
                  <th className="px-3 py-2 font-medium">Workflow</th>
                  <th className="px-3 py-2 font-medium">Triggers</th>
                </tr>
              </thead>
              <tbody>
                {paged.map((t) => (
                  <TaskRow key={t.id} task={t} onPonder={ponder} onOpenOffer={openOffer} />
                ))}
              </tbody>
            </table>
          )}
          {pageCount > 1 ? (
            <div
              className="flex items-center justify-center gap-3 border-t border-border-subtle px-4 py-2.5"
              data-testid="map-pager"
            >
              <button
                type="button"
                onClick={() => setPage(Math.max(0, safePage - 1))}
                disabled={safePage === 0}
                aria-label="Previous page"
                className="focus-ring-accent rounded-md p-1.5 text-content-muted hover:bg-surface-sunken disabled:opacity-30"
                data-testid="map-pager-prev"
              >
                <ChevronLeft size={16} />
              </button>
              <span className="text-caption text-content-subtle" data-testid="map-pager-label">
                Page {safePage + 1} of {pageCount}
                <span className="ml-1.5">· {visible.length} tasks</span>
              </span>
              <button
                type="button"
                onClick={() => setPage(Math.min(pageCount - 1, safePage + 1))}
                disabled={safePage >= pageCount - 1}
                aria-label="Next page"
                className="focus-ring-accent rounded-md p-1.5 text-content-muted hover:bg-surface-sunken disabled:opacity-30"
                data-testid="map-pager-next"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          ) : null}
        </section>

        {/* THE ROOM — coming sections read as room, not shrug. */}
        <section
          className="grid gap-4 md:grid-cols-2"
          data-testid="map-room"
        >
          {[
            {
              icon: Sparkles,
              title: "Capabilities",
              body: "Walkthroughs of what each part of the platform can do — the same ponder treatment, for capabilities.",
            },
            {
              icon: FileText,
              title: "Documents & monitoring",
              body: "The documents your tasks produce and how your runs have been going, mapped in one place.",
            },
          ].map(({ icon: Icon, title, body }) => (
            <div
              key={title}
              className="rounded-lg border border-dashed border-border-base p-4"
            >
              <p className="flex items-center gap-2 text-body-sm font-medium text-content-muted">
                <Icon size={14} className="text-content-subtle" /> {title}
                <span className="rounded-full bg-surface-sunken px-1.5 py-0.5 text-micro text-content-subtle">
                  coming
                </span>
              </p>
              <p className="mt-1 text-caption text-content-subtle">{body}</p>
            </div>
          ))}
        </section>

        {ponderTaskId ? (
          <PonderOverlay
            taskId={ponderTaskId}
            onClose={() => {
              setPonderTaskId(null)
              void reload() // in-ponder edits reflect in the table on return
            }}
            canEdit={isAdmin}
            onRequestEdit={onRequestEdit}
          />
        ) : null}

        {/* P3 — the standard updated: the offer, in the prose grammar. */}
        {offerFor?.offer_state ? (
          <TaskOfferDialog
            offerId={offerFor.offer_state.offer_id}
            taskName={offerFor.name}
            canDecide={isAdmin}
            onClose={() => setOfferFor(null)}
            onDecided={reload}
          />
        ) : null}

        {/* THE PROMPTED FORK — deliberate, one step. */}
        {forkPrompt ? (
          <Dialog open onOpenChange={(open) => { if (!open) forkPrompt.resolve(false) }}>
            <DialogContent className="max-w-md" data-testid="fork-prompt">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <GitBranch size={16} className="flex-none text-accent" />
                  Make this task yours?
                </DialogTitle>
                <DialogDescription data-testid="fork-prompt-copy">
                  <strong>{forkPrompt.task.name}</strong> is the standard{" "}
                  {vertical ?? "platform"} version. Create{" "}
                  <strong>{company?.name ?? "your company"}</strong>'s own
                  version to customize its schedule, wording, and settings —
                  the standard version stays untouched for everyone else.
                </DialogDescription>
              </DialogHeader>
              <p className="rounded-md border border-border-base bg-surface-sunken p-2.5 text-body-sm text-content-muted">
                Your version starts as an exact copy. Its triggers begin in
                dry-run — nothing fires live until it's deliberately promoted.
              </p>
              <DialogFooter>
                <Button variant="outline" disabled={forking}
                  onClick={() => forkPrompt.resolve(false)}
                  data-testid="fork-cancel">
                  Keep the standard version
                </Button>
                <Button disabled={forking}
                  onClick={() => forkPrompt.resolve(true)}
                  data-testid="fork-accept">
                  {forking ? "Creating…" : "Create our version"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        ) : null}
      </div>
    </PonderServiceContext.Provider>
  )
}
