/**
 * useMapOverlays — the fork gate's DECLINE path (regression pin).
 *
 * Latent since P2, caught by the R-2 witness: "Keep the standard version"
 * resolved the gate promise but the early return skipped the cleanup that
 * only lived in the accept branch's finally — the dialog stayed mounted
 * forever. Both answers must dismiss the prompt.
 */
import { describe, expect, it, vi, beforeEach } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import { useMapOverlays } from "./useMapOverlays"
import type { MapTask } from "@/services/moc-map-service"

const forkTask = vi.fn()
vi.mock("@/services/moc-map-service", () => ({
  forkTask: (...a: unknown[]) => forkTask(...a),
  recordEngagement: vi.fn(),
}))

vi.mock("@/contexts/auth-context", () => ({
  useAuth: () => ({ company: { name: "Sunnycrest Precast" }, isAdmin: true }),
}))

// The overlay's default ponder service binds the admin module exports.
const getPonderScript = vi.fn()
vi.mock("@/bridgeable-admin/services/moc-service", () => ({
  getPonderScript: (...a: unknown[]) => getPonderScript(...a),
  savePonderCaption: vi.fn(),
  getPonderDocumentPreview: vi.fn().mockResolvedValue({ html: "" }),
  addTaskTrigger: vi.fn(),
  patchTrigger: vi.fn(),
  deleteTrigger: vi.fn(),
  listTriggerEvents: vi.fn().mockResolvedValue([]),
  setPonderWorkflowParam: vi.fn(),
  searchPonderUsers: vi.fn().mockResolvedValue([]),
  getTaskOfferPreview: vi.fn().mockResolvedValue({
    task_id: "t", task_name: "T", fork_count: 0, offerable_count: 0, forks: [],
  }),
  publishTaskOffer: vi.fn(),
  adoptTaskSchedule: vi.fn(),
}))

const SHARED_TASK: MapTask = {
  id: "t1",
  name: "AR Collections",
  display_order: 0,
  scope: "vertical_default",
  triggers: [],
}

function Harness() {
  const { ponderTask, overlays } = useMapOverlays({
    tasks: [SHARED_TASK],
    vertical: "manufacturing",
    reload: async () => {},
  })
  return (
    <>
      <button data-testid="open" onClick={() => ponderTask(SHARED_TASK)}>
        open
      </button>
      {overlays}
    </>
  )
}

async function openForkPrompt() {
  render(
    <MemoryRouter>
      <Harness />
    </MemoryRouter>,
  )
  fireEvent.click(screen.getByTestId("open"))
  await waitFor(() => screen.getByTestId("ponder-beat-when"))
  fireEvent.click(screen.getByTestId("ponder-edit-toggle"))
  await waitFor(() => screen.getByTestId("fork-prompt"))
}

beforeEach(() => {
  forkTask.mockReset()
  getPonderScript.mockReset().mockResolvedValue({
    task_id: "t1",
    task_name: "AR Collections",
    beats: [
      { key: "when", kind: "when", text: "Nightly.", derived_text: "Nightly.", authored: false },
    ],
    orphaned_captions: {},
    mirror_drift: [],
  })
})

describe("useMapOverlays fork gate", () => {
  it("DECLINE dismisses the prompt (the P2 latent bug) and never forks", async () => {
    await openForkPrompt()
    fireEvent.click(screen.getByTestId("fork-cancel"))
    await waitFor(() =>
      expect(screen.queryByTestId("fork-prompt")).toBeNull(),
    )
    expect(forkTask).not.toHaveBeenCalled()
  })

  it("ACCEPT forks, dismisses, and swaps the overlay to the fork", async () => {
    forkTask.mockResolvedValue({ ...SHARED_TASK, id: "fork-1", scope: "tenant_override" })
    await openForkPrompt()
    fireEvent.click(screen.getByTestId("fork-accept"))
    await waitFor(() =>
      expect(screen.queryByTestId("fork-prompt")).toBeNull(),
    )
    expect(forkTask).toHaveBeenCalledWith("t1")
    // The overlay re-derives against the fork's id.
    await waitFor(() =>
      expect(getPonderScript).toHaveBeenCalledWith("fork-1"),
    )
  })
})
