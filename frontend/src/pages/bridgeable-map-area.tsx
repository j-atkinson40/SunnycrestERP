/**
 * THE AREA PAGE — the sections-with-cards layout, RE-HOMED per-area
 * (The Map Home campaign; nothing discarded — the Sunnycrest Workshop's
 * layout is this page now). Breadcrumbed back to the home; the same
 * overlay machinery (ponder, fork, offers, add) rides along.
 */
import { useCallback, useEffect, useMemo, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { ChevronRight, Map as MapIcon } from "lucide-react"

import {
  PonderServiceContext,
} from "@/bridgeable-admin/components/moc/ponder-service-context"
import {
  getMapTasks, tenantPonderService, type MapTask,
} from "@/services/moc-map-service"
import { TaskSections } from "@/components/moc-map/TaskSections"
import { useMapOverlays } from "@/components/moc-map/useMapOverlays"

export default function BridgeableMapAreaPage() {
  const { area = "" } = useParams<{ area: string }>()
  const [tasks, setTasks] = useState<MapTask[]>([])
  const [vertical, setVertical] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const reload = useCallback(async () => {
    const data = await getMapTasks()
    setTasks(data.tasks)
    setVertical(data.vertical)
  }, [])

  useEffect(() => {
    reload().finally(() => setLoading(false))
  }, [reload])

  const areaTasks = useMemo(
    () => tasks.filter((t) => (t.task_type || "General") === area),
    [tasks, area],
  )

  const {
    ponderTask, ponderArea, openOffer, openAdd, overlays, isAdmin,
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
            Every {area} task on your map — hold{" "}
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

        {loading ? (
          <p className="py-10 text-center text-body-sm text-content-muted">
            Loading…
          </p>
        ) : areaTasks.length === 0 ? (
          <p className="py-10 text-center text-body-sm text-content-muted">
            Nothing lives in {area} yet.
          </p>
        ) : (
          <TaskSections
            tasks={areaTasks}
            onPonder={ponderTask}
            onOpenOffer={openOffer}
            canAdd={isAdmin}
            onAdd={openAdd}
          />
        )}

        {overlays}
      </div>
    </PonderServiceContext.Provider>
  )
}
