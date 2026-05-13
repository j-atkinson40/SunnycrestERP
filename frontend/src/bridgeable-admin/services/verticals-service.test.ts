/**
 * verticals-service axios wrapper test coverage.
 *
 * Verifies the 3 client methods hit the canonical
 * `/api/platform/admin/verticals/*` paths with correct params/payloads.
 * Backend coverage is in test_verticals.py — these tests pin the
 * frontend wire contract.
 */
import { afterEach, describe, expect, it, vi } from "vitest"


vi.mock("@/bridgeable-admin/lib/admin-api", () => ({
  adminApi: {
    get: vi.fn(),
    patch: vi.fn(),
    post: vi.fn(),
  },
}))


import { adminApi } from "@/bridgeable-admin/lib/admin-api"
import { verticalsService } from "./verticals-service"


afterEach(() => {
  vi.clearAllMocks()
})


describe("verticalsService.list", () => {
  it("calls adminApi.get with canonical path + empty params by default", async () => {
    (adminApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    await verticalsService.list()
    expect(adminApi.get).toHaveBeenCalledWith(
      "/api/platform/admin/verticals/",
      { params: {} },
    )
  })

  it("threads include_archived flag through query params", async () => {
    (adminApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    await verticalsService.list({ include_archived: true })
    expect(adminApi.get).toHaveBeenCalledWith(
      "/api/platform/admin/verticals/",
      { params: { include_archived: true } },
    )
  })

  it("returns the response data", async () => {
    const payload = [
      {
        slug: "manufacturing",
        display_name: "Manufacturing",
        description: null,
        status: "published",
        icon: null,
        sort_order: 10,
        created_at: "2026-05-13T00:00:00",
        updated_at: "2026-05-13T00:00:00",
      },
    ]
    ;(adminApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: payload,
    })
    const result = await verticalsService.list()
    expect(result).toEqual(payload)
  })
})


describe("verticalsService.get", () => {
  it("calls adminApi.get with /{slug} path", async () => {
    (adminApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { slug: "manufacturing" },
    })
    await verticalsService.get("manufacturing")
    expect(adminApi.get).toHaveBeenCalledWith(
      "/api/platform/admin/verticals/manufacturing",
    )
  })
})


describe("verticalsService.update", () => {
  it("calls adminApi.patch with /{slug} path + payload", async () => {
    (adminApi.patch as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { slug: "manufacturing", display_name: "Custom" },
    })
    await verticalsService.update("manufacturing", {
      display_name: "Custom",
      sort_order: 5,
    })
    expect(adminApi.patch).toHaveBeenCalledWith(
      "/api/platform/admin/verticals/manufacturing",
      { display_name: "Custom", sort_order: 5 },
    )
  })

  it("does not include slug in payload (slug is immutable)", async () => {
    (adminApi.patch as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { slug: "manufacturing" },
    })
    // TypeScript prevents passing slug at compile time; verify the
    // actual wire payload matches the typed VerticalUpdate shape.
    await verticalsService.update("manufacturing", {
      display_name: "X",
    })
    const lastCall = (adminApi.patch as ReturnType<typeof vi.fn>).mock
      .calls[0]
    expect(lastCall[1]).not.toHaveProperty("slug")
  })
})
