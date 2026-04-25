/**
 * AncillaryPoolPin — vitest unit tests.
 *
 * Covers:
 *   - Empty state when pool is empty
 *   - Populated state renders one item per pool ancillary
 *   - Headline label fallback chain (product_summary → vault_type →
 *     delivery_type label)
 *   - Subhead resolution (family_name → funeral_home_name)
 *   - Count badge reflects pool length
 *   - Each item has draggable attributes (aria-roledescription,
 *     data-ancillary-id, ancillary: drag id via dnd-kit)
 *   - Hook contract: throws when mounted outside provider
 *   - Loading state subdues the surface
 *
 * Drag motion (pointer events) is not exercised here — testing-
 * library / jsdom can't reliably drive @dnd-kit's window-level
 * sensors. End-to-end drag verification lives in manual + Playwright
 * paths.
 */

import { render } from "@testing-library/react"
import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core"
import { afterEach, describe, expect, it, vi } from "vitest"

import {
  SchedulingFocusContext,
  type SchedulingFocusContextValue,
} from "@/contexts/scheduling-focus-context"
import type { DeliveryDTO } from "@/services/dispatch-service"

import { AncillaryPoolPin } from "./AncillaryPoolPin"


function makePoolItem(overrides: Partial<DeliveryDTO> = {}): DeliveryDTO {
  return {
    id: "anc-" + Math.random().toString(36).slice(2, 8),
    company_id: "co-1",
    order_id: null,
    customer_id: null,
    delivery_type: "funeral_home_pickup",
    status: "pending",
    priority: "normal",
    requested_date: null,
    scheduled_at: null,
    completed_at: null,
    scheduling_type: "ancillary",
    ancillary_fulfillment_status: "unassigned",
    direct_ship_status: null,
    primary_assignee_id: null,
    helper_user_id: null,
    attached_to_delivery_id: null,
    driver_start_time: null,
    helper_user_name: null,
    attached_to_family_name: null,
    hole_dug_status: "unknown",
    type_config: null,
    special_instructions: null,
    ...overrides,
  }
}


function Harness({
  contextValue,
  children,
}: {
  contextValue: SchedulingFocusContextValue
  children: React.ReactNode
}) {
  // DndContext required because PoolItem uses useDraggable; no
  // listeners necessary for these structural tests.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  )
  return (
    <DndContext sensors={sensors}>
      <SchedulingFocusContext.Provider value={contextValue}>
        {children}
      </SchedulingFocusContext.Provider>
    </DndContext>
  )
}


function makeContext(
  overrides: Partial<SchedulingFocusContextValue> = {},
): SchedulingFocusContextValue {
  return {
    poolAncillaries: [],
    poolLoading: false,
    reloadPool: vi.fn(),
    removeFromPoolOptimistic: vi.fn(),
    ...overrides,
  }
}


afterEach(() => {
  vi.clearAllMocks()
})


describe("AncillaryPoolPin — empty state", () => {
  it("renders the eyebrow header even when pool is empty", () => {
    render(
      <Harness contextValue={makeContext({ poolAncillaries: [] })}>
        <AncillaryPoolPin />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="ancillary-pool-pin-header"]'),
    ).toBeInTheDocument()
    // Header carries the "Ancillary pool" eyebrow.
    expect(document.body.textContent).toContain("Ancillary pool")
  })

  it("renders empty-state copy when no pool items + not loading", () => {
    render(
      <Harness contextValue={makeContext({ poolAncillaries: [] })}>
        <AncillaryPoolPin />
      </Harness>,
    )
    const empty = document.querySelector(
      '[data-slot="ancillary-pool-pin-empty"]',
    )
    expect(empty).toBeInTheDocument()
    expect(empty?.textContent).toMatch(/No pool items/)
  })

  it("hides empty-state copy while loading (subdued list, not spinner)", () => {
    render(
      <Harness
        contextValue={makeContext({
          poolAncillaries: [],
          poolLoading: true,
        })}
      >
        <AncillaryPoolPin />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="ancillary-pool-pin-empty"]'),
    ).toBeNull()
  })

  it("hides count badge when pool is empty", () => {
    render(
      <Harness contextValue={makeContext({ poolAncillaries: [] })}>
        <AncillaryPoolPin />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="ancillary-pool-pin-count"]'),
    ).toBeNull()
  })
})


