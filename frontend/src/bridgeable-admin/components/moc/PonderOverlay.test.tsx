/** PonderOverlay — scrub, replay, edit-mode pins (P1). */
import { describe, expect, it, vi, beforeEach } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import { PonderOverlay } from "./PonderOverlay"

const SCRIPT = {
  task_id: "t1",
  task_name: "Monthly Statement Run",
  workflow_name: "Monthly Statement Run",
  beats: [
    { key: "when", kind: "when", text: "The 1st of each month at 6:00 AM (tenant-local).", derived_text: "same", authored: false },
    { key: "step:identify_customers", kind: "step", text: "Find charge-account customers with activity", derived_text: "Find charge-account customers with activity", authored: false, label: "identify customers", node_type: "action" },
    { key: "pause:approval_gate", kind: "pause", text: "Review flagged statements", derived_text: "Review flagged statements", authored: false, label: "approval gate", node_type: "input" },
    { key: "downstream:failure", kind: "downstream", text: "And if a run ever fails, it lands in Decision Triage…", derived_text: "same", authored: false, queue_id: "workflow_review_triage", queue_label: "Decision Triage" },
  ],
  orphaned_captions: { "step:renamed_away": "stale words" },
  mirror_drift: [],
}

const getPonderScript = vi.fn()
const savePonderCaption = vi.fn()
vi.mock("@/bridgeable-admin/services/moc-service", () => ({
  getPonderScript: (...a: unknown[]) => getPonderScript(...a),
  savePonderCaption: (...a: unknown[]) => savePonderCaption(...a),
}))

beforeEach(() => {
  getPonderScript.mockReset().mockResolvedValue(structuredClone(SCRIPT))
  savePonderCaption.mockReset().mockResolvedValue({})
})

describe("PonderOverlay", () => {
  it("opens on the WHEN beat and scrubs via the dot rail", async () => {
    render(<PonderOverlay taskId="t1" onClose={() => {}} />)
    await waitFor(() => expect(screen.getByTestId("ponder-beat-when")).toBeTruthy())
    expect(screen.getByText(/1st of each month/)).toBeTruthy()

    const dots = screen.getAllByLabelText(/^Beat \d/)
    expect(dots).toHaveLength(4)
    fireEvent.click(dots[2])
    await waitFor(() =>
      expect(screen.getByTestId("ponder-beat-pause:approval_gate")).toBeTruthy(),
    )
    expect(screen.getByText(/pauses for you/i)).toBeTruthy()
  })

  it("reaches the end, offers Replay, and replays to beat one", async () => {
    render(<PonderOverlay taskId="t1" onClose={() => {}} />)
    await waitFor(() => screen.getByTestId("ponder-beat-when"))
    fireEvent.click(screen.getAllByLabelText(/^Beat \d/)[3])
    await waitFor(() => screen.getByTestId("ponder-replay"))
    fireEvent.click(screen.getByTestId("ponder-replay"))
    await waitFor(() => expect(screen.getByTestId("ponder-beat-when")).toBeTruthy())
  })

  it("edit mode: authors a caption through the editor, orphans visible", async () => {
    render(<PonderOverlay taskId="t1" onClose={() => {}} />)
    await waitFor(() => screen.getByTestId("ponder-beat-when"))
    fireEvent.click(screen.getByTestId("ponder-edit-toggle"))
    // Orphans surface in edit mode only.
    expect(screen.getByTestId("ponder-orphans").textContent).toContain("stale words")

    fireEvent.click(screen.getAllByLabelText(/^Beat \d/)[1])
    await waitFor(() => screen.getByTestId("ponder-beat-step:identify_customers"))
    fireEvent.click(screen.getByText("Find charge-account customers with activity"))
    await waitFor(() => screen.getByTestId("ponder-caption-editor"))
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Every open charge account gets a look." },
    })
    fireEvent.click(screen.getByText("Save caption"))
    await waitFor(() =>
      expect(savePonderCaption).toHaveBeenCalledWith(
        "t1", "step:identify_customers", "Every open charge account gets a look.",
      ),
    )
  })

  it("Escape closes", async () => {
    const onClose = vi.fn()
    render(<PonderOverlay taskId="t1" onClose={onClose} />)
    await waitFor(() => screen.getByTestId("ponder-beat-when"))
    fireEvent.keyDown(window, { key: "Escape" })
    expect(onClose).toHaveBeenCalled()
  })
})
