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
  // The ponder-service-context default (P2) binds every service export —
  // stub the rest so the module graph resolves.
  getPonderDocumentPreview: vi.fn().mockResolvedValue({ html: "" }),
  addTaskTrigger: vi.fn(),
  patchTrigger: vi.fn(),
  deleteTrigger: vi.fn(),
  listTriggerEvents: vi.fn().mockResolvedValue([]),
  setPonderWorkflowParam: vi.fn(),
  searchPonderUsers: vi.fn().mockResolvedValue([]),
  // P3 — the publish boundary (fork_count 0 → the bar stays hidden).
  getTaskOfferPreview: vi.fn().mockResolvedValue({
    task_id: "t", task_name: "T", fork_count: 0, offerable_count: 0, forks: [],
  }),
  publishTaskOffer: vi.fn(),
  // T-1 — the atomic adopt (the blocked card's affordance).
  adoptTaskSchedule: vi.fn(),
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

  it("R-2: a ponder_ref beat renders the walk button and swaps overlays", async () => {
    // REGRESSION PIN — the witness caught `onOpenPonder is not defined`
    // (prop declared in the type but missing from the destructuring).
    const script = structuredClone(SCRIPT)
    script.beats[1] = {
      key: "automation:a1", kind: "task", authored: false,
      text: "Bank Rec Matching — matches payments nightly. Daily.",
      derived_text: "same",
      ponder_ref: { overlay_id: "a1", label: "Walk Bank Rec Matching" },
    } as (typeof script.beats)[number]
    getPonderScript.mockResolvedValue(script)
    const onOpenPonder = vi.fn()
    render(
      <PonderOverlay taskId="job:j1" onClose={() => {}} onOpenPonder={onOpenPonder} />,
    )
    await waitFor(() => screen.getByTestId("ponder-beat-when"))
    fireEvent.click(screen.getAllByLabelText(/^Beat \d/)[1])
    await waitFor(() => screen.getByTestId("ponder-beat-ponder-ref"))
    fireEvent.click(screen.getByTestId("ponder-beat-ponder-ref"))
    expect(onOpenPonder).toHaveBeenCalledWith("a1")
  })

  it("R-2: without onOpenPonder the affordance stays hidden (honest absence)", async () => {
    const script = structuredClone(SCRIPT)
    script.beats[1] = {
      key: "automation:a1", kind: "task", authored: false,
      text: "Bank Rec Matching.", derived_text: "same",
      ponder_ref: { overlay_id: "a1", label: "Walk it" },
    } as (typeof script.beats)[number]
    getPonderScript.mockResolvedValue(script)
    render(<PonderOverlay taskId="job:j1" onClose={() => {}} />)
    await waitFor(() => screen.getByTestId("ponder-beat-when"))
    fireEvent.click(screen.getAllByLabelText(/^Beat \d/)[1])
    await waitFor(() => screen.getByTestId("ponder-beat-automation:a1"))
    expect(screen.queryByTestId("ponder-beat-ponder-ref")).toBeNull()
  })

  it("Escape closes", async () => {
    const onClose = vi.fn()
    render(<PonderOverlay taskId="t1" onClose={onClose} />)
    await waitFor(() => screen.getByTestId("ponder-beat-when"))
    fireEvent.keyDown(window, { key: "Escape" })
    expect(onClose).toHaveBeenCalled()
  })
})