describe("AncillaryPoolPin — populated state", () => {
  it("renders one item per pool ancillary", () => {
    const items = [
      makePoolItem({ id: "anc-1", type_config: { product_summary: "Urn vault" } }),
      makePoolItem({ id: "anc-2", type_config: { product_summary: "Marker base" } }),
      makePoolItem({ id: "anc-3", type_config: { vault_type: "Cameo Rose" } }),
    ]
    render(
      <Harness contextValue={makeContext({ poolAncillaries: items })}>
        <AncillaryPoolPin />
      </Harness>,
    )
    const rows = document.querySelectorAll(
      '[data-slot="ancillary-pool-item"]',
    )
    expect(rows.length).toBe(3)
  })

  it("count badge shows total pool length", () => {
    const items = [
      makePoolItem({ id: "anc-1" }),
      makePoolItem({ id: "anc-2" }),
    ]
    render(
      <Harness contextValue={makeContext({ poolAncillaries: items })}>
        <AncillaryPoolPin />
      </Harness>,
    )
    const badge = document.querySelector(
      '[data-slot="ancillary-pool-pin-count"]',
    )
    expect(badge?.textContent).toBe("2")
  })

  it("headline label uses product_summary when present", () => {
    const item = makePoolItem({
      id: "anc-1",
      type_config: { product_summary: "Urn vault (rider)" },
    })
    render(
      <Harness contextValue={makeContext({ poolAncillaries: [item] })}>
        <AncillaryPoolPin />
      </Harness>,
    )
    const row = document.querySelector(
      '[data-slot="ancillary-pool-item"]',
    )
    expect(row?.textContent).toContain("Urn vault (rider)")
  })

  it("headline falls back to vault_type when product_summary missing", () => {
    const item = makePoolItem({
      id: "anc-1",
      type_config: { vault_type: "Cameo Rose" },
    })
    render(
      <Harness contextValue={makeContext({ poolAncillaries: [item] })}>
        <AncillaryPoolPin />
      </Harness>,
    )
    expect(document.body.textContent).toContain("Cameo Rose")
  })

  it("headline falls back to delivery_type label when both missing", () => {
    const item = makePoolItem({
      id: "anc-1",
      delivery_type: "funeral_home_dropoff",
      type_config: null,
    })
    render(
      <Harness contextValue={makeContext({ poolAncillaries: [item] })}>
        <AncillaryPoolPin />
      </Harness>,
    )
    expect(document.body.textContent).toContain("Drop-off")
  })

  it("subhead uses family_name when present", () => {
    const item = makePoolItem({
      id: "anc-1",
      type_config: {
        product_summary: "Urn vault",
        family_name: "Lombardi",
      },
    })
    render(
      <Harness contextValue={makeContext({ poolAncillaries: [item] })}>
        <AncillaryPoolPin />
      </Harness>,
    )
    expect(document.body.textContent).toContain("Lombardi")
  })

  it("subhead falls back to funeral_home_name when family missing", () => {
    const item = makePoolItem({
      id: "anc-1",
      type_config: {
        product_summary: "Urn vault",
        funeral_home_name: "Memorial Chapel",
      },
    })
    render(
      <Harness contextValue={makeContext({ poolAncillaries: [item] })}>
        <AncillaryPoolPin />
      </Harness>,
    )
    expect(document.body.textContent).toContain("Memorial Chapel")
  })
})


describe("AncillaryPoolPin — drag wiring", () => {
  it("each item carries data-ancillary-id matching the delivery id", () => {
    const items = [
      makePoolItem({ id: "anc-abc-123" }),
      makePoolItem({ id: "anc-xyz-789" }),
    ]
    render(
      <Harness contextValue={makeContext({ poolAncillaries: items })}>
        <AncillaryPoolPin />
      </Harness>,
    )
    const rows = document.querySelectorAll(
      '[data-slot="ancillary-pool-item"]',
    )
    expect(rows[0].getAttribute("data-ancillary-id")).toBe("anc-abc-123")
    expect(rows[1].getAttribute("data-ancillary-id")).toBe("anc-xyz-789")
  })

  it("each item has aria-roledescription='draggable' (useDraggable wired)", () => {
    const items = [makePoolItem({ id: "anc-1" })]
    render(
      <Harness contextValue={makeContext({ poolAncillaries: items })}>
        <AncillaryPoolPin />
      </Harness>,
    )
    const row = document.querySelector(
      '[data-slot="ancillary-pool-item"]',
    )
    expect(row?.getAttribute("aria-roledescription")).toBe("draggable")
  })

  it("aria-label describes the drag intent + label", () => {
    const item = makePoolItem({
      id: "anc-1",
      type_config: { product_summary: "Marker base" },
    })
    render(
      <Harness contextValue={makeContext({ poolAncillaries: [item] })}>
        <AncillaryPoolPin />
      </Harness>,
    )
    const row = document.querySelector(
      '[data-slot="ancillary-pool-item"]',
    )
    expect(row?.getAttribute("aria-label")).toMatch(/drag.*marker base.*pool/i)
  })
})


describe("AncillaryPoolPin — provider contract", () => {
  it("throws when rendered outside SchedulingFocusContext.Provider", () => {
    // Suppress error log for the expected throw.
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {})
    expect(() => {
      render(
        <DndContext>
          <AncillaryPoolPin />
        </DndContext>,
      )
    }).toThrow(/useSchedulingFocus must be used inside/)
    consoleError.mockRestore()
  })
})


describe("AncillaryPoolPin — loading state", () => {
  it("subdues the surface (data-loading-style: opacity-80)", () => {
    render(
      <Harness
        contextValue={makeContext({
          poolAncillaries: [makePoolItem({ id: "anc-1" })],
          poolLoading: true,
        })}
      >
        <AncillaryPoolPin />
      </Harness>,
    )
    const root = document.querySelector(
      '[data-slot="ancillary-pool-pin"]',
    ) as HTMLElement
    expect(root.className).toMatch(/opacity-80/)
  })

  it("does not subdue the surface when not loading", () => {
    render(
      <Harness
        contextValue={makeContext({
          poolAncillaries: [makePoolItem({ id: "anc-1" })],
          poolLoading: false,
        })}
      >
        <AncillaryPoolPin />
      </Harness>,
    )
    const root = document.querySelector(
      '[data-slot="ancillary-pool-pin"]',
    ) as HTMLElement
    expect(root.className).not.toMatch(/opacity-80/)
  })
})
