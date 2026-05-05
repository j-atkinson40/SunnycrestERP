/**
 * CommitAffordance tests — canonical per-authoring-context button
 * labels per §14.14.5 + canonical commit flow + canonical anti-pattern
 * guards.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { CommitAffordance } from "./CommitAffordance"
import { PersonalizationCanvasStateProvider } from "./canvas-state-context"
import {
  emptyCanvasState,
  type GenerationFocusInstance,
} from "@/types/personalization-studio"

// Mock the service module canonical at module substrate.
vi.mock("@/services/personalization-studio-service", () => ({
  commitCanvasState: vi.fn().mockResolvedValue({
    document_version_id: "ver-1",
    version_number: 1,
    storage_key: "tenants/x/documents/y/canvas_state_v1.json",
  }),
  commitInstance: vi.fn().mockResolvedValue({
    id: "instance-1",
    company_id: "co-1",
    template_type: "burial_vault_personalization_studio",
    authoring_context: "manufacturer_without_family",
    lifecycle_state: "committed",
    linked_entity_type: "sales_order",
    linked_entity_id: "order-1",
    document_id: "doc-1",
    opened_at: "2026-05-05T00:00:00Z",
    opened_by_user_id: null,
    last_active_at: "2026-05-05T00:00:00Z",
    committed_at: "2026-05-05T00:01:00Z",
    committed_by_user_id: "user-1",
    abandoned_at: null,
    abandoned_by_user_id: null,
    family_approval_status: null,
    family_approval_requested_at: null,
    family_approval_decided_at: null,
  }),
}))


function makeInstance(
  overrides: Partial<GenerationFocusInstance> = {},
): GenerationFocusInstance {
  return {
    id: "instance-1",
    company_id: "co-1",
    template_type: "burial_vault_personalization_studio",
    authoring_context: "manufacturer_without_family",
    lifecycle_state: "active",
    linked_entity_type: "sales_order",
    linked_entity_id: "order-1",
    document_id: "doc-1",
    opened_at: "2026-05-05T00:00:00Z",
    opened_by_user_id: null,
    last_active_at: "2026-05-05T00:00:00Z",
    committed_at: null,
    committed_by_user_id: null,
    abandoned_at: null,
    abandoned_by_user_id: null,
    family_approval_status: null,
    family_approval_requested_at: null,
    family_approval_decided_at: null,
    ...overrides,
  }
}


function renderAffordance(instance: GenerationFocusInstance) {
  return render(
    <PersonalizationCanvasStateProvider
      initialCanvasState={emptyCanvasState("burial_vault_personalization_studio")}
    >
      <CommitAffordance instance={instance} />
    </PersonalizationCanvasStateProvider>,
  )
}


describe("CommitAffordance — canonical per-authoring-context labels per §14.14.5", () => {
  it("'Add to case' canonical label for funeral_home_with_family", () => {
    const instance = makeInstance({
      authoring_context: "funeral_home_with_family",
      linked_entity_type: "fh_case",
    })
    renderAffordance(instance)
    expect(screen.getByText("Add to case")).toBeInTheDocument()
  })

  it("'Add to order' canonical label for manufacturer_without_family", () => {
    const instance = makeInstance({
      authoring_context: "manufacturer_without_family",
    })
    renderAffordance(instance)
    expect(screen.getByText("Add to order")).toBeInTheDocument()
  })

  it("'Mark reviewed' canonical label + canonical read-only chrome for manufacturer_from_fh_share", () => {
    const instance = makeInstance({
      authoring_context: "manufacturer_from_fh_share",
      linked_entity_type: "document_share",
    })
    renderAffordance(instance)
    expect(screen.getByText("Mark reviewed")).toBeInTheDocument()
    // Canonical read-only consume mode: no Save draft button.
    expect(screen.queryByText("Save draft")).toBeNull()
    const root = document.querySelector("[data-slot='commit-affordance']") as HTMLElement
    expect(root.getAttribute("data-mode")).toBe("read-only-consume")
  })

  it("Save draft + commit buttons disabled when canonical lifecycle is terminal", () => {
    const instance = makeInstance({ lifecycle_state: "committed" })
    renderAffordance(instance)
    const saveDraftBtn = screen.getByRole("button", { name: /save draft/i })
    const commitBtn = screen.getByRole("button", { name: /add to order/i })
    expect((saveDraftBtn as HTMLButtonElement).disabled).toBe(true)
    expect((commitBtn as HTMLButtonElement).disabled).toBe(true)
  })
})


describe("CommitAffordance — canonical commit flow + anti-pattern guards", () => {
  it("Save draft canonically calls commitCanvasState (NOT commitInstance) per canonical operator agency", async () => {
    const service = await import("@/services/personalization-studio-service")
    const instance = makeInstance()
    renderAffordance(instance)
    fireEvent.click(screen.getByText("Save draft"))
    await waitFor(() => {
      expect(service.commitCanvasState).toHaveBeenCalledTimes(1)
    })
    // Canonical anti-pattern guard: Save draft does NOT trigger
    // canonical lifecycle transition (commitInstance) per
    // §3.26.11.12.16 Anti-pattern 1 + canonical operator agency.
    expect(service.commitInstance).not.toHaveBeenCalled()
  })

  it("Commit button canonically calls commitCanvasState THEN commitInstance per canonical sequence", async () => {
    const service = await import("@/services/personalization-studio-service")
    vi.clearAllMocks()
    const instance = makeInstance()
    renderAffordance(instance)
    fireEvent.click(screen.getByText("Add to order"))
    await waitFor(() => {
      expect(service.commitCanvasState).toHaveBeenCalledTimes(1)
      expect(service.commitInstance).toHaveBeenCalledTimes(1)
    })
  })

  it("onCommitted callback fires canonical post-commit with canonical updated instance", async () => {
    const onCommitted = vi.fn()
    const instance = makeInstance()
    render(
      <PersonalizationCanvasStateProvider
        initialCanvasState={emptyCanvasState("burial_vault_personalization_studio")}
      >
        <CommitAffordance instance={instance} onCommitted={onCommitted} />
      </PersonalizationCanvasStateProvider>,
    )
    fireEvent.click(screen.getByText("Add to order"))
    await waitFor(() => {
      expect(onCommitted).toHaveBeenCalledTimes(1)
    })
    expect(onCommitted.mock.calls[0][0].lifecycle_state).toBe("committed")
  })
})
