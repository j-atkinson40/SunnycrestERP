/**
 * useAncillaryPool — vitest unit tests (Phase W-4a Cleanup Session B.2).
 *
 * Surface-aware data hook. Tests verify:
 *   • Context-present path: returns DeliveryDTO context items +
 *     isInteractive=true + drag helpers wired.
 *   • Context-absent path: fetches /widget-data/ancillary-pool +
 *     returns slim items + isInteractive=false + no-op helpers.
 *   • Fetch-error fallback: gracefully degrades to empty + console.warn.
 *   • Mode-aware fields: operatingMode + modeNote + isVaultEnabled
 *     surfaced from endpoint.
 */

import { renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import {
  SchedulingFocusContext,
  type SchedulingFocusContextValue,
} from "@/contexts/scheduling-focus-context"
import type { DeliveryDTO } from "@/services/dispatch-service"

import { useAncillaryPool } from "./useAncillaryPool"


// Module-level mock for apiClient — must be hoisted so the hook's
// internal fetch goes through it.
const mockApiGet = vi.fn()

vi.mock("@/lib/api-client", () => ({
  default: {
    get: (...args: unknown[]) => mockApiGet(...args),
  },
}))


function makeDeliveryDTO(overrides: Partial<DeliveryDTO> = {}): DeliveryDTO {
  return {
    id: "anc-" + Math.random().toString(36).slice(2, 8),
    company_id: "co-1",
    order_id: null,
    customer_id: null,
    delivery_type: "supply_delivery",
    status: "pending",
    priority: "normal",
    requested_date: null,
    scheduled_at: null,
    completed_at: null,
    scheduling_type: "ancillary",
    ancillary_fulfillment_status: null,
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


function ContextWrapper(value: SchedulingFocusContextValue) {
  return ({ children }: { children: React.ReactNode }) => (
    <SchedulingFocusContext.Provider value={value}>
      {children}
    </SchedulingFocusContext.Provider>
  )
}


afterEach(() => {
  mockApiGet.mockReset()
  vi.clearAllMocks()
})


describe("useAncillaryPool — context-present path (FH Focus)", () => {
  it("returns context's poolAncillaries with isInteractive=true", () => {
    const items = [
      makeDeliveryDTO({ id: "a", type_config: { product_summary: "Bronze urn" } }),
      makeDeliveryDTO({ id: "b", type_config: { product_summary: "Marker base" } }),
    ]
    const ctx: SchedulingFocusContextValue = {
      poolAncillaries: items,
      poolLoading: false,
      reloadPool: vi.fn(),
      removeFromPoolOptimistic: vi.fn(),
    }
    const { result } = renderHook(() => useAncillaryPool(), {
      wrapper: ContextWrapper(ctx),
    })

    expect(result.current.isInteractive).toBe(true)
    expect(result.current.totalCount).toBe(2)
    expect(result.current.items.length).toBe(2)
    expect(result.current.items[0].id).toBe("a")
    expect(result.current.items[1].id).toBe("b")
    // interactiveItems exposes the rich DeliveryDTO shape
    expect(result.current.interactiveItems).not.toBeNull()
    expect(result.current.interactiveItems?.length).toBe(2)
    // Hook should NOT have called the endpoint when context provides data
    expect(mockApiGet).not.toHaveBeenCalled()
  })

  it("wires reload + removeFromPoolOptimistic from context", () => {
    const reloadSpy = vi.fn()
    const removeSpy = vi.fn()
    const ctx: SchedulingFocusContextValue = {
      poolAncillaries: [],
      poolLoading: false,
      reloadPool: reloadSpy,
      removeFromPoolOptimistic: removeSpy,
    }
    const { result } = renderHook(() => useAncillaryPool(), {
      wrapper: ContextWrapper(ctx),
    })
    result.current.reload()
    result.current.removeFromPoolOptimistic("anc-x")
    expect(reloadSpy).toHaveBeenCalledOnce()
    expect(removeSpy).toHaveBeenCalledWith("anc-x")
  })

  it("surfaces poolLoading from context", () => {
    const ctx: SchedulingFocusContextValue = {
      poolAncillaries: [],
      poolLoading: true,
      reloadPool: vi.fn(),
      removeFromPoolOptimistic: vi.fn(),
    }
    const { result } = renderHook(() => useAncillaryPool(), {
      wrapper: ContextWrapper(ctx),
    })
    expect(result.current.loading).toBe(true)
  })
})


describe("useAncillaryPool — context-absent path (Pulse fallback fetch)", () => {
  beforeEach(() => {
    mockApiGet.mockResolvedValue({
      data: {
        operating_mode: "production",
        is_vault_enabled: true,
        items: [
          {
            id: "a",
            delivery_type: "supply_delivery",
            type_config: { product_summary: "Bronze urn", family_name: "Smith" },
            ancillary_soft_target_date: null,
            created_at: null,
          },
        ],
        total_count: 1,
        mode_note: null,
        primary_navigation_target: "/dispatch",
      },
    })
  })

  it("fetches /widget-data/ancillary-pool when no context provider mounted", async () => {
    const { result } = renderHook(() => useAncillaryPool())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    expect(mockApiGet).toHaveBeenCalledWith("/widget-data/ancillary-pool")
    expect(result.current.isInteractive).toBe(false)
    expect(result.current.totalCount).toBe(1)
    expect(result.current.items[0].id).toBe("a")
    expect(result.current.interactiveItems).toBeNull()
  })

  it("surfaces operatingMode + modeNote + isVaultEnabled from endpoint", async () => {
    mockApiGet.mockResolvedValue({
      data: {
        operating_mode: "purchase",
        is_vault_enabled: true,
        items: [],
        total_count: 0,
        mode_note: "no_pool_in_purchase_mode",
        primary_navigation_target: "/dispatch",
      },
    })
    const { result } = renderHook(() => useAncillaryPool())
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    expect(result.current.operatingMode).toBe("purchase")
    expect(result.current.modeNote).toBe("no_pool_in_purchase_mode")
    expect(result.current.isVaultEnabled).toBe(true)
    expect(result.current.primaryNavigationTarget).toBe("/dispatch")
  })

  it("removeFromPoolOptimistic is a no-op in read-only path", async () => {
    const { result } = renderHook(() => useAncillaryPool())
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    // Should not throw
    expect(() => result.current.removeFromPoolOptimistic("anc-1")).not.toThrow()
  })

  it("gracefully degrades on fetch error (empty + console.warn)", async () => {
    const consoleWarn = vi
      .spyOn(console, "warn")
      .mockImplementation(() => {})
    mockApiGet.mockRejectedValue(new Error("Network error"))
    const { result } = renderHook(() => useAncillaryPool())
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    expect(result.current.items).toEqual([])
    expect(result.current.totalCount).toBe(0)
    expect(result.current.isVaultEnabled).toBe(false)
    expect(consoleWarn).toHaveBeenCalled()
    consoleWarn.mockRestore()
  })
})
