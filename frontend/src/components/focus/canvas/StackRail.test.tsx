/**
 * StackRail — vitest unit tests. Phase A Session 3.7.
 */

import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import type { WidgetState } from "@/contexts/focus-registry"

import { StackRail } from "./StackRail"


const threeWidgets: Record<string, WidgetState> = {
  "w1": {
    position: { anchor: "top-left", offsetX: 0, offsetY: 0, width: 280, height: 200 },
  },
  "w2": {
    position: { anchor: "top-left", offsetX: 0, offsetY: 0, width: 280, height: 200 },
  },
  "w3": {
    position: { anchor: "top-left", offsetX: 0, offsetY: 0, width: 280, height: 200 },
  },
}


describe("StackRail", () => {
  it("renders nothing when widgets map is empty", () => {
    render(<StackRail widgets={{}} onExpandWidget={() => {}} />)
    expect(
      document.querySelector('[data-slot="focus-stack-rail"]'),
    ).not.toBeInTheDocument()
  })

  it("renders one tile per widget with scroll-snap align", () => {
    render(<StackRail widgets={threeWidgets} onExpandWidget={() => {}} />)
    const tiles = document.querySelectorAll('[data-slot="focus-stack-tile"]')
    expect(tiles).toHaveLength(3)
    // Each tile must have scroll-snap-align inline style.
    tiles.forEach((tile) => {
      expect((tile as HTMLElement).style.scrollSnapAlign).toBe("start")
    })
  })

  it("each tile fills full rail height (Smart Stack contract)", () => {
    // Session 3.7.1 regression guard: tiles must be `height: 100%`
    // + `minHeight: 100%` + `flexShrink: 0` so each fills the rail
    // exactly, forcing scroll-snap to cycle one-by-one. The 3.7
    // bug rendered tiles at their canvas-mode heights (200-320px)
    // which fit simultaneously in the 70vh rail — no snap.
    render(<StackRail widgets={threeWidgets} onExpandWidget={() => {}} />)
    const tiles = document.querySelectorAll('[data-slot="focus-stack-tile"]')
    tiles.forEach((tile) => {
      const style = (tile as HTMLElement).style
      expect(style.height).toBe("100%")
      expect(style.minHeight).toBe("100%")
      expect(style.flexShrink).toBe("0")
    })
  })

  it("renders dots indicator with one dot per widget", () => {
    render(<StackRail widgets={threeWidgets} onExpandWidget={() => {}} />)
    const tabs = screen.getAllByRole("tab")
    expect(tabs).toHaveLength(3)
  })

  it("omits dots when only one widget (single = no need to indicate)", () => {
    const oneWidget = { "w1": threeWidgets["w1"] }
    render(<StackRail widgets={oneWidget} onExpandWidget={() => {}} />)
    expect(
      document.querySelector('[data-slot="focus-stack-dots"]'),
    ).not.toBeInTheDocument()
  })

  it("tapping a tile fires onExpandWidget with that widget id", async () => {
    const user = userEvent.setup()
    const onExpand = vi.fn()
    render(<StackRail widgets={threeWidgets} onExpandWidget={onExpand} />)
    const tiles = document.querySelectorAll('[data-slot="focus-stack-tile"]')
    await user.click(tiles[1])
    expect(onExpand).toHaveBeenCalledWith("w2")
  })

  it("scroll container has scroll-snap-type inline style", () => {
    render(<StackRail widgets={threeWidgets} onExpandWidget={() => {}} />)
    const rail = document.querySelector(
      '[data-slot="focus-stack-rail"]',
    ) as HTMLElement
    expect(rail.style.scrollSnapType).toBe("y mandatory")
  })
})
