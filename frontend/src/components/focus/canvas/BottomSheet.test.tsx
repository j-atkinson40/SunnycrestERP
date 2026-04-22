/**
 * BottomSheet — vitest unit tests. Phase A Session 3.7.
 *
 * Swipe-dismiss gesture is covered at the useSwipeDismiss hook level
 * indirectly (via pointer-event threshold logic). jsdom can't
 * simulate realistic pointer velocity; real-device verification
 * deferred to mobile polish session per PLATFORM_QUALITY_BAR.md.
 */

import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import type { WidgetState } from "@/contexts/focus-registry"

import { BottomSheet } from "./BottomSheet"


const twoWidgets: Record<string, WidgetState> = {
  "w1": {
    position: { anchor: "top-left", offsetX: 0, offsetY: 0, width: 280, height: 200 },
  },
  "w2": {
    position: { anchor: "top-left", offsetX: 0, offsetY: 0, width: 280, height: 200 },
  },
}


describe("BottomSheet", () => {
  it("renders sheet + backdrop + drag handle", () => {
    render(<BottomSheet widgets={twoWidgets} onDismiss={() => {}} />)
    expect(
      document.querySelector('[data-slot="focus-bottom-sheet"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector('[data-slot="focus-bottom-sheet-backdrop"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector('[data-slot="focus-bottom-sheet-handle"]'),
    ).toBeInTheDocument()
  })

  it("renders one tile per widget", () => {
    render(<BottomSheet widgets={twoWidgets} onDismiss={() => {}} />)
    const tiles = document.querySelectorAll(
      '[data-slot="focus-bottom-sheet-tile"]',
    )
    expect(tiles).toHaveLength(2)
  })

  it("backdrop click dismisses sheet", async () => {
    const user = userEvent.setup()
    const onDismiss = vi.fn()
    render(<BottomSheet widgets={twoWidgets} onDismiss={onDismiss} />)
    await user.click(
      screen.getByRole("button", { name: /dismiss widget sheet/i }),
    )
    expect(onDismiss).toHaveBeenCalledTimes(1)
  })

  it("tapping a tile opens the expanded view", async () => {
    const user = userEvent.setup()
    render(<BottomSheet widgets={twoWidgets} onDismiss={() => {}} />)
    const firstTile = document.querySelector(
      '[data-slot="focus-bottom-sheet-tile"]',
    ) as HTMLElement
    await user.click(firstTile)
    expect(
      document.querySelector('[data-slot="focus-bottom-sheet-expanded"]'),
    ).toBeInTheDocument()
  })

  it("Esc on expanded view collapses to sheet (not full dismiss)", async () => {
    const user = userEvent.setup()
    const onDismiss = vi.fn()
    render(<BottomSheet widgets={twoWidgets} onDismiss={onDismiss} />)
    const firstTile = document.querySelector(
      '[data-slot="focus-bottom-sheet-tile"]',
    ) as HTMLElement
    await user.click(firstTile)
    expect(
      document.querySelector('[data-slot="focus-bottom-sheet-expanded"]'),
    ).toBeInTheDocument()

    // Esc should close the expanded view, NOT the sheet itself.
    await user.keyboard("{Escape}")
    expect(
      document.querySelector('[data-slot="focus-bottom-sheet-expanded"]'),
    ).not.toBeInTheDocument()
    expect(
      document.querySelector('[data-slot="focus-bottom-sheet"]'),
    ).toBeInTheDocument()
    expect(onDismiss).not.toHaveBeenCalled()
  })

  it("Esc with no expanded view dismisses sheet", async () => {
    const user = userEvent.setup()
    const onDismiss = vi.fn()
    render(<BottomSheet widgets={twoWidgets} onDismiss={onDismiss} />)
    await user.keyboard("{Escape}")
    expect(onDismiss).toHaveBeenCalledTimes(1)
  })

  it("drag handle has touch-action: none to prevent scroll hijack", () => {
    render(<BottomSheet widgets={twoWidgets} onDismiss={() => {}} />)
    const handle = document.querySelector(
      '[data-slot="focus-bottom-sheet-handle"]',
    ) as HTMLElement
    expect(handle.style.touchAction).toBe("none")
  })
})
