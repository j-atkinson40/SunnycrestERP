/**
 * Arc 4b.2b — StringControl mention integration tests.
 *
 * Covers the supportsMentions flag wiring through StringControl
 * + PropControlDispatcher. The hook + picker semantics are tested
 * independently in `useMentionPicker.test.tsx` + `MentionPicker.test.tsx`;
 * this suite verifies the integration boundary.
 */
import { describe, expect, it, vi, beforeEach } from "vitest"
import { useState } from "react"
import { fireEvent, render } from "@testing-library/react"

import {
  PropControlDispatcher,
  StringControl,
} from "./PropControls"
import type { ConfigPropSchema } from "@/lib/visual-editor/registry"


// Mock the document-mentions-service for the picker fetch.
const resolveMentionMock = vi.fn()
vi.mock("@/bridgeable-admin/services/document-mentions-service", async () => {
  const actual = await vi.importActual<
    typeof import("@/bridgeable-admin/services/document-mentions-service")
  >("@/bridgeable-admin/services/document-mentions-service")
  return {
    ...actual,
    resolveMention: (...args: unknown[]) => resolveMentionMock(...args),
  }
})


beforeEach(() => {
  resolveMentionMock.mockReset()
  resolveMentionMock.mockResolvedValue({ results: [], total: 0 })
})


function ControlledHarness({
  initial = "",
  supportsMentions = false,
  multiline = false,
}: {
  initial?: string
  supportsMentions?: boolean
  multiline?: boolean
}) {
  const [value, setValue] = useState(initial)
  return (
    <div>
      <StringControl
        value={value}
        onChange={setValue}
        supportsMentions={supportsMentions}
        multiline={multiline}
      />
      <div data-testid="emitted-value">{value}</div>
    </div>
  )
}


// MentionPicker testid inside StringControl — StringControl wraps the
// picker with `${testid}-mention` (default testid="prop-string" → root
// "prop-string-mention").
const MENTION_TESTID = "prop-string-mention"


describe("StringControl — supportsMentions=false (default)", () => {
  it("does NOT render MentionPicker when supportsMentions is unset", () => {
    const { queryByTestId } = render(<ControlledHarness />)
    expect(queryByTestId(MENTION_TESTID)).toBeNull()
  })

  it("data-supports-mentions attribute reflects false", () => {
    const { getByTestId } = render(<ControlledHarness />)
    expect(
      getByTestId("prop-string-input").getAttribute("data-supports-mentions"),
    ).toBe("false")
  })

  it("typing `@` does NOT open picker when supportsMentions=false", () => {
    const { getByTestId, queryByTestId } = render(<ControlledHarness />)
    const input = getByTestId("prop-string-input") as HTMLInputElement
    fireEvent.change(input, { target: { value: "@" } })
    expect(queryByTestId(MENTION_TESTID)).toBeNull()
  })
})


describe("StringControl — supportsMentions=true", () => {
  it("data-supports-mentions attribute reflects true", () => {
    const { getByTestId } = render(<ControlledHarness supportsMentions />)
    expect(
      getByTestId("prop-string-input").getAttribute("data-supports-mentions"),
    ).toBe("true")
  })

  it("renders multiline variant when multiline=true", () => {
    const { getByTestId } = render(
      <ControlledHarness supportsMentions multiline />,
    )
    const el = getByTestId("prop-string-input")
    expect(el.tagName).toBe("TEXTAREA")
  })

  it("renders input variant when multiline=false", () => {
    const { getByTestId } = render(<ControlledHarness supportsMentions />)
    const el = getByTestId("prop-string-input")
    expect(el.tagName).toBe("INPUT")
  })

  it("typing `@` at start opens MentionPicker", () => {
    const { getByTestId } = render(<ControlledHarness supportsMentions />)
    const input = getByTestId("prop-string-input") as HTMLInputElement
    // Per testing-library semantics, fireEvent.change(input, {target: {value}})
    // sets input.value and fires the change event; jsdom positions
    // selectionStart at end of new value automatically.
    fireEvent.change(input, { target: { value: "@" } })
    expect(getByTestId(MENTION_TESTID)).toBeTruthy()
  })

  it("preserves emitted value via onChange", () => {
    const { getByTestId } = render(
      <ControlledHarness initial="" supportsMentions />,
    )
    const input = getByTestId("prop-string-input") as HTMLInputElement
    fireEvent.change(input, { target: { value: "hello" } })
    expect(getByTestId("emitted-value").textContent).toBe("hello")
  })
})


