/**
 * The Integrations area (2026-07-18) — the platform's engine room, the
 * grammar every future integration inherits. One real card today; the
 * room reads intentional, not empty.
 *
 * STATUS-LED: healthy / needs re-connecting / disconnected at a glance.
 * THE DERIVED DEPENDENTS: the job-ref spine queried live — nobody
 * maintains it. The grown B-3 connection card is RE-HOMED here whole.
 */
import { useCallback, useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { Plug, Tags } from "lucide-react"

import apiClient from "@/lib/api-client"
import {
  HoldRing, useHoldToPonder,
} from "@/bridgeable-admin/components/moc/MoCTaskTable"
import { ConnectBankCard } from "./ConnectBankCard"

interface IntegrationSummary {
  key: string
  title: string
  face: "never" | "degraded" | "connected"
  institution_name: string | null
  dependents: { jobs: string[]; automation_count: number }
}

const FACE_CHIP: Record<IntegrationSummary["face"], { label: string; cls: string }> = {
  connected: { label: "healthy", cls: "bg-status-success-muted text-status-success" },
  degraded: { label: "needs re-connecting", cls: "bg-status-warning-muted text-status-warning" },
  never: { label: "not connected", cls: "bg-surface-sunken text-content-subtle" },
}

function IntegrationCard({
  ig, onPonder,
}: {
  ig: IntegrationSummary
  onPonder: (overlayId: string) => void
}) {
  const complete = () => onPonder(`integration:${ig.key}`)
  const { hovered, holding, reduced, hoverProps } = useHoldToPonder(true, complete)
  return (
    <div
      {...hoverProps}
      role="button"
      tabIndex={0}
      onClick={complete}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); complete() }
      }}
      className="group flex min-h-[8rem] cursor-pointer flex-col rounded-md bg-surface-elevated p-4 shadow-level-1 transition-shadow duration-quick ease-settle hover:shadow-level-2 focus-ring-accent"
      data-testid={`integration-card-${ig.key}`}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="flex items-center gap-2 text-body font-medium leading-snug text-content-strong">
          <Plug size={14} className="flex-none text-accent" /> {ig.title}
        </p>
        {hovered ? (
          <span className="flex flex-none items-center gap-1.5 whitespace-nowrap text-caption text-content-muted">
            <HoldRing holding={holding} reduced={reduced} />
            Hold{" "}
            <kbd className="rounded-sm border border-border-base px-1 font-plex-mono text-micro">P</kbd>
          </span>
        ) : null}
      </div>

      {ig.dependents.jobs.length > 0 ? (
        <p className="mt-1.5 line-clamp-2 text-body-sm leading-relaxed text-content-muted"
          data-testid={`integration-deps-${ig.key}`}>
          Feeds {ig.dependents.jobs.join(" and ")} —{" "}
          {ig.dependents.automation_count} automation
          {ig.dependents.automation_count === 1 ? "" : "s"} depend on this.
        </p>
      ) : null}

      <div className="mt-auto flex items-center gap-2 pt-3">
        {ig.institution_name ? (
          <span className="text-caption text-content-muted">{ig.institution_name}</span>
        ) : (
          <span className="text-caption text-content-subtle">no connection yet</span>
        )}
        <span className={`ml-auto rounded-full px-2 py-0.5 text-micro font-medium ${FACE_CHIP[ig.face].cls}`}
          data-testid={`integration-face-${ig.key}`}>
          {FACE_CHIP[ig.face].label}
        </span>
      </div>
    </div>
  )
}

export function IntegrationsArea({
  isAdmin, onPonder,
}: {
  isAdmin: boolean
  /** Opens the per-integration ponder (overlay id `integration:<key>`). */
  onPonder: (overlayId: string) => void
}) {
  const [integrations, setIntegrations] = useState<IntegrationSummary[]>([])
  const [params] = useSearchParams()
  const autoConnect = params.get("connect") === "1"

  const load = useCallback(() => {
    apiClient.get("/moc/integrations/summary")
      .then((r) => setIntegrations(r.data.integrations))
      .catch(() => setIntegrations([]))
  }, [])
  useEffect(() => { load() }, [load])

  return (
    <div className="space-y-6" data-testid="integrations-area">
      <section>
        <h2 className="text-caption font-medium uppercase tracking-wide text-content-subtle">
          Connections
        </h2>
        <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {integrations.map((ig) => (
            <IntegrationCard key={ig.key} ig={ig} onPonder={onPonder} />
          ))}
        </div>
      </section>

      {/* THE MANAGEMENT — the grown B-3 card, beneath the grid. */}
      <div>
        <ConnectBankCard isAdmin={isAdmin} autoConnect={autoConnect} />
        <Link
          to="/settings/bank-categories"
          className="focus-ring-accent mt-2 inline-flex items-center gap-1.5 rounded-md text-body-sm text-accent underline-offset-2 hover:underline"
          data-testid="integrations-category-link"
        >
          <Tags size={13} /> Bank categories — how transactions get named
        </Link>
      </div>
    </div>
  )
}
