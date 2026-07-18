/**
 * THE BRIDGEABLE MAP — HOME (The Map Home campaign): the adaptive
 * three-part home.
 *
 *   1. THE RAIL (above) — rule-based suggestions, each carrying its honest
 *      why; empty-honest; AUGMENTS, never reorders what's below.
 *   2. THE STABLE SPINE — area cards derived from the vocabulary
 *      types-with-content. THE NAVIGATION GUARANTEE: the spine never
 *      reorders by personalization — the same areas in the same places,
 *      every visit. Hover + hold-P → the area overview ponder; click →
 *      the area page (the sections/cards layout, re-homed per-area).
 *   3. THE "YOURS" SECTION — the tenant's forks + additions gathered, each
 *      card ponderable, each linking into its area page.
 *
 * DELIBERATE ROOM: capability cards slot into areas later; the home's
 * composition accepts new sections without restructure.
 */
import { useCallback, useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { FileText, Map as MapIcon, Plus, Sparkles } from "lucide-react"

import apiClient from "@/lib/api-client"
import { useAuth } from "@/contexts/auth-context"
import { Button } from "@/components/ui/button"
import {
  PonderServiceContext,
} from "@/bridgeable-admin/components/moc/ponder-service-context"
import {
  getMapJobs, getMapTasks, tenantPonderService,
  type MapJob, type MapTask,
} from "@/services/moc-map-service"
import { AreaCard, type AreaSummary } from "@/components/moc-map/AreaCard"
import { SuggestionsRail } from "@/components/moc-map/SuggestionsRail"
import { TaskCard } from "@/components/moc-map/TaskCard"
import { deriveSections } from "@/components/moc-map/TaskSections"
import { useMapOverlays } from "@/components/moc-map/useMapOverlays"

/** The spine's summaries — derived, STABLE (alphabetical, General last —
 * the same order deriveSections pins; personalization never touches it). */
export function deriveAreaSummaries(tasks: MapTask[]): AreaSummary[] {
  return deriveSections(tasks).map(({ type, tasks: sectionTasks }) => ({
    area: type,
    taskCount: sectionTasks.length,
    liveCount: sectionTasks.filter((t) =>
      (t.triggers ?? []).some((tr) => tr.is_live && tr.is_active !== false),
    ).length,
  }))
}

export default function BridgeableMapPage() {
  const { isAdmin } = useAuth()
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<MapTask[]>([])
  const [jobs, setJobs] = useState<MapJob[]>([])
  const [vertical, setVertical] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [platformAreas, setPlatformAreas] = useState<Array<{ area: string }>>([])

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

  useEffect(() => {
    reload().finally(() => setLoading(false))
    apiClient.get("/moc/platform-areas")
      .then((r) => setPlatformAreas(r.data))
      .catch(() => setPlatformAreas([]))
  }, [reload])

  const {
    ponderTask, ponderArea, ponderKeyed, openOffer, openAdd, overlays,
  } = useMapOverlays({ tasks, vertical, reload })

  const areas = useMemo(() => deriveAreaSummaries(tasks), [tasks])
  // Honest arithmetic per area: jobs count where jobs exist (Reframe R-2).
  const jobCounts = useMemo(() => {
    const by = new Map<string, number>()
    for (const j of jobs) {
      const a = j.task_type || "General"
      by.set(a, (by.get(a) ?? 0) + 1)
    }
    return by
  }, [jobs])
  const yours = useMemo(
    () => tasks.filter((t) => t.scope === "tenant_override"),
    [tasks],
  )

  return (
    <PonderServiceContext.Provider value={tenantPonderService}>
      <div className="space-y-8 p-6" data-testid="bridgeable-map-page">
        <div>
          <h1 className="flex items-center gap-2.5 text-h1 font-semibold text-content-strong">
            <MapIcon size={26} className="text-accent" strokeWidth={1.8} />
            Bridgeable Map
          </h1>
          <p className="mt-1 max-w-2xl text-body text-content-muted">
            The map of what your platform does. Each card is an area of your
            business — hold{" "}
            <kbd className="rounded-sm border border-border-base px-1 font-plex-mono text-caption">P</kbd>{" "}
            on one for the story, click it for the work inside.
          </p>
        </div>

        {/* 1. THE RAIL — augments; never reorders the spine below. */}
        <SuggestionsRail onOpen={(s) => ponderKeyed(s.ponder_key)} refreshToken={tasks} />

        {/* 2. THE STABLE SPINE — the areas, in the same places every visit. */}
        {loading ? (
          <p className="py-10 text-center text-body-sm text-content-muted">
            Loading the map…
          </p>
        ) : areas.length === 0 ? (
          <p className="py-10 text-center text-body-sm text-content-muted">
            No automations yet — your vertical's defaults appear here as they ship.
          </p>
        ) : (
          <section data-testid="map-area-spine">
            <h2 className="text-caption font-medium uppercase tracking-wide text-content-subtle">
              Your areas
            </h2>
            <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              {areas.map((a) => (
                <AreaCard
                  key={a.area}
                  summary={a}
                  jobCount={jobCounts.get(a.area) ?? 0}
                  onPonder={ponderArea}
                  onOpen={(area) => navigate(`/bridgeable-map/${encodeURIComponent(area)}`)}
                />
              ))}
              {/* THE PLATFORM ROOMS — the spine absorbs them (stable
                  order after the business areas; the map teaches
                  Bridgeable, not just the tenant's work). */}
              {platformAreas.map((pa) => (
                <div
                  key={pa.area}
                  role="button"
                  tabIndex={0}
                  onClick={() => navigate(`/bridgeable-map/${encodeURIComponent(pa.area)}`)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault()
                      navigate(`/bridgeable-map/${encodeURIComponent(pa.area)}`)
                    }
                  }}
                  className="focus-ring-accent flex min-h-[6rem] cursor-pointer flex-col justify-between rounded-md border border-dashed border-border-base bg-surface-elevated/60 p-4 transition-shadow duration-quick ease-settle hover:shadow-level-1"
                  data-testid={`map-platform-area-${pa.area}`}
                >
                  <p className="text-body font-medium text-content-strong">{pa.area}</p>
                  <p className="text-body-sm text-content-muted">
                    {pa.area === "Platform"
                      ? "How Bridgeable itself works — the primitives."
                      : pa.area === "Onboarding & Setup"
                        ? "The path in — every step visible, none locked."
                        : "What's not turned on yet — and what's coming."}
                  </p>
                </div>
              ))}
              {/* THE INTEGRATIONS ROOM (2026-07-18) — admin-led
                  visibility; one deliberate card, status at a glance. */}
              {isAdmin ? (
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => navigate("/bridgeable-map/Integrations")}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault()
                      navigate("/bridgeable-map/Integrations")
                    }
                  }}
                  className="focus-ring-accent flex min-h-[6rem] cursor-pointer flex-col justify-between rounded-md border border-dashed border-border-base bg-surface-elevated/60 p-4 transition-shadow duration-quick ease-settle hover:shadow-level-1"
                  data-testid="map-integrations-card"
                >
                  <p className="text-body font-medium text-content-strong">
                    Integrations
                  </p>
                  <p className="text-body-sm text-content-muted">
                    The platform's connections — banks today, more to come.
                  </p>
                </div>
              ) : null}
            </div>
          </section>
        )}

        {/* 3. YOURS — the pills' content given a home. */}
        {yours.length > 0 ? (
          <section data-testid="map-yours-section">
            <h2 className="text-caption font-medium uppercase tracking-wide text-content-subtle">
              Yours
            </h2>
            <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              {yours.map((t) => (
                <TaskCard
                  key={t.id}
                  task={t}
                  onPonder={ponderTask}
                  onOpenOffer={openOffer}
                  areaHref={`/bridgeable-map/${encodeURIComponent(t.task_type || "General")}`}
                />
              ))}
            </div>
          </section>
        ) : null}

        {isAdmin && !loading ? (
          <div>
            <Button
              variant="outline" size="sm"
              onClick={() => openAdd(null)}
              data-testid="map-add-task-button"
            >
              <Plus size={14} /> Add an automation
            </Button>
          </div>
        ) : null}

        {/* THE ROOM — coming sections read as room, not shrug. */}
        <section className="grid gap-4 md:grid-cols-2" data-testid="map-room">
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

        {overlays}
      </div>
    </PonderServiceContext.Provider>
  )
}
