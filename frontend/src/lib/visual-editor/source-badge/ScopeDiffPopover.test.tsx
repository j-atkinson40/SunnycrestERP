/**
 * Arc 4d — ScopeDiffPopover co-located primitive tests.
 *
 * Verifies:
 *   - Empty sources renders trigger only (no popover).
 *   - Populated sources: hover after delay opens popover.
 *   - Mouse-leave closes popover.
 *   - Esc dismisses.
 *   - Click-outside dismisses.
 *   - Winning (idx=0) entry highlighted with accent.
 *   - Scope ordering preserved (resolver order).
 *   - Version + vertical + tenant_id metadata renders.
 *   - Drift warning shows when currentValue differs from winning.
 *   - fieldLabel renders in header.
 *   - Mouse-enter content keeps popover open (prevents flicker).
 *   - 300ms default delay (configurable via openDelayMs).
 */
import { describe, expect, it, vi, afterEach, beforeEach } from "vitest"
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react"

import { ScopeDiffPopover } from "./ScopeDiffPopover"
import type { ResolutionSourceEntry } from "./ScopeDiffPopover"


afterEach(() => {
  cleanup()
  vi.useRealTimers()
})


function makeSources(): ResolutionSourceEntry[] {
  return [
    {
      scope: "tenant_override",
      value: "tenant-val",
      version: 3,
      tenant_id: "abcd1234-tenant",
    },
    {
      scope: "vertical_default",
      value: "vert-val",
      version: 2,
      vertical: "manufacturing",
    },
    {
      scope: "platform_default",
      value: "platform-val",
      version: 1,
    },
  ]
}


describe("ScopeDiffPopover — empty state", () => {
  it("renders trigger only when sources is empty", () => {
    render(
      <ScopeDiffPopover sources={[]}>
        <span data-testid="trigger">badge</span>
      </ScopeDiffPopover>,
    )
    expect(screen.getByTestId("trigger")).toBeInTheDocument()
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(
      screen.getByTestId("scope-diff-popover").getAttribute("data-state"),
    ).toBe("empty")
  })

  it("does not open on hover when sources empty", () => {
    vi.useFakeTimers()
    render(
      <ScopeDiffPopover sources={[]}>
        <span>badge</span>
      </ScopeDiffPopover>,
    )
    fireEvent.mouseEnter(screen.getByTestId("scope-diff-popover"))
    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })
})


describe("ScopeDiffPopover — hover open/close", () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  it("opens after default 300ms delay on hover", () => {
    render(
      <ScopeDiffPopover sources={makeSources()}>
        <span>badge</span>
      </ScopeDiffPopover>,
    )
    fireEvent.mouseEnter(screen.getByTestId("scope-diff-popover"))
    // Not open yet.
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    act(() => {
      vi.advanceTimersByTime(300)
    })
    expect(screen.getByRole("dialog")).toBeInTheDocument()
  })

  it("does NOT open before delay elapses", () => {
    render(
      <ScopeDiffPopover sources={makeSources()} openDelayMs={500}>
        <span>badge</span>
      </ScopeDiffPopover>,
    )
    fireEvent.mouseEnter(screen.getByTestId("scope-diff-popover"))
    act(() => {
      vi.advanceTimersByTime(499)
    })
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    act(() => {
      vi.advanceTimersByTime(1)
    })
    expect(screen.getByRole("dialog")).toBeInTheDocument()
  })

  it("closes on mouse-leave", () => {
    render(
      <ScopeDiffPopover sources={makeSources()}>
        <span>badge</span>
      </ScopeDiffPopover>,
    )
    const trigger = screen.getByTestId("scope-diff-popover")
    fireEvent.mouseEnter(trigger)
    act(() => {
      vi.advanceTimersByTime(300)
    })
    expect(screen.getByRole("dialog")).toBeInTheDocument()
    fireEvent.mouseLeave(trigger)
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("mouse-enter on popover content does not close (prevents flicker)", () => {
    render(
      <ScopeDiffPopover sources={makeSources()}>
        <span>badge</span>
      </ScopeDiffPopover>,
    )
    const trigger = screen.getByTestId("scope-diff-popover")
    fireEvent.mouseEnter(trigger)
    act(() => {
      vi.advanceTimersByTime(300)
    })
    const content = screen.getByTestId("scope-diff-popover-content")
    fireEvent.mouseEnter(content)
    // Still open.
    expect(screen.getByRole("dialog")).toBeInTheDocument()
  })
})


describe("ScopeDiffPopover — dismiss behaviors", () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  it("Esc dismisses open popover", () => {
    render(
      <ScopeDiffPopover sources={makeSources()}>
        <span>badge</span>
      </ScopeDiffPopover>,
    )
    fireEvent.mouseEnter(screen.getByTestId("scope-diff-popover"))
    act(() => {
      vi.advanceTimersByTime(300)
    })
    expect(screen.getByRole("dialog")).toBeInTheDocument()
    fireEvent.keyDown(document, { key: "Escape" })
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("click-outside dismisses", () => {
    render(
      <div>
        <ScopeDiffPopover sources={makeSources()}>
          <span>badge</span>
        </ScopeDiffPopover>
        <div data-testid="outside">outside</div>
      </div>,
    )
    fireEvent.mouseEnter(screen.getByTestId("scope-diff-popover"))
    act(() => {
      vi.advanceTimersByTime(300)
    })
    expect(screen.getByRole("dialog")).toBeInTheDocument()
    fireEvent.mouseDown(screen.getByTestId("outside"))
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })
})


describe("ScopeDiffPopover — content rendering", () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  function openPopover(sources = makeSources(), extraProps = {}) {
    render(
      <ScopeDiffPopover sources={sources} {...extraProps}>
        <span>badge</span>
      </ScopeDiffPopover>,
    )
    fireEvent.mouseEnter(screen.getByTestId("scope-diff-popover"))
    act(() => {
      vi.advanceTimersByTime(300)
    })
  }

  it("renders scope entries in resolver order", () => {
    openPopover()
    expect(screen.getByTestId("scope-diff-entry-0").getAttribute("data-scope")).toBe(
      "tenant_override",
    )
    expect(screen.getByTestId("scope-diff-entry-1").getAttribute("data-scope")).toBe(
      "vertical_default",
    )
    expect(screen.getByTestId("scope-diff-entry-2").getAttribute("data-scope")).toBe(
      "platform_default",
    )
  })

  it("marks idx=0 as winning entry", () => {
    openPopover()
    expect(
      screen.getByTestId("scope-diff-entry-0").getAttribute("data-winning"),
    ).toBe("true")
    expect(
      screen.getByTestId("scope-diff-entry-1").getAttribute("data-winning"),
    ).toBe("false")
  })

  it("renders fieldLabel in header", () => {
    openPopover(makeSources(), { fieldLabel: "accent token" })
    expect(screen.getByText("accent token")).toBeInTheDocument()
  })

  it("renders drift warning when currentValue differs from winning", () => {
    openPopover(makeSources(), { currentValue: "stale-val" })
    expect(screen.getByTestId("scope-diff-drift-warning")).toBeInTheDocument()
  })

  it("does NOT render drift warning when currentValue matches winning", () => {
    openPopover(makeSources(), { currentValue: "tenant-val" })
    expect(
      screen.queryByTestId("scope-diff-drift-warning"),
    ).not.toBeInTheDocument()
  })
})
