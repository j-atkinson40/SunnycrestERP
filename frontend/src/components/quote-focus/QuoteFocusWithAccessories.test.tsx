/**
 * QuoteFocusWithAccessories (S-3b) — the EDITABLE quote core.
 *
 * S-3a proved the re-host with a read-only preview core; S-3b swaps in the
 * edit canvas. These tests pin: the register identity (editCanvas mode +
 * coreComponent override, unchanged across the swap); the seeded
 * extraction renders as editable line rows; the price-list PIN derives its
 * products from the LIVE draft and suppresses with no lines; and the
 * add-line affordance is present. Repricing + persistence services are
 * mocked (async network + debounce timers are out of scope for a unit).
 */

import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

import {
  _resetWidgetRendererRegistryForTests,
  registerWidgetRenderer,
  type WidgetRendererProps,
} from "@/components/focus/canvas/widget-renderers"
import type { ExtractionContext } from "@/components/command-bar-surfaces/types"

// Feed currentFocus without standing up FocusProvider. sessionId=null so
// the persistence effect is a no-op; draftState=null so no hydration.
let mockExtraction: ExtractionContext | null = null
vi.mock("@/contexts/focus-context", () => ({
  useFocus: () => ({
    currentFocus: {
      id: "quote-building",
      params: mockExtraction ? { extraction: mockExtraction } : {},
      sessionId: null,
      draftState: null,
    },
  }),
}))

// Mock the data services — the component fires a reprice on mount and the
// combobox lazy-searches; neither should hit the network in a unit.
vi.mock("@/services/quote-preview-service", async (importActual) => {
  const actual = await importActual<
    typeof import("@/services/quote-preview-service")
  >()
  return {
    ...actual,
    fetchQuotePreview: vi.fn().mockResolvedValue({
      html: "",
      subtotal_formatted: "$0.00",
      total_formatted: null,
      tax_resolved: false,
      has_call_office: false,
      unresolved_products: [],
      ambiguous_products: [],
      line_count: 0,
      lines: [],
    }),
    searchQuoteProducts: vi.fn().mockResolvedValue([]),
  }
})
vi.mock("@/services/focus-service", () => ({
  saveFocusDraft: vi.fn().mockResolvedValue({}),
}))

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
  registerWidgetRenderer("surface.price-list-reference", Fake)
  mockExtraction = null
})

describe("QuoteFocusWithAccessories — S-3b edit canvas", () => {
  it("registers the quote Focus (editCanvas mode, coreComponent override)", () => {
    const c = getFocusConfig(QUOTE_FOCUS_ID)
    expect(c).toBeTruthy()
    // §5.2 forward-stable identity — S-3b kept the mode, swapped the core.
    expect(c?.mode).toBe("editCanvas")
    expect(c?.coreComponent).toBeTruthy()
  })

  it("renders the edit canvas with editable rows seeded from the extraction", () => {
    mockExtraction = draft
    render(<QuoteFocusWithAccessories focusId="quote-building" config={cfg} />)
    expect(screen.getByTestId("quote-edit-canvas")).toBeInTheDocument()
    // The seeded line renders as an editable row (product + qty input).
    expect(screen.getByText("Monticello")).toBeInTheDocument()
    const rows = screen.getAllByTestId("quote-line-row")
    expect(rows).toHaveLength(1)
    expect(screen.getByTestId("quote-line-qty")).toHaveValue(3)
    // Customer surfaces in the header.
    expect(screen.getByText("Hopkins Funeral Home")).toBeInTheDocument()
  })

  it("offers the add-line affordance", () => {
    mockExtraction = draft
    render(<QuoteFocusWithAccessories focusId="quote-building" config={cfg} />)
    expect(screen.getByTestId("quote-add-line")).toBeInTheDocument()
  })

  it("re-hosts the price-list pin with products derived from the LIVE draft", () => {
    mockExtraction = draft
    render(<QuoteFocusWithAccessories focusId="quote-building" config={cfg} />)
    const pin = screen.getByTestId("fake:quote-focus:price-list")
    expect(pin).toHaveAttribute("data-surface", "focus_canvas")
    expect(pin).toHaveAttribute(
      "data-config",
      JSON.stringify({ products: ["Monticello"], customerId: "c1" }),
    )
  })

  it("suppresses the price-list pin when there are no lines (empty canvas)", () => {
    mockExtraction = { ...draft, lines: [] }
    render(<QuoteFocusWithAccessories focusId="quote-building" config={cfg} />)
    expect(screen.getByTestId("quote-edit-canvas")).toBeInTheDocument()
    expect(
      screen.queryByTestId("fake:quote-focus:price-list"),
    ).not.toBeInTheDocument()
  })

  it("renders the save primary as deferred (no materialization path yet)", () => {
    mockExtraction = draft
    render(<QuoteFocusWithAccessories focusId="quote-building" config={cfg} />)
    const save = screen.getByTestId("quote-save")
    expect(save).toBeDisabled()
  })
})
