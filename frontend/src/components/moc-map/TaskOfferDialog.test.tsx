/**
 * P3 — the offer dialog: the prose-grammar diff, per-field keep-mine,
 * accept/decline for admins, honest read-only for everyone else.
 */
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import { TaskOfferDialog } from "./TaskOfferDialog"
import * as svc from "@/services/moc-map-service"

vi.mock("@/services/moc-map-service", async () => {
  const actual = await vi.importActual<typeof svc>("@/services/moc-map-service")
  return {
    ...actual,
    getTaskOffer: vi.fn(),
    acceptTaskOffer: vi.fn().mockResolvedValue({ task_id: "t", applied: [], kept: [] }),
    declineTaskOffer: vi.fn().mockResolvedValue({ status: "declined" }),
  }
})

const OFFER = {
  id: "offer-1", task_id: "fork-1", version_from: 0, version_to: 1,
  patch_notes: "Back to Mondays.",
  diff: {
    fields: {
      schedule: {
        from: ["The last Friday of every month at 9:30 AM"],
        to: ["The first Monday of every month at 4:00 PM"],
      },
      description: { from: "Tenant words.", to: "The standard description." },
    },
    summary: "description, schedule",
  },
  status: "pending" as const,
  created_at: "2026-07-16T00:00:00Z",
}

describe("TaskOfferDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(svc.getTaskOffer).mockResolvedValue(structuredClone(OFFER))
  })

  it("renders the note + the diff in the prose grammar", async () => {
    render(
      <TaskOfferDialog offerId="offer-1" taskName="Monthly Statement Run"
        canDecide onClose={() => {}} onDecided={() => {}} />,
    )
    await waitFor(() =>
      expect(screen.getByTestId("task-offer-notes-display").textContent)
        .toContain("Back to Mondays"))
    const sched = screen.getByTestId("task-offer-field-schedule")
    expect(sched.textContent).toContain("The last Friday of every month at 9:30 AM")
    expect(sched.textContent).toContain("The first Monday of every month at 4:00 PM")
  })

  it("accept sends per-field keep-mine choices", async () => {
    const onDecided = vi.fn()
    render(
      <TaskOfferDialog offerId="offer-1" taskName="T" canDecide
        onClose={() => {}} onDecided={onDecided} />,
    )
    await waitFor(() => screen.getByTestId("task-offer-keep-description"))
    fireEvent.click(screen.getByTestId("task-offer-keep-description"))
    fireEvent.click(screen.getByTestId("task-offer-accept"))
    await waitFor(() => expect(svc.acceptTaskOffer).toHaveBeenCalledWith(
      "offer-1", { description: "keep" },
    ))
    expect(onDecided).toHaveBeenCalled()
  })

  it("decline is available on pending offers", async () => {
    render(
      <TaskOfferDialog offerId="offer-1" taskName="T" canDecide
        onClose={() => {}} onDecided={() => {}} />,
    )
    await waitFor(() => screen.getByTestId("task-offer-decline"))
    fireEvent.click(screen.getByTestId("task-offer-decline"))
    await waitFor(() => expect(svc.declineTaskOffer).toHaveBeenCalledWith("offer-1"))
  })

  it("a declined offer reopens recallable (no decline button, accept stands)", async () => {
    vi.mocked(svc.getTaskOffer).mockResolvedValue({ ...structuredClone(OFFER), status: "declined" })
    render(
      <TaskOfferDialog offerId="offer-1" taskName="T" canDecide
        onClose={() => {}} onDecided={() => {}} />,
    )
    await waitFor(() => screen.getByTestId("task-offer-declined-note"))
    expect(screen.queryByTestId("task-offer-decline")).toBeNull()
    expect(screen.getByTestId("task-offer-accept")).toBeInTheDocument()
  })

  it("non-admins read; no dead decision controls", async () => {
    render(
      <TaskOfferDialog offerId="offer-1" taskName="T" canDecide={false}
        onClose={() => {}} onDecided={() => {}} />,
    )
    await waitFor(() => screen.getByTestId("task-offer-field-schedule"))
    expect(screen.queryByTestId("task-offer-accept")).toBeNull()
    expect(screen.queryByTestId("task-offer-keep-description")).toBeNull()
    expect(screen.getByText("An admin can apply this update.")).toBeInTheDocument()
  })
})
