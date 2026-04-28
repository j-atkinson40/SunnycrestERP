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

  it("aria-label describes the item + drag intent", () => {
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
    // Phase 4.3b.3.2 — aria-label updated to whole-item drag style
    // ("Marker base — drag to assign or attach"). No "pool"
    // qualifier needed since the row is intrinsically inside the pool.
    expect(row?.getAttribute("aria-label")).toMatch(/marker base/i)
    expect(row?.getAttribute("aria-label")).toMatch(/drag/i)
  })
})


// Phase 4.3b.3.2 — whole-item drag invariant (no grip handle).
//
// Platform principle (canonicalized in PRODUCT_PRINCIPLES.md):
// drag handles are an anti-pattern. Every draggable surface
// supports whole-element drag via PointerSensor activation
// constraint (distance: 8). This regression-guards the principle
// for AncillaryPoolPin specifically.
describe("AncillaryPoolPin — whole-item drag (no grip handle)", () => {
  it("does NOT render a GripVertical icon (drag handles are anti-pattern)", () => {
    const item = makePoolItem({ id: "anc-1" })
    render(
      <Harness contextValue={makeContext({ poolAncillaries: [item] })}>
        <AncillaryPoolPin />
      </Harness>,
    )
    // Lucide icons render as SVGs with class containing "lucide-grip-vertical"
    // OR pre-classed via the icon component name. The structural assertion:
    // no SVG with that data-attribute or class inside the pin.
    const allSvgs = document.querySelectorAll(
      '[data-slot="ancillary-pool-pin"] svg',
    )
    const hasGrip = Array.from(allSvgs).some((svg) => {
      const cls = svg.getAttribute("class") ?? ""
      return cls.includes("lucide-grip-vertical")
    })
    expect(hasGrip).toBe(false)
  })

  it("draggable listeners + ref attach to the row container itself (not a sub-handle)", () => {
    const item = makePoolItem({ id: "anc-1" })
    render(
      <Harness contextValue={makeContext({ poolAncillaries: [item] })}>
        <AncillaryPoolPin />
      </Harness>,
    )
    const row = document.querySelector(
      '[data-slot="ancillary-pool-item"]',
    ) as HTMLElement
    // The row IS the draggable surface; useDraggable applies
    // aria-roledescription="draggable" + role="button" on the
    // element with the listeners. If grip-handle pattern were in
    // place, these would be on a child instead.
    expect(row.getAttribute("aria-roledescription")).toBe("draggable")
    expect(row.getAttribute("role")).toBe("button")
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


// Phase 4.3b.4 — pin as drop target.
//
// AncillaryPoolPin's outer container becomes a useDroppable consumer
// for the canonical "ancillary-pool" id. Standalone + attached
// ancillaries dropping here trigger return-to-pool;
// SchedulingKanbanCore's drag handler routes the API call. This
// suite covers the pin's structural side: droppable wired,
// data-pool-drop-target stamps correctly when the visual feedback
// gate is satisfied.
describe("AncillaryPoolPin — drop target (Phase 4.3b.4)", () => {
  it("renders data-pool-drop-target=false at rest (no active drag)", () => {
    render(
      <Harness contextValue={makeContext({ poolAncillaries: [] })}>
        <AncillaryPoolPin />
      </Harness>,
    )
    const root = document.querySelector(
      '[data-slot="ancillary-pool-pin"]',
    ) as HTMLElement
    expect(root.getAttribute("data-pool-drop-target")).toBe("false")
  })

  it("exports stable droppable id constant matching the handler", async () => {
    // The pin's useDroppable id and the kanban core's drop-routing
    // logic share the canonical string via a single export. Drift
    // would silently break drag-to-pool. This test asserts the
    // export exists and is the expected value.
    const mod = await import("./AncillaryPoolPin")
    expect(mod.ANCILLARY_POOL_DROPPABLE_ID).toBe("ancillary-pool")
  })

  it("empty state copy stays default when no active drag", () => {
    render(
      <Harness contextValue={makeContext({ poolAncillaries: [] })}>
        <AncillaryPoolPin />
      </Harness>,
    )
    const empty = document.querySelector(
      '[data-slot="ancillary-pool-pin-empty"]',
    )
    expect(empty?.textContent).toMatch(/No pool items/)
    expect(empty?.textContent).toMatch(/Pair complete/)
    // No "Drop to return" copy when no drag is active.
    expect(empty?.textContent).not.toMatch(/Drop to return/)
  })
})


// ── Widget Library Phase W-2 — Glance variant ───────────────────────


describe("AncillaryPoolPin — Glance variant (Phase W-2)", () => {
  it("renders Glance variant when surface=spaces_pin", () => {
    render(
      <Harness contextValue={makeContext({ poolAncillaries: [] })}>
        <AncillaryPoolPin surface="spaces_pin" />
      </Harness>,
    )
    const glance = document.querySelector(
      '[data-slot="ancillary-pool-pin"][data-variant="glance"]',
    )
    expect(glance).toBeInTheDocument()
    // Glance does NOT render the Detail-variant list / empty.
    expect(
      document.querySelector('[data-slot="ancillary-pool-pin-list"]'),
    ).toBeNull()
    expect(
      document.querySelector('[data-slot="ancillary-pool-pin-empty"]'),
    ).toBeNull()
  })

  it("renders Glance variant when variant_id=glance", () => {
    render(
      <Harness contextValue={makeContext({ poolAncillaries: [] })}>
        <AncillaryPoolPin variant_id="glance" />
      </Harness>,
    )
    expect(
      document.querySelector(
        '[data-slot="ancillary-pool-pin"][data-variant="glance"]',
      ),
    ).toBeInTheDocument()
  })

  it("renders Detail variant by default (no variant_id, no surface)", () => {
    render(
      <Harness contextValue={makeContext({ poolAncillaries: [] })}>
        <AncillaryPoolPin />
      </Harness>,
    )
    // Detail variant has the empty-state slot; Glance does not.
    expect(
      document.querySelector('[data-slot="ancillary-pool-pin-empty"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector(
        '[data-slot="ancillary-pool-pin"][data-variant="glance"]',
      ),
    ).toBeNull()
  })

  it("Glance shows count chip when pool has items", () => {
    const items = [
      makePoolItem({ id: "a" }),
      makePoolItem({ id: "b" }),
      makePoolItem({ id: "c" }),
    ]
    render(
      <Harness contextValue={makeContext({ poolAncillaries: items })}>
        <AncillaryPoolPin surface="spaces_pin" />
      </Harness>,
    )
    const chip = document.querySelector(
      '[data-slot="ancillary-pool-pin-count"]',
    )
    expect(chip).toBeInTheDocument()
    expect(chip?.textContent).toBe("3")
    const subtext = document.querySelector(
      '[data-slot="ancillary-pool-pin-glance-subtext"]',
    )
    expect(subtext?.textContent).toMatch(/3 items waiting/)
  })

  it("Glance hides count chip when pool empty + shows 'Pool clear'", () => {
    render(
      <Harness contextValue={makeContext({ poolAncillaries: [] })}>
        <AncillaryPoolPin surface="spaces_pin" />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="ancillary-pool-pin-count"]'),
    ).toBeNull()
    const subtext = document.querySelector(
      '[data-slot="ancillary-pool-pin-glance-subtext"]',
    )
    expect(subtext?.textContent).toMatch(/Pool clear/)
  })

  it("Glance singular wording 'item' when count = 1", () => {
    const items = [makePoolItem({ id: "only" })]
    render(
      <Harness contextValue={makeContext({ poolAncillaries: items })}>
        <AncillaryPoolPin surface="spaces_pin" />
      </Harness>,
    )
    const subtext = document.querySelector(
      '[data-slot="ancillary-pool-pin-glance-subtext"]',
    )
    expect(subtext?.textContent).toMatch(/1 item waiting/)
    // Should NOT pluralize when 1.
    expect(subtext?.textContent).not.toMatch(/items waiting/)
  })

  it("Glance carries role=button + tabIndex=0 for keyboard summon", () => {
    render(
      <Harness contextValue={makeContext({ poolAncillaries: [] })}>
        <AncillaryPoolPin surface="spaces_pin" />
      </Harness>,
    )
    const glance = document.querySelector(
      '[data-slot="ancillary-pool-pin"][data-variant="glance"]',
    ) as HTMLElement
    expect(glance.getAttribute("role")).toBe("button")
    expect(glance.getAttribute("tabIndex")).toBe("0")
    expect(glance.getAttribute("aria-label")).toMatch(/Ancillary pool/)
  })

  it("Glance keeps eyebrow + bezel grip from Pattern 1 reference", () => {
    render(
      <Harness contextValue={makeContext({ poolAncillaries: [] })}>
        <AncillaryPoolPin surface="spaces_pin" />
      </Harness>,
    )
    // Eyebrow label is consistent across variants — same identifying
    // tablet name "Ancillary pool" reads on canvas + sidebar.
    expect(
      document.querySelector(
        '[data-slot="ancillary-pool-pin-eyebrow"]',
      )?.textContent,
    ).toBe("Ancillary pool")
    // Bezel grip column is the Pattern 1 structural left edge —
    // identical between Glance + Detail.
    expect(
      document.querySelector('[data-slot="ancillary-pool-pin-bezel-grip"]'),
    ).toBeInTheDocument()
  })

  it("Glance renders without a Focus provider (sidebar mounting)", () => {
    // Spaces sidebar mounts the widget OUTSIDE the funeral-scheduling
    // Focus, so the SchedulingFocusContext provider isn't present.
    // Glance must degrade gracefully (count=0) — Detail variant
    // would crash in this mounting per its hard-hook contract.
    // Render directly with no Provider wrapper; Glance variant
    // doesn't need DndContext (no draggables in the Glance shape).
    render(<AncillaryPoolPin surface="spaces_pin" />)
    const glance = document.querySelector(
      '[data-slot="ancillary-pool-pin"][data-variant="glance"]',
    )
    expect(glance).toBeInTheDocument()
    // No items, no count chip; subtext shows "Pool clear".
    expect(
      document.querySelector('[data-slot="ancillary-pool-pin-count"]'),
    ).toBeNull()
    expect(
      document.querySelector(
        '[data-slot="ancillary-pool-pin-glance-subtext"]',
      )?.textContent,
    ).toMatch(/Pool clear/)
  })
})
