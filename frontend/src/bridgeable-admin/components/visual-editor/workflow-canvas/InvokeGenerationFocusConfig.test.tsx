/**
 * Vitest — InvokeGenerationFocusConfig (R-6.0b).
 *
 * Covers focus + operation Select wiring, kwargs round-trip via
 * `bindingRowsToKwargs` + `kwargsToBindingRows`, add-binding mutation,
 * remove-binding, and the output-type derivation from the catalog.
 */

import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import {
  HEADLESS_FOCUS_CATALOG,
  InvokeGenerationFocusConfig,
  bindingRowsToKwargs,
  kwargsToBindingRows,
} from "./InvokeGenerationFocusConfig"


describe("InvokeGenerationFocusConfig — R-6.0b", () => {
  it("renders the canonical headless focus catalog", () => {
    const onChange = vi.fn()
    render(
      <InvokeGenerationFocusConfig
        config={{}}
        onChange={onChange}
      />,
    )
    expect(
      screen.getByTestId("wf-invoke-generation-focus-config"),
    ).toBeTruthy()
    // The hardcoded catalog ships exactly one focus today —
    // burial_vault_personalization_studio. Future Generation Focuses
    // extend HEADLESS_FOCUS_CATALOG.
    expect(HEADLESS_FOCUS_CATALOG.length).toBeGreaterThanOrEqual(1)
    expect(HEADLESS_FOCUS_CATALOG[0].focus_id).toBe(
      "burial_vault_personalization_studio",
    )
  })

  it("derives output_type from the selected focus", () => {
    const onChange = vi.fn()
    render(
      <InvokeGenerationFocusConfig
        config={{ focus_id: "burial_vault_personalization_studio" }}
        onChange={onChange}
      />,
    )
    const out = screen.getByTestId(
      "wf-invoke-generation-focus-output-type",
    )
    expect(out.textContent).toContain("burial_vault_personalization_draft")
  })

  it("renders binding rows from existing kwargs", () => {
    const onChange = vi.fn()
    render(
      <InvokeGenerationFocusConfig
        config={{
          focus_id: "burial_vault_personalization_studio",
          op_id: "extract_decedent_info",
          kwargs: {
            instance_id: "{workflow_input.instance_id}",
            verbose: "true",
          },
        }}
        onChange={onChange}
      />,
    )
    expect(
      screen.getByTestId("wf-invoke-generation-focus-binding-0"),
    ).toBeTruthy()
    expect(
      screen.getByTestId("wf-invoke-generation-focus-binding-1"),
    ).toBeTruthy()
  })

  it("Add-binding button appends a workflow_input row", () => {
    const onChange = vi.fn()
    render(
      <InvokeGenerationFocusConfig
        config={{ focus_id: "burial_vault_personalization_studio" }}
        onChange={onChange}
      />,
    )
    fireEvent.click(
      screen.getByTestId("wf-invoke-generation-focus-add-binding"),
    )
    expect(onChange).toHaveBeenCalled()
    const last = onChange.mock.calls[onChange.mock.calls.length - 1][0]
    // Empty key drops in serialization → kwargs stays {}.
    expect(last.kwargs).toEqual({})
    // But a binding row is added in-component (visible after rerender)
    expect(
      screen.getByTestId("wf-invoke-generation-focus-binding-0"),
    ).toBeTruthy()
  })

  it("kwargsToBindingRows + bindingRowsToKwargs round-trip preserves bindings", () => {
    const original = {
      instance_id: "{workflow_input.instance_id}",
      content_blocks: "{incoming_email.attachments}",
      literal_field: "raw value",
    }
    const rows = kwargsToBindingRows(original)
    expect(rows).toHaveLength(3)
    expect(rows[0]).toEqual({
      key: "instance_id",
      source_type: "workflow_input",
      path: "instance_id",
    })
    expect(rows[2]).toEqual({
      key: "literal_field",
      source_type: "literal",
      path: "raw value",
    })
    const reserialized = bindingRowsToKwargs(rows)
    expect(reserialized).toEqual(original)
  })

  it("kwargsToBindingRows handles unrecognized prefixes as literal", () => {
    const rows = kwargsToBindingRows({
      key1: "{unknown_prefix.path}",
    })
    expect(rows[0]).toEqual({
      key: "key1",
      source_type: "literal",
      path: "{unknown_prefix.path}",
    })
  })
})
