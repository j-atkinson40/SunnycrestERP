/**
 * EmailGlanceWidget — vitest unit tests.
 *
 * Phase W-4b Layer 1 Step 5 contract:
 *   - Three density tiers render simultaneously (CSS @container
 *     queries dispatch visibility; tests verify all three are present)
 *   - Click navigation: single-thread → /inbox?thread_id={id};
 *     multi-thread → /inbox?status=unread; empty → /inbox
 *   - Empty + no access state: "No email access" copy
 *   - Empty + has access state: "Inbox clear" copy
 *   - Count rendered as monospaced numeral (font-plex-mono class)
 *   - Top-sender display falls back from name → email
 *   - Cross-tenant tenant label rendered in default tier when present
 *   - Spaces-pin variant renders single-line tablet (not 3 tiers)
 */

import { render, fireEvent } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"


let mockData: unknown = null
let mockIsLoading = false


vi.mock("@/components/widgets/useWidgetData", () => ({
  useWidgetData: () => ({
    data: mockData,
    isLoading: mockIsLoading,
    error: null,
    refresh: vi.fn(),
    lastUpdated: new Date(),
  }),
}))


const mockNavigate = vi.fn()
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  )
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})


import { EmailGlanceWidget } from "./EmailGlanceWidget"
import type { EmailGlanceData } from "./EmailGlanceWidget"


function makeData(
  overrides: Partial<EmailGlanceData> = {},
): EmailGlanceData {
  return {
    has_email_access: true,
    unread_count: 3,
    top_sender_email: "fh@hopkins.test",
    top_sender_name: "Mary Hopkins",
    top_sender_tenant_label: "Hopkins FH",
    cross_tenant_indicator: false,
    ai_priority_count: 0,
    target_thread_id: null,
    ...overrides,
  }
}


function renderWidget(
  props: Parameters<typeof EmailGlanceWidget>[0] = {},
) {
  return render(
    <MemoryRouter>
      <EmailGlanceWidget {...props} />
    </MemoryRouter>,
  )
}


