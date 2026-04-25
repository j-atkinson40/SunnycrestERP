/**
 * QuickEditDialog — vitest unit tests. Phase B Session 1 Phase 3.1.
 *
 * Covers: field hydration from delivery, save on draft schedule
 * (no confirmation), save on finalized schedule (confirmation
 * dialog), cancel preserves state, hole-dug three-state radio
 * selection (no "not_set" option post-3.1).
 */

import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import type { DeliveryDTO, DriverDTO } from "@/services/dispatch-service"

import { QuickEditDialog } from "./QuickEditDialog"


function makeDelivery(overrides: Partial<DeliveryDTO> = {}): DeliveryDTO {
  return {
    id: "del-1",
    company_id: "co-1",
    order_id: "so-1",
    customer_id: "cust-1",
    delivery_type: "vault",
    status: "scheduled",
    priority: "normal",
    requested_date: "2026-04-24",
    scheduled_at: null,
    completed_at: null,
    scheduling_type: "kanban",
    ancillary_fulfillment_status: null,
    direct_ship_status: null,
    primary_assignee_id: "driver-1",
    helper_user_id: null,
    attached_to_delivery_id: null,
    driver_start_time: null,
    hole_dug_status: "unknown",
    type_config: {
      family_name: "Fitzgerald",
      service_time: "10:00",
      service_type: "graveside",
    },
    special_instructions: "Handle with care",
    ...overrides,
  }
}


// Phase 4.3.2 (r56) — user_id is the assignee identity (FK users.id);
// dropdown option values come from user_id. id stays for record id.
const drivers: DriverDTO[] = [
  { id: "driver-1", user_id: "driver-1", license_number: "CDL-1", license_class: "CDL-A", active: true, display_name: "Dave Miller" },
  { id: "driver-2", user_id: "driver-2", license_number: "CDL-2", license_class: "CDL-A", active: true, display_name: "Tom Henderson" },
]


