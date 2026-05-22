/**
 * Tests for CanvasPreviewBanner (WB-5).
 */
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import type { CanvasPreviewDataMap } from "@/bridgeable-admin/hooks/useCanvasPreviewData"
import type { SavedViewResult } from "@/types/saved-views"
import { CanvasPreviewBanner } from "./CanvasPreviewBanner"


function fakeResult(): SavedViewResult {
  return {
    total_count: 1,
    rows: [{ value: 1 }],
    aggregations: null,
    permission_mode: "full",
    masked_fields: [],
  }
}


describe("CanvasPreviewBanner", () => {
  it("renders nothing when previewData is empty / idle", () => {
    const { container } = render(<CanvasPreviewBanner previewData={{}} />)
    expect(container.innerHTML).toBe("")
  })

  it("renders nothing for non-network errors (atom-level only)", () => {
    const data: CanvasPreviewDataMap = {
      vA: {
        status: "error",
        error: {
          code: "view_not_found",
          message: "missing",
          network_class: false,
        },
      },
    }
    const { container } = render(<CanvasPreviewBanner previewData={data} />)
    expect(container.innerHTML).toBe("")
  })

  it("surfaces network-class errors with the retry affordance", () => {
    const data: CanvasPreviewDataMap = {
      vA: {
        status: "error",
        error: {
          code: "network_error",
          message: "Network Error",
          network_class: true,
        },
      },
    }
    const onRetry = vi.fn()
    render(<CanvasPreviewBanner previewData={data} onRetry={onRetry} />)
    const banner = screen.getByTestId("widget-builder-canvas-preview-banner")
    expect(banner.getAttribute("data-banner-state")).toBe("network-error")
    expect(banner.textContent).toMatch(/network error/i)

    const retryBtn = screen.getByTestId(
      "widget-builder-canvas-preview-banner-retry",
    )
    fireEvent.click(retryBtn)
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it("renders the fetching pill when at least one fetch is loading", () => {
    const data: CanvasPreviewDataMap = {
      vA: { status: "loading" },
    }
    render(<CanvasPreviewBanner previewData={data} />)
    const banner = screen.getByTestId("widget-builder-canvas-preview-banner")
    expect(banner.getAttribute("data-banner-state")).toBe("fetching")
    expect(banner.textContent).toMatch(/fetching/i)
  })

  it("prefers network-error banner over fetching pill when both apply", () => {
    const data: CanvasPreviewDataMap = {
      vA: { status: "loading" },
      vB: {
        status: "error",
        error: {
          code: "network_error",
          message: "boom",
          network_class: true,
        },
      },
    }
    render(<CanvasPreviewBanner previewData={data} />)
    expect(
      screen
        .getByTestId("widget-builder-canvas-preview-banner")
        .getAttribute("data-banner-state"),
    ).toBe("network-error")
  })

  it("aggregates count when multiple network errors present", () => {
    const data: CanvasPreviewDataMap = {
      vA: {
        status: "error",
        error: {
          code: "network_error",
          message: "boom1",
          network_class: true,
        },
      },
      vB: {
        status: "error",
        error: {
          code: "network_error",
          message: "boom2",
          network_class: true,
        },
      },
    }
    render(<CanvasPreviewBanner previewData={data} />)
    expect(screen.getByText(/2 saved views/i)).toBeTruthy()
  })

  it("visual chrome is distinct from validation chrome (uses status-warning, not status-error)", () => {
    const data: CanvasPreviewDataMap = {
      vA: {
        status: "error",
        error: {
          code: "network_error",
          message: "boom",
          network_class: true,
        },
      },
    }
    const { container } = render(<CanvasPreviewBanner previewData={data} />)
    expect(container.innerHTML).toMatch(/status-warning/)
    expect(container.innerHTML).not.toMatch(/status-error/)
  })

  it("ignores success states (no banner when all loaded cleanly)", () => {
    const data: CanvasPreviewDataMap = {
      vA: { status: "success", data: fakeResult() },
    }
    const { container } = render(<CanvasPreviewBanner previewData={data} />)
    expect(container.innerHTML).toBe("")
  })
})
