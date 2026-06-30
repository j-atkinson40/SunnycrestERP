/**
 * WorkflowAssistantRail — Shell-2 deliver-once: an NL request handed in from the
 * omnipresent bar (via initialNl + deliveryNonce) pre-fills + auto-runs onGenerate
 * exactly once per nonce, feeding the existing 1b generate path. The nonce-ref
 * guard is robust to onGenerate identity churn (the editor passes a fresh arrow
 * each render) — only a NEW nonce re-delivers.
 */
import { render } from "@testing-library/react"
import { describe, it, expect, vi } from "vitest"

import {
  WorkflowAssistantRail,
  type WorkflowAssistantRailProps,
} from "./WorkflowAssistantRail"

function props(
  over: Partial<WorkflowAssistantRailProps> = {},
): WorkflowAssistantRailProps {
  return {
    vertical: "manufacturing",
    workflowType: "billing",
    isDraftDirty: false,
    generating: false,
    error: null,
    candidate: null,
    onGenerate: vi.fn(),
    onAccept: vi.fn(),
    onReject: vi.fn(),
    initialNl: null,
    deliveryNonce: null,
    ...over,
  }
}

describe("WorkflowAssistantRail — Shell-2 deliver-once", () => {
  it("auto-runs onGenerate ONCE when a deliveryNonce arrives with an NL", () => {
    const onGenerate = vi.fn()
    const p = props({ onGenerate, initialNl: "invoice at month end", deliveryNonce: 1 })
    const { rerender } = render(<WorkflowAssistantRail {...p} />)
    expect(onGenerate).toHaveBeenCalledTimes(1)
    expect(onGenerate).toHaveBeenCalledWith("invoice at month end")
    // Re-render, SAME nonce → no re-run (deliver-once).
    rerender(<WorkflowAssistantRail {...p} />)
    expect(onGenerate).toHaveBeenCalledTimes(1)
  })

  it("a NEW nonce delivers again (a fresh request from the bar)", () => {
    const onGenerate = vi.fn()
    const { rerender } = render(
      <WorkflowAssistantRail {...props({ onGenerate, initialNl: "first", deliveryNonce: 1 })} />,
    )
    expect(onGenerate).toHaveBeenCalledTimes(1)
    rerender(
      <WorkflowAssistantRail {...props({ onGenerate, initialNl: "second", deliveryNonce: 2 })} />,
    )
    expect(onGenerate).toHaveBeenCalledTimes(2)
    expect(onGenerate).toHaveBeenLastCalledWith("second")
  })

  it("calls onDelivered once after delivering (so the carrier can clear it)", () => {
    const onDelivered = vi.fn()
    render(
      <WorkflowAssistantRail
        {...props({ initialNl: "x", deliveryNonce: 7, onDelivered })}
      />,
    )
    expect(onDelivered).toHaveBeenCalledTimes(1)
  })

  it("does nothing without a deliveryNonce (the manual rail path is unchanged)", () => {
    const onGenerate = vi.fn()
    render(<WorkflowAssistantRail {...props({ onGenerate })} />)
    expect(onGenerate).not.toHaveBeenCalled()
  })
})
