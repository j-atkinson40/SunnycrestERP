/**
 * AncillaryCard — vitest unit tests. Phase 4.3.3 commit 2.
 *
 * Covers the reduced-field rendering contract, headline-fallback
 * priority, optional status-row rendering (only when a note is
 * present), and click-to-edit handler wiring. Drag physics aren't
 * exercised in jsdom (the same limitation that prevents real-pointer
 * @dnd-kit testing) — the structural data-slot contract is asserted
 * here; visual drag verification is via Playwright + manual.
 */

import { render } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core"

import { TooltipProvider } from "@/components/ui/tooltip"
import type { DeliveryDTO } from "@/services/dispatch-service"

import { AncillaryCard } from "./AncillaryCard"


function makeAncillary(overrides: Partial<DeliveryDTO> = {}): DeliveryDTO {
  return {
    id: "anc-1",
    company_id: "co-1",
    order_id: "so-1",
    customer_id: null,
    delivery_type: "funeral_home_dropoff",
    status: "pending",
    priority: "normal",
    requested_date: "2026-04-25",
    scheduled_at: null,
    completed_at: null,
    scheduling_type: "ancillary",
    ancillary_fulfillment_status: "assigned_to_driver",
    direct_ship_status: null,
    primary_assignee_id: "user-dave",
    helper_user_id: null,
    attached_to_delivery_id: null,
    driver_start_time: null,
    hole_dug_status: "unknown",
    type_config: {
      product_summary: "Urn vault",
      funeral_home_name: "Hopkins Funeral Home",
      cemetery_city: "Auburn",
    },
    special_instructions: null,
    ...overrides,
  }
}


function Harness({ children }: { children: React.ReactNode }) {
  // Mirrors DeliveryCard.test.tsx Harness — same activation
  // constraint + TooltipProvider mount, so click + tooltip tests
  // exercise the production drag/click contract.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  )
  return (
    <TooltipProvider delay={0}>
      <DndContext sensors={sensors}>{children}</DndContext>
    </TooltipProvider>
  )
}


// ── Headline resolution ───────────────────────────────────────────────


describe("AncillaryCard — headline label fallback chain", () => {
  it("uses type_config.product_summary when present", () => {
    render(
      <Harness>
        <AncillaryCard delivery={makeAncillary()} />
      </Harness>,
    )
    const product = document.querySelector(
      '[data-slot="dispatch-ancillary-card-product"]',
    )
    expect(product?.textContent).toBe("Urn vault")
  })

  it("falls back to type_config.vault_type when product_summary is absent", () => {
    render(
      <Harness>
        <AncillaryCard
          delivery={makeAncillary({
            type_config: {
              product_summary: undefined,
              vault_type: "Cameo Rose",
              funeral_home_name: "Hopkins",
            },
          })}
        />
      </Harness>,
    )
    const product = document.querySelector(
      '[data-slot="dispatch-ancillary-card-product"]',
    )
    expect(product?.textContent).toBe("Cameo Rose")
  })

  it("falls back to delivery_type label when product/vault both absent", () => {
    render(
      <Harness>
        <AncillaryCard
          delivery={makeAncillary({
            delivery_type: "funeral_home_pickup",
            type_config: { funeral_home_name: "Hopkins" },
          })}
        />
      </Harness>,
    )
    const product = document.querySelector(
      '[data-slot="dispatch-ancillary-card-product"]',
    )
    expect(product?.textContent).toBe("Pickup")
  })

  it("falls back to raw delivery_type for unknown ancillary types", () => {
    render(
      <Harness>
        <AncillaryCard
          delivery={makeAncillary({
            delivery_type: "future_unknown_type",
            type_config: {},
          })}
        />
      </Harness>,
    )
    const product = document.querySelector(
      '[data-slot="dispatch-ancillary-card-product"]',
    )
    expect(product?.textContent).toBe("future_unknown_type")
  })
})


// ── Reduced field set ────────────────────────────────────────────────


describe("AncillaryCard — reduced field set vs DeliveryCard", () => {
  it("renders product + destination + (no city when null)", () => {
    render(
      <Harness>
        <AncillaryCard
          delivery={makeAncillary({
            type_config: {
              product_summary: "Urn",
              funeral_home_name: "Hopkins",
              cemetery_city: null,
            },
          })}
        />
      </Harness>,
    )
    const dest = document.querySelector(
      '[data-slot="dispatch-ancillary-card-destination"]',
    )
    expect(dest?.textContent).toContain("Hopkins")
    expect(dest?.textContent).not.toContain("·")
  })

  it("renders city after destination separator when present", () => {
    render(
      <Harness>
        <AncillaryCard delivery={makeAncillary()} />
      </Harness>,
    )
    const dest = document.querySelector(
      '[data-slot="dispatch-ancillary-card-destination"]',
    )
    expect(dest?.textContent).toContain("Hopkins Funeral Home")
    expect(dest?.textContent).toContain("·")
    expect(dest?.textContent).toContain("Auburn")
  })

  it("does NOT render hole-dug, family icon, section icon, chat, equipment", () => {
    render(
      <Harness>
        <AncillaryCard delivery={makeAncillary()} />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-hole-dug-badge"]'),
    ).toBeNull()
    expect(
      document.querySelector('[data-slot="dispatch-icon-family"]'),
    ).toBeNull()
    expect(
      document.querySelector('[data-slot="dispatch-icon-section"]'),
    ).toBeNull()
    expect(
      document.querySelector('[data-slot="dispatch-icon-chat"]'),
    ).toBeNull()
    expect(
      document.querySelector('[data-slot="dispatch-card-product"]'),
    ).toBeNull()  // primary card's product line, distinct from ancillary's product
  })
})


