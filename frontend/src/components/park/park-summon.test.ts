/**
 * Park summon bridge (S-5) — the (b) palette-stays-open contract.
 *
 * RULED (b): summoning a park tablet from the command bar keeps the
 * palette OPEN so the user can chain the next summon (assemble a working
 * set in one burst). `planParkSummon` is the pure dispatch seam CommandBar
 * consumes; its `keepPaletteOpen: true` is the invariant that would break
 * if someone re-added an onClose to the summon path (CommandBar itself
 * isn't render-unit-testable). Also pins the summon bridge routing.
 */

import { describe, expect, it, vi } from "vitest"

import {
  _setParkSummon,
  planParkSummon,
  summonParkAct,
} from "./park-summon"

describe("planParkSummon — (b) palette stays open", () => {
  it("plans a park summon that keeps the palette OPEN", () => {
    expect(planParkSummon("park:summon:reply-dm")).toEqual({
      actType: "reply-dm",
      keepPaletteOpen: true,
    })
    expect(planParkSummon("park:summon:add-note")).toEqual({
      actType: "add-note",
      keepPaletteOpen: true,
    })
    expect(planParkSummon("park:summon:start-quote")).toEqual({
      actType: "start-quote",
      keepPaletteOpen: true,
    })
  })

  it("returns null for non-park handlers (they close/route normally)", () => {
    expect(planParkSummon("create.quote")).toBeNull()
    expect(planParkSummon("nav:home")).toBeNull()
    expect(planParkSummon(undefined)).toBeNull()
    expect(planParkSummon(() => {})).toBeNull()
  })
})

describe("summonParkAct — the ParkProvider bridge", () => {
  it("routes to the published summon fn; no-op when park is unmounted", () => {
    _setParkSummon(null)
    expect(summonParkAct("reply-dm")).toBeNull()

    const fn = vi.fn().mockReturnValue("pt1")
    _setParkSummon(fn)
    expect(summonParkAct("reply-dm")).toBe("pt1")
    expect(fn).toHaveBeenCalledWith("reply-dm")

    _setParkSummon(null) // cleanup
  })
})
