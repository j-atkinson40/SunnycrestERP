/**
 * The sphere — geometry, the four states, and the canon that quiet does not glow.
 *
 * Three kinds of check, kept apart on purpose:
 *   1. the arithmetic, as pure functions against stated viewports
 *   2. the DOM, for the only things a DOM can show here (layers, state, open)
 *   3. the STYLESHEET, read as a file, for the no-glow rule — because jsdom
 *      does not load the app's CSS, so no computed style could ever prove it
 */
import { readFileSync } from "node:fs"
import { resolve } from "node:path"

import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { Sphere } from "./Sphere"
import {
  clampY,
  edgeX,
  isDrag,
  snapSide,
  specTarget,
  SPHERE_GUTTER,
  SPHERE_SIZE,
} from "./sphere-geometry"

describe("the geometry", () => {
  it("snaps to the NEARER edge, measured from the sphere's centre", () => {
    // Viewport 1000: the centre line is 500, so the sphere's centre crosses it
    // when its left passes 500 - 28 = 472.
    expect(snapSide(471, 1000)).toBe("left")
    expect(snapSide(472, 1000)).toBe("right")
    // Far sides, for the obvious cases.
    expect(snapSide(0, 1000)).toBe("left")
    expect(snapSide(944, 1000)).toBe("right")
  })

  it("rests a gutter in from whichever edge it chose", () => {
    expect(edgeX("left", 1000)).toBe(SPHERE_GUTTER)
    expect(edgeX("right", 1000)).toBe(1000 - SPHERE_GUTTER - SPHERE_SIZE)
    expect(edgeX("right", 1000)).toBe(928)
  })

  it("keeps its vertical FRACTION, clamped inside the gutter", () => {
    // 0.72 of 800 = 576, comfortably inside, so it is kept exactly.
    expect(clampY(0.72, 800)).toBe(576)
    // Above the top gutter and below the bottom one, both clamped.
    expect(clampY(0, 800)).toBe(SPHERE_GUTTER)
    expect(clampY(1, 800)).toBe(800 - SPHERE_GUTTER - SPHERE_SIZE - 8)
  })

  it("⚠️ leaves 8px MORE room at the bottom than the top, for the shadow", () => {
    const top = clampY(0, 800)
    const bottom = clampY(1, 800)
    expect(800 - bottom - SPHERE_SIZE - top).toBe(8)
  })

  it("survives a viewport smaller than the sphere without inverting", () => {
    // clampv's second bound is itself clamped against the first, so a
    // viewport narrower than the gutters cannot produce a NaN or a negative
    // range — it pins to the gutter instead.
    expect(clampY(0.5, 40)).toBe(SPHERE_GUTTER)
    expect(Number.isFinite(edgeX("right", 10))).toBe(true)
  })

  it("treats 5px as still a click and anything past it as a drag", () => {
    expect(isDrag(5, 0)).toBe(false)
    expect(isDrag(0, 5)).toBe(false)
    expect(isDrag(6, 0)).toBe(true)
    expect(isDrag(4, 4)).toBe(true) // hypot ≈ 5.66
    expect(isDrag(3, 4)).toBe(false) // hypot exactly 5
  })

  it("aims the highlight toward the pointer, saturating with distance", () => {
    const near = specTarget(10, 0)
    const far = specTarget(1000, 0)
    expect(far.x).toBeGreaterThan(near.x)
    // Saturates: beyond 260px the factor is 1, so x stops growing.
    expect(specTarget(260, 0).x).toBeCloseTo(specTarget(10_000, 0).x, 5)
    // A pointer exactly on the centre must not divide by zero.
    expect(Number.isFinite(specTarget(0, 0).x)).toBe(true)
  })
})

describe("the DOM", () => {
  it("renders the six layers, in paint order", () => {
    render(<Sphere state="quiet" onOpen={() => {}} />)
    const el = screen.getByTestId("opas-sphere")
    expect([...el.children].map((c) => c.className)).toEqual([
      "halo", "ball", "tint", "inner", "spec", "rim",
    ])
  })

  it("carries its state as an attribute, which is what the stylesheet keys on", () => {
    const { rerender } = render(<Sphere state="quiet" onOpen={() => {}} />)
    expect(screen.getByTestId("opas-sphere").getAttribute("data-state")).toBe("quiet")
    rerender(<Sphere state="needs" onOpen={() => {}} />)
    expect(screen.getByTestId("opas-sphere").getAttribute("data-state")).toBe("needs")
  })

  it("opens on a click", async () => {
    const onOpen = vi.fn()
    render(<Sphere state="quiet" onOpen={onOpen} />)
    await userEvent.click(screen.getByTestId("opas-sphere"))
    expect(onOpen).toHaveBeenCalledTimes(1)
  })

  it("⚠️ opens ONCE on a mouse click, not twice", async () => {
    // A mouse click fires pointerup AND click. `end` opens on pointerup and
    // the onClick handler is guarded on `detail === 0`, which is only true for
    // keyboard activation. Without that guard this is 2.
    const onOpen = vi.fn()
    render(<Sphere state="quiet" onOpen={onOpen} />)
    await userEvent.click(screen.getByTestId("opas-sphere"))
    expect(onOpen).toHaveBeenCalledTimes(1)
  })

  it("steps out of the way when Opas is open, without unmounting", () => {
    render(<Sphere state="quiet" onOpen={() => {}} hidden />)
    expect(screen.getByTestId("opas-sphere").getAttribute("data-hidden")).toBe("true")
  })

  it("renders no hint shortcut when none is given, and the given one when it is", () => {
    const { rerender } = render(<Sphere state="quiet" onOpen={() => {}} />)
    expect(screen.getByTestId("opas-sphere-hint").querySelector("kbd")).toBeNull()
    rerender(<Sphere state="quiet" onOpen={() => {}} shortcut="⌘K" />)
    expect(screen.getByTestId("opas-sphere-hint").querySelector("kbd")?.textContent).toBe("⌘K")
  })
})

describe("⚠️ the canon: quiet does not glow", () => {
  const css = readFileSync(
    resolve(process.cwd(), "src/styles/opas-sphere.css"),
    "utf8",
  )

  it("read the stylesheet it claims to read", () => {
    // The positive control. A path typo would otherwise make every assertion
    // below pass against an empty string.
    expect(css.length).toBeGreaterThan(2_000)
    expect(css).toContain(".opas-sphere .halo")
  })

  it("gives the halo opacity 0 by default", () => {
    const halo = css.slice(css.indexOf(".opas-sphere .halo"))
    expect(halo.slice(0, halo.indexOf("}"))).toContain("opacity: 0")
  })

  it("has NO rule that lights the halo for quiet", () => {
    // Stated as an absence, so it needs the control above AND the control
    // below: the three other states must have such a rule, or "no rule for
    // quiet" would be true of a stylesheet with no state rules at all.
    expect(css).not.toContain('[data-state="quiet"]')
    for (const state of ["suggest", "needs", "working"]) {
      expect(css).toContain(`.opas-sphere[data-state="${state}"] .halo`)
    }
  })

  it("matches the prototype's four glow colours exactly", () => {
    expect(css).toContain('[data-state="suggest"] { --glow: #8aa4bd; }')
    expect(css).toContain('[data-state="working"] { --glow: #d6d6d6; }')
    expect(css).toContain('[data-state="needs"]   { --glow: #cc7452; }')
    expect(css).toContain('[data-state="done"]    { --glow: #86ad73; }')
  })
})
