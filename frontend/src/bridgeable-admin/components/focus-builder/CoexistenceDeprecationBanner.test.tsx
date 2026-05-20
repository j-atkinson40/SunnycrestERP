/**
 * CoexistenceDeprecationBanner unit tests (sub-arc F-5).
 */
import { afterEach, describe, expect, it } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import {
  CoexistenceDeprecationBanner,
  COEXISTENCE_BANNER_STORAGE_KEY,
} from "./CoexistenceDeprecationBanner"


afterEach(() => {
  window.localStorage.clear()
})


describe("CoexistenceDeprecationBanner", () => {
  it("renders by default when localStorage flag not set", () => {
    render(<CoexistenceDeprecationBanner />)
    const banner = screen.getByTestId("coexistence-banner")
    expect(banner).toBeInTheDocument()
    // operator-observable textContent contains the expected copy.
    expect(banner.textContent).toMatch(/legacy Focus editor/i)
    expect(banner.textContent).toMatch(/Focus Builder/)
  })

  it("does NOT render when dismissed flag is set in localStorage", () => {
    window.localStorage.setItem(COEXISTENCE_BANNER_STORAGE_KEY, "true")
    render(<CoexistenceDeprecationBanner />)
    expect(screen.queryByTestId("coexistence-banner")).not.toBeInTheDocument()
  })

  it("link href defaults to /studio/builder/focuses", () => {
    render(<CoexistenceDeprecationBanner />)
    const link = screen.getByTestId("coexistence-banner-link")
    expect(link).toHaveAttribute("href", "/studio/builder/focuses")
  })

  it("respects custom linkHref prop", () => {
    render(
      <CoexistenceDeprecationBanner linkHref="/bridgeable-admin/studio/builder/focuses" />,
    )
    const link = screen.getByTestId("coexistence-banner-link")
    expect(link).toHaveAttribute(
      "href",
      "/bridgeable-admin/studio/builder/focuses",
    )
  })

  it("dismiss button removes banner from DOM and sets localStorage flag", () => {
    render(<CoexistenceDeprecationBanner />)
    expect(screen.getByTestId("coexistence-banner")).toBeInTheDocument()
    fireEvent.click(screen.getByTestId("coexistence-banner-dismiss"))
    expect(screen.queryByTestId("coexistence-banner")).not.toBeInTheDocument()
    expect(
      window.localStorage.getItem(COEXISTENCE_BANNER_STORAGE_KEY),
    ).toBe("true")
  })

  it("dismissal persists across re-mount (localStorage)", () => {
    const { unmount } = render(<CoexistenceDeprecationBanner />)
    fireEvent.click(screen.getByTestId("coexistence-banner-dismiss"))
    expect(screen.queryByTestId("coexistence-banner")).not.toBeInTheDocument()
    unmount()
    render(<CoexistenceDeprecationBanner />)
    expect(screen.queryByTestId("coexistence-banner")).not.toBeInTheDocument()
  })

  it("dismiss button has aria-label for screen readers", () => {
    render(<CoexistenceDeprecationBanner />)
    expect(
      screen.getByTestId("coexistence-banner-dismiss"),
    ).toHaveAttribute("aria-label", "Dismiss legacy editor banner")
  })
})