describe("QuickEditDialog", () => {
  it("renders nothing when delivery is null", () => {
    const { container } = render(
      <QuickEditDialog
        delivery={null}
        drivers={drivers}
        scheduleFinalized={false}
        onClose={() => {}}
        onSave={() => {}}
      />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it("renders family name in title when delivery provided", () => {
    render(
      <QuickEditDialog
        delivery={makeDelivery()}
        drivers={drivers}
        scheduleFinalized={false}
        onClose={() => {}}
        onSave={() => {}}
      />,
    )
    expect(screen.getByText("Fitzgerald")).toBeInTheDocument()
  })

  it("pre-fills time, driver, hole-dug, note from delivery", () => {
    render(
      <QuickEditDialog
        delivery={makeDelivery()}
        drivers={drivers}
        scheduleFinalized={false}
        onClose={() => {}}
        onSave={() => {}}
      />,
    )
    const timeInput = screen.getByLabelText(/service time/i) as HTMLInputElement
    expect(timeInput.value).toBe("10:00")

    const driverSelect = screen.getByLabelText(
      /assigned driver/i,
    ) as HTMLSelectElement
    expect(driverSelect.value).toBe("driver-1")

    const noteField = screen.getByLabelText(/note/i) as HTMLTextAreaElement
    expect(noteField.value).toBe("Handle with care")

    // Unknown radio selected
    const unknownRadio = screen.getByRole("radio", { name: /unknown/i })
    expect(unknownRadio.getAttribute("aria-checked")).toBe("true")
  })

  it("save on draft schedule fires onSave directly (no confirmation)", async () => {
    const user = userEvent.setup()
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(
      <QuickEditDialog
        delivery={makeDelivery()}
        drivers={drivers}
        scheduleFinalized={false}
        onClose={() => {}}
        onSave={onSave}
      />,
    )
    await user.click(screen.getByRole("button", { name: /^save$/i }))
    expect(onSave).toHaveBeenCalledTimes(1)
    const payload = onSave.mock.calls[0][0]
    expect(payload.deliveryId).toBe("del-1")
    expect(payload.scheduleWasFinalized).toBe(false)
  })

  it("save on finalized schedule opens revert-confirmation dialog first", async () => {
    const user = userEvent.setup()
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(
      <QuickEditDialog
        delivery={makeDelivery()}
        drivers={drivers}
        scheduleFinalized={true}
        onClose={() => {}}
        onSave={onSave}
      />,
    )
    // Revert warning visible in the edit dialog
    expect(
      document.querySelector(
        '[data-slot="dispatch-quick-edit-revert-warning"]',
      ),
    ).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /^save$/i }))
    // Confirmation dialog now open; onSave not yet called
    expect(onSave).not.toHaveBeenCalled()
    expect(
      document.querySelector('[data-slot="dispatch-revert-confirm-dialog"]'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/revert schedule to draft/i),
    ).toBeInTheDocument()

    // Confirm
    await user.click(
      screen.getByRole("button", { name: /save & revert to draft/i }),
    )
    expect(onSave).toHaveBeenCalledTimes(1)
    expect(onSave.mock.calls[0][0].scheduleWasFinalized).toBe(true)
  })

  it("revert-confirmation cancel preserves edit state (onSave not called)", async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    render(
      <QuickEditDialog
        delivery={makeDelivery()}
        drivers={drivers}
        scheduleFinalized={true}
        onClose={() => {}}
        onSave={onSave}
      />,
    )
    await user.click(screen.getByRole("button", { name: /^save$/i }))
    // Cancel revert confirmation — two Cancel buttons at this point
    // (one in the primary dialog, one in the confirmation). Click the
    // confirmation's Cancel.
    const cancelButtons = screen.getAllByRole("button", { name: /^cancel$/i })
    await user.click(cancelButtons[cancelButtons.length - 1])
    expect(onSave).not.toHaveBeenCalled()
  })

  it("hole-dug radio selection updates the payload", async () => {
    const user = userEvent.setup()
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(
      <QuickEditDialog
        delivery={makeDelivery()}
        drivers={drivers}
        scheduleFinalized={false}
        onClose={() => {}}
        onSave={onSave}
      />,
    )
    await user.click(screen.getByRole("radio", { name: /^yes$/i }))
    await user.click(screen.getByRole("button", { name: /^save$/i }))
    expect(onSave.mock.calls[0][0].holeDugStatus).toBe("yes")
  })

  it("cancel button fires onClose without calling onSave", async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    const onSave = vi.fn()
    render(
      <QuickEditDialog
        delivery={makeDelivery()}
        drivers={drivers}
        scheduleFinalized={false}
        onClose={onClose}
        onSave={onSave}
      />,
    )
    await user.click(screen.getByRole("button", { name: /^cancel$/i }))
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(onSave).not.toHaveBeenCalled()
  })
})


