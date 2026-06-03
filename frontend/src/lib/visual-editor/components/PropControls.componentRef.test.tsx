/**
 * PropControls — ComponentReferenceControl direct coverage.
 *
 * RELOCATED here in focus-invocation reconciliation P2: the componentReference
 * CONTROL-render coverage previously rode incidentally on the
 * `generation-focus-invocation.focusTemplateName` workflow-node exemplar
 * (RegistryDrivenConfig.test + NodeLabelSentence.test). That node was the last
 * workflow-node with a componentReference prop; retiring it (the redundant twin
 * of invoke_generation_focus) removed those exemplars. This is the direct,
 * subject-independent home for the control's render + dispatch coverage — a
 * better test than the incidental exemplar.
 */
import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

import "@/lib/visual-editor/registry/auto-register"
import { ComponentReferenceControl, PropControlDispatcher } from "./PropControls"
import type { ConfigPropSchema } from "@/lib/visual-editor/registry"

describe("ComponentReferenceControl (direct)", () => {
  it("renders a <select> over registered components + onChange fires with the picked value", () => {
    const onChange = vi.fn()
    render(
      <ComponentReferenceControl
        value=""
        onChange={onChange}
        componentTypes={["focus-template"]}
      />,
    )
    const select = screen.getByTestId("prop-comp-ref") as HTMLSelectElement
    expect(select.tagName).toBe("SELECT")
    // The empty placeholder option + ≥1 focus-template entry — proves the
    // getAllRegistered() lookup + the componentTypes filter populate the picker.
    expect(select.options.length).toBeGreaterThan(1)
    const pick = select.options[1].value
    fireEvent.change(select, { target: { value: pick } })
    expect(onChange).toHaveBeenCalledWith(pick)
  })

  it("filters to the requested componentTypes (an unknown kind → only the empty option)", () => {
    render(
      <ComponentReferenceControl
        value=""
        onChange={vi.fn()}
        componentTypes={["__no_such_kind__"]}
      />,
    )
    const select = screen.getByTestId("prop-comp-ref") as HTMLSelectElement
    // Only the "— select component —" placeholder when nothing matches.
    expect(select.options.length).toBe(1)
  })

  it("PropControlDispatcher routes type:componentReference → ComponentReferenceControl", () => {
    const onChange = vi.fn()
    render(
      <PropControlDispatcher
        schema={
          {
            type: "componentReference",
            default: "",
            componentTypes: ["focus-template"],
          } as ConfigPropSchema
        }
        value=""
        onChange={onChange}
        data-testid="dispatch-comp-ref"
      />,
    )
    const select = screen.getByTestId("dispatch-comp-ref") as HTMLSelectElement
    expect(select.tagName).toBe("SELECT")
    expect(select.options.length).toBeGreaterThan(1)
    const pick = select.options[1].value
    fireEvent.change(select, { target: { value: pick } })
    expect(onChange).toHaveBeenCalledWith(pick)
  })
})
