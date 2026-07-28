/**
 * QuoteFocusWithAccessories (S-3a) — the RE-HOST proof.
 *
 * The architectural point of S-3a: the S-2 command-bar surfaces mount
 * UNCHANGED inside the quote Focus via the same getWidgetRenderer
 * contract — proving the host-agnostic claim at the Focus core+pin layer.
 * These tests pin: the display core dispatches `surface.quote-preview`
 * with the draft config; the pin dispatches `surface.price-list-reference`
 * with products derived from the draft; the pin suppresses with no lines;
 * and the empty state renders when the ephemeral draft is absent.
 */

import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

import {
  _resetWidgetRendererRegistryForTests,
  registerWidgetRenderer,
  type WidgetRendererProps,
} from "@/components/focus/canvas/widget-renderers"
import type { ExtractionContext } from "@/components/command-bar-surfaces/types"

// Feed currentFocus.params.extraction without standing up FocusProvider
// (open() writes URL + fires an async POST — too heavy for a unit).
let mockExtraction: ExtractionContext | null = null
vi.mock("@/contexts/focus-context", () => ({
  useFocus: () => ({
    currentFocus: {
      id: "quote-building",
      params: mockExtraction ? { extraction: mockExtraction } : {},
    },
  }),
}))

// Import AFTER the mock so the component picks it up. Also runs the
// registration side-effect for the registration test below.
import { QuoteFocusWithAccessories } from "./QuoteFocusWithAccessories"
import { QUOTE_FOCUS_ID } from "./register"
import { getFocusConfig } from "@/contexts/focus-registry"

function Fake({ widgetId, config, surface }: WidgetRendererProps) {
  return (
    <div
      data-testid={`fake:${widgetId}`}
      data-config={JSON.stringify(config ?? null)}
      data-surface={surface}
    />
  )
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const cfg = { id: "quote-building", mode: "editCanvas", displayName: "Quote" } as any

const draft: ExtractionContext = {
  entryIntent: "quote",
  customer: { id: "c1", name: "Hopkins Funeral Home" },
  lines: [{ productRef: "Monticello", quantity: 3 }],
  rawInput: "quote 3 Monticello for Hopkins",
}

beforeEach(() => {
  _resetWidgetRendererRegistryForTests()
  registerWidgetRenderer("surface.quote-preview", Fake)
  registerWidgetRenderer("surface.price-list-reference", Fake)
  mockExtraction = null
})

describe("QuoteFocusWithAccessories — S-3a display core", () => {
  it("registers the quote Focus (editCanvas mode, display coreComponent override)", () => {
    const c = getFocusConfig(QUOTE_FOCUS_ID)
    expect(c).toBeTruthy()
    // §5.2 forward-stable identity — S-3b swaps the core, keeps the mode.
    expect(c?.mode).toBe("editCanvas")
    // A coreComponent override is registered (the disabled EditCanvasCore
    // stub is NOT used).
    expect(c?.coreComponent).toBeTruthy()
  })

  it("renders the empty state when the ephemeral draft is absent (no data persisted)", () => {
    mockExtraction = null
    render(<QuoteFocusWithAccessories focusId="quote-building" config={cfg} />)
    expect(screen.getByText(/No quote in progress/i)).toBeInTheDocument()
    expect(
      screen.queryByTestId("fake:quote-focus:preview"),
    ).not.toBeInTheDocument()
  })

  it("re-hosts the S-2 quote-preview as the core with the draft config", () => {
    mockExtraction = draft
    render(<QuoteFocusWithAccessories focusId="quote-building" config={cfg} />)
    const preview = screen.getByTestId("fake:quote-focus:preview")
    expect(preview).toHaveAttribute("data-surface", "focus_canvas")
    expect(preview).toHaveAttribute(
      "data-config",
      JSON.stringify({ customer: draft.customer, lines: draft.lines }),
    )
  })

  it("re-hosts the price-list pin with products derived from the draft", () => {
    mockExtraction = draft
    render(<QuoteFocusWithAccessories focusId="quote-building" config={cfg} />)
    const pin = screen.getByTestId("fake:quote-focus:price-list")
    expect(pin).toHaveAttribute(
      "data-config",
      JSON.stringify({ products: ["Monticello"], customerId: "c1" }),
    )
  })

  it("suppresses the price-list pin when there are no lines (customer only)", () => {
    mockExtraction = { ...draft, lines: [] }
    render(<QuoteFocusWithAccessories focusId="quote-building" config={cfg} />)
    expect(screen.getByTestId("fake:quote-focus:preview")).toBeInTheDocument()
    expect(
      screen.queryByTestId("fake:quote-focus:price-list"),
    ).not.toBeInTheDocument()
  })
})
