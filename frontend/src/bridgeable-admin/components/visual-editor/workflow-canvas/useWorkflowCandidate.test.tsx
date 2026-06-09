/**
 * useWorkflowCandidate — Phase 1b candidate-slot transition tests (jsdom).
 *
 * Covers the de-risk-order item 1 contract without the polished UI:
 *   - generate → candidate (valid verdict fills the slot)
 *   - generate graceful handling: invalid structure → rephrase msg;
 *     unconfigured/errored AI → unavailable msg; transport throw → transport msg
 *   - accept → onAccept(candidate) called + slot cleared (candidate → draft)
 *   - reject → slot cleared + onAccept NOT called (draft untouched)
 */
import { describe, it, expect, vi } from "vitest"
import { act, renderHook, waitFor } from "@testing-library/react"

import {
  interpretGenerateResult,
  useWorkflowCandidate,
} from "./useWorkflowCandidate"
import type { GenerateWorkflowResponse } from "@/bridgeable-admin/services/workflow-authoring-service"
import type { CanvasState } from "@/bridgeable-admin/services/workflow-templates-service"

const CANDIDATE: CanvasState = {
  version: 1,
  nodes: [
    { id: "n_start", type: "start", label: "Start", position: { x: 0, y: 0 }, config: {} },
    { id: "n_end", type: "end", label: "End", position: { x: 0, y: 120 }, config: {} },
  ],
  edges: [{ id: "e1", source: "n_start", target: "n_end" }],
}

function ok(canvas: CanvasState): GenerateWorkflowResponse {
  return {
    canvas_state: canvas,
    valid: true,
    validation_error: null,
    ai_status: "success",
    ai_execution_id: "exec-1",
    ai_latency_ms: 42,
    model_used: "claude-sonnet-4-6",
  }
}
function invalidStructure(): GenerateWorkflowResponse {
  return {
    canvas_state: { version: 1, nodes: [], edges: [{ id: "e1", source: "n_x", target: "n_y" }] },
    valid: false,
    validation_error: "edge references undeclared node id",
    ai_status: "success",
    ai_execution_id: "exec-2",
    ai_latency_ms: 50,
    model_used: "claude-sonnet-4-6",
  }
}
function aiUnavailable(): GenerateWorkflowResponse {
  return {
    canvas_state: null,
    valid: false,
    validation_error: "generation could not run (PromptNotFoundError: ...)",
    ai_status: "error",
    ai_execution_id: null,
    ai_latency_ms: null,
    model_used: null,
  }
}

