/**
 * TriageQueueCore (3a.1-B) — the Decide-as-Focus core mounts the real Phase 5
 * triage workspace bound to config.queueId, replacing the old hardcoded stub.
 */
import { render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, it, expect, vi } from "vitest"

import { TriageQueueCore } from "./TriageQueueCore"
import type { FocusConfig } from "@/contexts/focus-registry"

vi.mock("@/services/triage-service", () => ({
  getQueueConfig: vi.fn(),
  startSession: vi.fn(),
  fetchNextItem: vi.fn(),
  endSession: vi.fn(),
  applyAction: vi.fn(),
  snoozeItem: vi.fn(),
}))
import * as triageService from "@/services/triage-service"

function renderCore(config: FocusConfig) {
  return render(
    <MemoryRouter>
      <TriageQueueCore focusId={config.id} config={config} />
    </MemoryRouter>,
  )
}

const PLACEHOLDER = "Review PO #1042" // a row from the old hardcoded stub

describe("TriageQueueCore", () => {
  it("renders a deliberate 'not bound' state when no queueId (not the old placeholder)", () => {
    renderCore({ id: "x", mode: "triageQueue", displayName: "Unbound" })
    expect(screen.getByText(/isn.t bound to a queue/i)).toBeInTheDocument()
    expect(screen.queryByText(PLACEHOLDER)).not.toBeInTheDocument()
  })

  it("mounts the real Phase 5 workspace bound to config.queueId", async () => {
    vi.mocked(triageService.getQueueConfig).mockResolvedValue({
      queue_id: "workflow_review_triage",
      queue_name: "Workflow Review",
      config: {
        queue_name: "Workflow Review",
        item_display: { display_component: "workflow_review" },
        action_palette: [],
        flow_controls: {},
        context_panels: [],
      },
    } as never)
    vi.mocked(triageService.startSession).mockResolvedValue({
      session_id: "s1", items_processed_count: 0, items_approved_count: 0,
      items_rejected_count: 0, items_snoozed_count: 0,
    } as never)
    vi.mocked(triageService.fetchNextItem).mockResolvedValue(null) // empty queue
    vi.mocked(triageService.endSession).mockResolvedValue({} as never)

    renderCore({
      id: "decision-triage", mode: "triageQueue", displayName: "Decision Triage",
      queueId: "workflow_review_triage",
    })

    // Focus chrome (CoreHeader) renders the queue's display name.
    expect(screen.getByText("Decision Triage")).toBeInTheDocument()
    // It mounted the REAL workspace, scoped to the bound queue.
    await waitFor(() =>
      expect(triageService.startSession).toHaveBeenCalledWith("workflow_review_triage"),
    )
    await waitFor(() =>
      expect(screen.getByTestId("triage-caught-up")).toBeInTheDocument(),
    )
    // Never the old hardcoded placeholder.
    expect(screen.queryByText(PLACEHOLDER)).not.toBeInTheDocument()
  })
})