// ── Status row (note icon only, conditionally) ───────────────────────


describe("AncillaryCard — status row icon visibility", () => {
  it("renders the note icon when type_config.driver_note is present", () => {
    render(
      <Harness>
        <AncillaryCard
          delivery={makeAncillary({
            type_config: {
              ...makeAncillary().type_config,
              driver_note: "Leave at the back loading dock",
            },
          })}
        />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-ancillary-icon-note"]'),
    ).toBeInTheDocument()
  })

  it("renders the note icon when special_instructions is present (driver_note absent)", () => {
    render(
      <Harness>
        <AncillaryCard
          delivery={makeAncillary({
            special_instructions: "Call FH on arrival",
          })}
        />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-ancillary-icon-note"]'),
    ).toBeInTheDocument()
  })

  it("collapses the entire status row when no note present", () => {
    render(
      <Harness>
        <AncillaryCard delivery={makeAncillary()} />
      </Harness>,
    )
    // Card body present; status row absent (no note in fixture).
    expect(
      document.querySelector('[data-slot="dispatch-ancillary-card-icon-row"]'),
    ).toBeNull()
    expect(
      document.querySelector('[data-slot="dispatch-ancillary-icon-note"]'),
    ).toBeNull()
  })
})


// ── Card chrome — DL §6 canonical (no perimeter border) ────────────


describe("AncillaryCard — DL §6 chrome canon", () => {
  it("uses bg-surface-elevated + shadow-level-1 + rounded-md, no border", () => {
    render(
      <Harness>
        <AncillaryCard delivery={makeAncillary()} />
      </Harness>,
    )
    const card = document.querySelector('[data-slot="dispatch-ancillary-card"]')
    const cls = card?.className ?? ""
    expect(cls).toMatch(/bg-surface-elevated/)
    expect(cls).toMatch(/shadow-level-1/)
    expect(cls).toMatch(/rounded-md/)
    // Phase 4.3.3 — DL §6 forbids perimeter border on cards. Same
    // regression guard pattern as DeliveryCard.test.tsx.
    expect(cls).not.toMatch(/\bborder\b(?!-)/)
    expect(cls).not.toMatch(/border-dashed/)
  })

  it("matches DeliveryCard's compact-card chrome tokens (sibling primitives)", () => {
    render(
      <Harness>
        <AncillaryCard delivery={makeAncillary()} />
      </Harness>,
    )
    const card = document.querySelector('[data-slot="dispatch-ancillary-card"]')
    const cls = card?.className ?? ""
    // Same tokens DeliveryCard uses — visual hierarchy comes from
    // padding/typography density, NOT from differing chrome.
    expect(cls).toMatch(/bg-surface-elevated/)
    expect(cls).toMatch(/shadow-level-1/)
    // Drag-lift physics token consistency
    expect(cls).toMatch(/cursor-grab/)
  })
})


// ── Click-to-edit ────────────────────────────────────────────────────


describe("AncillaryCard — body click fires onOpenEdit", () => {
  it("short click on body → onOpenEdit(delivery)", async () => {
    const user = userEvent.setup()
    const onOpenEdit = vi.fn()
    const ancillary = makeAncillary()
    render(
      <Harness>
        <AncillaryCard
          delivery={ancillary}
          onOpenEdit={onOpenEdit}
        />
      </Harness>,
    )
    const body = document.querySelector(
      '[data-slot="dispatch-ancillary-card-body"]',
    ) as HTMLElement
    await user.click(body)
    expect(onOpenEdit).toHaveBeenCalledWith(ancillary)
  })

  it("renders without onOpenEdit prop (graceful no-op)", async () => {
    const user = userEvent.setup()
    render(
      <Harness>
        <AncillaryCard delivery={makeAncillary()} />
      </Harness>,
    )
    const body = document.querySelector(
      '[data-slot="dispatch-ancillary-card-body"]',
    ) as HTMLElement
    // Should not throw when callback is undefined.
    await user.click(body)
    expect(body).toBeInTheDocument()
  })
})


// ── Drag wiring (DOM contract only — physics tested in Playwright) ──


describe("AncillaryCard — drag DOM contract", () => {
  it("carries data-delivery-id + data-dragging attributes", () => {
    render(
      <Harness>
        <AncillaryCard delivery={makeAncillary({ id: "anc-xyz" })} />
      </Harness>,
    )
    const card = document.querySelector('[data-slot="dispatch-ancillary-card"]')
    expect(card?.getAttribute("data-delivery-id")).toBe("anc-xyz")
    expect(card?.getAttribute("data-dragging")).toBe("false")
  })

  it("uses delivery: prefixed drag id (consistent with DeliveryCard)", () => {
    // Phase 4.3.3 — drag id format is `delivery:<id>` for both card
    // types so SchedulingKanbanCore's onDragEnd handler can treat
    // them uniformly. No `ancillary:<id>` prefix; same prefix.
    // We can't introspect @dnd-kit's internal id directly, but we
    // can verify the DOM has a stable selector:
    render(
      <Harness>
        <AncillaryCard delivery={makeAncillary({ id: "anc-7" })} />
      </Harness>,
    )
    const card = document.querySelector('[data-delivery-id="anc-7"]')
    expect(card).toBeInTheDocument()
  })
})