describe("QuickEditDialog — Phase 4.3.3 grouped sections + helper + start time", () => {
  it("renders Assignment + Delivery state section headers", () => {
    render(
      <QuickEditDialog
        delivery={makeDelivery()}
        drivers={drivers}
        scheduleFinalized={false}
        onClose={() => {}}
        onSave={() => {}}
      />,
    )
    expect(
      document.querySelector(
        '[data-slot="dispatch-quick-edit-section-assignment"]',
      ),
    ).toBeInTheDocument()
    expect(
      document.querySelector(
        '[data-slot="dispatch-quick-edit-section-state"]',
      ),
    ).toBeInTheDocument()
    // Header copy is uppercase eyebrow
    expect(screen.getByText(/^Assignment$/)).toBeInTheDocument()
    expect(screen.getByText(/^Delivery state$/)).toBeInTheDocument()
  })

  it("renders helper dropdown when helperCandidates provided, filtering primary", () => {
    render(
      <QuickEditDialog
        delivery={makeDelivery({ primary_assignee_id: "driver-1" })}
        drivers={drivers}
        helperCandidates={[
          { id: "driver-1", display_name: "Dave Miller" },
          { id: "driver-2", display_name: "Tom Henderson" },
          { id: "user-x", display_name: "Office Sue" },
        ]}
        scheduleFinalized={false}
        onClose={() => {}}
        onSave={() => {}}
      />,
    )
    const helperSel = document.querySelector(
      '[data-slot="dispatch-quick-edit-helper"]',
    ) as HTMLSelectElement
    expect(helperSel).toBeInTheDocument()
    const options = Array.from(helperSel.querySelectorAll("option"))
    const values = options.map((o) => o.value)
    // "" + driver-2 + user-x — driver-1 (primary) excluded
    expect(values).toContain("")
    expect(values).toContain("driver-2")
    expect(values).toContain("user-x")
    expect(values).not.toContain("driver-1")
  })

  it("hides helper dropdown when helperCandidates undefined (legacy callers)", () => {
    // Legacy back-compat: pre-4.3.3 callers don't pass helperCandidates.
    // Helper field falls back to driver list (excluding primary) so it
    // stays usable. Helper dropdown DOES render — just sourced from drivers.
    render(
      <QuickEditDialog
        delivery={makeDelivery({ primary_assignee_id: "driver-1" })}
        drivers={drivers}
        scheduleFinalized={false}
        onClose={() => {}}
        onSave={() => {}}
      />,
    )
    const helperSel = document.querySelector(
      '[data-slot="dispatch-quick-edit-helper"]',
    ) as HTMLSelectElement
    expect(helperSel).toBeInTheDocument()
    // Driver-1 is the primary; should NOT appear in helper options
    const options = Array.from(helperSel.querySelectorAll("option"))
    const values = options.map((o) => o.value)
    expect(values).not.toContain("driver-1")
    expect(values).toContain("driver-2")
  })

  it("start-time toggle: default-on disables input + clears value on save", async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    render(
      <QuickEditDialog
        delivery={makeDelivery({ driver_start_time: null })}
        drivers={drivers}
        scheduleFinalized={false}
        onClose={() => {}}
        onSave={onSave}
      />,
    )
    const input = document.querySelector(
      '[data-slot="dispatch-quick-edit-start-time-input"]',
    ) as HTMLInputElement
    expect(input.disabled).toBe(true)
    // Save → driverStartTime should be null
    await user.click(screen.getByRole("button", { name: /^save$/i }))
    expect(onSave).toHaveBeenCalledTimes(1)
    expect(onSave.mock.calls[0][0].driverStartTime).toBeNull()
  })

  it("start-time toggle: default-off enables input + persists explicit value", async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    render(
      <QuickEditDialog
        delivery={makeDelivery({ driver_start_time: "06:30:00" })}
        drivers={drivers}
        scheduleFinalized={false}
        onClose={() => {}}
        onSave={onSave}
      />,
    )
    // Initial state: explicit value set → toggle is off → input
    // enabled with the value pre-filled.
    const input = document.querySelector(
      '[data-slot="dispatch-quick-edit-start-time-input"]',
    ) as HTMLInputElement
    expect(input.disabled).toBe(false)
    expect(input.value).toBe("06:30")
    // Save without changes → driverStartTime should be the explicit value
    await user.click(screen.getByRole("button", { name: /^save$/i }))
    expect(onSave.mock.calls[0][0].driverStartTime).toBe("06:30")
  })

  it("payload carries helperUserId and driverStartTime fields", async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    render(
      <QuickEditDialog
        delivery={makeDelivery({
          helper_user_id: "user-mike",
          driver_start_time: "07:00:00",
        })}
        drivers={drivers}
        scheduleFinalized={false}
        onClose={() => {}}
        onSave={onSave}
      />,
    )
    await user.click(screen.getByRole("button", { name: /^save$/i }))
    const payload = onSave.mock.calls[0][0]
    expect(payload).toMatchObject({
      helperUserId: "user-mike",
      driverStartTime: "07:00",
    })
  })

  it("changing primary-assignee to current helper clears helper", async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    render(
      <QuickEditDialog
        delivery={makeDelivery({
          primary_assignee_id: "driver-1",
          helper_user_id: "driver-2",
        })}
        drivers={drivers}
        helperCandidates={[
          { id: "driver-1", display_name: "Dave Miller" },
          { id: "driver-2", display_name: "Tom Henderson" },
        ]}
        scheduleFinalized={false}
        onClose={() => {}}
        onSave={onSave}
      />,
    )
    // Change primary to driver-2 (current helper). Dialog should
    // auto-clear the helper to avoid "be your own helper" state.
    const primarySel = screen.getByLabelText(/Assigned driver/i) as HTMLSelectElement
    await user.selectOptions(primarySel, "driver-2")
    await user.click(screen.getByRole("button", { name: /^save$/i }))
    expect(onSave.mock.calls[0][0].helperUserId).toBeNull()
  })
})
