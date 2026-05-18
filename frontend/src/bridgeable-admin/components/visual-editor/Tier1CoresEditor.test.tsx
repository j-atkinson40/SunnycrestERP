/**
 * Tier1CoresEditor tests — sub-arc E-1.1.
 *
 * Asserts the editor canvas atmosphere matches the canonical funeral-
 * scheduling mockup (four-layer composition: three radial gradients +
 * vertical cream-to-tan linear base). E-1.1 replaced the prior warm-
 * amber diagonal gradient so admin-facing surfaces feel canon-matched
 * alongside operator-facing surfaces.
 */
import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"

vi.mock("@/bridgeable-admin/services/focus-cores-service", () => ({
  focusCoresService: {
    list: vi.fn().mockResolvedValue([]),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
}))

vi.mock("@/bridgeable-admin/hooks/useFocusCoreDraft", () => ({
  useFocusCoreDraft: () => ({
    core: null,
    draft: null,
    updateDraft: vi.fn(),
    isDirty: false,
    isSaving: false,
    lastSavedAt: null,
    error: null,
    isLoading: false,
  }),
}))

vi.mock("@/bridgeable-admin/lib/admin-api", () => ({
  adminApi: { get: vi.fn().mockResolvedValue({ data: { tokens: {} } }) },
}))

vi.mock("@/bridgeable-admin/components/studio/StudioRailContext", () => ({
  useStudioRail: () => ({ railExpanded: false, inStudioContext: false }),
}))

import { Tier1CoresEditor } from "./Tier1CoresEditor"

describe("Tier1CoresEditor — canonical mockup canvas (E-1.1)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders the four-layer canonical mockup composition on the preview canvas", async () => {
    render(
      <Tier1CoresEditor
        selectedCoreId={null}
        onSelectCore={vi.fn()}
      />,
    )

    const canvas = await waitFor(() => screen.getByTestId("tier1-preview"))
    const bg = (canvas as HTMLElement).style.background
    // Three radial gradients at canonical positions/colors:
    expect(bg).toContain("radial-gradient")
    expect(bg).toContain("15% 10%")
    expect(bg).toContain("rgba(252, 220, 180, 0.55)")
    expect(bg).toContain("85% 15%")
    expect(bg).toContain("rgba(220, 170, 200, 0.4)")
    expect(bg).toContain("50% 90%")
    expect(bg).toContain("rgba(180, 200, 220, 0.45)")
    // Vertical cream-to-tan linear base (JSDom normalizes hex → rgb):
    expect(bg).toContain("linear-gradient(180deg")
    // #f7ebe0 → rgb(247, 235, 224); #f0dfd0 → rgb(240, 223, 208)
    expect(bg).toContain("rgb(247, 235, 224)")
    expect(bg).toContain("rgb(240, 223, 208)")
    // Establishes its own stacking context:
    expect((canvas as HTMLElement).style.isolation).toBe("isolate")
  })

  it("does NOT carry the pre-E-1.1 warm-amber diagonal gradient", async () => {
    render(
      <Tier1CoresEditor
        selectedCoreId={null}
        onSelectCore={vi.fn()}
      />,
    )

    const canvas = await waitFor(() => screen.getByTestId("tier1-preview"))
    const bg = (canvas as HTMLElement).style.background
    expect(bg).not.toContain("135deg")
    // Prior amber stops #f9d9a6 / #e9b27e / #c97d52 / #9C5640
    // normalize via JSDom to rgb() — assert their normalized forms
    // and the hex sources are both absent.
    expect(bg).not.toContain("#f9d9a6")
    expect(bg).not.toContain("#9C5640")
    expect(bg).not.toContain("#9c5640")
    expect(bg).not.toContain("rgb(249, 217, 166)")
    expect(bg).not.toContain("rgb(156, 86, 64)")
  })
})
