/**
 * Unit tests for visual-editor-widgets-service (WB-cycle-followup-2).
 *
 * Mocks the adminApi axios instance + asserts:
 *  - Each method targets the correct platform-realm URL.
 *  - List accepts both `{widgets: [...]}` and raw-array responses.
 *  - Errors are wrapped as WidgetBuilderApiError with status + detail.
 *  - The legacy `widget-builder-service` shim re-exports the same
 *    `widgetBuilderService` symbol so existing consumers and
 *    `vi.mock(...)` paths continue working.
 */
import { describe, it, expect, vi, beforeEach } from "vitest"


// Mock adminApi BEFORE importing the service.
vi.mock("@/bridgeable-admin/lib/admin-api", () => ({
  adminApi: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import { adminApi } from "@/bridgeable-admin/lib/admin-api"
import {
  visualEditorWidgetsService,
  WidgetBuilderApiError,
} from "./visual-editor-widgets-service"


const BASE = "/api/platform/admin/visual-editor/widgets"


beforeEach(() => {
  vi.clearAllMocks()
})


describe("visualEditorWidgetsService URL targeting", () => {
  it("list() targets the platform-realm base URL", async () => {
    ;(adminApi.get as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { widgets: [] },
    })
    await visualEditorWidgetsService.list()
    expect(adminApi.get).toHaveBeenCalledWith(BASE)
  })

  it("listComposedDefinitions() targets composed-definitions", async () => {
    ;(adminApi.get as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: [],
    })
    await visualEditorWidgetsService.listComposedDefinitions()
    expect(adminApi.get).toHaveBeenCalledWith(`${BASE}/composed-definitions`)
  })

  it("create() posts to the platform-realm base URL", async () => {
    ;(adminApi.post as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { widget_id: "w-1", title: "X" },
    })
    await visualEditorWidgetsService.create({ title: "X" })
    expect(adminApi.post).toHaveBeenCalledWith(BASE, { title: "X" })
  })

  it("get(slug) targets /{slug}", async () => {
    ;(adminApi.get as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { widget_id: "w-1" },
    })
    await visualEditorWidgetsService.get("w-1")
    expect(adminApi.get).toHaveBeenCalledWith(`${BASE}/w-1`)
  })

  it("get(slug) URL-encodes the slug", async () => {
    ;(adminApi.get as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { widget_id: "spaces and/slash" },
    })
    await visualEditorWidgetsService.get("spaces and/slash")
    expect(adminApi.get).toHaveBeenCalledWith(
      `${BASE}/${encodeURIComponent("spaces and/slash")}`,
    )
  })

  it("saveDraft(slug) puts to /{slug}/draft", async () => {
    ;(adminApi.put as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { widget_id: "w-1" },
    })
    const blob = { schema_version: 1 } as never
    await visualEditorWidgetsService.saveDraft("w-1", {
      composition_blob: blob,
      edit_session_id: "session-1",
    })
    expect(adminApi.put).toHaveBeenCalledWith(`${BASE}/w-1/draft`, {
      composition_blob: blob,
      edit_session_id: "session-1",
    })
  })

  it("publish(slug) posts to /{slug}/publish", async () => {
    ;(adminApi.post as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { widget_id: "w-1" },
    })
    await visualEditorWidgetsService.publish("w-1")
    expect(adminApi.post).toHaveBeenCalledWith(`${BASE}/w-1/publish`)
  })
})


describe("visualEditorWidgetsService.list response shape tolerance", () => {
  it("accepts {widgets: [...]} envelope", async () => {
    ;(adminApi.get as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { widgets: [{ widget_id: "w-1", title: "X" }] },
    })
    const r = await visualEditorWidgetsService.list()
    expect(r.widgets).toHaveLength(1)
    expect(r.widgets[0]?.widget_id).toBe("w-1")
  })

  it("accepts raw array response", async () => {
    ;(adminApi.get as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: [{ widget_id: "w-1", title: "X" }],
    })
    const r = await visualEditorWidgetsService.list()
    expect(r.widgets).toHaveLength(1)
    expect(r.widgets[0]?.widget_id).toBe("w-1")
  })

  it("returns empty list on malformed payload", async () => {
    ;(adminApi.get as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { something_else: 42 },
    })
    const r = await visualEditorWidgetsService.list()
    expect(r.widgets).toEqual([])
  })
})


describe("visualEditorWidgetsService error wrapping", () => {
  it("wraps axios error responses as WidgetBuilderApiError", async () => {
    ;(adminApi.post as unknown as ReturnType<typeof vi.fn>).mockRejectedValue({
      response: { status: 401, data: { detail: "Tenant tokens cannot..." } },
    })
    await expect(
      visualEditorWidgetsService.create({ title: "X" }),
    ).rejects.toBeInstanceOf(WidgetBuilderApiError)
  })

  it("captures status + detail on the error instance", async () => {
    ;(adminApi.get as unknown as ReturnType<typeof vi.fn>).mockRejectedValue({
      response: { status: 404, data: { detail: "nope" } },
    })
    try {
      await visualEditorWidgetsService.get("missing")
      expect.fail("should have thrown")
    } catch (err) {
      expect(err).toBeInstanceOf(WidgetBuilderApiError)
      const e = err as WidgetBuilderApiError
      expect(e.status).toBe(404)
      expect(e.detail).toBe("nope")
    }
  })

  it("preserves publish 422 detail shape (composition_invalid)", async () => {
    ;(adminApi.post as unknown as ReturnType<typeof vi.fn>).mockRejectedValue({
      response: {
        status: 422,
        data: {
          detail: { code: "composition_invalid", errors: ["bad node"] },
        },
      },
    })
    try {
      await visualEditorWidgetsService.publish("w-1")
      expect.fail("should have thrown")
    } catch (err) {
      const e = err as WidgetBuilderApiError
      expect(e.status).toBe(422)
      expect(e.detail).toEqual({
        code: "composition_invalid",
        errors: ["bad node"],
      })
    }
  })
})


describe("legacy widget-builder-service shim", () => {
  it("re-exports widgetBuilderService bound to the platform service", async () => {
    const legacy = await import("./widget-builder-service")
    expect(legacy.widgetBuilderService).toBe(visualEditorWidgetsService)
  })

  it("re-exports WidgetBuilderApiError class", async () => {
    const legacy = await import("./widget-builder-service")
    expect(legacy.WidgetBuilderApiError).toBe(WidgetBuilderApiError)
  })
})
