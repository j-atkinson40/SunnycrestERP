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
import HomePage from "@/pages/home/HomePage"


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


/**
 * ⚠️ WHAT A COMPONENT RENDERS, not what a route mounts.
 *
 * `elementTypeName` below reads the element a Route MOUNTS. That is the
 * right instrument for the R-1.6.9 invariant (RootRedirect must be absent
 * from the tree) and the WRONG instrument for "the runtime editor still
 * shows Pulse" — a Route mounting <HomePage /> keeps mounting <HomePage />
 * however HomePage's body is rewritten.
 *
 * That gap was live: session 5 of the note arc pointed /home at the daily
 * note, and the obvious way to do it was to swap HomePage's body. These
 * assertions would have stayed green while the runtime editor's root and
 * catch-all silently became the note surface. Green without contact —
 * CLAUDE.md §11 shape 9, in the one position that could have caught it.
 *
 * This helper shallow-invokes the component and reads what comes back, so
 * a body swap goes red.
 */
function rendersTypeName(Component: () => ReactElement | null): string {
  const out = Component()
  if (!isValidElement(out)) return "<no-element>"
  const t: unknown = out.type
  if (typeof t === "string") return t
  if (typeof t === "function") {
    const fn = t as { name?: string; displayName?: string }
    return fn.displayName || fn.name || "<anon-fn>"
  }
  if (typeof t === "object" && t !== null) {
    const obj = t as { displayName?: string; name?: string }
    return obj.displayName || obj.name || "<anon-obj>"
  }
  return "<unknown>"
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
      // ⚠️ And that HomePage still renders PULSE. The line above asserts
      // the mount; this asserts the surface. Without it, repointing
      // HomePage's body at another surface leaves this test green.
      expect(rendersTypeName(HomePage)).toBe("PulseSurface")
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
      expect(rendersTypeName(HomePage)).toBe("PulseSurface")
    })

    it("R-1.6.9 invariant — no NotFound anywhere when excludeRootRedirect=true", () => {
      const fragment = renderTenantSlugRoutes({ excludeRootRedirect: true })
      const allNotFounds = findRoutesByPath(fragment, () => true).filter(
        (r) => elementTypeName(r) === "NotFound",
      )
      expect(allNotFounds).toHaveLength(0)
    })
  })

  describe("R-2.x.1 — universal relative-paths invariant", () => {
    /**
     * R-2.x.1 — guards against absolute-path Route declarations
     * leaking into renderTenantSlugRoutes(). R-2.x converted ~100 of
     * ~203 paths; R-2.x.1 completed the conversion across the
     * remaining 102. Under the editor shell's nested <Routes> mount
     * (TenantRouteTree inside RuntimeEditorShell inside Studio Live),
     * absolute-path child routes don't match against the splat
     * remainder pathname — the catch-all wins, HomePage mounts in
     * place of the intended page. The invariant below fails loudly
     * if a future commit reintroduces an absolute path.
     *
     * The `index` route + `*` catch-all are excluded (no literal
     * leading-slash issue; both are RR v7 idiomatic).
     */
    function findAllRoutePaths(fragment: ReactElement): string[] {
      const paths: string[] = []
      function walk(node: unknown): void {
        if (!isValidElement(node)) return
        const props = node.props as {
          path?: unknown
          children?: unknown
        } | null
        const path = props?.path
        if (typeof path === "string") {
          paths.push(path)
        }
        const children = props?.children
        if (children) {
          Children.forEach(children, walk)
        }
      }
      Children.forEach(
        (fragment.props as { children?: unknown }).children,
        walk,
      )
      return paths
    }

    it("no Route inside renderTenantSlugRoutes uses an absolute path (default mode)", () => {
      const fragment = renderTenantSlugRoutes()
      const allPaths = findAllRoutePaths(fragment)
      const offenders = allPaths.filter((p) => p.startsWith("/"))
      expect(offenders).toEqual([])
      // Sanity: we did walk meaningful surface area.
      expect(allPaths.length).toBeGreaterThan(50)
    })

    it("no Route inside renderTenantSlugRoutes uses an absolute path (excludeRootRedirect mode)", () => {
      const fragment = renderTenantSlugRoutes({ excludeRootRedirect: true })
      const allPaths = findAllRoutePaths(fragment)
      const offenders = allPaths.filter((p) => p.startsWith("/"))
      expect(offenders).toEqual([])
      expect(allPaths.length).toBeGreaterThan(50)
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

  /**
   * THE FRONT DOOR — note arc session 5, 2026-09-10.
   *
   * /home serves the daily note. It is mounted DIRECTLY rather than via
   * <HomePage />, because HomePage is also the runtime editor's root and
   * catch-all element; routing both through one component would mean a
   * change to either surface silently moved the other.
   *
   * These assertions are about the SURFACE at each route, which is what
   * the two mounts differing is for.
   */
  describe("front door: /home is the note, /pulse is Pulse", () => {
    it("mounts <NotePage /> at `home` in the production tenant tree", () => {
      const fragment = renderTenantSlugRoutes()
      const homes = findRoutesByPath(fragment, (p) => p === "home")
      expect(homes).toHaveLength(1)
      expect(elementTypeName(homes[0])).toBe("NotePage")
    })

    it("keeps `note` pointing at the same surface (deferral records link there)", () => {
      const fragment = renderTenantSlugRoutes()
      const notes = findRoutesByPath(fragment, (p) => p === "note")
      expect(notes).toHaveLength(1)
      expect(elementTypeName(notes[0])).toBe("NotePage")
    })

    it("does NOT route `home` through HomePage — the runtime editor owns that", () => {
      const fragment = renderTenantSlugRoutes()
      const homes = findRoutesByPath(fragment, (p) => p === "home")
      expect(elementTypeName(homes[0])).not.toBe("HomePage")
    })

    it("keeps Pulse reachable at `pulse` until its code is removed", () => {
      const fragment = renderTenantSlugRoutes()
      const pulses = findRoutesByPath(fragment, (p) => p === "pulse")
      expect(pulses).toHaveLength(1)
      expect(elementTypeName(pulses[0])).toBe("HomePage")
      expect(rendersTypeName(HomePage)).toBe("PulseSurface")
    })
  })
})
