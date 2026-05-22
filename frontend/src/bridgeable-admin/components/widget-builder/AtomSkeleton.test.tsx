/**
 * Tests for AtomSkeleton (WB-5).
 */
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import type { AtomType } from "@/lib/widget-builder/types/composition-blob"
import { AtomSkeleton } from "./AtomSkeleton"


const ALL_ATOM_TYPES: AtomType[] = [
  "text_label",
  "value_display",
  "icon",
  "status_badge",
  "divider",
  "button",
  "image",
  "conditional_container",
  "repeater_atom",
]


describe("AtomSkeleton", () => {
  it.each(ALL_ATOM_TYPES)(
    "renders a body for atom_type=%s with the canonical test id",
    (atomType) => {
      render(<AtomSkeleton atomType={atomType} />)
      expect(screen.getByTestId(`atom-skeleton-${atomType}`)).toBeTruthy()
      expect(screen.getByTestId("atom-skeleton-body")).toBeTruthy()
    },
  )

  it("does NOT render shimmer overlay by default", () => {
    render(<AtomSkeleton atomType="text_label" />)
    expect(screen.queryByTestId("atom-skeleton-shimmer")).toBeNull()
    expect(
      screen.getByTestId("atom-skeleton-text_label").getAttribute("data-shimmer"),
    ).toBe("false")
  })

  it("renders shimmer overlay when shimmer prop is true", () => {
    render(<AtomSkeleton atomType="value_display" shimmer />)
    expect(screen.getByTestId("atom-skeleton-shimmer")).toBeTruthy()
    expect(
      screen
        .getByTestId("atom-skeleton-value_display")
        .getAttribute("data-shimmer"),
    ).toBe("true")
  })

  it("uses DESIGN_LANGUAGE surface tokens (no raw hex)", () => {
    const { container } = render(<AtomSkeleton atomType="text_label" />)
    const html = container.innerHTML
    // No raw hex colors.
    expect(html).not.toMatch(/#[0-9a-fA-F]{3,6}/)
    // Surface-sunken token referenced.
    expect(html).toMatch(/bg-surface-sunken/)
  })

  it("visual chrome is distinct from validation chrome (no status-error class)", () => {
    const { container } = render(<AtomSkeleton atomType="text_label" />)
    expect(container.innerHTML).not.toMatch(/outline-status-error/)
    expect(container.innerHTML).not.toMatch(/status-error/)
  })
})
