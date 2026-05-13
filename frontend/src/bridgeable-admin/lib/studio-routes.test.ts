/**
 * studio-routes.ts smoke tests — URL scheme + redirect translation.
 *
 * Studio 1a-i.A1. Validates:
 *   - studioPath() for the canonical URL shapes
 *   - parseStudioPath() round-trips
 *   - redirectFromStandalone() for the 10 standalone routes
 *   - reserved-slug guards
 *   - localStorage helpers
 */
import { afterEach, beforeEach, describe, expect, it } from "vitest"
import {
  assertSafeVerticalSlug,
  computeInitialRailExpanded,
  disambiguateStudioLive,
  extractStudioLiveDeepTail,
  isOverviewRoute,
  isReservedSlug,
  isStudioEditorKey,
  parseStudioPath,
  PLATFORM_ONLY_EDITORS,
  readLastVertical,
  readRailExpanded,
  redirectFromStandalone,
  RESERVED_FIRST_SEGMENTS,
  STANDALONE_TO_STUDIO_PATH,
  studioLivePath,
  studioPath,
  STUDIO_EDITOR_KEYS,
  toggleMode,
  writeLastVertical,
  writeRailExpanded,
} from "./studio-routes"


describe("studioPath", () => {
  it("renders Platform overview for empty args", () => {
    expect(studioPath({})).toBe("/studio")
  })

  it("renders vertical overview", () => {
    expect(studioPath({ vertical: "manufacturing" })).toBe(
      "/studio/manufacturing",
    )
  })

  it("renders Platform-scope editor", () => {
    expect(studioPath({ editor: "themes" })).toBe("/studio/themes")
  })

  it("renders vertical-scope editor", () => {
    expect(studioPath({ vertical: "manufacturing", editor: "focuses" })).toBe(
      "/studio/manufacturing/focuses",
    )
  })

  it("drops vertical for platform-only editors", () => {
    expect(studioPath({ vertical: "manufacturing", editor: "classes" })).toBe(
      "/studio/classes",
    )
    expect(studioPath({ vertical: "manufacturing", editor: "registry" })).toBe(
      "/studio/registry",
    )
    expect(
      studioPath({ vertical: "funeral_home", editor: "plugin-registry" }),
    ).toBe("/studio/plugin-registry")
  })

  it("appends query params", () => {
    expect(
      studioPath({
        vertical: "manufacturing",
        editor: "focuses",
        query: { template: "scheduling", category: "decision" },
      }),
    ).toBe("/studio/manufacturing/focuses?template=scheduling&category=decision")
  })

  it("skips null / undefined / empty query values", () => {
    expect(
      studioPath({
        editor: "themes",
        query: { a: "1", b: null, c: undefined, d: "" },
      }),
    ).toBe("/studio/themes?a=1")
  })
})


describe("studioLivePath", () => {
  it("renders /studio/live with no vertical", () => {
    expect(studioLivePath()).toBe("/studio/live")
  })

  it("renders /studio/live/:vertical", () => {
    expect(studioLivePath({ vertical: "funeral_home" })).toBe(
      "/studio/live/funeral_home",
    )
  })

  it("preserves query params", () => {
    expect(
      studioLivePath({
        vertical: "manufacturing",
        query: { tenant: "testco", user: "u1" },
      }),
    ).toBe("/studio/live/manufacturing?tenant=testco&user=u1")
  })
})


