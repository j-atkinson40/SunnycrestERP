/**
 * Arc 4d — SourceBadge canonical primitive tests.
 *
 * Verifies the tenth shared authoring component primitive:
 *   - Both variants render across all 6 canonical SourceValue cases.
 *   - Letter variant produces single-char circle with title tooltip.
 *   - Chip variant produces full-word pill with visible label.
 *   - onHoverReveal callback fires on mouseEnter.
 *   - Accent state (data-accented) flips correctly for tenant + draft.
 *   - Custom data-testid override works.
 */
import { describe, expect, it, vi, afterEach } from "vitest"
import { render, screen, cleanup, fireEvent } from "@testing-library/react"

import { SourceBadge } from "./SourceBadge"
import type { SourceValue, SourceBadgeVariant } from "./SourceBadge"


afterEach(() => {
  cleanup()
})


const ALL_SOURCES: SourceValue[] = [
  "default",
  "class-default",
  "platform",
  "vertical",
  "tenant",
  "draft",
]


describe("SourceBadge — letter variant", () => {
  it.each(ALL_SOURCES)(
    "renders single-char circle for source=%s",
    (source) => {
      render(<SourceBadge source={source} variant="letter" />)
      const el = screen.getByTestId(`source-badge-letter-${source}`)
      expect(el).toBeInTheDocument()
      expect(el.getAttribute("data-variant")).toBe("letter")
      expect(el.getAttribute("data-source")).toBe(source)
      // Single-char visible content.
      expect(el.textContent?.length ?? 0).toBeLessThanOrEqual(1)
    },
  )

  it("uses canonical letter mapping per source", () => {
    const mapping: Record<SourceValue, string> = {
      default: "D",
      "class-default": "C",
      platform: "P",
      vertical: "V",
      tenant: "T",
      draft: "•",
    }
    for (const source of ALL_SOURCES) {
      const { unmount } = render(
        <SourceBadge source={source} variant="letter" />,
      )
      const el = screen.getByTestId(`source-badge-letter-${source}`)
      expect(el.textContent).toBe(mapping[source])
      unmount()
    }
  })

  it("exposes full label as title tooltip", () => {
    render(<SourceBadge source="tenant" variant="letter" />)
    expect(screen.getByTestId("source-badge-letter-tenant").title).toBe(
      "Tenant",
    )
  })
})


describe("SourceBadge — chip variant", () => {
  it.each(ALL_SOURCES)("renders full-word pill for source=%s", (source) => {
    render(<SourceBadge source={source} variant="chip" />)
    const el = screen.getByTestId(`source-badge-chip-${source}`)
    expect(el).toBeInTheDocument()
    expect(el.getAttribute("data-variant")).toBe("chip")
    expect(el.getAttribute("data-source")).toBe(source)
    // Visible label, NOT a single char.
    expect((el.textContent ?? "").length).toBeGreaterThan(1)
  })

  it("shows canonical label per source", () => {
    const mapping: Record<SourceValue, string> = {
      default: "Default",
      "class-default": "Class default",
      platform: "Platform",
      vertical: "Vertical",
      tenant: "Tenant",
      draft: "Draft",
    }
    for (const source of ALL_SOURCES) {
      const { unmount } = render(
        <SourceBadge source={source} variant="chip" />,
      )
      expect(
        screen.getByTestId(`source-badge-chip-${source}`).textContent,
      ).toBe(mapping[source])
      unmount()
    }
  })
})


describe("SourceBadge — accent state", () => {
  it.each<[SourceValue, boolean]>([
    ["default", false],
    ["class-default", false],
    ["platform", false],
    ["vertical", false],
    ["tenant", true],
    ["draft", true],
  ])("accents source=%s ↔ %s", (source, expected) => {
    render(<SourceBadge source={source} variant="chip" />)
    expect(
      screen
        .getByTestId(`source-badge-chip-${source}`)
        .getAttribute("data-accented"),
    ).toBe(expected ? "true" : "false")
  })
})


describe("SourceBadge — hover callback", () => {
  it("fires onHoverReveal on mouseEnter", () => {
    const onHoverReveal = vi.fn()
    render(
      <SourceBadge
        source="tenant"
        variant="chip"
        onHoverReveal={onHoverReveal}
      />,
    )
    const el = screen.getByTestId("source-badge-chip-tenant")
    fireEvent.mouseEnter(el)
    expect(onHoverReveal).toHaveBeenCalledTimes(1)
  })

  it("works without onHoverReveal", () => {
    render(<SourceBadge source="platform" variant="letter" />)
    expect(() =>
      fireEvent.mouseEnter(
        screen.getByTestId("source-badge-letter-platform"),
      ),
    ).not.toThrow()
  })
})


describe("SourceBadge — test-id override", () => {
  it("respects custom data-testid prop", () => {
    render(
      <SourceBadge
        source="vertical"
        variant="chip"
        data-testid="my-custom-id"
      />,
    )
    expect(screen.getByTestId("my-custom-id")).toBeInTheDocument()
  })
})


describe("SourceBadge — variant interface canonical", () => {
  it("both variants are valid SourceBadgeVariant values", () => {
    const variants: SourceBadgeVariant[] = ["letter", "chip"]
    for (const v of variants) {
      const { unmount } = render(
        <SourceBadge source="platform" variant={v} />,
      )
      expect(
        screen.getByTestId(`source-badge-${v}-platform`),
      ).toBeInTheDocument()
      unmount()
    }
  })
})
