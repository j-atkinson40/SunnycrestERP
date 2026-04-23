/**
 * Focus API client — contract tests.
 *
 * Mocks apiClient and verifies the service functions format requests
 * correctly. Full integration coverage lives in
 * backend/tests/test_focus_session.py.
 */

import { afterEach, describe, expect, it, vi } from "vitest"

import apiClient from "@/lib/api-client"
import {
  closeFocusSession,
  fetchFocusLayout,
  listRecentFocusSessions,
  openFocusSession,
  updateFocusLayout,
} from "./focus-service"


vi.mock("@/lib/api-client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}))


describe("focus-service", () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it("fetchFocusLayout hits GET /focus/{type}/layout", async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { layout_state: null, source: null },
    } as never)
    const r = await fetchFocusLayout("kanban")
    expect(apiClient.get).toHaveBeenCalledWith("/focus/kanban/layout")
    expect(r.layout_state).toBeNull()
  })

  it("openFocusSession hits POST /focus/{type}/open", async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        session: {
          id: "sid",
          focus_type: "kanban",
          layout_state: {},
          is_active: true,
          opened_at: "",
          closed_at: null,
          last_interacted_at: "",
        },
        layout_state: null,
        source: null,
      },
    } as never)
    const r = await openFocusSession("kanban")
    expect(apiClient.post).toHaveBeenCalledWith("/focus/kanban/open")
    expect(r.session.id).toBe("sid")
  })

  it("updateFocusLayout hits PATCH /focus/sessions/{id}/layout", async () => {
    vi.mocked(apiClient.patch).mockResolvedValueOnce({
      data: {
        id: "sid",
        focus_type: "kanban",
        layout_state: { widgets: {} },
        is_active: true,
        opened_at: "",
        closed_at: null,
        last_interacted_at: "",
      },
    } as never)
    const layout = { widgets: { w1: { position: { anchor: "top-left", offsetX: 0, offsetY: 0, width: 0, height: 0 } } } }
    await updateFocusLayout("sid", layout as never)
    expect(apiClient.patch).toHaveBeenCalledWith(
      "/focus/sessions/sid/layout",
      { layout_state: layout },
    )
  })

  it("closeFocusSession hits POST /focus/sessions/{id}/close", async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        id: "sid",
        focus_type: "kanban",
        layout_state: {},
        is_active: false,
        opened_at: "",
        closed_at: "",
        last_interacted_at: "",
      },
    } as never)
    await closeFocusSession("sid")
    expect(apiClient.post).toHaveBeenCalledWith(
      "/focus/sessions/sid/close",
    )
  })

  it("listRecentFocusSessions passes limit param", async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: [],
    } as never)
    await listRecentFocusSessions(5)
    expect(apiClient.get).toHaveBeenCalledWith("/focus/recent", {
      params: { limit: 5 },
    })
  })
})
