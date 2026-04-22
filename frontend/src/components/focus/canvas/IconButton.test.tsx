/**
 * IconButton — vitest unit tests. Phase A Session 3.7.
 */

import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { IconButton } from "./IconButton"


describe("IconButton", () => {
  it("renders nothing when widgetCount is 0", () => {
    const { container } = render(
      <IconButton widgetCount={0} onOpen={() => {}} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it("renders button with widget count aria-label when count > 0", () => {
    render(<IconButton widgetCount={3} onOpen={() => {}} />)
    expect(
      screen.getByRole("button", { name: /open widgets \(3\)/i }),
    ).toBeInTheDocument()
  })

  it("shows badge when widgetCount > 1", () => {
    render(<IconButton widgetCount={3} onOpen={() => {}} />)
    const badge = document.querySelector('[data-slot="focus-icon-badge"]')
    expect(badge).toBeInTheDocument()
    expect(badge?.textContent).toBe("3")
  })

  it("omits badge when widgetCount is exactly 1", () => {
    render(<IconButton widgetCount={1} onOpen={() => {}} />)
    const badge = document.querySelector('[data-slot="focus-icon-badge"]')
    expect(badge).not.toBeInTheDocument()
  })

  it("onOpen fires on click", async () => {
    const user = userEvent.setup()
    const onOpen = vi.fn()
    render(<IconButton widgetCount={2} onOpen={onOpen} />)
    await user.click(screen.getByRole("button", { name: /open widgets/i }))
    expect(onOpen).toHaveBeenCalledTimes(1)
  })

  it("has safe-area-inset-bottom handling in className", () => {
    render(<IconButton widgetCount={1} onOpen={() => {}} />)
    const btn = screen.getByRole("button", { name: /open widgets/i })
    // Tailwind arbitrary value embeds the env() call — verify the
    // class contains `safe-area-inset-bottom` (the class doesn't
    // compute until browser; class-string presence is the proxy).
    expect(btn.className).toMatch(/safe-area-inset-bottom/)
  })
})
