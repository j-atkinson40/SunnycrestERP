/**
 * Phase R-0 — Dual-token API client unit tests.
 *
 * Covers the four canonical cases plus error semantics:
 *   - platform read   → PlatformUser token attached
 *   - platform write  → PlatformUser token attached
 *   - tenant read     → impersonation token attached
 *   - tenant write    → throws (forbidden by design)
 *
 * Also asserts:
 *   - Unsupported paths throw clearly.
 *   - Missing platform token throws with `platform_token_missing`.
 *   - Missing impersonation token throws with
 *     `impersonation_token_missing`.
 *   - Helper functions enforce path-prefix expectations.
 */
import { describe, it, expect, beforeEach, afterEach } from "vitest"
import MockAdapter from "axios-mock-adapter"

import {
  __dual_token_internals,
  getImpersonationToken,
  makeDualTokenClient,
  makeDualTokenHelpers,
  type DualTokenError,
} from "./dual-token-client"


const PLATFORM_TOKEN_KEY = "bridgeable-admin-token-production"
const PLATFORM_TOKEN = "platform-token-xyz"
const IMPERSONATION_TOKEN = "impersonation-token-abc"


function setPlatformToken(value: string | null) {
  if (value === null) {
    localStorage.removeItem(PLATFORM_TOKEN_KEY)
  } else {
    localStorage.setItem(PLATFORM_TOKEN_KEY, value)
  }
}


function setImpersonationToken(value: string | null) {
  if (value === null) {
    localStorage.removeItem("access_token")
  } else {
    localStorage.setItem("access_token", value)
  }
}


function setEnvironment(env: "production" | "staging") {
  localStorage.setItem("bridgeable-admin-env", env)
}


describe("dual-token-client classifier", () => {
  it("classifies /api/platform/* as platform", () => {
    expect(__dual_token_internals.classifyPath("/api/platform/auth/me")).toBe(
      "platform",
    )
    expect(
      __dual_token_internals.classifyPath(
        "/api/platform/admin/visual-editor/dashboard-layouts/",
      ),
    ).toBe("platform")
  })

  it("classifies /api/v1/* as tenant", () => {
    expect(__dual_token_internals.classifyPath("/api/v1/auth/me")).toBe("tenant")
    expect(__dual_token_internals.classifyPath("/api/v1/widgets/layout")).toBe(
      "tenant",
    )
  })

  it("classifies anything else as unknown", () => {
    expect(__dual_token_internals.classifyPath("/api/other/thing")).toBe(
      "unknown",
    )
    expect(__dual_token_internals.classifyPath("/v1/auth")).toBe("unknown")
    expect(__dual_token_internals.classifyPath("")).toBe("unknown")
  })
})


describe("dual-token-client routing", () => {
  beforeEach(() => {
    setEnvironment("production")
    setPlatformToken(PLATFORM_TOKEN)
    setImpersonationToken(IMPERSONATION_TOKEN)
  })

  afterEach(() => {
    setPlatformToken(null)
    setImpersonationToken(null)
    localStorage.removeItem("bridgeable-admin-env")
  })

  it("attaches PlatformUser token on /api/platform/* GET", async () => {
    const client = makeDualTokenClient()
    const mock = new MockAdapter(client)
    mock.onGet(/\/api\/platform\/foo/).reply((config) => {
      expect(config.headers?.Authorization).toBe(`Bearer ${PLATFORM_TOKEN}`)
      return [200, { ok: true }]
    })

    const res = await client.get("/api/platform/foo")
    expect(res.status).toBe(200)
    expect(res.data).toEqual({ ok: true })
  })

  it("attaches PlatformUser token on /api/platform/* POST (write)", async () => {
    const client = makeDualTokenClient()
    const mock = new MockAdapter(client)
    mock.onPost(/\/api\/platform\/foo/).reply((config) => {
      expect(config.headers?.Authorization).toBe(`Bearer ${PLATFORM_TOKEN}`)
      return [201, { id: "x" }]
    })

    const res = await client.post("/api/platform/foo", { data: 1 })
    expect(res.status).toBe(201)
  })

  it("attaches impersonation token on /api/v1/* GET (tenant read)", async () => {
    const client = makeDualTokenClient()
    const mock = new MockAdapter(client)
    mock.onGet(/\/api\/v1\/widgets\/layout/).reply((config) => {
      expect(config.headers?.Authorization).toBe(
        `Bearer ${IMPERSONATION_TOKEN}`,
      )
      return [200, { widgets: [] }]
    })

    const res = await client.get("/api/v1/widgets/layout")
    expect(res.status).toBe(200)
  })

  it("THROWS on /api/v1/* POST (tenant write forbidden)", async () => {
    const client = makeDualTokenClient()
    const mock = new MockAdapter(client)
    mock.onPost(/\/api\/v1\/orders/).reply(() => {
      throw new Error("interceptor should have rejected before the request")
    })

    await expect(
      client.post("/api/v1/orders", { foo: 1 }),
    ).rejects.toMatchObject({
      code: "tenant_write_forbidden",
    })
  })

  it("THROWS on /api/v1/* PATCH (tenant write forbidden)", async () => {
    const client = makeDualTokenClient()
    await expect(
      client.patch("/api/v1/some/thing", { x: 1 }),
    ).rejects.toMatchObject({
      code: "tenant_write_forbidden",
    })
  })

  it("THROWS on /api/v1/* DELETE (tenant write forbidden)", async () => {
    const client = makeDualTokenClient()
    await expect(client.delete("/api/v1/some/thing")).rejects.toMatchObject({
      code: "tenant_write_forbidden",
    })
  })

  it("THROWS on unsupported path", async () => {
    const client = makeDualTokenClient()
    await expect(client.get("/api/other/thing")).rejects.toMatchObject({
      code: "unsupported_path",
    })
  })

  it("THROWS when platform token missing", async () => {
    setPlatformToken(null)
    const client = makeDualTokenClient()
    await expect(client.get("/api/platform/foo")).rejects.toMatchObject({
      code: "platform_token_missing",
    })
  })

  it("THROWS when impersonation token missing", async () => {
    setImpersonationToken(null)
    const client = makeDualTokenClient()
    await expect(
      client.get("/api/v1/widgets/layout"),
    ).rejects.toMatchObject({
      code: "impersonation_token_missing",
    })
  })
})