describe("parseStudioPath", () => {
  it("parses Platform overview", () => {
    expect(parseStudioPath("/studio")).toEqual({
      isLive: false,
      vertical: null,
      editor: null,
      malformed: false,
    })
  })

  it("parses vertical overview", () => {
    expect(parseStudioPath("/studio/manufacturing")).toEqual({
      isLive: false,
      vertical: "manufacturing",
      editor: null,
      malformed: false,
    })
  })

  it("parses Platform-scope editor", () => {
    expect(parseStudioPath("/studio/themes")).toEqual({
      isLive: false,
      vertical: null,
      editor: "themes",
      malformed: false,
    })
  })

  it("parses vertical-scope editor", () => {
    expect(parseStudioPath("/studio/manufacturing/focuses")).toEqual({
      isLive: false,
      vertical: "manufacturing",
      editor: "focuses",
      malformed: false,
    })
  })

  it("parses live mode (no vertical)", () => {
    expect(parseStudioPath("/studio/live")).toEqual({
      isLive: true,
      vertical: null,
      editor: null,
      malformed: false,
    })
  })

  it("parses live mode (vertical pre-filter)", () => {
    expect(parseStudioPath("/studio/live/funeral_home")).toEqual({
      isLive: true,
      vertical: "funeral_home",
      editor: null,
      malformed: false,
    })
  })

  it("flags unknown second-segment as malformed", () => {
    expect(parseStudioPath("/studio/manufacturing/not-an-editor")).toEqual({
      isLive: false,
      vertical: "manufacturing",
      editor: null,
      malformed: true,
    })
  })

  it("tolerates trailing slashes", () => {
    expect(parseStudioPath("/studio/manufacturing/")).toEqual({
      isLive: false,
      vertical: "manufacturing",
      editor: null,
      malformed: false,
    })
  })
})


describe("redirectFromStandalone — 10-route translation table", () => {
  const cases: Array<[string, string, string]> = [
    ["/visual-editor", "", "/studio"],
    ["/visual-editor/themes", "", "/studio/themes"],
    [
      "/visual-editor/focuses",
      "focus_type=scheduling&template_id=funeral-scheduling",
      "/studio/focuses?category=scheduling&template=funeral-scheduling",
    ],
    [
      "/visual-editor/widgets",
      "mode=class",
      "/studio/widgets?mode=class",
    ],
    [
      "/visual-editor/documents",
      "template_id=invoice-default",
      "/studio/documents?template=invoice-default",
    ],
    ["/visual-editor/classes", "", "/studio/classes"],
    [
      "/visual-editor/workflows",
      "workflow_type=cash_receipts",
      "/studio/workflows?workflow_type=cash_receipts",
    ],
    ["/visual-editor/edge-panels", "", "/studio/edge-panels"],
    ["/visual-editor/registry", "", "/studio/registry"],
    ["/visual-editor/plugin-registry", "", "/studio/plugin-registry"],
    ["/runtime-editor", "tenant=testco&user=u1", "/studio/live?tenant=testco&user=u1"],
  ]
  for (const [pathname, search, expected] of cases) {
    it(`${pathname}?${search} → ${expected}`, () => {
      expect(redirectFromStandalone(pathname, search)).toBe(expected)
    })
  }

  it("preserves query string for paths without per-editor translation", () => {
    expect(
      redirectFromStandalone("/visual-editor/themes", "scope=tenant&token=accent"),
    ).toBe("/studio/themes?scope=tenant&token=accent")
  })

  it("splices in lastVertical for vertical-aware editors", () => {
    expect(
      redirectFromStandalone("/visual-editor/themes", "", {
        lastVertical: "manufacturing",
      }),
    ).toBe("/studio/manufacturing/themes")
  })

  it("does NOT splice lastVertical for platform-only editors", () => {
    expect(
      redirectFromStandalone("/visual-editor/classes", "", {
        lastVertical: "manufacturing",
      }),
    ).toBe("/studio/classes")
    expect(
      redirectFromStandalone("/visual-editor/registry", "", {
        lastVertical: "manufacturing",
      }),
    ).toBe("/studio/registry")
  })

  it("falls back to /studio for unknown paths", () => {
    expect(redirectFromStandalone("/visual-editor/unknown", "")).toBe("/studio")
  })

  it("tolerates trailing slash", () => {
    expect(redirectFromStandalone("/visual-editor/", "")).toBe("/studio")
  })
})


describe("translation table coverage", () => {
  it("covers all 9 visual-editor pages + runtime-editor + visual-editor index", () => {
    // 9 editor URLs + /visual-editor index + /runtime-editor = 11 entries.
    expect(Object.keys(STANDALONE_TO_STUDIO_PATH)).toHaveLength(11)
  })

  it("translation table covers every editor key", () => {
    for (const key of STUDIO_EDITOR_KEYS) {
      expect(STANDALONE_TO_STUDIO_PATH[`/visual-editor/${key}`]).toBe(
        `/studio/${key}`,
      )
    }
  })
})


