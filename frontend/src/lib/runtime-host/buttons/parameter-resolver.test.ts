/**
 * R-4.0 — parameter-resolver vitest coverage.
 *
 * Pure-function resolver tests cover all 7 binding sources + missing
 * context fallbacks + multi-binding flat resolution + URL template
 * substitution.
 */
import { describe, it, expect } from "vitest"

import {
  resolveBinding,
  resolveBindings,
  substituteTemplate,
  type BindingContext,
} from "./parameter-resolver"


const baseCtx: BindingContext = {
  user: { id: "user-1", email: "u@example.com", role: "admin" },
  tenant: { id: "tenant-1", slug: "testco", vertical: "manufacturing" },
  nowMs: Date.UTC(2026, 4, 8, 12, 0, 0),
  routeParams: { id: "case-42", slug: "smith-john" },
  queryParams: new URLSearchParams("?focus=funeral-scheduling&date=2026-05-08"),
  currentFocusId: "funeral-scheduling",
}


describe("R-4.0 parameter-resolver", () => {
  describe("literal source", () => {
    it("returns the configured literal value (string)", () => {
      expect(
        resolveBinding(
          { name: "x", source: "literal", value: "hello" },
          baseCtx,
        ),
      ).toBe("hello")
    })
    it("returns the configured literal value (number)", () => {
      expect(
        resolveBinding(
          { name: "x", source: "literal", value: 42 },
          baseCtx,
        ),
      ).toBe(42)
    })
    it("returns null when literal value is undefined", () => {
      expect(
        resolveBinding({ name: "x", source: "literal" }, baseCtx),
      ).toBe(null)
    })
  })

  describe("current_user source", () => {
    it("defaults to user.id when userField unset", () => {
      expect(
        resolveBinding({ name: "u", source: "current_user" }, baseCtx),
      ).toBe("user-1")
    })
    it("returns user.email when userField=email", () => {
      expect(
        resolveBinding(
          { name: "u", source: "current_user", userField: "email" },
          baseCtx,
        ),
      ).toBe("u@example.com")
    })
    it("returns null when user is missing", () => {
      expect(
        resolveBinding(
          { name: "u", source: "current_user" },
          { ...baseCtx, user: null },
        ),
      ).toBe(null)
    })
  })

  describe("current_tenant source", () => {
    it("defaults to tenant.id", () => {
      expect(
        resolveBinding({ name: "t", source: "current_tenant" }, baseCtx),
      ).toBe("tenant-1")
    })
    it("returns slug when tenantField=slug", () => {
      expect(
        resolveBinding(
          { name: "t", source: "current_tenant", tenantField: "slug" },
          baseCtx,
        ),
      ).toBe("testco")
    })
    it("returns null when tenant is missing", () => {
      expect(
        resolveBinding(
          { name: "t", source: "current_tenant" },
          { ...baseCtx, tenant: null },
        ),
      ).toBe(null)
    })
  })

  describe("current_date source", () => {
    it("defaults to iso-date format YYYY-MM-DD", () => {
      expect(
        resolveBinding({ name: "d", source: "current_date" }, baseCtx),
      ).toBe("2026-05-08")
    })
    it("returns full ISO when format=iso", () => {
      expect(
        resolveBinding(
          { name: "d", source: "current_date", dateFormat: "iso" },
          baseCtx,
        ),
      ).toBe("2026-05-08T12:00:00.000Z")
    })
    it("returns epoch-ms when format=epoch-ms", () => {
      expect(
        resolveBinding(
          { name: "d", source: "current_date", dateFormat: "epoch-ms" },
          baseCtx,
        ),
      ).toBe(Date.UTC(2026, 4, 8, 12, 0, 0))
    })
  })

  describe("current_route_param source", () => {
    it("resolves a route param by name", () => {
      expect(
        resolveBinding(
          {
            name: "case_id",
            source: "current_route_param",
            paramName: "id",
          },
          baseCtx,
        ),
      ).toBe("case-42")
    })
    it("returns null when paramName missing from binding", () => {
      expect(
        resolveBinding(
          { name: "x", source: "current_route_param" },
          baseCtx,
        ),
      ).toBe(null)
    })
    it("returns null when route param absent", () => {
      expect(
        resolveBinding(
          {
            name: "x",
            source: "current_route_param",
            paramName: "missing",
          },
          baseCtx,
        ),
      ).toBe(null)
    })
  })

  describe("current_query_param source", () => {
    it("resolves a query param by name", () => {
      expect(
        resolveBinding(
          {
            name: "focus",
            source: "current_query_param",
            paramName: "focus",
          },
          baseCtx,
        ),
      ).toBe("funeral-scheduling")
    })
    it("returns null when query param absent", () => {
      expect(
        resolveBinding(
          {
            name: "missing",
            source: "current_query_param",
            paramName: "missing",
          },
          baseCtx,
        ),
      ).toBe(null)
    })
  })

  describe("current_focus_id source", () => {
    it("resolves from currentFocusId", () => {
      expect(
        resolveBinding(
          { name: "focus_id", source: "current_focus_id" },
          baseCtx,
        ),
      ).toBe("funeral-scheduling")
    })
    it("returns null when no focus is open", () => {
      expect(
        resolveBinding(
          { name: "focus_id", source: "current_focus_id" },
          { ...baseCtx, currentFocusId: null },
        ),
      ).toBe(null)
    })
  })

  describe("resolveBindings (multiple)", () => {
    it("produces a flat name→value object", () => {
      const out = resolveBindings(
        [
          { name: "user_id", source: "current_user" },
          {
            name: "tenant_slug",
            source: "current_tenant",
            tenantField: "slug",
          },
          { name: "fixed", source: "literal", value: "x" },
          {
            name: "case_id",
            source: "current_route_param",
            paramName: "id",
          },
        ],
        baseCtx,
      )
      expect(out).toEqual({
        user_id: "user-1",
        tenant_slug: "testco",
        fixed: "x",
        case_id: "case-42",
      })
    })
    it("skips bindings without a name", () => {
      const out = resolveBindings(
        [
          // @ts-expect-error — testing defensive skip
          { source: "literal", value: "x" },
          { name: "y", source: "literal", value: "y" },
        ],
        baseCtx,
      )
      expect(out).toEqual({ y: "y" })
    })
  })

  describe("substituteTemplate", () => {
    it("replaces single placeholder", () => {
      expect(substituteTemplate("/cases/{id}", { id: "42" })).toBe(
        "/cases/42",
      )
    })
    it("URL-encodes string values", () => {
      expect(
        substituteTemplate("/q/{q}", { q: "hello world" }),
      ).toBe("/q/hello%20world")
    })
    it("leaves placeholder literal when value is null", () => {
      expect(substituteTemplate("/x/{y}", { y: null })).toBe("/x/{y}")
    })
    it("multiple placeholders + mixed presence", () => {
      expect(
        substituteTemplate("/x/{a}/y/{b}/z/{c}", {
          a: "1",
          b: null,
          c: 2,
        }),
      ).toBe("/x/1/y/{b}/z/2")
    })
  })
})
