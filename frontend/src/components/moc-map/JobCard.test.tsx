/**
 * Reframe R-2 — the job card (the map's new face) + the honest glance.
 *
 *  * The composition glance: "N automations · M live" — quiet arithmetic.
 *  * THE PENDING CHIP is permission-honest: a number when the read was
 *    honest (accent when work waits; quiet "nothing waiting" at zero),
 *    ABSENT when null — never a lie, never a fake zero.
 *  * No edit/fork affordances — jobs are pedagogy in v1; editing lives on
 *    automations (the ponder's beats are the path).
 */
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { JobCard } from "./JobCard"
import type { MapJob } from "@/services/moc-map-service"

function job(over: Partial<MapJob>): MapJob {
  return {
    id: over.id ?? "j1",
    name: "Bank reconciliation",
    display_order: 0,
    refs: [],
    dead_refs: [],
    glance: { automation_count: 1, live_count: 1, queue_pending: 3 },
    ...over,
  } as MapJob
}

describe("JobCard", () => {
  it("the glance + the accent pending chip when work waits", () => {
    render(<JobCard job={job({})} onPonder={() => {}} />)
    expect(screen.getByTestId("map-job-glance-j1").textContent)
      .toContain("1 automation")
    expect(screen.getByTestId("map-job-glance-j1").textContent)
      .toContain("1 live")
    expect(screen.getByTestId("map-job-pending-j1").textContent)
      .toContain("3 waiting")
  })

  it("zero pending reads quiet, not absent", () => {
    render(
      <JobCard
        job={job({ id: "j2", glance: { automation_count: 2, live_count: 0, queue_pending: 0 } })}
        onPonder={() => {}}
      />,
    )
    expect(screen.getByTestId("map-job-clear-j2")).toBeTruthy()
    expect(screen.queryByTestId("map-job-pending-j2")).toBeNull()
  })

  it("null pending is HONEST ABSENCE — no chip at all", () => {
    render(
      <JobCard
        job={job({ id: "j3", glance: { automation_count: 1, live_count: 0, queue_pending: null } })}
        onPonder={() => {}}
      />,
    )
    expect(screen.queryByTestId("map-job-pending-j3")).toBeNull()
    expect(screen.queryByTestId("map-job-clear-j3")).toBeNull()
  })

  it("click opens the job ponder; no edit affordances exist", () => {
    const onPonder = vi.fn()
    render(<JobCard job={job({ id: "j4" })} onPonder={onPonder} />)
    fireEvent.click(screen.getByTestId("map-job-j4"))
    expect(onPonder).toHaveBeenCalledWith("j4")
    expect(screen.queryByText(/edit|fork/i)).toBeNull()
  })
})