describe("reserved-slug guard", () => {
  it("rejects editor keys as vertical slugs", () => {
    for (const editor of STUDIO_EDITOR_KEYS) {
      expect(() => assertSafeVerticalSlug(editor)).toThrow(
        /collides with reserved Studio path segment/,
      )
    }
  })

  it("rejects 'live' and 'admin'", () => {
    expect(() => assertSafeVerticalSlug("live")).toThrow()
    expect(() => assertSafeVerticalSlug("admin")).toThrow()
  })

  it("accepts canonical vertical slugs", () => {
    expect(() => assertSafeVerticalSlug("manufacturing")).not.toThrow()
    expect(() => assertSafeVerticalSlug("funeral_home")).not.toThrow()
    expect(() => assertSafeVerticalSlug("cemetery")).not.toThrow()
    expect(() => assertSafeVerticalSlug("crematory")).not.toThrow()
  })

  it("accepts hypothetical future slugs that don't collide", () => {
    expect(() => assertSafeVerticalSlug("wastewater")).not.toThrow()
    expect(() => assertSafeVerticalSlug("paving")).not.toThrow()
    expect(() => assertSafeVerticalSlug("vet")).not.toThrow()
  })

  it("isReservedSlug agrees with the guard", () => {
    expect(isReservedSlug("themes")).toBe(true)
    expect(isReservedSlug("live")).toBe(true)
    expect(isReservedSlug("manufacturing")).toBe(false)
  })

  it("RESERVED_FIRST_SEGMENTS contains every editor + live + admin", () => {
    expect(RESERVED_FIRST_SEGMENTS.has("live")).toBe(true)
    expect(RESERVED_FIRST_SEGMENTS.has("admin")).toBe(true)
    for (const editor of STUDIO_EDITOR_KEYS) {
      expect(RESERVED_FIRST_SEGMENTS.has(editor)).toBe(true)
    }
  })

  it("PLATFORM_ONLY_EDITORS includes the 3 platform-only editors", () => {
    expect(PLATFORM_ONLY_EDITORS.has("classes")).toBe(true)
    expect(PLATFORM_ONLY_EDITORS.has("registry")).toBe(true)
    expect(PLATFORM_ONLY_EDITORS.has("plugin-registry")).toBe(true)
    expect(PLATFORM_ONLY_EDITORS.has("themes")).toBe(false)
  })

  it("isStudioEditorKey type guard", () => {
    expect(isStudioEditorKey("themes")).toBe(true)
    expect(isStudioEditorKey("not-a-key")).toBe(false)
  })
})


describe("toggleMode — Edit ↔ Live translation (5 canonical rules)", () => {
  it("Edit + Platform → Live (no vertical)", () => {
    expect(toggleMode("/studio/themes", "")).toBe("/studio/live")
  })

  it("Edit + vertical → Live + vertical", () => {
    expect(toggleMode("/studio/wastewater/themes", "")).toBe(
      "/studio/live/wastewater",
    )
  })

  it("Live + vertical + tenant params → Edit + vertical (drops tenant params)", () => {
    expect(
      toggleMode(
        "/studio/live/wastewater",
        "?tenant=testco&user=u1",
      ),
    ).toBe("/studio/wastewater")
  })

  it("Live + Platform → Edit + Platform (no trailing slash)", () => {
    expect(toggleMode("/studio/live", "")).toBe("/studio")
  })

  it("Live + vertical (no tenant params) → Edit + vertical", () => {
    expect(toggleMode("/studio/live/wastewater", "")).toBe("/studio/wastewater")
  })

  it("edge case — Edit overview (no editor) Platform → Live Platform", () => {
    expect(toggleMode("/studio", "")).toBe("/studio/live")
  })

  it("edge case — Edit overview + vertical → Live + vertical", () => {
    expect(toggleMode("/studio/manufacturing", "")).toBe(
      "/studio/live/manufacturing",
    )
  })

  it("tolerates /bridgeable-admin path prefix", () => {
    expect(toggleMode("/bridgeable-admin/studio/themes", "")).toBe("/studio/live")
    expect(toggleMode("/bridgeable-admin/studio/live", "")).toBe("/studio")
  })
})


