/**
 * useMapOverlays — the tenant map's shared overlay machinery (The Map Home
 * campaign). The home and every area page mount the SAME ponder overlay,
 * fork prompt, offer dialog, and add dialog; this hook owns that wiring
 * once so the layout pages stay layout.
 *
 * ENGAGEMENT (the quiet writes): every overlay open records `viewed`,
 * reaching the final beat records `completed` — fire-and-forget, one
 * keyspace ('task:<id>' | 'area:<vertical>:<Area>' | 'onboarding:<key>').
 *
 * Composition ponders (area / onboarding) are VIEW-ONLY tenant-side —
 * platform pedagogy is authored platform-side; canEdit is forced false for
 * them regardless of role.
 */
import { useCallback, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { GitBranch } from "lucide-react"

import { useAuth } from "@/contexts/auth-context"
import { Button } from "@/components/ui/button"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import { PonderOverlay } from "@/bridgeable-admin/components/moc/PonderOverlay"
import {
  forkTask, recordEngagement, type MapTask,
} from "@/services/moc-map-service"
import { AddTaskDialog } from "./AddTaskDialog"
import { TaskOfferDialog } from "./TaskOfferDialog"

/** The overlay taskId → the engagement keyspace.
 *
 * LANDMINE #1 (Reframe R-1, pinned): `task:` means AUTOMATION ponders —
 * the data already written says so. The `job:` prefix is RESERVED for the
 * reframe's new entity (R-2's job ponders) and passes through untouched;
 * it must never be wrapped into the task: space. */
export function engagementKey(overlayId: string, vertical: string | null): string {
  if (overlayId.startsWith("area:")) {
    return `area:${vertical}:${overlayId.slice(5)}`
  }
  if (
    overlayId.startsWith("onboarding:") || overlayId.startsWith("job:") ||
    overlayId.startsWith("integration:") || overlayId.startsWith("platform:") ||
    overlayId.startsWith("tip:") || overlayId.startsWith("module:")
  ) {
    return overlayId
  }
  return `task:${overlayId}`
}

export function useMapOverlays({
  tasks, vertical, reload,
}: {
  tasks: MapTask[]
  vertical: string | null
  reload: () => Promise<void>
}) {
  const { company, isAdmin } = useAuth()
  const navigate = useNavigate()
  const [ponderId, setPonderId] = useState<string | null>(null)
  const [offerFor, setOfferFor] = useState<MapTask | null>(null)
  const [adding, setAdding] = useState<{ type: string | null } | null>(null)
  const [forkPrompt, setForkPrompt] = useState<{
    task: MapTask
    resolve: (ok: boolean) => void
  } | null>(null)
  const [forking, setForking] = useState(false)
  const tasksRef = useRef<MapTask[]>([])
  tasksRef.current = tasks

  const ponderTask = useCallback((task: MapTask) => setPonderId(task.id), [])
  const ponderArea = useCallback((area: string) => setPonderId(`area:${area}`), [])
  const ponderJob = useCallback((jobId: string) => setPonderId(`job:${jobId}`), [])
  const ponderKeyed = useCallback((ponderKey: string) => {
    // A suggestion's ponder_key → the overlay id convention.
    if (ponderKey.startsWith("task:")) setPonderId(ponderKey.slice(5))
    else if (ponderKey.startsWith("area:")) {
      const parts = ponderKey.split(":")
      setPonderId(`area:${parts.slice(2).join(":")}`)
    } else setPonderId(ponderKey)
  }, [])
  const openOffer = useCallback((task: MapTask) => setOfferFor(task), [])
  const openAdd = useCallback((type: string | null) => setAdding({ type }), [])

  const onRequestEdit = useCallback(async (): Promise<boolean> => {
    const task = tasksRef.current.find((t) => t.id === ponderId)
    if (!task) return false
    if (task.scope === "tenant_override") return true
    const ok = await new Promise<boolean>((resolve) =>
      setForkPrompt({ task, resolve }),
    )
    if (!ok) {
      // Decline must clear the prompt too — the early return used to leave
      // the dialog mounted forever (latent since P2; caught by R-2's witness).
      setForkPrompt(null)
      return false
    }
    setForking(true)
    try {
      const fork = await forkTask(task.id)
      await reload()
      setPonderId(fork.id)
      return true
    } catch {
      return false
    } finally {
      setForking(false)
      setForkPrompt(null)
    }
  }, [ponderId, reload])

  const isComposition =
    !!ponderId &&
    (ponderId.startsWith("area:") || ponderId.startsWith("onboarding:") ||
     ponderId.startsWith("job:") || ponderId.startsWith("integration:") ||
     ponderId.startsWith("platform:") || ponderId.startsWith("tip:") ||
     ponderId.startsWith("module:"))

  const overlays = (
    <>
      {ponderId ? (
        <PonderOverlay
          taskId={ponderId}
          onClose={() => {
            setPonderId(null)
            void reload()
          }}
          // Platform pedagogy is view-only tenant-side, whoever you are.
          canEdit={isAdmin && !isComposition}
          onRequestEdit={onRequestEdit}
          onViewed={() => recordEngagement(engagementKey(ponderId, vertical), "viewed")}
          onCompleted={() =>
            recordEngagement(engagementKey(ponderId, vertical), "completed")}
          onNavigate={(href) => navigate(href)}
          onOpenPonder={(overlayId) => setPonderId(overlayId)}
        />
      ) : null}

      {offerFor?.offer_state ? (
        <TaskOfferDialog
          offerId={offerFor.offer_state.offer_id}
          taskName={offerFor.name}
          canDecide={isAdmin}
          onClose={() => setOfferFor(null)}
          onDecided={reload}
        />
      ) : null}

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

      {forkPrompt ? (
        <Dialog open onOpenChange={(open) => { if (!open) forkPrompt.resolve(false) }}>
          <DialogContent className="max-w-md" data-testid="fork-prompt">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <GitBranch size={16} className="flex-none text-accent" />
                Make this automation yours?
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
    </>
  )

  return {
    ponderTask, ponderArea, ponderJob, ponderKeyed, openOffer, openAdd,
    overlays, isAdmin,
  }
}
