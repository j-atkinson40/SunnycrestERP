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
 * to swap RootRedirect + NotFound for the tenant home surface at both
 * root and `*` (HomePage until 2026-09-10, NotePage since).
 * TenantRouteTree passes the opt; production tenant boot path uses the
 * default (no opts) so RootRedirect continues to dispatch role-based
 * landing.
 *
 * R-2.x note: paths inside renderTenantSlugRoutes were converted from
 * absolute (`<Route path="/login">`) to relative (`<Route path="login">`)
 * + the two root routes became `<Route index>` (RR v7 idiom). The
 * R-1.6.9 invariant is preserved — the home surface still renders at the root
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


/*
 * ⚠️ `rendersTypeName` LIVED HERE AND WAS DELETED 2026-09-10, ON PURPOSE.
 *
 * It shallow-invoked a component and read what came back, because
 * `elementTypeName` below reads what a Route MOUNTS — and the runtime editor
 * mounted <HomePage />, a three-line wrapper whose body was the Pulse mount.
 * Asserting the mount stayed green through any body swap: CLAUDE.md §11 shape
 * 9, in the one position that could have caught the coupling. Measured at the
 * time: with the defect applied and the old assertions in place, 13 passed and
 * 0 failed.
 *
 * The helper is gone because the INDIRECTION is gone. Both slots now mount the
 * surface component directly, so `elementTypeName` reads the surface and there
 * is no wrapper left to swap. Removing what made the guard necessary is a
 * better fix than keeping a guard that passes — an absent field is not a hole.
 *
 * If a wrapper is ever reintroduced at either slot, the guard has to come back
 * with it. The rule it encoded: assert what renders, not what is mounted.
 */
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
    it("mounts <NotePage /> at the root index slot (NOT RootRedirect)", () => {
      const fragment = renderTenantSlugRoutes({ excludeRootRedirect: true })
      const indexRoutes = findIndexRoutes(fragment)
      expect(indexRoutes.length).toBeGreaterThan(0)
      const lastIndex = indexRoutes[indexRoutes.length - 1]
      // The mount IS the surface now — no wrapper in between.
      expect(elementTypeName(lastIndex)).toBe("NotePage")
      // R-1.6.9 regression guard: RootRedirect must NOT be in the tree
      // anywhere when excludeRootRedirect=true. Otherwise the runtime
      // editor would still trigger the absolute /home navigation.
      const allRootRedirects = findRoutesByPath(fragment, () => true).filter(
        (r) => elementTypeName(r) === "RootRedirect",
      )
      expect(allRootRedirects).toHaveLength(0)
    })

    it("mounts <NotePage /> at path='*' (NOT NotFound)", () => {
      const fragment = renderTenantSlugRoutes({ excludeRootRedirect: true })
      const catchAlls = findRoutesByPath(fragment, (p) => p === "*")
      expect(catchAlls.length).toBeGreaterThan(0)
      const lastCatch = catchAlls[catchAlls.length - 1]
      expect(elementTypeName(lastCatch)).toBe("NotePage")
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
     * remainder pathname — the catch-all wins, the home surface mounts
     * in place of the intended page. The invariant below fails loudly
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
   * /home serves the daily note, mounted directly. It went through
   * <HomePage /> for one session — which was also the runtime editor's
   * root and catch-all element, so a change to either surface would
   * silently have moved the other. Separating them is what made the
   * front-door move safe; HomePage is now deleted with Pulse and both
   * slots mount the surface directly.
   *
   * These assertions are about the SURFACE at each route.
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

    it("has NO `pulse` route — the holding address went with the code", () => {
      /* `/pulse` existed for exactly one session, so the front door could
       * move before the implementation was removed. Removal-last is
       * satisfied; the address has no surface behind it now. */
      const fragment = renderTenantSlugRoutes()
      expect(findRoutesByPath(fragment, (p) => p === "pulse")).toHaveLength(0)
    })

    it("routes `home` and the runtime-editor slots at the SAME surface", () => {
      /* They used to differ — /home was the note, the editor slots were
       * Pulse via HomePage. With Pulse gone both show what a tenant
       * operator actually lands on, and nothing sits in between. */
      const prod = renderTenantSlugRoutes()
      const rte = renderTenantSlugRoutes({ excludeRootRedirect: true })
      const home = findRoutesByPath(prod, (p) => p === "home")[0]
      const idx = findIndexRoutes(rte).slice(-1)[0]
      expect(elementTypeName(home)).toBe("NotePage")
      expect(elementTypeName(idx)).toBe("NotePage")
    })
  })
})