describe("localStorage helpers", () => {
  beforeEach(() => {
    window.localStorage.clear()
  })
  afterEach(() => {
    window.localStorage.clear()
  })

  it("readRailExpanded defaults to true when unset", () => {
    expect(readRailExpanded()).toBe(true)
  })

  it("readRailExpanded honors stored value", () => {
    writeRailExpanded(false)
    expect(readRailExpanded()).toBe(false)
    writeRailExpanded(true)
    expect(readRailExpanded()).toBe(true)
  })

  it("readLastVertical defaults to null when unset", () => {
    expect(readLastVertical()).toBe(null)
  })

  it("writeLastVertical persists + readLastVertical retrieves", () => {
    writeLastVertical("manufacturing")
    expect(readLastVertical()).toBe("manufacturing")
  })

  it("writeLastVertical(null) clears", () => {
    writeLastVertical("manufacturing")
    writeLastVertical(null)
    expect(readLastVertical()).toBe(null)
  })
})


describe("isOverviewRoute — Studio 1a-i.B follow-up", () => {
  it("platform overview /studio is overview", () => {
    expect(isOverviewRoute("/studio")).toBe(true)
  })

  it("vertical overview /studio/:vertical is overview", () => {
    expect(isOverviewRoute("/studio/manufacturing")).toBe(true)
    expect(isOverviewRoute("/studio/funeral_home")).toBe(true)
  })

  it("platform-scope editor /studio/:editor is NOT overview", () => {
    expect(isOverviewRoute("/studio/themes")).toBe(false)
    expect(isOverviewRoute("/studio/widgets")).toBe(false)
    expect(isOverviewRoute("/studio/edge-panels")).toBe(false)
  })

  it("vertical-scope editor /studio/:vertical/:editor is NOT overview", () => {
    expect(isOverviewRoute("/studio/manufacturing/themes")).toBe(false)
    expect(isOverviewRoute("/studio/funeral_home/focuses")).toBe(false)
  })

  it("Live mode /studio/live[/:vertical] is NOT overview", () => {
    expect(isOverviewRoute("/studio/live")).toBe(false)
    expect(isOverviewRoute("/studio/live/manufacturing")).toBe(false)
  })

  it("/studio/admin is treated as non-overview (reserved future area)", () => {
    expect(isOverviewRoute("/studio/admin")).toBe(false)
    expect(isOverviewRoute("/studio/admin/anything")).toBe(false)
  })

  it("tolerates /bridgeable-admin prefix", () => {
    expect(isOverviewRoute("/bridgeable-admin/studio")).toBe(true)
    expect(isOverviewRoute("/bridgeable-admin/studio/manufacturing")).toBe(true)
    expect(isOverviewRoute("/bridgeable-admin/studio/themes")).toBe(false)
    expect(isOverviewRoute("/bridgeable-admin/studio/live")).toBe(false)
  })

  it("non-Studio routes return false", () => {
    expect(isOverviewRoute("/")).toBe(false)
    expect(isOverviewRoute("/bridgeable-admin")).toBe(false)
    expect(isOverviewRoute("/bridgeable-admin/tenants")).toBe(false)
    expect(isOverviewRoute("/runtime-editor")).toBe(false)
    expect(isOverviewRoute("/visual-editor/themes")).toBe(false)
  })

  it("tolerates trailing slash", () => {
    expect(isOverviewRoute("/studio/")).toBe(true)
    expect(isOverviewRoute("/studio/manufacturing/")).toBe(true)
    expect(isOverviewRoute("/studio/themes/")).toBe(false)
  })
})


describe("computeInitialRailExpanded — Studio 1a-i.B follow-up", () => {
  it("returns true on overview routes", () => {
    expect(computeInitialRailExpanded("/studio")).toBe(true)
    expect(computeInitialRailExpanded("/studio/manufacturing")).toBe(true)
    expect(computeInitialRailExpanded("/bridgeable-admin/studio/funeral_home")).toBe(true)
  })

  it("returns false on editor routes", () => {
    expect(computeInitialRailExpanded("/studio/themes")).toBe(false)
    expect(computeInitialRailExpanded("/studio/manufacturing/themes")).toBe(false)
  })

  it("returns false on Live mode routes", () => {
    expect(computeInitialRailExpanded("/studio/live")).toBe(false)
    expect(computeInitialRailExpanded("/studio/live/funeral_home")).toBe(false)
  })

  it("returns false outside Studio", () => {
    expect(computeInitialRailExpanded("/")).toBe(false)
    expect(computeInitialRailExpanded("/bridgeable-admin")).toBe(false)
  })
})


