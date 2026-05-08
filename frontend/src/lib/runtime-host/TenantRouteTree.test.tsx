/**
 * R-1.6.9 — regression guard for renderTenantSlugRoutes()
 * parameterization + TenantRouteTree's runtime-editor consumer.
 *
 * Pre-R-1.6.9, when TenantRouteTree mounted inside the runtime editor's
 * `/runtime-editor/*` parent route, the inner `<Routes>` matched the
 * relative empty path against `<Route path="/" element={<RootRedirect />} />`.
 * RootRedirect rendered `<Navigate to="/home" replace />`, an absolute
 * navigation that escaped the parent route and bounced the user to
 * `admin.<domain>/home` (empty AdminLayout chrome).
 *
 * Fix: parameterize `renderTenantSlugRoutes({ excludeRootRedirect: true })`
 * to swap RootRedirect + NotFound for HomePage at both root and `*`.
 * TenantRouteTree passes the opt; production tenant boot path uses the
 * default (no opts) so RootRedirect continues to dispatch role-based
 * landing.
 *
 * R-2.x note: paths inside renderTenantSlugRoutes were converted from
 * absolute (`<Route path="/login">`) to relative (`<Route path="login">`)
 * + the two root routes became `<Route index>` (RR v7 idiom). The
 * R-1.6.9 invariant is preserved — HomePage still renders at the root
 * slot when excludeRootRedirect=true, RootRedirect at the root slot
 * otherwise — but the path-string predicates below were updated to
 * match the new relative shape + index-route discriminator.
 *
 * These tests fail loudly if a future "let me clean this up" patch
 * removes the parameterization.
 */
import { Children, type ReactElement, isValidElement } from "react"
import { describe, expect, it } from "vitest"

import { renderTenantSlugRoutes } from "@/App"


/**
 * Helper: walk the JSX fragment returned by renderTenantSlugRoutes()
 * and return the array of `<Route>` definitions whose `path` prop
 * matches the supplied predicate. We don't actually mount the routes —
 * doing so would require a BrowserRouter + a full provider stack
 * (TenantProviders, AuthProvider, etc). We assert structurally on the
 * returned JSX, which is enough to catch parameterization regressions.
 */
function findRoutesByPath(
  fragment: ReactElement,
  predicate: (path: string) => boolean,
): ReactElement[] {
  const matches: ReactElement[] = []

  function walk(node: unknown): void {
    if (!isValidElement(node)) return
    const props = node.props as { path?: unknown; children?: unknown } | null
    const path = props?.path
    if (typeof path === "string" && predicate(path)) {
      matches.push(node as ReactElement)
    }
    const children = props?.children
    if (children) {
      Children.forEach(children, walk)
    }
  }

  Children.forEach((fragment.props as { children?: unknown }).children, walk)
  return matches
}


/**
 * R-2.x — find index routes (RR v7 idiom: `<Route index>` with no path).
 * Used to assert the root-slot semantics (formerly `<Route path="/">`)
 * after R-2.x converted the two root routes inside the
 * excludeRootRedirect ternary to index routes.
 */
function findIndexRoutes(fragment: ReactElement): ReactElement[] {
  const matches: ReactElement[] = []

  function walk(node: unknown): void {
    if (!isValidElement(node)) return
    const props = node.props as {
      index?: unknown
      path?: unknown
      children?: unknown
    } | null
    if (props?.index === true) {
      matches.push(node as ReactElement)
    }
    const children = props?.children
    if (children) {
      Children.forEach(children, walk)
    }
  }

  Children.forEach((fragment.props as { children?: unknown }).children, walk)
  return matches
}


function elementTypeName(el: ReactElement | undefined): string {
  if (!el) return "<undefined>"
  const elementProp = (el.props as { element?: unknown } | null)?.element
  if (!isValidElement(elementProp)) return "<no-element>"
  const t: unknown = elementProp.type
  if (typeof t === "string") return t
  if (typeof t === "function") {
    const fn = t as { name?: string; displayName?: string }
    return fn.displayName || fn.name || "<anon-fn>"
  }
  if (typeof t === "object" && t !== null) {
    const obj = t as { displayName?: string; name?: string }
    return obj.displayName || obj.name || "<anon-obj>"
  }
  return String(t)
}


