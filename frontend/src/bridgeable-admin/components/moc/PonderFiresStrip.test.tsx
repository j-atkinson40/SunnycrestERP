/**
 * P3 — the fires strip: honest badges, the H1 deep link role-mapped
 * (never a dead link), the plain never-fired empty state.
 */
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import { PonderFiresStrip } from "./PonderFiresStrip"
import type { PonderFire } from "@/bridgeable-admin/services/moc-service"

const fires: PonderFire[] = [
  { run_id: "r1", started_at: "2026-07-14T16:00:00Z", status: "completed",
    is_dry_run: true, source: "moc_task_schedule", event_key: null },
  { run_id: "r2", started_at: "2026-07-15T16:00:00Z", status: "failed",
    is_dry_run: false, source: "schedule", event_key: "order.created",
    review_item_id: "rev-1" },
]

function mount(el: React.ReactElement) {
  return render(<MemoryRouter>{el}</MemoryRouter>)
}

describe("PonderFiresStrip", () => {
  it("renders the ledger with honest dry-run/live badges + provenance", () => {
    mount(<PonderFiresStrip fires={fires} canFollowReviews />)
    expect(screen.getByTestId("ponder-fire-r1").textContent).toContain("dry-run")
    expect(screen.getByTestId("ponder-fire-r2").textContent).toContain("live")
    expect(screen.getByTestId("ponder-fire-r2").textContent).toContain("failed")
    expect(screen.getByTestId("ponder-fire-r2").textContent).toContain("order created")
  })

  it("a failed fire deep-links to Decision Triage for roles that can follow", () => {
    mount(<PonderFiresStrip fires={fires} canFollowReviews />)
    const link = screen.getByTestId("ponder-fire-review-r2")
    expect(link.getAttribute("href")).toBe("/triage/workflow_review_triage")
  })

  it("no dead links: without the role, the honest status stands alone", () => {
    mount(<PonderFiresStrip fires={fires} canFollowReviews={false} />)
    expect(screen.queryByTestId("ponder-fire-review-r2")).toBeNull()
    expect(screen.getByTestId("ponder-fire-r2").textContent).toContain("failed")
  })

  it("never-fired says so plainly, with the dry-run/live state", () => {
    mount(<PonderFiresStrip fires={[]} isLive={false} />)
    expect(screen.getByTestId("ponder-fires-empty").textContent)
      .toContain("Hasn't run yet — it previews in dry-run")
    mount(<PonderFiresStrip fires={[]} isLive />)
    expect(screen.getAllByTestId("ponder-fires-empty")[1].textContent)
      .toContain("its trigger is live")
  })
})
