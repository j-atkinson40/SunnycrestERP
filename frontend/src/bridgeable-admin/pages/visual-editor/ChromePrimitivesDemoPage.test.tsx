/**
 * ChromePrimitivesDemoPage smoke tests — sub-arc C-1.
 *
 * Verifies primitives mount, state propagates through preview, and
 * theme fetch falls back gracefully on error.
 */
import { describe, it, expect, vi, beforeEach } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

vi.mock("@/bridgeable-admin/lib/admin-api", () => ({
  adminApi: {
    get: vi.fn().mockResolvedValue({
      data: {
        tokens: {
          "surface-base": "#fbfaf6",
          "surface-elevated": "#ffffff",
          "border-subtle": "#e8e3d8",
        },
      },
    }),
  },
}))

import ChromePrimitivesDemoPage from "./ChromePrimitivesDemoPage"
import { adminApi } from "@/bridgeable-admin/lib/admin-api"

describe("ChromePrimitivesDemoPage", () => {
  beforeEach(() => {
    ;(adminApi.get as ReturnType<typeof vi.fn>).mockClear()
  })

  it("mounts and renders preview card + all four primitives", async () => {
    render(<ChromePrimitivesDemoPage />)
    expect(screen.getByTestId("chrome-primitives-demo-page")).toBeInTheDocument()
    expect(screen.getByTestId("chrome-preview-card")).toBeInTheDocument()
    expect(screen.getByTestId("chrome-preset-picker")).toBeInTheDocument()
    // Three ScrubbableButtons rendered.
    expect(screen.getAllByTestId("scrubbable-button")).toHaveLength(3)
    // Three TokenSwatchPickers rendered.
    expect(screen.getAllByTestId("token-swatch-trigger")).toHaveLength(3)
    // PropertyPanel mounted.
    expect(screen.getByTestId("property-panel")).toBeInTheDocument()
  })

  it("fetches resolved theme tokens on mount", async () => {
    render(<ChromePrimitivesDemoPage />)
    await waitFor(() => {
      expect(adminApi.get).toHaveBeenCalledWith(
        "/api/platform/admin/visual-editor/themes/resolve",
        expect.objectContaining({ params: { mode: "light" } }),
      )
    })
  })

  it("changing preset updates the preview card style", async () => {
    render(<ChromePrimitivesDemoPage />)
    const before = screen.getByTestId("chrome-preview-card")
    const beforeRadius = before.style.borderRadius
    fireEvent.click(screen.getByTestId("preset-pill-modal"))
    // Modal preset → corner_radius 62 (> 50) → 14px in our mapping.
    await waitFor(() => {
      const after = screen.getByTestId("chrome-preview-card")
      expect(after.style.borderRadius).not.toBe("")
      expect(after.style.borderRadius).not.toBe(beforeRadius)
    })
  })

  it("scrubbing elevation slider updates preview shadow", async () => {
    render(<ChromePrimitivesDemoPage />)
    const buttons = screen.getAllByTestId("scrubbable-button")
    const elevationButton = buttons[0] as HTMLButtonElement
    ;(elevationButton as unknown as { setPointerCapture: () => void }).setPointerCapture =
      vi.fn()
    ;(elevationButton as unknown as { releasePointerCapture: () => void }).releasePointerCapture =
      vi.fn()
    fireEvent.pointerDown(elevationButton, { clientX: 100, button: 0, pointerId: 1 })
    fireEvent.pointerMove(elevationButton, { clientX: 400, pointerId: 1 })
    // High elevation → strong shadow.
    await waitFor(() => {
      const card = screen.getByTestId("chrome-preview-card")
      expect(card.style.boxShadow).toContain("rgba")
    })
    fireEvent.pointerUp(elevationButton, { clientX: 400, pointerId: 1 })
  })

  it("picking a background token updates preview background", async () => {
    render(<ChromePrimitivesDemoPage />)
    await waitFor(() => {
      expect(adminApi.get).toHaveBeenCalled()
    })
    // First swatch trigger is Background.
    const triggers = screen.getAllByTestId("token-swatch-trigger")
    fireEvent.click(triggers[0])
    fireEvent.click(screen.getByTestId("token-swatch-option-surface-elevated"))
    const card = screen.getByTestId("chrome-preview-card")
    expect(card.style.background).toBeTruthy()
  })

  it("falls back to local tokens when API fetch fails", async () => {
    ;(adminApi.get as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("network"),
    )
    render(<ChromePrimitivesDemoPage />)
    // Page still renders.
    expect(screen.getByTestId("chrome-primitives-demo-page")).toBeInTheDocument()
    expect(screen.getByTestId("chrome-preview-card")).toBeInTheDocument()
  })
})