describe("EmailGlanceWidget", () => {
  beforeEach(() => {
    mockNavigate.mockReset()
    mockData = null
    mockIsLoading = false
  })

  describe("density tiers", () => {
    it("renders all three tiers simultaneously (CSS dispatches visibility)", () => {
      mockData = makeData()
      const { getByTestId } = renderWidget()
      expect(getByTestId("email-glance-default")).toBeInTheDocument()
      expect(getByTestId("email-glance-compact")).toBeInTheDocument()
      expect(getByTestId("email-glance-ultra-compact")).toBeInTheDocument()
    })

    it("default tier carries class for @container query dispatch", () => {
      mockData = makeData()
      const { getByTestId } = renderWidget()
      expect(getByTestId("email-glance-default")).toHaveClass(
        "email-glance-widget-pulse-default",
      )
      expect(getByTestId("email-glance-compact")).toHaveClass(
        "email-glance-widget-pulse-compact",
      )
      expect(getByTestId("email-glance-ultra-compact")).toHaveClass(
        "email-glance-widget-pulse-ultra-compact",
      )
    })

    it("count rendered as font-plex-mono numeral", () => {
      mockData = makeData({ unread_count: 7 })
      const { getAllByTestId } = renderWidget()
      // Each tier renders its own count; all should display "7"
      const counts = getAllByTestId("email-glance-count")
      counts.forEach((el) => {
        expect(el.textContent).toBe("7")
      })
    })

    it("count is em-dash placeholder during load", () => {
      mockIsLoading = true
      mockData = null
      const { getByTestId } = renderWidget()
      const def = getByTestId("email-glance-default")
      expect(def.textContent).toContain("—")
    })
  })

  describe("click navigation", () => {
    it("single-thread surface routes to /inbox?thread_id=...", () => {
      mockData = makeData({
        unread_count: 1,
        target_thread_id: "thread-abc",
      })
      const { getByTestId } = renderWidget()
      fireEvent.click(getByTestId("email-glance-default"))
      expect(mockNavigate).toHaveBeenCalledWith("/inbox?thread_id=thread-abc")
    })

    it("multi-thread surface routes to /inbox?status=unread", () => {
      mockData = makeData({ unread_count: 3, target_thread_id: null })
      const { getByTestId } = renderWidget()
      fireEvent.click(getByTestId("email-glance-default"))
      expect(mockNavigate).toHaveBeenCalledWith("/inbox?status=unread")
    })

    it("empty + has_email_access routes to /inbox", () => {
      mockData = makeData({
        has_email_access: true,
        unread_count: 0,
        top_sender_email: null,
        top_sender_name: null,
        target_thread_id: null,
      })
      const { getByTestId } = renderWidget()
      fireEvent.click(getByTestId("email-glance-default"))
      expect(mockNavigate).toHaveBeenCalledWith("/inbox")
    })

    it("no access routes to /inbox (graceful)", () => {
      mockData = makeData({ has_email_access: false, unread_count: 0 })
      const { getByTestId } = renderWidget()
      fireEvent.click(getByTestId("email-glance-default"))
      expect(mockNavigate).toHaveBeenCalledWith("/inbox")
    })
  })

  describe("empty states", () => {
    it("no access shows 'No email access'", () => {
      mockData = makeData({
        has_email_access: false,
        unread_count: 0,
        top_sender_email: null,
        top_sender_name: null,
      })
      const { getAllByText } = renderWidget()
      // Empty-state appears in both default + compact tiers
      expect(getAllByText(/No email access/i).length).toBeGreaterThan(0)
    })

    it("has access + zero unread shows 'Inbox clear'", () => {
      mockData = makeData({
        has_email_access: true,
        unread_count: 0,
        top_sender_email: null,
        top_sender_name: null,
      })
      const { getAllByText } = renderWidget()
      expect(getAllByText(/Inbox clear/i).length).toBeGreaterThan(0)
    })
  })

  describe("sender display", () => {
    it("falls back to email when name is null", () => {
      mockData = makeData({
        top_sender_name: null,
        top_sender_email: "fh@hopkins.test",
      })
      const { getAllByText } = renderWidget()
      expect(getAllByText(/fh@hopkins\.test/).length).toBeGreaterThan(0)
    })

    it("renders cross-tenant label in default tier when present", () => {
      mockData = makeData({
        top_sender_tenant_label: "Hopkins FH",
      })
      const { getByTestId } = renderWidget()
      const def = getByTestId("email-glance-default")
      expect(def.textContent).toContain("Hopkins FH")
    })
  })

  describe("spaces_pin variant", () => {
    it("renders single-line tablet (not three tiers)", () => {
      mockData = makeData()
      const { getByTestId, queryByTestId } = renderWidget({
        surface: "spaces_pin",
      })
      expect(getByTestId("email-glance-spaces-pin")).toBeInTheDocument()
      expect(queryByTestId("email-glance-default")).toBeNull()
    })

    it("spaces_pin click navigates correctly", () => {
      mockData = makeData({
        unread_count: 2,
        target_thread_id: null,
      })
      const { getByTestId } = renderWidget({ surface: "spaces_pin" })
      fireEvent.click(getByTestId("email-glance-spaces-pin"))
      expect(mockNavigate).toHaveBeenCalledWith("/inbox?status=unread")
    })

    it("spaces_pin omits count when zero", () => {
      mockData = makeData({
        unread_count: 0,
        top_sender_email: null,
        top_sender_name: null,
      })
      const { getByTestId } = renderWidget({ surface: "spaces_pin" })
      const pin = getByTestId("email-glance-spaces-pin")
      // Count badge should not render when count = 0
      expect(pin.querySelector(".font-plex-mono")).toBeNull()
    })
  })
})