describe("redirectFromStandalone — deep-path runtime-editor preservation (Studio 1a-i.B follow-up #3)", () => {
  it("/runtime-editor/dispatch/funeral-schedule preserves tail", () => {
    expect(
      redirectFromStandalone(
        "/runtime-editor/dispatch/funeral-schedule",
        "tenant=X&user=Y",
      ),
    ).toBe("/studio/live/dispatch/funeral-schedule?tenant=X&user=Y")
  })

  it("/runtime-editor/home preserves single-segment tail", () => {
    expect(
      redirectFromStandalone("/runtime-editor/home", "tenant=X&user=Y"),
    ).toBe("/studio/live/home?tenant=X&user=Y")
  })

  it("/bridgeable-admin/runtime-editor/dashboard preserves admin prefix + tail", () => {
    expect(
      redirectFromStandalone(
        "/bridgeable-admin/runtime-editor/dashboard",
        "tenant=X&user=Y",
      ),
    ).toBe("/bridgeable-admin/studio/live/dashboard?tenant=X&user=Y")
  })

  it("bare /runtime-editor still maps via legacy STANDALONE_TO_STUDIO_PATH", () => {
    expect(
      redirectFromStandalone("/runtime-editor", "tenant=X&user=Y"),
    ).toBe("/studio/live?tenant=X&user=Y")
  })

  it("/runtime-editor/ (trailing slash) still maps via legacy STANDALONE_TO_STUDIO_PATH", () => {
    // Trailing slash is stripped before lookup → matches `/runtime-editor`.
    expect(redirectFromStandalone("/runtime-editor/", "")).toBe("/studio/live")
  })

  it("deep tail preserves multi-segment paths", () => {
    expect(
      redirectFromStandalone(
        "/runtime-editor/cases/abc-123",
        "tenant=X&user=Y",
      ),
    ).toBe("/studio/live/cases/abc-123?tenant=X&user=Y")
  })

  it("deep tail with no query string", () => {
    expect(
      redirectFromStandalone("/runtime-editor/dispatch/funeral-schedule", ""),
    ).toBe("/studio/live/dispatch/funeral-schedule")
  })

  it("deep tail does NOT insert vertical (per locked decision 1)", () => {
    // Even if `lastVertical` is supplied, deep-path runtime-editor
    // redirects do NOT splice in a vertical — the URL stays honest
    // until impersonation resolves the vertical (pickup-and-replay
    // closes the gap).
    expect(
      redirectFromStandalone("/runtime-editor/dispatch/funeral-schedule", "", {
        lastVertical: "manufacturing",
      }),
    ).toBe("/studio/live/dispatch/funeral-schedule")
  })
})


describe("extractStudioLiveDeepTail — Studio 1a-i.B follow-up #3", () => {
  it("returns empty string for bare /studio/live", () => {
    expect(extractStudioLiveDeepTail("/studio/live")).toBe("")
  })

  it("returns single-segment tail when no resolved vertical", () => {
    expect(extractStudioLiveDeepTail("/studio/live/manufacturing")).toBe(
      "manufacturing",
    )
  })

  it("returns full tail when no resolved vertical (multi-segment)", () => {
    expect(
      extractStudioLiveDeepTail("/studio/live/dispatch/funeral-schedule"),
    ).toBe("dispatch/funeral-schedule")
  })

  it("strips matching vertical when resolved", () => {
    expect(
      extractStudioLiveDeepTail(
        "/studio/live/manufacturing/dispatch/funeral-schedule",
        "manufacturing",
      ),
    ).toBe("dispatch/funeral-schedule")
  })

  it("keeps non-matching first segment as part of tail", () => {
    // Defense-in-depth: if the caller's resolvedVertical doesn't match
    // the URL's first post-`live` segment, treat the segment as tail.
    expect(
      extractStudioLiveDeepTail(
        "/studio/live/dispatch/funeral-schedule",
        "manufacturing",
      ),
    ).toBe("dispatch/funeral-schedule")
  })

  it("tolerates /bridgeable-admin prefix", () => {
    expect(
      extractStudioLiveDeepTail(
        "/bridgeable-admin/studio/live/dispatch/funeral-schedule",
      ),
    ).toBe("dispatch/funeral-schedule")
  })

  it("returns empty string for non-Studio-live URLs", () => {
    expect(extractStudioLiveDeepTail("/studio/themes")).toBe("")
    expect(extractStudioLiveDeepTail("/studio")).toBe("")
    expect(extractStudioLiveDeepTail("/dashboard")).toBe("")
  })

  it("tolerates trailing slash", () => {
    expect(
      extractStudioLiveDeepTail("/studio/live/dispatch/funeral-schedule/"),
    ).toBe("dispatch/funeral-schedule")
  })
})


