/** Phase R-6.2b — CaptchaWidget tests. */

import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest"

import { CaptchaWidget } from "./CaptchaWidget"

// Mock the Turnstile component — we don't want to hit Cloudflare's
// real iframe in tests. We expose a calleable onSuccess via mocked
// useEffect-style fire-on-mount.
vi.mock("@marsidev/react-turnstile", () => ({
  Turnstile: (props: { onSuccess?: (t: string) => void }) => {
    // Fire success once on mount with a fake token — emulates
    // Cloudflare's behavior with the test-always-passes site key.
    if (props.onSuccess) {
      setTimeout(() => props.onSuccess?.("fake-token-1x000"), 0)
    }
    return <div data-testid="turnstile-stub" />
  },
}))

describe("CaptchaWidget", () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it("renders disabled placeholder when VITE_TURNSTILE_SITE_KEY unset", () => {
    // Default test env has no VITE_TURNSTILE_SITE_KEY.
    const onTokenChange = vi.fn()
    render(<CaptchaWidget onTokenChange={onTokenChange} />)
    expect(
      screen.getByTestId("captcha-widget-disabled"),
    ).toBeInTheDocument()
    // Backend graceful degradation handles dev — frontend reports null.
    expect(onTokenChange).toHaveBeenCalledWith(null)
  })

  it("calls onTokenChange exactly once when key unset", () => {
    const onTokenChange = vi.fn()
    const { rerender } = render(
      <CaptchaWidget onTokenChange={onTokenChange} />,
    )
    rerender(<CaptchaWidget onTokenChange={onTokenChange} />)
    expect(onTokenChange).toHaveBeenCalledTimes(1)
  })
})
