/**
 * Tenant Ponder-Editor P1 — param fields + the live-edit confirm.
 *
 * Pins: (a) only configurable declared params render as fields; (b) saving
 * writes the platform live value + refetches (the beat re-derives); (c) the
 * audience picker (role chips) writes the exact key the derivation reads;
 * (d) email-ish beats carry the sending-identity link-out, never duplicated
 * config; (e) the live gate blocks/permits writes; dry-run passes free.
 */
import { beforeEach, describe, expect, it, vi } from "vitest"
import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react"

import { PonderParamFields } from "./PonderParamFields"
import { LiveEditConfirm, useLiveEditGate } from "./LiveEditConfirm"
import * as svc from "@/bridgeable-admin/services/moc-service"
import type { PonderStepParam } from "@/bridgeable-admin/services/moc-service"

vi.mock("@/bridgeable-admin/services/moc-service", async () => {
  const actual = await vi.importActual<typeof svc>("@/bridgeable-admin/services/moc-service")
  return { ...actual, setPonderWorkflowParam: vi.fn().mockResolvedValue({ saved: true }) }
})

function param(over: Partial<PonderStepParam>): PonderStepParam {
  return {
    step_key: "send_statements", param_key: "reply_to", label: "Reply-to email",
    param_type: "email", default_value: null, platform_value: null,
    current_value: null, effective_value: null, live: false,
    is_configurable: true, validation: null, ...over,
  }
}

describe("PonderParamFields", () => {
  beforeEach(() => vi.clearAllMocks())

  it("renders only configurable params + the sending-identity link-out", () => {
    render(
      <PonderParamFields
        workflowId="wf-1"
        params={[
          param({}),
          param({ param_key: "locked", param_type: "text", is_configurable: false }),
        ]}
        onSaved={() => {}}
      />,
    )
    expect(screen.getByTestId("ponder-param-reply_to")).toBeInTheDocument()
    expect(screen.queryByTestId("ponder-param-locked")).toBeNull()
    // The split: per-step fields here; identity LINKS out, never duplicated.
    expect(screen.getByTestId("ponder-sending-identity-note")).toBeInTheDocument()
  })

  it("saves an email param and refetches (the beat re-derives)", async () => {
    const onSaved = vi.fn()
    render(
      <PonderParamFields workflowId="wf-1" params={[param({})]} onSaved={onSaved} />,
    )
    fireEvent.change(screen.getByTestId("ponder-param-input-reply_to"), {
      target: { value: "billing@sunnycrest.example" },
    })
    fireEvent.click(screen.getByTestId("ponder-param-save-reply_to"))
    await waitFor(() => expect(svc.setPonderWorkflowParam).toHaveBeenCalledWith(
      "wf-1", "send_statements", "reply_to", "billing@sunnycrest.example",
    ))
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
  })

  it("audience picker writes the exact roles the derivation reads", async () => {
    render(
      <PonderParamFields
        workflowId="wf-1"
        params={[param({
          param_key: "notify_roles", param_type: "role_multi_select",
          default_value: ["admin"], effective_value: ["admin"],
        })]}
        onSaved={() => {}}
      />,
    )
    fireEvent.click(screen.getByTestId("ponder-role-chip-office"))
    fireEvent.click(screen.getByTestId("ponder-param-save-notify_roles"))
    await waitFor(() => expect(svc.setPonderWorkflowParam).toHaveBeenCalledWith(
      "wf-1", "send_statements", "notify_roles", ["admin", "office"],
    ))
  })

  it("a live param offers reset-to-default (clears with null)", async () => {
    render(
      <PonderParamFields
        workflowId="wf-1"
        params={[param({ live: true, platform_value: "x@y.com", effective_value: "x@y.com" })]}
        onSaved={() => {}}
      />,
    )
    expect(screen.getByTestId("ponder-param-live-reply_to")).toBeInTheDocument()
    fireEvent.click(screen.getByTestId("ponder-param-clear-reply_to"))
    await waitFor(() => expect(svc.setPonderWorkflowParam).toHaveBeenCalledWith(
      "wf-1", "send_statements", "reply_to", null,
    ))
  })

  it("surfaces the validator's reason on a rejected value", async () => {
    vi.mocked(svc.setPonderWorkflowParam).mockRejectedValueOnce({
      response: { data: { detail: "reply_to: 'nope' is not an email address" } },
    })
    render(
      <PonderParamFields workflowId="wf-1" params={[param({})]} onSaved={() => {}} />,
    )
    fireEvent.change(screen.getByTestId("ponder-param-input-reply_to"), {
      target: { value: "nope" },
    })
    fireEvent.click(screen.getByTestId("ponder-param-save-reply_to"))
    await waitFor(() =>
      expect(screen.getByTestId("ponder-param-error-reply_to").textContent)
        .toContain("not an email address"),
    )
  })

  it("blocked by the confirm gate — no write", async () => {
    const gate = vi.fn().mockResolvedValue(false)
    render(
      <PonderParamFields workflowId="wf-1" params={[param({})]} onSaved={() => {}}
        confirmGate={gate} />,
    )
    fireEvent.change(screen.getByTestId("ponder-param-input-reply_to"), {
      target: { value: "a@b.com" },
    })
    fireEvent.click(screen.getByTestId("ponder-param-save-reply_to"))
    await waitFor(() => expect(gate).toHaveBeenCalled())
    expect(svc.setPonderWorkflowParam).not.toHaveBeenCalled()
  })
})

describe("useLiveEditGate + LiveEditConfirm", () => {
  it("dry-run tasks pass free — no dialog", async () => {
    const { result } = renderHook(() => useLiveEditGate(false))
    await expect(result.current.confirmGate("anything")).resolves.toBe(true)
    expect(result.current.pending).toBeNull()
  })

  it("live tasks see the evidence and Apply resolves true", async () => {
    const { result } = renderHook(() => useLiveEditGate(true))
    let outcome: boolean | undefined
    act(() => {
      void result.current.confirmGate("Change the schedule to “The last Friday…”")
        .then((ok) => { outcome = ok })
    })
    expect(result.current.pending?.detail).toContain("last Friday")

    render(
      <LiveEditConfirm
        taskName="Monthly Statement Run"
        pending={result.current.pending}
        onSettle={result.current.settle}
      />,
    )
    expect(screen.getByTestId("live-edit-consequence").textContent)
      .toContain("the next fire uses these settings")
    expect(screen.getByTestId("live-edit-diff").textContent).toContain("last Friday")
    fireEvent.click(screen.getByTestId("live-edit-apply"))
    await waitFor(() => expect(outcome).toBe(true))
  })

  it("Cancel resolves false", async () => {
    const { result } = renderHook(() => useLiveEditGate(true))
    let outcome: boolean | undefined
    act(() => {
      void result.current.confirmGate("Remove the trigger").then((ok) => { outcome = ok })
    })
    render(
      <LiveEditConfirm taskName="T" pending={result.current.pending}
        onSettle={result.current.settle} />,
    )
    fireEvent.click(screen.getByTestId("live-edit-cancel"))
    await waitFor(() => expect(outcome).toBe(false))
  })
})