describe("disambiguateStudioLive — Studio 1a-i.B follow-up #4", () => {
  const KNOWN: readonly string[] = [
    "manufacturing",
    "funeral_home",
    "cemetery",
    "crematory",
  ]

  it("bare /studio/live → vertical=null, tail=''", () => {
    expect(disambiguateStudioLive("/studio/live", KNOWN)).toEqual({
      vertical: null,
      tail: "",
    })
  })

  it("known vertical alone → vertical=slug, tail=''", () => {
    expect(disambiguateStudioLive("/studio/live/manufacturing", KNOWN)).toEqual(
      { vertical: "manufacturing", tail: "" },
    )
  })

  it("known vertical + single tail segment → vertical=slug, tail=segment", () => {
    expect(
      disambiguateStudioLive("/studio/live/manufacturing/dashboard", KNOWN),
    ).toEqual({ vertical: "manufacturing", tail: "dashboard" })
  })

  it("known vertical + multi-segment tail → vertical=slug, full tail", () => {
    expect(
      disambiguateStudioLive(
        "/studio/live/manufacturing/dispatch/funeral-schedule",
        KNOWN,
      ),
    ).toEqual({
      vertical: "manufacturing",
      tail: "dispatch/funeral-schedule",
    })
  })

  it("unknown first segment + tail → vertical=null, full content is tail (canonical follow-up #4 bug fix)", () => {
    expect(
      disambiguateStudioLive("/studio/live/dispatch/funeral-schedule", KNOWN),
    ).toEqual({ vertical: null, tail: "dispatch/funeral-schedule" })
  })

  it("single unknown segment → vertical=null, tail=segment", () => {
    expect(disambiguateStudioLive("/studio/live/dispatch", KNOWN)).toEqual({
      vertical: null,
      tail: "dispatch",
    })
  })

  it("tolerates /bridgeable-admin prefix", () => {
    expect(
      disambiguateStudioLive(
        "/bridgeable-admin/studio/live/manufacturing/dashboard",
        KNOWN,
      ),
    ).toEqual({ vertical: "manufacturing", tail: "dashboard" })
    expect(
      disambiguateStudioLive(
        "/bridgeable-admin/studio/live/dispatch/funeral-schedule",
        KNOWN,
      ),
    ).toEqual({ vertical: null, tail: "dispatch/funeral-schedule" })
  })

  it("tolerates trailing slash", () => {
    expect(
      disambiguateStudioLive("/studio/live/manufacturing/", KNOWN),
    ).toEqual({ vertical: "manufacturing", tail: "" })
  })

  it("non-Studio-live URL → vertical=null, tail=''", () => {
    expect(disambiguateStudioLive("/studio", KNOWN)).toEqual({
      vertical: null,
      tail: "",
    })
    expect(disambiguateStudioLive("/studio/themes", KNOWN)).toEqual({
      vertical: null,
      tail: "",
    })
    expect(disambiguateStudioLive("/dashboard", KNOWN)).toEqual({
      vertical: null,
      tail: "",
    })
  })

  it("empty knownVerticals list → every segment becomes tail", () => {
    // Fail-soft mode: if verticals fetch failed, the hook reports an
    // empty list. Wrap still mounts; every segment is treated as tail
    // (vertical resolution falls to the picker at impersonation time).
    expect(
      disambiguateStudioLive("/studio/live/manufacturing/dashboard", []),
    ).toEqual({ vertical: null, tail: "manufacturing/dashboard" })
  })
})
