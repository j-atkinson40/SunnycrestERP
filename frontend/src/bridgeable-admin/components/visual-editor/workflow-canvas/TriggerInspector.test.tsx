/**
 * TriggerInspector.test — Phase B sub-arc B-5.
 *
 * Bespoke trigger editor (audit-first: trigger types unregistered →
 * JSON-config editor, not RegistryDrivenConfig). Covers type select +
 * JSON config roundtrip + invalid-JSON guard + undefined-trigger default.
 */
import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

import { TriggerInspector, TRIGGER_TYPES } from "./TriggerInspector"
import type { CanvasTrigger } from "@/bridgeable-admin/services/workflow-templates-service"

const trigger: CanvasTrigger = {
  trigger_type: "scheduled",
  trigger_config: { cron: "0 0 * * *" },
}

describe("TriggerInspector", () => {
  it("declares the 5 canonical trigger types", () => {
    expect([...TRIGGER_TYPES]).toEqual([
      "manual",
      "event",
      "scheduled",
      "time_after_event",
      "time_of_day",
    ])
  })

  it("renders type select + config JSON from the trigger", () => {
    render(<TriggerInspector trigger={trigger} onChange={() => {}} />)
    expect(screen.getByTestId("trigger-inspector-type")).toBeInTheDocument()
    expect((screen.getByTestId("trigger-inspector-config") as HTMLTextAreaElement).value).toContain("cron")
  })

  it("defaults to manual / {} when trigger is undefined", () => {
    render(<TriggerInspector trigger={undefined} onChange={() => {}} />)
    expect((screen.getByTestId("trigger-inspector-config") as HTMLTextAreaElement).value).toBe("{}")
  })

  it("emits parsed config on a valid JSON edit (preserves trigger_type)", () => {
    const onChange = vi.fn()
    render(<TriggerInspector trigger={trigger} onChange={onChange} />)
    fireEvent.change(screen.getByTestId("trigger-inspector-config"), {
      target: { value: '{"cron":"*/5 * * * *"}' },
    })
    expect(onChange).toHaveBeenCalledWith({
      trigger_type: "scheduled",
      trigger_config: { cron: "*/5 * * * *" },
    })
  })

  it("shows an error + does NOT emit on invalid JSON", () => {
    const onChange = vi.fn()
    render(<TriggerInspector trigger={trigger} onChange={onChange} />)
    fireEvent.change(screen.getByTestId("trigger-inspector-config"), {
      target: { value: "{not json" },
    })
    expect(screen.getByTestId("trigger-inspector-config-error")).toBeInTheDocument()
    expect(onChange).not.toHaveBeenCalled()
  })

  it("rejects a non-object JSON (array) with an error", () => {
    const onChange = vi.fn()
    render(<TriggerInspector trigger={trigger} onChange={onChange} />)
    fireEvent.change(screen.getByTestId("trigger-inspector-config"), {
      target: { value: "[1,2,3]" },
    })
    expect(screen.getByTestId("trigger-inspector-config-error")).toHaveTextContent(/JSON object/i)
    expect(onChange).not.toHaveBeenCalled()
  })
})
