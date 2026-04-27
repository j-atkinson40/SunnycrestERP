/**
 * DeliveryCard — vitest unit tests. Phase B Session 1 Phase 3.1+3.2.
 *
 * Covers visual-state rendering (draft/finalized border, no
 * service-type tints post-3.1), hole-dug three-state cycle (no null),
 * ancillary badge toggle, icon+tooltip compaction row (family / note
 * / chat / section), primary text hierarchy (FH headline, cemetery ·
 * city, service-time with ETA, vault · equipment), and body
 * click-to-edit.
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

import { DeliveryCard, nextHoleDugStatus } from "./DeliveryCard"


// ── Fixtures ──────────────────────────────────────────────────────────


function makeDelivery(overrides: Partial<DeliveryDTO> = {}): DeliveryDTO {
  return {
    id: "del-1",
    company_id: "co-1",
    order_id: "so-1",
    customer_id: "cust-1",
    delivery_type: "vault",
    status: "scheduled",
    priority: "normal",
    requested_date: "2026-04-23",
    scheduled_at: "2026-04-23T14:00:00Z",
    completed_at: null,
    scheduling_type: "kanban",
    ancillary_fulfillment_status: null,
    direct_ship_status: null,
    primary_assignee_id: "driver-1",
    helper_user_id: null,
    attached_to_delivery_id: null,
    driver_start_time: null,
    helper_user_name: null,
    attached_to_family_name: null,
    hole_dug_status: "unknown",
    type_config: {
      family_name: "Fitzgerald",
      cemetery_name: "St. Joseph's Cemetery",
      cemetery_city: "Auburn",
      cemetery_section: "Sec 14, Lot 42B",
      funeral_home_name: "Johnson Funeral Home",
      service_time: "10:00",
      service_type: "graveside",
      vault_type: "Monticello",
      equipment_type: "Full w/ Placer",
    },
    special_instructions: null,
    ...overrides,
  }
}


function Harness({ children }: { children: React.ReactNode }) {
  // TooltipProvider mirrors the app-root mount (for the icon+tooltip
  // compaction row). DndContext required by useDraggable.
  //
  // Phase 4.2.4 — PointerSensor configured with the same activation
  // constraint as production (distance: 8). Without this, any
  // pointerdown on the body would activate drag and suppress the
  // subsequent click — breaking the "short click opens detail"
  // contract the test exercises.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  )
  return (
    <TooltipProvider delay={0}>
      <DndContext sensors={sensors}>{children}</DndContext>
    </TooltipProvider>
  )
}


// ── Tests ─────────────────────────────────────────────────────────────


describe("nextHoleDugStatus three-state cycle (Phase 3.1)", () => {
  it("cycles unknown → yes → no → unknown (no null state)", () => {
    expect(nextHoleDugStatus("unknown")).toBe("yes")
    expect(nextHoleDugStatus("yes")).toBe("no")
    expect(nextHoleDugStatus("no")).toBe("unknown")
  })
})


describe("DeliveryCard — primary text hierarchy (Phase 3.1)", () => {
  it("funeral home is the headline", () => {
    const base = makeDelivery()
    render(
      <Harness>
        <DeliveryCard
          delivery={{ ...base, type_config: { ...base.type_config } }}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    const fh = document.querySelector('[data-slot="dispatch-card-fh"]')
    expect(fh).toBeInTheDocument()
    expect(fh?.textContent).toBe("Johnson Funeral Home")
  })

  it("cemetery line shows name · city", () => {
    const base = makeDelivery()
    render(
      <Harness>
        <DeliveryCard delivery={base} scheduleFinalized={false} />
      </Harness>,
    )
    const cem = document.querySelector('[data-slot="dispatch-card-cemetery"]')
    expect(cem).toBeInTheDocument()
    expect(cem?.textContent).toMatch(/St\. Joseph's Cemetery/)
    expect(cem?.textContent).toMatch(/Auburn/)
  })

  it("service time line — graveside shows only time + location, no ETA", () => {
    const base = makeDelivery()
    render(
      <Harness>
        <DeliveryCard delivery={base} scheduleFinalized={false} />
      </Harness>,
    )
    const line = document.querySelector('[data-slot="dispatch-card-timeline"]')
    expect(line).toBeInTheDocument()
    expect(line?.textContent).toMatch(/10:00/)
    expect(line?.textContent).toMatch(/Graveside/)
    expect(line?.textContent).not.toMatch(/ETA/)
  })

  it("service time line — church shows '11:00 Church · ETA 12:00' order", () => {
    const base = makeDelivery()
    render(
      <Harness>
        <DeliveryCard
          delivery={{
            ...base,
            type_config: {
              ...base.type_config,
              service_type: "church",
              service_time: "11:00",
              eta: "12:00",
            },
          }}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    const line = document.querySelector('[data-slot="dispatch-card-timeline"]')
    expect(line?.textContent).toMatch(/11:00/)
    expect(line?.textContent).toMatch(/Church/)
    expect(line?.textContent).toMatch(/ETA 12:00/)
    // Service time MUST precede ETA in the rendered string.
    const txt = line?.textContent ?? ""
    const serviceIdx = txt.indexOf("11:00")
    const etaIdx = txt.indexOf("ETA")
    expect(serviceIdx).toBeGreaterThanOrEqual(0)
    expect(etaIdx).toBeGreaterThan(serviceIdx)
  })

  it("service time line — funeral_home shows 'time Funeral Home · ETA Y'", () => {
    const base = makeDelivery()
    render(
      <Harness>
        <DeliveryCard
          delivery={{
            ...base,
            type_config: {
              ...base.type_config,
              service_type: "funeral_home",
              service_time: "14:00",
              eta: "15:30",
            },
          }}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    const line = document.querySelector('[data-slot="dispatch-card-timeline"]')
    expect(line?.textContent).toMatch(/14:00/)
    expect(line?.textContent).toMatch(/Funeral Home/)
    expect(line?.textContent).toMatch(/ETA 15:30/)
  })

  it("product line shows vault type · equipment bundle (Phase 3.2.1)", () => {
    const base = makeDelivery()
    render(
      <Harness>
        <DeliveryCard delivery={base} scheduleFinalized={false} />
      </Harness>,
    )
    const prod = document.querySelector('[data-slot="dispatch-card-product"]')
    expect(prod?.textContent).toMatch(/Monticello/)
    expect(prod?.textContent).toMatch(/Full w\/ Placer/)
    // Phase 3.2.1 regression guard: the old service_type-derived hints
    // ("Graveside setup", "Church procession") should NOT appear —
    // those were mismapped as equipment. Equipment comes from its
    // own type_config.equipment_type field now.
    expect(prod?.textContent).not.toMatch(/Graveside setup/)
    expect(prod?.textContent).not.toMatch(/Church procession/)
    expect(prod?.textContent).not.toMatch(/FH procession/)
  })

  it("product line renders vault alone if equipment_type is absent", () => {
    const base = makeDelivery()
    render(
      <Harness>
        <DeliveryCard
          delivery={{
            ...base,
            type_config: {
              ...base.type_config,
              equipment_type: null,
            },
          }}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    const prod = document.querySelector('[data-slot="dispatch-card-product"]')
    expect(prod?.textContent).toContain("Monticello")
    // No separator when one side is absent
    expect(prod?.textContent).not.toMatch(/ · /)
  })

  it("service-time line uses service_type as the LOCATION label, not as equipment", () => {
    // Phase 3.2.1 field-mapping test — service_type='church' yields
    // "11:00 Church" in the time line (the service LOCATION). It does
    // NOT show up as equipment on line 4 (equipment is its own field).
    const base = makeDelivery()
    render(
      <Harness>
        <DeliveryCard
          delivery={{
            ...base,
            type_config: {
              ...base.type_config,
              service_type: "church",
              service_time: "11:00",
              eta: "12:00",
              equipment_type: "Full Equipment",
            },
          }}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    const timeLine = document.querySelector(
      '[data-slot="dispatch-card-timeline"]',
    )
    expect(timeLine?.textContent).toMatch(/Church/)
    const prodLine = document.querySelector(
      '[data-slot="dispatch-card-product"]',
    )
    expect(prodLine?.textContent).toContain("Full Equipment")
    expect(prodLine?.textContent).not.toMatch(/Church/)
  })
})


describe("DeliveryCard — no service-type tint (Phase 3.1 removal)", () => {
  it("graveside card does NOT carry bg-status-success-muted", () => {
    const { container } = render(
      <Harness>
        <DeliveryCard delivery={makeDelivery()} scheduleFinalized={false} />
      </Harness>,
    )
    const card = container.querySelector('[data-slot="dispatch-delivery-card"]')
    expect(card?.className).not.toMatch(/bg-status-success-muted/)
    expect(card?.className).toMatch(/bg-surface-elevated/)
  })

  it("church card does NOT carry bg-status-warning-muted", () => {
    const base = makeDelivery()
    const { container } = render(
      <Harness>
        <DeliveryCard
          delivery={{
            ...base,
            type_config: { ...base.type_config, service_type: "church" },
          }}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    const card = container.querySelector('[data-slot="dispatch-delivery-card"]')
    expect(card?.className).not.toMatch(/bg-status-warning-muted/)
    expect(card?.className).toMatch(/bg-surface-elevated/)
  })
})


describe("DeliveryCard — schedule state (Phase 3.3: no perimeter border)", () => {
  it("draft schedule → data-schedule-state='draft', no border class", () => {
    // Phase 3.3 per DL §6 canonical "Card perimeter: no border" —
    // cards never carry a drawn perimeter border regardless of
    // schedule state. State signal moved entirely to the day-header
    // "Draft" pill.
    const { container } = render(
      <Harness>
        <DeliveryCard delivery={makeDelivery()} scheduleFinalized={false} />
      </Harness>,
    )
    const card = container.querySelector('[data-slot="dispatch-delivery-card"]')
    expect(card?.getAttribute("data-schedule-state")).toBe("draft")
    expect(card?.className).not.toMatch(/border-dashed/)
    // Regression guard — `border ` token (standalone, pre-hyphen-variant)
    // would indicate a restored perimeter border.
    expect(card?.className).not.toMatch(/\bborder\b(?!-)/)
  })

  it("finalized schedule → data-schedule-state='finalized', still no border", () => {
    const { container } = render(
      <Harness>
        <DeliveryCard delivery={makeDelivery()} scheduleFinalized={true} />
      </Harness>,
    )
    const card = container.querySelector('[data-slot="dispatch-delivery-card"]')
    expect(card?.getAttribute("data-schedule-state")).toBe("finalized")
    expect(card?.className).not.toMatch(/border-dashed/)
    expect(card?.className).not.toMatch(/\bborder\b(?!-)/)
  })

  it("card carries canonical elevated + composite material shadow + rounded-md chrome", () => {
    const { container } = render(
      <Harness>
        <DeliveryCard delivery={makeDelivery()} scheduleFinalized={false} />
      </Harness>,
    )
    const card = container.querySelector('[data-slot="dispatch-delivery-card"]')
    expect(card?.className).toMatch(/bg-surface-elevated/)
    expect(card?.className).toMatch(/rounded-md/)
    // Aesthetic Arc Session 4.5 — shadow-level-1 no longer a Tailwind
    // utility on the wrapper. The card composes a multi-layer box-
    // shadow inline (edge highlight + edge shadow + ambient + flag-
    // press + level-1) per DL §11 Pattern 2 material treatment.
    // Asserting via inline style now: verify --shadow-level-1 token
    // reference is part of the composite, plus the new edge tokens.
    const inlineShadow = (card as HTMLElement | null)?.style.boxShadow ?? ""
    expect(inlineShadow).toContain("--shadow-level-1")
    expect(inlineShadow).toContain("--card-edge-highlight")
    expect(inlineShadow).toContain("--card-edge-shadow")
    expect(inlineShadow).toContain("--card-ambient-shadow")
  })
})


describe("DeliveryCard — hole-dug badge (three-state, non-nullable)", () => {
  it("status=unknown renders by default (no null state)", () => {
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery({ hole_dug_status: "unknown" })}
          scheduleFinalized={false}
          onCycleHoleDug={() => {}}
        />
      </Harness>,
    )
    const badge = document.querySelector(
      '[data-slot="dispatch-hole-dug-badge"]',
    ) as HTMLElement
    expect(badge).toBeInTheDocument()
    expect(badge.getAttribute("data-status")).toBe("unknown")
  })

  it("click on unknown → cycles to yes", async () => {
    const user = userEvent.setup()
    const onCycle = vi.fn()
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery({ hole_dug_status: "unknown" })}
          scheduleFinalized={false}
          onCycleHoleDug={onCycle}
        />
      </Harness>,
    )
    const badge = document.querySelector(
      '[data-slot="dispatch-hole-dug-badge"]',
    ) as HTMLElement
    await user.click(badge)
    expect(onCycle).toHaveBeenCalledTimes(1)
    expect(onCycle.mock.calls[0][1]).toBe("yes")
  })

  it("click on no → cycles back to unknown (not null)", async () => {
    const user = userEvent.setup()
    const onCycle = vi.fn()
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery({ hole_dug_status: "no" })}
          scheduleFinalized={false}
          onCycleHoleDug={onCycle}
        />
      </Harness>,
    )
    const badge = document.querySelector(
      '[data-slot="dispatch-hole-dug-badge"]',
    ) as HTMLElement
    await user.click(badge)
    expect(onCycle).toHaveBeenCalledTimes(1)
    expect(onCycle.mock.calls[0][1]).toBe("unknown")
  })
})


describe("DeliveryCard — icon + tooltip compaction row (Phase 3.2)", () => {
  it("family icon renders when family_name is present", () => {
    render(
      <Harness>
        <DeliveryCard delivery={makeDelivery()} scheduleFinalized={false} />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-icon-family"]'),
    ).toBeInTheDocument()
  })

  it("section icon renders when cemetery_section is present", () => {
    render(
      <Harness>
        <DeliveryCard delivery={makeDelivery()} scheduleFinalized={false} />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-icon-section"]'),
    ).toBeInTheDocument()
  })

  it("section icon hidden when cemetery_section is empty", () => {
    const base = makeDelivery()
    render(
      <Harness>
        <DeliveryCard
          delivery={{
            ...base,
            type_config: { ...base.type_config, cemetery_section: null },
          }}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-icon-section"]'),
    ).toBeNull()
  })

  it("note icon renders only when driver_note non-empty", () => {
    const base = makeDelivery()
    const { rerender } = render(
      <Harness>
        <DeliveryCard delivery={base} scheduleFinalized={false} />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-icon-note"]'),
    ).toBeNull()

    rerender(
      <Harness>
        <DeliveryCard
          delivery={{
            ...base,
            type_config: {
              ...base.type_config,
              driver_note: "FH said procession may run long",
            },
          }}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-icon-note"]'),
    ).toBeInTheDocument()
  })

  it("chat icon + badge render when chat_activity_count > 0", () => {
    const base = makeDelivery()
    render(
      <Harness>
        <DeliveryCard
          delivery={{
            ...base,
            type_config: { ...base.type_config, chat_activity_count: 3 },
          }}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    const icon = document.querySelector('[data-slot="dispatch-icon-chat"]')
    expect(icon).toBeInTheDocument()
    const badge = document.querySelector(
      '[data-slot="dispatch-icon-chat-badge"]',
    )
    expect(badge?.textContent).toBe("3")
  })

  it("chat icon hidden when chat_activity_count is 0", () => {
    render(
      <Harness>
        <DeliveryCard delivery={makeDelivery()} scheduleFinalized={false} />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-icon-chat"]'),
    ).toBeNull()
  })
})


describe("DeliveryCard — ancillary badge", () => {
  it("hidden when ancillaryCount is 0", () => {
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery()}
          scheduleFinalized={false}
          ancillaryCount={0}
        />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-ancillary-badge"]'),
    ).toBeNull()
  })

  it("shown when ancillaryCount > 0; click fires onToggleAncillary", async () => {
    // Phase 4.3.3.1 — badge converted from "+N ancillary" text pill to
    // Paperclip icon + count chip. Visual weight matches the chat-icon
    // unread chip on the icon row's left cluster.
    const user = userEvent.setup()
    const onToggle = vi.fn()
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery()}
          scheduleFinalized={false}
          ancillaryCount={2}
          onToggleAncillary={onToggle}
        />
      </Harness>,
    )
    const badge = document.querySelector(
      '[data-slot="dispatch-ancillary-badge"]',
    ) as HTMLElement
    // Count chip is a separate sub-slot; render as the digit only,
    // not the legacy "+N ancillary" text pill.
    const countChip = document.querySelector(
      '[data-slot="dispatch-ancillary-badge-count"]',
    ) as HTMLElement
    expect(countChip.textContent).toBe("2")
    expect(badge.getAttribute("aria-label")).toMatch(/2 ancillary items attached/i)
    await user.click(badge)
    expect(onToggle).toHaveBeenCalledWith("del-1")
  })
})


// ── Phase 4.3.3.1 — helper icon ──────────────────────────────────────


describe("DeliveryCard — helper icon (Phase 4.3.3.1)", () => {
  it("hidden when delivery has no helper_user_id", () => {
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery({ helper_user_id: null })}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-icon-helper"]'),
    ).toBeNull()
  })

  it("shown when helper_user_id is set; tooltip carries resolved name", () => {
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery({
            helper_user_id: "user-mike",
            helper_user_name: "Mike Kowalski",
          })}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    const icon = document.querySelector(
      '[data-slot="dispatch-icon-helper"]',
    ) as HTMLElement
    expect(icon).toBeTruthy()
    expect(icon.getAttribute("aria-label")).toBe("Helper: Mike Kowalski")
  })

  it("falls back to 'Helper: assigned' when helper_user_name didn't resolve", () => {
    // Defensive — backend lost the user row but the UI still flags
    // the helper presence so the dispatcher knows there's a second
    // person they haven't seen the name of.
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery({
            helper_user_id: "user-orphan",
            helper_user_name: null,
          })}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    const icon = document.querySelector(
      '[data-slot="dispatch-icon-helper"]',
    ) as HTMLElement
    expect(icon.getAttribute("aria-label")).toBe("Helper: assigned")
  })
})


describe("DeliveryCard — density prop (Phase 4.2.1)", () => {
  it("default density (no prop) uses generous body padding px-3 py-2", () => {
    render(
      <Harness>
        <DeliveryCard delivery={makeDelivery()} scheduleFinalized={false} />
      </Harness>,
    )
    const body = document.querySelector(
      '[data-slot="dispatch-card-body"]',
    ) as HTMLElement
    // data-density stamp defaults to "default"
    expect(body.getAttribute("data-density")).toBe("default")
    expect(body.className).toMatch(/px-3/)
    expect(body.className).toMatch(/py-2\b/)
  })

  it("density='default' explicit matches default behavior", () => {
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery()}
          scheduleFinalized={false}
          density="default"
        />
      </Harness>,
    )
    const body = document.querySelector(
      '[data-slot="dispatch-card-body"]',
    ) as HTMLElement
    expect(body.getAttribute("data-density")).toBe("default")
    expect(body.className).toMatch(/px-3/)
  })

  it("density='compact' tightens body padding to px-2.5 py-1.5", () => {
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery()}
          scheduleFinalized={false}
          density="compact"
        />
      </Harness>,
    )
    const body = document.querySelector(
      '[data-slot="dispatch-card-body"]',
    ) as HTMLElement
    expect(body.getAttribute("data-density")).toBe("compact")
    expect(body.className).toMatch(/px-2\.5/)
    expect(body.className).toMatch(/py-1\.5/)
    // Regression guard — default padding must NOT appear on compact.
    expect(body.className).not.toMatch(/\bpx-3\b/)
    expect(body.className).not.toMatch(/\bpy-2\b/)
  })

  it("density='compact' tightens icon-row padding to px-2.5 py-1", () => {
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery()}
          scheduleFinalized={false}
          density="compact"
        />
      </Harness>,
    )
    const iconRow = document.querySelector(
      '[data-slot="dispatch-card-icon-row"]',
    ) as HTMLElement
    expect(iconRow.className).toMatch(/px-2\.5/)
    expect(iconRow.className).toMatch(/py-1\b/)
    expect(iconRow.className).not.toMatch(/\bpx-3\b/)
    expect(iconRow.className).not.toMatch(/py-1\.5/)
  })

  it("density='compact' preserves all primary text lines (data density principle)", () => {
    // Compact mode tightens padding; it must NOT hide FH / cemetery /
    // time / product lines. All 4 primary lines continue to render.
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery()}
          scheduleFinalized={false}
          density="compact"
        />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-card-fh"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector('[data-slot="dispatch-card-cemetery"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector('[data-slot="dispatch-card-timeline"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector('[data-slot="dispatch-card-product"]'),
    ).toBeInTheDocument()
  })

  it("density='compact' preserves status-icon row (family / section / hole-dug)", () => {
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery()}
          scheduleFinalized={false}
          density="compact"
          onCycleHoleDug={() => {}}
        />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-icon-family"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector('[data-slot="dispatch-icon-section"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector('[data-slot="dispatch-hole-dug-badge"]'),
    ).toBeInTheDocument()
  })
})


describe("DeliveryCard — body click fires onOpenEdit", () => {
  it("click on card body → onOpenEdit(delivery)", async () => {
    const user = userEvent.setup()
    const onOpenEdit = vi.fn()
    const delivery = makeDelivery()
    render(
      <Harness>
        <DeliveryCard
          delivery={delivery}
          scheduleFinalized={false}
          onOpenEdit={onOpenEdit}
        />
      </Harness>,
    )
    const body = document.querySelector(
      '[data-slot="dispatch-card-body"]',
    ) as HTMLElement
    await user.click(body)
    expect(onOpenEdit).toHaveBeenCalledWith(delivery)
  })
})


describe("DeliveryCard — driver_start_time eyebrow (Phase 4.3.3)", () => {
  it("renders eyebrow when driver_start_time is set, formatted to 12-hour", () => {
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery({ driver_start_time: "06:30:00" })}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    const eyebrow = document.querySelector(
      '[data-slot="dispatch-card-start-time"]',
    )
    expect(eyebrow).toBeInTheDocument()
    expect(eyebrow?.textContent).toBe("Start 6:30am")
  })

  it("formats whole-hour as 'Start 5am' (no :00)", () => {
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery({ driver_start_time: "05:00:00" })}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    const eyebrow = document.querySelector(
      '[data-slot="dispatch-card-start-time"]',
    )
    expect(eyebrow?.textContent).toBe("Start 5am")
  })

  it("renders pm for hours >=12", () => {
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery({ driver_start_time: "13:15:00" })}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    const eyebrow = document.querySelector(
      '[data-slot="dispatch-card-start-time"]',
    )
    expect(eyebrow?.textContent).toBe("Start 1:15pm")
  })

  it("hides eyebrow when driver_start_time is null (use tenant default)", () => {
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery({ driver_start_time: null })}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-card-start-time"]'),
    ).toBeNull()
  })

  it("hides eyebrow when driver_start_time is undefined", () => {
    // Older Monitor responses might omit the field entirely. Defensive
    // guard: treat undefined same as null.
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery({ driver_start_time: undefined as unknown as string | null })}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-card-start-time"]'),
    ).toBeNull()
  })
})
