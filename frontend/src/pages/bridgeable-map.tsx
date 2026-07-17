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
import { useCallback, useEffect, useRef, useState } from "react"
import {
  FileText, GitBranch, Map as MapIcon, Plus, Sparkles,
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
  forkTask, getMapTasks, tenantPonderService, type MapTask,
} from "@/services/moc-map-service"
import { AddTaskDialog } from "@/components/moc-map/AddTaskDialog"
import { TaskOfferDialog } from "@/components/moc-map/TaskOfferDialog"
import { TaskSections } from "@/components/moc-map/TaskSections"

export default function BridgeableMapPage() {
  const { company, isAdmin } = useAuth()
  const [tasks, setTasks] = useState<MapTask[]>([])
  const [vertical, setVertical] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [ponderTaskId, setPonderTaskId] = useState<string | null>(null)
  // Tenant ADD (The Sunnycrest Workshop) — null = closed; {type} = open,
  // pre-filled from the section whose Add was clicked.
  const [adding, setAdding] = useState<{ type: string | null } | null>(null)
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

        {/* THE BODY — sections-with-cards, derived from the vocabulary
            types that HAVE tasks (The Sunnycrest Workshop; tabs/table/pager
            retired). Sections are the overflow management. */}
        {loading ? (
          <p className="py-10 text-center text-body-sm text-content-muted">
            Loading the map…
          </p>
        ) : tasks.length === 0 ? (
          <p className="py-10 text-center text-body-sm text-content-muted">
            No tasks yet — your vertical's defaults appear here as they ship.
          </p>
        ) : (
          <TaskSections
            tasks={tasks}
            onPonder={ponder}
            onOpenOffer={openOffer}
            canAdd={isAdmin}
            onAdd={(type) => setAdding({ type })}
          />
        )}

        {/* The general add — the same dialog, no section pre-fill. */}
        {isAdmin && !loading ? (
          <div>
            <Button
              variant="outline" size="sm"
              onClick={() => setAdding({ type: null })}
              data-testid="map-add-task-button"
            >
              <Plus size={14} /> Add a task
            </Button>
          </div>
        ) : null}

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

        {/* TENANT ADD — the card appears in its section immediately. */}
        {adding ? (
          <AddTaskDialog
            presetType={adding.type}
            companyName={company?.name ?? "your company"}
            onClose={() => setAdding(null)}
            onCreated={async () => {
              setAdding(null)
              await reload()
            }}
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