describe("dual-token-client helpers", () => {
  beforeEach(() => {
    setEnvironment("production")
    setPlatformToken(PLATFORM_TOKEN)
    setImpersonationToken(IMPERSONATION_TOKEN)
  })

  afterEach(() => {
    setPlatformToken(null)
    setImpersonationToken(null)
    localStorage.removeItem("bridgeable-admin-env")
  })

  it("helpers enforce path-prefix expectations (platformGet rejects /api/v1)", () => {
    const client = makeDualTokenClient()
    const helpers = makeDualTokenHelpers(client)
    expect(() => helpers.platformGet("/api/v1/widgets/layout")).toThrow()
  })

  it("helpers enforce path-prefix expectations (tenantGet rejects /api/platform)", () => {
    const client = makeDualTokenClient()
    const helpers = makeDualTokenHelpers(client)
    expect(() => helpers.tenantGet("/api/platform/foo")).toThrow()
  })

  it("platformGet routes via PlatformUser token", async () => {
    const client = makeDualTokenClient()
    const helpers = makeDualTokenHelpers(client)
    const mock = new MockAdapter(client)
    mock.onGet(/\/api\/platform\/foo/).reply((config) => {
      expect(config.headers?.Authorization).toBe(`Bearer ${PLATFORM_TOKEN}`)
      return [200, { x: 1 }]
    })
    const res = await helpers.platformGet<{ x: number }>("/api/platform/foo")
    expect(res.data.x).toBe(1)
  })

  it("tenantGet routes via impersonation token", async () => {
    const client = makeDualTokenClient()
    const helpers = makeDualTokenHelpers(client)
    const mock = new MockAdapter(client)
    mock.onGet(/\/api\/v1\/widgets\/layout/).reply((config) => {
      expect(config.headers?.Authorization).toBe(
        `Bearer ${IMPERSONATION_TOKEN}`,
      )
      return [200, []]
    })
    const res = await helpers.tenantGet<unknown[]>("/api/v1/widgets/layout")
    expect(res.status).toBe(200)
  })
})


describe("getImpersonationToken", () => {
  it("returns null when no token set", () => {
    setImpersonationToken(null)
    expect(getImpersonationToken()).toBeNull()
  })

  it("returns the access_token when set", () => {
    setImpersonationToken("xyz")
    expect(getImpersonationToken()).toBe("xyz")
    setImpersonationToken(null)
  })
})


describe("DualTokenError carries code", () => {
  it("error code is forbidden / missing / unsupported", async () => {
    const client = makeDualTokenClient()
    setPlatformToken(null)
    setImpersonationToken(null)

    let err: DualTokenError | null = null
    try {
      await client.post("/api/v1/orders", {})
    } catch (e) {
      err = e as DualTokenError
    }
    expect(err).not.toBeNull()
    // tenant_write_forbidden fires BEFORE token resolution.
    expect(err!.code).toBe("tenant_write_forbidden")
  })
})
