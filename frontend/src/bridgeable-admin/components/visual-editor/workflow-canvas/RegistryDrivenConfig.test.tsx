/**
 * RegistryDrivenConfig.test — Phase B sub-arc B-3 (schema-driven inspector).
 *
 * Exercises the generic renderer against REAL B-2 registrations (via the
 * auto-register side-effect import) so the per-ConfigPropType control
 * mapping is validated against the actual configurableProps shipped — not
 * a synthetic fixture. Roundtrip (config -> control -> onChange) is driven
 * through the reliably-testable controls (text input, number, switch,
 * array); base-ui Select presence is asserted structurally.
 */

import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

import "@/lib/visual-editor/registry/auto-register"
import { RegistryDrivenConfig } from "./RegistryDrivenConfig"

const noop = () => {}

describe("RegistryDrivenConfig — control mapping per ConfigPropType", () => {
  it("renders a string control (ai_prompt.promptKey)", () => {
    render(
      <RegistryDrivenConfig nodeName="ai_prompt" config={{}} onChange={noop} />,
    )
    expect(screen.getByTestId("registry-driven-config")).toBeInTheDocument()
    expect(screen.getByTestId("prop-promptKey")).toBeInTheDocument()
  })

  it("renders a number control with min/max bounds (ai_prompt.temperature 0..1)", () => {
    render(
      <RegistryDrivenConfig nodeName="ai_prompt" config={{}} onChange={noop} />,
    )
    const input = screen.getByTestId("prop-temperature") as HTMLInputElement
    expect(input.type).toBe("number")
    expect(input.min).toBe("0")
    expect(input.max).toBe("1")
  })

  it("renders an enum control as a select trigger (ai_prompt.model)", () => {
    render(
      <RegistryDrivenConfig nodeName="ai_prompt" config={{}} onChange={noop} />,
    )
    expect(screen.getByTestId("prop-model")).toBeInTheDocument()
  })

  it("renders a boolean control as a switch (cross_tenant_order.acknowledgmentRequired)", () => {
    render(
      <RegistryDrivenConfig
        nodeName="cross_tenant_order"
        config={{}}
        onChange={noop}
      />,
    )
    expect(screen.getByTestId("prop-acknowledgmentRequired")).toBeInTheDocument()
  })

  it("renders an object control as a JSON textarea (create_record.fieldBindings)", () => {
    render(
      <RegistryDrivenConfig
        nodeName="create_record"
        config={{}}
        onChange={noop}
      />,
    )
    expect(screen.getByTestId("prop-fieldBindings")).toBeInTheDocument()
  })

  it("renders an array control (decision.branches)", () => {
    render(
      <RegistryDrivenConfig
        nodeName="decision"
        config={{ branches: ["a", "b"] }}
        onChange={noop}
      />,
    )
    expect(screen.getByTestId("prop-branches")).toBeInTheDocument()
    expect(screen.getByTestId("prop-branches-item-0")).toBeInTheDocument()
    expect(screen.getByTestId("prop-branches-item-1")).toBeInTheDocument()
  })

  it("renders a tokenReference control (start.accentToken)", () => {
    render(
      <RegistryDrivenConfig nodeName="start" config={{}} onChange={noop} />,
    )
    expect(screen.getByTestId("prop-accentToken")).toBeInTheDocument()
  })

  it("renders a componentReference control (generation-focus-invocation.focusTemplateName)", () => {
    render(
      <RegistryDrivenConfig
        nodeName="generation-focus-invocation"
        config={{}}
        onChange={noop}
      />,
    )
    expect(screen.getByTestId("prop-focusTemplateName")).toBeInTheDocument()
  })

  it("renders the empty-state for an unknown node type (no registry entry)", () => {
    render(
      <RegistryDrivenConfig
        nodeName="__nonexistent__"
        config={{}}
        onChange={noop}
      />,
    )
    expect(screen.getByTestId("registry-driven-config-empty")).toBeInTheDocument()
  })
})

describe("RegistryDrivenConfig — config -> control -> onChange roundtrip", () => {
  it("seeds a string control from config (not just the registry default)", () => {
    render(
      <RegistryDrivenConfig
        nodeName="ai_prompt"
        config={{ promptKey: "my.custom.prompt" }}
        onChange={noop}
      />,
    )
    expect((screen.getByTestId("prop-promptKey") as HTMLInputElement).value).toBe(
      "my.custom.prompt",
    )
  })

  it("emits a merged config patch on string edit (preserves other keys)", () => {
    const onChange = vi.fn()
    render(
      <RegistryDrivenConfig
        nodeName="ai_prompt"
        config={{ model: "sonnet" }}
        onChange={onChange}
      />,
    )
    fireEvent.change(screen.getByTestId("prop-promptKey"), {
      target: { value: "x" },
    })
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ model: "sonnet", promptKey: "x" }),
    )
  })

  it("emits a numeric value (not a string) on number edit", () => {
    const onChange = vi.fn()
    render(
      <RegistryDrivenConfig nodeName="ai_prompt" config={{}} onChange={onChange} />,
    )
    fireEvent.change(screen.getByTestId("prop-maxTokens"), {
      target: { value: "2048" },
    })
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ maxTokens: 2048 }),
    )
  })

  it("array add/remove emits the updated array", () => {
    const onChange = vi.fn()
    render(
      <RegistryDrivenConfig
        nodeName="decision"
        config={{ branches: ["a"] }}
        onChange={onChange}
      />,
    )
    fireEvent.click(screen.getByTestId("prop-branches-add"))
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ branches: ["a", ""] }),
    )
    onChange.mockClear()
    fireEvent.click(screen.getByTestId("prop-branches-item-0-remove"))
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ branches: [] }),
    )
  })
})
