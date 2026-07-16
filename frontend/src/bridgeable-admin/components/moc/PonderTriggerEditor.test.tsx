/**
 * Tenant Ponder-Editor P1 — the trigger beat editor + the prose readback.
 *
 * The readback IS the derivation grammar in reverse: composing a schedule
 * renders the sentence the beat will speak. These tests pin (a) the TS
 * mirror of the backend grammar, (b) the composer → config shapes the T-1b
 * validator accepts, (c) the editor's write-then-rederive loop (save calls
 * the service; onSaved refetches), (d) the confirmGate short-circuit (the
 * live-edit confirm's hook — resolve false → no write).
 */
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import { scheduleProse } from "./schedule-prose"
import { PonderTriggerEditor } from "./PonderTriggerEditor"
import * as svc from "@/bridgeable-admin/services/moc-service"

vi.mock("@/bridgeable-admin/services/moc-service", async () => {
  const actual = await vi.importActual<typeof svc>("@/bridgeable-admin/services/moc-service")
  return {
    ...actual,
    addTaskTrigger: vi.fn().mockResolvedValue({}),
    patchTrigger: vi.fn().mockResolvedValue({}),
    deleteTrigger: vi.fn().mockResolvedValue(undefined),
    listTriggerEvents: vi.fn().mockResolvedValue([]),
  }
})

describe("scheduleProse — the readback grammar", () => {
  it("speaks the dispatch sentence", () => {
    expect(scheduleProse({
      spec_kind: "ordinal_weekday", ordinal: 1, weekday: "mon", time: "16:00",
    })).toBe("The first Monday of every month at 4:00 PM")
  })

  it("last Friday", () => {
    expect(scheduleProse({
      spec_kind: "ordinal_weekday", ordinal: "last", weekday: "fri", time: "09:30",
    })).toBe("The last Friday of every month at 9:30 AM")
  })

  it("daily + weekly time_of_day", () => {
    expect(scheduleProse({ spec_kind: "time_of_day", time: "23:30", days: [] }))
      .toBe("Every night at 11:30 PM")
    expect(scheduleProse({ spec_kind: "time_of_day", time: "18:00", days: ["mon", "wed"] }))
      .toBe("At 6:00 PM on Mon, Wed")
  })

  it("cron shows itself honestly", () => {
    expect(scheduleProse({ spec_kind: "cron", cron: "0 6 1 * *" }))
      .toContain("0 6 1 * *")
  })
})

const schedTrigger = {
  id: "trig-1", kind: "schedule" as const,
  config: { spec_kind: "ordinal_weekday", ordinal: 1, weekday: "mon", time: "16:00" },
  display_order: 0, is_active: true, is_live: false,
  summary: "Monthly · 1st Mon, 4:00 PM",
}

describe("PonderTriggerEditor", () => {
  beforeEach(() => vi.clearAllMocks())

  it("lists triggers with their summary and edit affordance", () => {
    render(
      <PonderTriggerEditor taskId="task-1" triggers={[schedTrigger]} onSaved={() => {}} />,
    )
    expect(screen.getByText("Monthly · 1st Mon, 4:00 PM")).toBeInTheDocument()
    expect(screen.getByTestId("ponder-trigger-edit-trig-1")).toBeInTheDocument()
  })

  it("live triggers wear the live badge", () => {
    render(
      <PonderTriggerEditor
        taskId="task-1"
        triggers={[{ ...schedTrigger, is_live: true }]}
        onSaved={() => {}}
      />,
    )
    expect(screen.getByTestId("ponder-trigger-live-badge")).toBeInTheDocument()
  })

  it("opens the composer with the LIVE readback and re-derives on save", async () => {
    const onSaved = vi.fn()
    render(
      <PonderTriggerEditor taskId="task-1" triggers={[schedTrigger]} onSaved={onSaved} />,
    )
    fireEvent.click(screen.getByTestId("ponder-trigger-edit-trig-1"))
    // The readback speaks the beat's own sentence, live.
    expect(screen.getByTestId("ponder-schedule-readback").textContent)
      .toContain("The first Monday of every month at 4:00 PM")
    // Recompose: last Friday.
    fireEvent.change(screen.getByTestId("ponder-ordinal"), { target: { value: "last" } })
    fireEvent.change(screen.getByTestId("ponder-weekday"), { target: { value: "fri" } })
    expect(screen.getByTestId("ponder-schedule-readback").textContent)
      .toContain("The last Friday of every month")
    fireEvent.click(screen.getByTestId("ponder-schedule-save"))
    await waitFor(() => expect(svc.patchTrigger).toHaveBeenCalledWith("trig-1", {
      config: { spec_kind: "ordinal_weekday", ordinal: "last", weekday: "fri", time: "16:00" },
    }))
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
  })

  it("adds an ordinal schedule through the add flow", async () => {
    const onSaved = vi.fn()
    render(<PonderTriggerEditor taskId="task-1" triggers={[]} onSaved={onSaved} />)
    fireEvent.click(screen.getByTestId("ponder-trigger-add"))
    fireEvent.click(screen.getByTestId("ponder-add-kind-schedule"))
    fireEvent.click(screen.getByTestId("ponder-schedule-save"))
    await waitFor(() => expect(svc.addTaskTrigger).toHaveBeenCalledWith("task-1", {
      kind: "schedule",
      config: { spec_kind: "ordinal_weekday", ordinal: 1, weekday: "mon", time: "16:00" },
    }))
  })

  it("confirmGate=false blocks the write (the live-edit gravity)", async () => {
    const gate = vi.fn().mockResolvedValue(false)
    render(
      <PonderTriggerEditor
        taskId="task-1" triggers={[schedTrigger]} onSaved={() => {}}
        confirmGate={gate}
      />,
    )
    fireEvent.click(screen.getByTestId("ponder-trigger-delete-trig-1"))
    await waitFor(() => expect(gate).toHaveBeenCalled())
    expect(svc.deleteTrigger).not.toHaveBeenCalled()
  })

  it("confirmGate=true lets the write through", async () => {
    const gate = vi.fn().mockResolvedValue(true)
    const onSaved = vi.fn()
    render(
      <PonderTriggerEditor
        taskId="task-1" triggers={[schedTrigger]} onSaved={onSaved}
        confirmGate={gate}
      />,
    )
    fireEvent.click(screen.getByTestId("ponder-trigger-delete-trig-1"))
    await waitFor(() => expect(svc.deleteTrigger).toHaveBeenCalledWith("trig-1"))
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
  })

  it("surfaces the validator's reason on a rejected save", async () => {
    vi.mocked(svc.patchTrigger).mockRejectedValueOnce({
      response: { data: { detail: "ordinal_weekday requires 'time' as HH:MM" } },
    })
    render(
      <PonderTriggerEditor taskId="task-1" triggers={[schedTrigger]} onSaved={() => {}} />,
    )
    fireEvent.click(screen.getByTestId("ponder-trigger-edit-trig-1"))
    fireEvent.click(screen.getByTestId("ponder-schedule-save"))
    await waitFor(() =>
      expect(screen.getByTestId("ponder-trigger-error").textContent)
        .toContain("requires 'time'"),
    )
  })
})
