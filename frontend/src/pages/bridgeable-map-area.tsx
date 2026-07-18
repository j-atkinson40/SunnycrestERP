/**
 * THE AREA PAGE — the sections-with-cards layout, RE-HOMED per-area
 * (The Map Home campaign; nothing discarded — the Sunnycrest Workshop's
 * layout is this page now). Breadcrumbed back to the home; the same
 * overlay machinery (ponder, fork, offers, add) rides along.
 */
import { useCallback, useEffect, useMemo, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { ChevronDown, ChevronRight, Map as MapIcon } from "lucide-react"

import {
  PonderServiceContext,
} from "@/bridgeable-admin/components/moc/ponder-service-context"
import {
  getMapJobs, getMapTasks, tenantPonderService,
  type MapJob, type MapTask,
} from "@/services/moc-map-service"
import { IntegrationsArea } from "@/components/moc-map/IntegrationsArea"
import { JobCard } from "@/components/moc-map/JobCard"
import { TaskSections } from "@/components/moc-map/TaskSections"
import { useMapOverlays } from "@/components/moc-map/useMapOverlays"

const ENGINE_ROOM_KEY = "bridgeable-map-engine-room-open"

function loadEngineRoomOpen(): Set<string> {
  try {
    const raw = localStorage.getItem(ENGINE_ROOM_KEY)
    return new Set(raw ? (JSON.parse(raw) as string[]) : [])
  } catch {
    return new Set()
  }
}

export default function BridgeableMapAreaPage() {
  const { area = "" } = useParams<{ area: string }>()
  const [tasks, setTasks] = useState<MapTask[]>([])
  const [jobs, setJobs] = useState<MapJob[]>([])
  const [vertical, setVertical] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  // THE ENGINE ROOM — collapsed by default, remembered per-user (open
  // areas are the stored exceptions).
  const [engineOpen, setEngineOpen] = useState<Set<string>>(loadEngineRoomOpen)

  const reload = useCallback(async () => {
    const data = await getMapTasks()
    setTasks(data.tasks)
    setVertical(data.vertical)
    try {
      setJobs((await getMapJobs()).jobs)
    } catch {
      setJobs([])
    }
  }, [])

  const toggleEngineRoom = useCallback((a: string) => {
    setEngineOpen((prev) => {
      const next = new Set(prev)
      if (next.has(a)) next.delete(a)
      else next.add(a)
      try {
        localStorage.setItem(ENGINE_ROOM_KEY, JSON.stringify([...next]))
      } catch { /* session-local */ }
      return next
    })
  }, [])

  useEffect(() => {
    reload().finally(() => setLoading(false))
  }, [reload])

  const areaTasks = useMemo(
    () => tasks.filter((t) => (t.task_type || "General") === area),
    [tasks, area],
  )
  const areaJobs = useMemo(
    () => jobs.filter((j) => (j.task_type || "General") === area),
    [jobs, area],
  )

  const {
    ponderTask, ponderArea, ponderJob, ponderKeyed, openOffer, openAdd,
    overlays, isAdmin,
  } = useMapOverlays({ tasks, vertical, reload })

  return (
    <PonderServiceContext.Provider value={tenantPonderService}>
      <div className="space-y-6 p-6" data-testid="bridgeable-map-area-page">
        <div>
          {/* The breadcrumb — home is one click away, always. */}
          <nav
            className="flex items-center gap-1 text-body-sm text-content-muted"
            data-testid="map-area-breadcrumb"
          >
            <Link
              to="/bridgeable-map"
              className="focus-ring-accent flex items-center gap-1.5 rounded-md px-1 py-0.5 hover:text-content-base"
            >
              <MapIcon size={13} className="text-accent" /> Bridgeable Map
            </Link>
            <ChevronRight size={12} className="text-content-subtle" />
            <span className="text-content-base">{area}</span>
          </nav>
          <h1 className="mt-2 text-h1 font-semibold text-content-strong">
            {area}
          </h1>
          <p className="mt-1 max-w-2xl text-body text-content-muted">
            The {area} work on your map — hold{" "}
            <kbd className="rounded-sm border border-border-base px-1 font-plex-mono text-caption">P</kbd>{" "}
            on a card to walk through it.
            {" "}
            <button
              type="button"
              onClick={() => ponderArea(area)}
              className="focus-ring-accent rounded-md text-accent underline-offset-2 hover:underline"
              data-testid="map-area-overview-link"
            >
              Or start with the area's story.
            </button>
          </p>
        </div>

        {/* THE INTEGRATIONS AREA (2026-07-18) — the engine room. The
            B-1 setup card LEFT accounting; management lives here. */}
        {area === "Integrations" ? (
          <IntegrationsArea isAdmin={isAdmin} onPonder={ponderKeyed} />
        ) : loading ? (
          <p className="py-10 text-center text-body-sm text-content-muted">
            Loading…
          </p>
        ) : areaTasks.length === 0 && areaJobs.length === 0 ? (
          <p className="py-10 text-center text-body-sm text-content-muted">
            Nothing lives in {area} yet.
          </p>
        ) : (
          <>
            {/* THE WORK LEADS — job cards (Reframe R-2). A shared
                automation appears under BOTH its jobs; each card honest. */}
            {areaJobs.length > 0 ? (
              <section data-testid="map-job-section">
                <h2 className="text-caption font-medium uppercase tracking-wide text-content-subtle">
                  Tasks
                </h2>
                <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {areaJobs.map((j) => (
                    <JobCard key={j.id} job={j} onPonder={ponderJob} />
                  ))}
                </div>
              </section>
            ) : null}

            {/* THE ENGINE ROOM — the automations beneath, collapsed by
                default when jobs lead (the shipped cards intact; every
                editing flow unchanged). No jobs → the automations stand
                open as before (nothing hidden behind an empty idea). */}
            {areaTasks.length > 0 ? (
              areaJobs.length > 0 ? (
                <section data-testid="map-engine-room">
                  <button
                    type="button"
                    onClick={() => toggleEngineRoom(area)}
                    aria-expanded={engineOpen.has(area)}
                    className="focus-ring-accent -ml-1 flex items-center gap-1.5 rounded-md px-1 py-0.5"
                    data-testid="map-engine-room-toggle"
                  >
                    <ChevronDown
                      size={14}
                      className={
                        "text-content-subtle transition-transform duration-quick ease-settle " +
                        (engineOpen.has(area) ? "" : "-rotate-90")
                      }
                    />
                    <h2 className="text-caption font-medium uppercase tracking-wide text-content-subtle">
                      The engine room
                    </h2>
                    <span className="text-caption text-content-subtle">
                      {areaTasks.length} automation{areaTasks.length === 1 ? "" : "s"}
                    </span>
                  </button>
                  {engineOpen.has(area) ? (
                    <div className="mt-3" data-testid="map-engine-room-body">
                      <TaskSections
                        tasks={areaTasks}
                        onPonder={ponderTask}
                        onOpenOffer={openOffer}
                        canAdd={isAdmin}
                        onAdd={openAdd}
                        sectionTitleOverride="Automations"
                      />
                    </div>
                  ) : null}
                </section>
              ) : (
                <TaskSections
                  tasks={areaTasks}
                  onPonder={ponderTask}
                  onOpenOffer={openOffer}
                  canAdd={isAdmin}
                  onAdd={openAdd}
                  sectionTitleOverride="Automations"
                />
              )
            ) : null}
          </>
        )}

        {overlays}
      </div>
    </PonderServiceContext.Provider>
  )
}
