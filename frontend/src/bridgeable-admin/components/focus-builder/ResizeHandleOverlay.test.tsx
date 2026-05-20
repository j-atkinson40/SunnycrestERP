/**
 * ResizeHandleOverlay unit tests (sub-arc FF-4).
 *
 * useDraggable requires a DndContext ancestor; tests render the
 * component inside a no-op DndContext.
 *
 * Operator-observable canon: assertions target the rendered handle
 * elements (their inline style, attributes) rather than internal
 * wrapper state.
 */
import type { ReactNode } from "react"
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { DndContext } from "@dnd-kit/core"

import {
  ResizeHandleOverlay,
  resizeHandleIdFor,
  parseResizeHandleId,
  RESIZE_HANDLE_POSITIONS,
} from "./ResizeHandleOverlay"

function renderWithDnd(node: ReactNode) {
  return render(<DndContext>{node}</DndContext>)
}

describe("ResizeHandleOverlay", () => {
  it("renders 8 handles, one per cardinal position", () => {
    renderWithDnd(<ResizeHandleOverlay placementId="p-1" />)
    const handles = screen.getAllByTestId("focus-builder-resize-handle")
    expect(handles).toHaveLength(8)
    const positions = handles.map((h) => h.getAttribute("data-handle-position"))
    for (const expected of RESIZE_HANDLE_POSITIONS) {
      expect(positions).toContain(expected)
    }
  })

  it("each handle carries the placementId via data-placement-id", () => {
    renderWithDnd(<ResizeHandleOverlay placementId="placement-xyz" />)
    const handles = screen.getAllByTestId("focus-builder-resize-handle")
    for (const h of handles) {
      expect(h.getAttribute("data-placement-id")).toBe("placement-xyz")
    }
  })

  it("each handle has the correct cursor inline style for its position", () => {
    renderWithDnd(<ResizeHandleOverlay placementId="p-1" />)
    const expected: Record<string, string> = {
      nw: "nw-resize",
      n: "n-resize",
      ne: "ne-resize",
      w: "w-resize",
      e: "e-resize",
      sw: "sw-resize",
      s: "s-resize",
      se: "se-resize",
    }
    for (const [pos, cursor] of Object.entries(expected)) {
      // Use querySelector against the data-handle-position attribute
      // — the operator-observable canon attaches the cursor at the
      // specific handle element.
      const handle = document.querySelector(
        `[data-testid="focus-builder-resize-handle"][data-handle-position="${pos}"]`,
      )
      expect(handle).not.toBeNull()
      const styleAttr = handle?.getAttribute("style") ?? ""
      expect(styleAttr).toMatch(new RegExp(`cursor:\\s*${cursor}`, "i"))
    }
  })

  it("each handle has the correct aria-label for accessibility", () => {
    renderWithDnd(<ResizeHandleOverlay placementId="p-1" />)
    for (const pos of RESIZE_HANDLE_POSITIONS) {
      const handle = document.querySelector(
        `[data-testid="focus-builder-resize-handle"][data-handle-position="${pos}"]`,
      )
      expect(handle).not.toBeNull()
      expect(handle?.getAttribute("aria-label")).toBe(`Resize ${pos}`)
    }
  })

  it("each handle is keyboard-focusable (tabIndex=0)", () => {
    renderWithDnd(<ResizeHandleOverlay placementId="p-1" />)
    const handles = screen.getAllByTestId("focus-builder-resize-handle")
    for (const h of handles) {
      expect(h.getAttribute("tabindex")).toBe("0")
    }
  })

  it("each handle declares pointer-events: auto so it receives events through the transparent overlay", () => {
    renderWithDnd(<ResizeHandleOverlay placementId="p-1" />)
    const handles = screen.getAllByTestId("focus-builder-resize-handle")
    for (const h of handles) {
      const styleAttr = h.getAttribute("style") ?? ""
      expect(styleAttr).toMatch(/pointer-events:\s*auto/i)
    }
  })

  it("each handle is positioned absolutely with the appropriate edge anchors", () => {
    renderWithDnd(<ResizeHandleOverlay placementId="p-1" />)
    // Spot-check 4 corner cases — operator-observable inline style.
    const nw = document.querySelector(
      `[data-handle-position="nw"]`,
    )
    const ne = document.querySelector(
      `[data-handle-position="ne"]`,
    )
    const sw = document.querySelector(
      `[data-handle-position="sw"]`,
    )
    const se = document.querySelector(
      `[data-handle-position="se"]`,
    )
    expect(nw?.getAttribute("style") ?? "").toMatch(/top:\s*-?4px/i)
    expect(nw?.getAttribute("style") ?? "").toMatch(/left:\s*-?4px/i)
    expect(ne?.getAttribute("style") ?? "").toMatch(/right:\s*-?4px/i)
    expect(sw?.getAttribute("style") ?? "").toMatch(/bottom:\s*-?4px/i)
    expect(se?.getAttribute("style") ?? "").toMatch(/bottom:\s*-?4px/i)
    expect(se?.getAttribute("style") ?? "").toMatch(/right:\s*-?4px/i)
  })

  // ── Id helpers roundtrip ──────────────────────────────────────────
  it("resizeHandleIdFor + parseResizeHandleId roundtrip", () => {
    const id = resizeHandleIdFor("placement-abc", "se")
    expect(id).toBe("placement-abc-handle-se")
    const parsed = parseResizeHandleId(id)
    expect(parsed).toEqual({ placementId: "placement-abc", position: "se" })
  })

  it("parseResizeHandleId returns null on non-handle ids", () => {
    expect(parseResizeHandleId("palette-widget:foo")).toBeNull()
    expect(parseResizeHandleId("free-form-placed-widget:p1")).toBeNull()
    expect(parseResizeHandleId("random-string")).toBeNull()
  })

  it("parseResizeHandleId handles placement ids containing dashes", () => {
    // The regex's `(.+)` is greedy but the trailing `-handle-<pos>`
    // anchor pulls everything up to the last `-handle-<pos>` match.
    const id = resizeHandleIdFor("placement-with-dashes-everywhere", "nw")
    const parsed = parseResizeHandleId(id)
    expect(parsed).toEqual({
      placementId: "placement-with-dashes-everywhere",
      position: "nw",
    })
  })
})