describe("interpretGenerateResult", () => {
  it("valid verdict → candidate, no error", () => {
    const r = interpretGenerateResult(ok(CANDIDATE))
    expect(r.candidate).toEqual(CANDIDATE)
    expect(r.error).toBeNull()
  })
  it("model ran but invalid structure → rephrase message, no candidate", () => {
    const r = interpretGenerateResult(invalidStructure())
    expect(r.candidate).toBeNull()
    expect(r.error).toMatch(/rephrasing|valid workflow/i)
  })
  it("AI didn't run (ai_status=error) → unavailable message, no candidate", () => {
    const r = interpretGenerateResult(aiUnavailable())
    expect(r.candidate).toBeNull()
    expect(r.error).toMatch(/isn't available/i)
  })
})

describe("useWorkflowCandidate transitions", () => {
  it("generate (valid) fills the candidate slot", async () => {
    const generate = vi.fn().mockResolvedValue(ok(CANDIDATE))
    const onAccept = vi.fn()
    const { result } = renderHook(() =>
      useWorkflowCandidate({ vertical: "funeral_home", workflowType: "t", onAccept, generate }),
    )
    expect(result.current.candidate).toBeNull()
    await act(async () => {
      await result.current.generateWorkflow("when a case is committed, do A then B")
    })
    expect(generate).toHaveBeenCalledWith({
      nl: "when a case is committed, do A then B",
      vertical: "funeral_home",
      workflow_type: "t",
    })
    expect(result.current.candidate).toEqual(CANDIDATE)
    expect(result.current.error).toBeNull()
    expect(result.current.generating).toBe(false)
  })

  it("generate (invalid structure) surfaces a graceful rephrase message, no candidate", async () => {
    const generate = vi.fn().mockResolvedValue(invalidStructure())
    const { result } = renderHook(() =>
      useWorkflowCandidate({ vertical: "manufacturing", workflowType: "t", onAccept: vi.fn(), generate }),
    )
    await act(async () => {
      await result.current.generateWorkflow("gibberish")
    })
    expect(result.current.candidate).toBeNull()
    expect(result.current.error).toMatch(/rephrasing|valid workflow/i)
  })

  it("generate (AI unavailable) surfaces a graceful unavailable message, no crash", async () => {
    const generate = vi.fn().mockResolvedValue(aiUnavailable())
    const { result } = renderHook(() =>
      useWorkflowCandidate({ vertical: "manufacturing", workflowType: "t", onAccept: vi.fn(), generate }),
    )
    await act(async () => {
      await result.current.generateWorkflow("x")
    })
    expect(result.current.candidate).toBeNull()
    expect(result.current.error).toMatch(/isn't available/i)
  })

  it("generate (transport throw) surfaces a graceful transport message, no crash", async () => {
    const generate = vi.fn().mockRejectedValue(new Error("network down"))
    const { result } = renderHook(() =>
      useWorkflowCandidate({ vertical: "manufacturing", workflowType: "t", onAccept: vi.fn(), generate }),
    )
    await act(async () => {
      await result.current.generateWorkflow("x")
    })
    expect(result.current.candidate).toBeNull()
    expect(result.current.error).toMatch(/couldn't reach/i)
  })

  it("accept → onAccept(candidate) called + slot cleared (candidate becomes draft)", async () => {
    const generate = vi.fn().mockResolvedValue(ok(CANDIDATE))
    const onAccept = vi.fn()
    const { result } = renderHook(() =>
      useWorkflowCandidate({ vertical: "funeral_home", workflowType: "t", onAccept, generate }),
    )
    await act(async () => {
      await result.current.generateWorkflow("x")
    })
    expect(result.current.candidate).toEqual(CANDIDATE)
    act(() => result.current.acceptCandidate())
    expect(onAccept).toHaveBeenCalledTimes(1)
    expect(onAccept).toHaveBeenCalledWith(CANDIDATE)
    expect(result.current.candidate).toBeNull()
  })

  it("reject → slot cleared + onAccept NOT called (draft untouched)", async () => {
    const generate = vi.fn().mockResolvedValue(ok(CANDIDATE))
    const onAccept = vi.fn()
    const { result } = renderHook(() =>
      useWorkflowCandidate({ vertical: "funeral_home", workflowType: "t", onAccept, generate }),
    )
    await act(async () => {
      await result.current.generateWorkflow("x")
    })
    expect(result.current.candidate).toEqual(CANDIDATE)
    act(() => result.current.rejectCandidate())
    expect(result.current.candidate).toBeNull()
    expect(onAccept).not.toHaveBeenCalled()
  })

  it("sets generating=true while the call is in flight", async () => {
    let resolveFn: (v: GenerateWorkflowResponse) => void = () => {}
    const generate = vi.fn().mockReturnValue(
      new Promise<GenerateWorkflowResponse>((res) => {
        resolveFn = res
      }),
    )
    const { result } = renderHook(() =>
      useWorkflowCandidate({ vertical: "funeral_home", workflowType: "t", onAccept: vi.fn(), generate }),
    )
    let pending: Promise<void>
    act(() => {
      pending = result.current.generateWorkflow("x")
    })
    await waitFor(() => expect(result.current.generating).toBe(true))
    await act(async () => {
      resolveFn(ok(CANDIDATE))
      await pending!
    })
    expect(result.current.generating).toBe(false)
    expect(result.current.candidate).toEqual(CANDIDATE)
  })
})
