/**
 * JobCard — the map's new face (Reframe R-2): one JOB (displayed Task),
 * the work leading; the machines serve beneath.
 *
 * DL discipline as TaskCard set it: material-not-paint (elevated + shadow
 * lift, no perimeter border), the calm body carries name + story, the
 * detail budget goes to the QUEUE PENDING chip (decision-weight — accent
 * when work waits) and the hold-P ring. The composition glance is quiet
 * arithmetic: "N automations · M live"; the pending count only renders
 * when the read is permission-honest (null = absence, never zero).
 *
 * EDITING HONESTY (v1): jobs are pedagogy — no fork/edit affordances here;
 * editing lives on AUTOMATIONS (the ponder's automation beats are the
 * path). Hold-P + click both open the job ponder.
 */
import { useCallback } from "react"
import { Inbox, Landmark, Radio, Workflow as WorkflowIcon } from "lucide-react"

import {
  HoldRing, useHoldToPonder,
} from "@/bridgeable-admin/components/moc/MoCTaskTable"
import type { MapJob } from "@/services/moc-map-service"

export function JobCard({
  job, onPonder,
}: {
  job: MapJob
  onPonder: (jobId: string) => void
}) {
  const complete = useCallback(() => onPonder(job.id), [onPonder, job.id])
  const { hovered, holding, reduced, hoverProps } = useHoldToPonder(true, complete)
  const { automation_count, live_count, queue_pending } = job.glance
  // The never-face: coming jobs wear the map's "coming" treatment —
  // dashed, quieter material — distinct from real cards at a glance.
  // is_coming flips false by REALITY (the arc landing), never a flag.
  const isComing = job.coming?.is_coming === true

  return (
    <div
      {...hoverProps}
      role="button"
      tabIndex={0}
      onClick={() => onPonder(job.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          onPonder(job.id)
        }
      }}
      className={
        isComing
          ? "group flex min-h-[8rem] cursor-pointer flex-col rounded-md border border-dashed border-border-base bg-surface-elevated/60 p-4 transition-shadow duration-quick ease-settle hover:shadow-level-1 focus-ring-accent"
          : "group flex min-h-[8rem] cursor-pointer flex-col rounded-md bg-surface-elevated p-4 shadow-level-1 transition-shadow duration-quick ease-settle hover:shadow-level-2 focus-ring-accent"
      }
      data-testid={`map-job-${job.id}`}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="flex items-center gap-2 text-body font-medium leading-snug text-content-strong">
          {job.name}
          {isComing ? (
            <span
              className="rounded-full bg-surface-sunken px-1.5 py-0.5 text-micro font-normal text-content-subtle"
              data-testid={`map-job-coming-${job.id}`}
            >
              coming
            </span>
          ) : null}
        </p>
        {hovered ? (
          <span
            className="flex flex-none items-center gap-1.5 whitespace-nowrap text-caption text-content-muted"
            data-testid="map-hold-hint"
          >
            <HoldRing holding={holding} reduced={reduced} />
            Hold{" "}
            <kbd className="rounded-sm border border-border-base px-1 font-plex-mono text-micro">
              P
            </kbd>
          </span>
        ) : null}
      </div>

      {job.description ? (
        <p className="mt-1.5 line-clamp-2 text-body-sm leading-relaxed text-content-muted">
          {job.description}
        </p>
      ) : null}

      {job.glance_live ? (
        <p
          className={
            job.glance_live.kind === "live"
              ? "mt-1.5 text-body-sm font-medium text-content-strong"
              : "mt-1.5 text-body-sm text-content-subtle"
          }
          title={job.glance_live.as_of ? `as of ${new Date(job.glance_live.as_of).toLocaleString()}` : undefined}
          data-testid={`map-job-glance-live-${job.id}`}
        >
          <Landmark size={11} className="mr-1 inline-block text-content-subtle" />
          {job.glance_live.text}
        </p>
      ) : null}

      {/* The composition glance — honest arithmetic, quiet. */}
      <div className="mt-auto flex items-center gap-2 pt-3">
        {automation_count > 0 ? (
          <span
            className="inline-flex items-center gap-1.5 text-caption text-content-muted"
            data-testid={`map-job-glance-${job.id}`}
          >
            <WorkflowIcon size={11} className="flex-none text-content-subtle" />
            {automation_count} automation{automation_count === 1 ? "" : "s"}
            {live_count > 0 ? (
              <span className="inline-flex items-center gap-0.5 text-accent">
                <Radio size={9} /> {live_count} live
              </span>
            ) : null}
          </span>
        ) : null}
        {/* THE JEWELRY: pending work is decision-weight — accent when it
            waits, quiet when clear, ABSENT when we can't honestly know. */}
        {queue_pending !== null && queue_pending !== undefined ? (
          queue_pending > 0 ? (
            <span
              className="ml-auto inline-flex flex-none items-center gap-1 rounded-full bg-accent-subtle px-2 py-0.5 text-micro font-medium text-accent"
              data-testid={`map-job-pending-${job.id}`}
            >
              <Inbox size={9} /> {queue_pending} waiting
            </span>
          ) : (
            <span
              className="ml-auto flex-none rounded-full bg-surface-sunken px-2 py-0.5 text-micro text-content-subtle"
              data-testid={`map-job-clear-${job.id}`}
            >
              nothing waiting
            </span>
          )
        ) : null}
      </div>
    </div>
  )
}