describe("PropControlDispatcher — supportsMentions threading", () => {
  it("threads supportsMentions=true from schema down to StringControl", () => {
    const schema: ConfigPropSchema = {
      type: "string",
      default: "",
      supportsMentions: true,
    }
    const onChange = vi.fn()
    const { getByTestId } = render(
      <PropControlDispatcher
        schema={schema}
        value="initial"
        onChange={onChange}
        data-testid="dispatcher"
      />,
    )
    expect(
      getByTestId("dispatcher-input").getAttribute("data-supports-mentions"),
    ).toBe("true")
  })

  it("defaults supportsMentions to false when schema omits it", () => {
    const schema: ConfigPropSchema = {
      type: "string",
      default: "",
    }
    const onChange = vi.fn()
    const { getByTestId } = render(
      <PropControlDispatcher
        schema={schema}
        value="initial"
        onChange={onChange}
        data-testid="dispatcher"
      />,
    )
    expect(
      getByTestId("dispatcher-input").getAttribute("data-supports-mentions"),
    ).toBe("false")
  })

  it("threads multiline + supportsMentions from schema.bounds + flag", () => {
    const schema: ConfigPropSchema = {
      type: "string",
      default: "",
      bounds: { multiline: true },
      supportsMentions: true,
    }
    const onChange = vi.fn()
    const { getByTestId } = render(
      <PropControlDispatcher
        schema={schema}
        value="initial"
        onChange={onChange}
        data-testid="dispatcher"
      />,
    )
    const el = getByTestId("dispatcher-input")
    expect(el.tagName).toBe("TEXTAREA")
    expect(el.getAttribute("data-supports-mentions")).toBe("true")
  })
})


describe("Arc 4b.2b — 4 field sites carry supportsMentions=true", () => {
  it("header.title schema declares supportsMentions=true", async () => {
    const { HEADER_BLOCK_SCHEMA } = await import(
      "@/lib/visual-editor/registry/registrations/document-blocks-config"
    )
    expect(HEADER_BLOCK_SCHEMA.title.supportsMentions).toBe(true)
  })

  it("header.subtitle schema declares supportsMentions=true", async () => {
    const { HEADER_BLOCK_SCHEMA } = await import(
      "@/lib/visual-editor/registry/registrations/document-blocks-config"
    )
    expect(HEADER_BLOCK_SCHEMA.subtitle.supportsMentions).toBe(true)
  })

  it("body_section.heading schema declares supportsMentions=true", async () => {
    const { BODY_SECTION_BLOCK_SCHEMA } = await import(
      "@/lib/visual-editor/registry/registrations/document-blocks-config"
    )
    expect(BODY_SECTION_BLOCK_SCHEMA.heading.supportsMentions).toBe(true)
  })

  it("body_section.body schema declares supportsMentions=true AND multiline", async () => {
    const { BODY_SECTION_BLOCK_SCHEMA } = await import(
      "@/lib/visual-editor/registry/registrations/document-blocks-config"
    )
    expect(BODY_SECTION_BLOCK_SCHEMA.body.supportsMentions).toBe(true)
    expect(
      (BODY_SECTION_BLOCK_SCHEMA.body.bounds as { multiline?: boolean })
        ?.multiline,
    ).toBe(true)
  })

  it("non-mention fields (accent_color, items_variable) do NOT declare supportsMentions", async () => {
    const { HEADER_BLOCK_SCHEMA, BODY_SECTION_BLOCK_SCHEMA, LINE_ITEMS_BLOCK_SCHEMA } =
      await import(
        "@/lib/visual-editor/registry/registrations/document-blocks-config"
      )
    expect(HEADER_BLOCK_SCHEMA.accent_color.supportsMentions).toBeUndefined()
    expect(
      BODY_SECTION_BLOCK_SCHEMA.accent_color.supportsMentions,
    ).toBeUndefined()
    expect(LINE_ITEMS_BLOCK_SCHEMA.items_variable.supportsMentions).toBeUndefined()
  })
})