describe("renderTenantSlugRoutes — R-1.6.9 parameterization", () => {
  describe("default (no opts) — production tenant operator flow", () => {
    it("mounts <RootRedirect /> at the root index slot", () => {
      const fragment = renderTenantSlugRoutes()
      const indexRoutes = findIndexRoutes(fragment)
      expect(indexRoutes.length).toBeGreaterThan(0)
      const lastIndex = indexRoutes[indexRoutes.length - 1]
      expect(elementTypeName(lastIndex)).toBe("RootRedirect")
    })

    it("mounts <NotFound /> at path='*'", () => {
      const fragment = renderTenantSlugRoutes()
      const catchAlls = findRoutesByPath(fragment, (p) => p === "*")
      expect(catchAlls.length).toBeGreaterThan(0)
      const lastCatch = catchAlls[catchAlls.length - 1]
      expect(elementTypeName(lastCatch)).toBe("NotFound")
    })
  })

  describe("excludeRootRedirect=true — runtime editor flow", () => {
    it("mounts <HomePage /> at the root index slot (NOT RootRedirect)", () => {
      const fragment = renderTenantSlugRoutes({ excludeRootRedirect: true })
      const indexRoutes = findIndexRoutes(fragment)
      expect(indexRoutes.length).toBeGreaterThan(0)
      const lastIndex = indexRoutes[indexRoutes.length - 1]
      expect(elementTypeName(lastIndex)).toBe("HomePage")
      // R-1.6.9 regression guard: RootRedirect must NOT be in the tree
      // anywhere when excludeRootRedirect=true. Otherwise the runtime
      // editor would still trigger the absolute /home navigation.
      const allRootRedirects = findRoutesByPath(fragment, () => true).filter(
        (r) => elementTypeName(r) === "RootRedirect",
      )
      expect(allRootRedirects).toHaveLength(0)
    })

    it("mounts <HomePage /> at path='*' (NOT NotFound)", () => {
      const fragment = renderTenantSlugRoutes({ excludeRootRedirect: true })
      const catchAlls = findRoutesByPath(fragment, (p) => p === "*")
      expect(catchAlls.length).toBeGreaterThan(0)
      const lastCatch = catchAlls[catchAlls.length - 1]
      expect(elementTypeName(lastCatch)).toBe("HomePage")
    })

    it("R-1.6.9 invariant — no NotFound anywhere when excludeRootRedirect=true", () => {
      const fragment = renderTenantSlugRoutes({ excludeRootRedirect: true })
      const allNotFounds = findRoutesByPath(fragment, () => true).filter(
        (r) => elementTypeName(r) === "NotFound",
      )
      expect(allNotFounds).toHaveLength(0)
    })
  })

  describe("default and runtime-editor branches share non-root routes", () => {
    it("both modes still register `login` (R-2.x: relative path)", () => {
      const defaultFragment = renderTenantSlugRoutes()
      const rteFragment = renderTenantSlugRoutes({
        excludeRootRedirect: true,
      })
      const defaultLogin = findRoutesByPath(
        defaultFragment,
        (p) => p === "login",
      )
      const rteLogin = findRoutesByPath(rteFragment, (p) => p === "login")
      expect(defaultLogin.length).toBeGreaterThan(0)
      expect(rteLogin.length).toBeGreaterThan(0)
    })

    it("both modes still register `calendar/actions/:token` (R-2.x: relative path)", () => {
      const defaultFragment = renderTenantSlugRoutes()
      const rteFragment = renderTenantSlugRoutes({
        excludeRootRedirect: true,
      })
      expect(
        findRoutesByPath(
          defaultFragment,
          (p) => p === "calendar/actions/:token",
        ),
      ).not.toHaveLength(0)
      expect(
        findRoutesByPath(
          rteFragment,
          (p) => p === "calendar/actions/:token",
        ),
      ).not.toHaveLength(0)
    })
  })
})
