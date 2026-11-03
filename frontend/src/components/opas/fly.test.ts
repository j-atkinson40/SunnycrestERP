/**
 * The flight's geometry and its refusals.
 *
 * ⚠️ THE ARITHMETIC IS THE HALF THAT CAN BE WRONG INVISIBLY. A chip that travels to the
 * wrong row, or slides instead of arcing, reads as a parser bug rather than an
 * animation bug — so the three points are asserted against the prototype's own
 * expressions rather than eyeballed.
 */
import { describe, expect, it, vi } from "vitest"

import {
  ARC_LIFT_FIELD,
  rowValueFor,
  ARC_LIFT_TITLE,
  FLY_EASING,
  FLY_MS,
  flightFrames,
  fly,
  type Box,
} from "./fly"

const box = (left: number, top: number, width = 60, height = 20): Box => ({
  left,
  top,
  width,
  height,
})

describe("the arc's three points", () => {
  it("starts at the word's own rect, centred on the chip", () => {
    /** The prototype: `x0=rect.x, y0=rect.y-h/2`. */
    const f = flightFrames(box(100, 400), box(300, 200), 22)
    expect(f.from).toEqual({ x: 100, y: 400 - 11 })
  })

  it("ends on the target's FIRST LINE, not its middle", () => {
    /** ⚠️ `Math.min(tr.height,24)` IS THE PROTOTYPE'S AND IT MATTERS FOR TALL ROWS. A
     *  row with a secondary line is ~40px high; centring on it would land the chip
     *  between the value and the chairs count rather than on the value. */
    const tall = flightFrames(box(100, 400), box(300, 200, 60, 80), 22)
    expect(tall.to).toEqual({ x: 300, y: 200 + 12 - 11 })
    const short = flightFrames(box(100, 400), box(300, 200, 60, 16), 22)
    expect(short.to).toEqual({ x: 300, y: 200 + 8 - 11 })
  })

  it("LIFTS at the midpoint, so it arcs rather than slides", () => {
    /** ⚠️ THE ONE PART A REIMPLEMENTATION WOULD DROP. `my` must be ABOVE both
     *  endpoints — the word rises out of the bar and falls into the row. A straight
     *  interpolation covers the same distance and reads as a glitch. */
    const f = flightFrames(box(100, 400), box(300, 200), 22)
    expect(f.mid.y).toBeLessThan(Math.min(f.from.y, f.to.y))
  })

  it("lifts LESS when the destination is a pane title", () => {
    /** The prototype's `-(field?26:12)`. The title is a shorter hop and a 26px arc
     *  over it overshoots the pane's own header. */
    const toRow = flightFrames(box(100, 400), box(300, 200), 22, false)
    const toTitle = flightFrames(box(100, 400), box(300, 200), 22, true)
    expect(toTitle.mid.y - toRow.mid.y).toBe(ARC_LIFT_FIELD - ARC_LIFT_TITLE)
  })

  it("biases the midpoint PAST half way, so the fall is shorter than the rise", () => {
    /** The prototype's `.55`. Asserted as a relation rather than a number so the
     *  constant can move without this test becoming a copy of it. */
    const f = flightFrames(box(0, 0), box(1000, 0), 22)
    expect(f.mid.x).toBeGreaterThan(500)
    expect(f.mid.x).toBeLessThan(1000)
  })

  it("the chip's own height moves BOTH ends, not one", () => {
    /** ⚠️ A CENTRING BUG SHOWS AS A HALF-LINE OFFSET AT ONE END ONLY, which is the
     *  shape this catches: both endpoints subtract `h/2`. */
    const thin = flightFrames(box(100, 400), box(300, 200), 10)
    const thick = flightFrames(box(100, 400), box(300, 200), 30)
    expect(thin.from.y - thick.from.y).toBe(10)
    expect(thin.to.y - thick.to.y).toBe(10)
  })
})

describe("it lands even when it cannot fly", () => {
  /** ⚠️ THE PROTOTYPE'S OWN RULE — `if(REDUCE||!tgt||!rect){land(field);return}` — and
   *  the important one: the VALUE IS ALREADY RECORDED by the time a flight starts. The
   *  animation is a report, so an environment that cannot animate must still show the
   *  result. Each refusal below would otherwise lose the landing. */

  it("with no target", () => {
    const onLanded = vi.fn()
    fly({ from: box(0, 0), target: null, text: "hopkins", onLanded })
    expect(onLanded).toHaveBeenCalledTimes(1)
  })

  it("with no document", () => {
    const onLanded = vi.fn()
    fly({
      from: box(0, 0),
      target: null,
      text: "hopkins",
      onLanded,
      doc: undefined,
    })
    expect(onLanded).toHaveBeenCalledTimes(1)
  })

  it("under prefers-reduced-motion", () => {
    const onLanded = vi.fn()
    const target = document.createElement("div")
    document.body.appendChild(target)
    const spy = vi
      .spyOn(window, "matchMedia")
      .mockReturnValue({ matches: true } as never)
    try {
      fly({ from: box(0, 0), target, text: "hopkins", onLanded })
      expect(onLanded).toHaveBeenCalledTimes(1)
      // ⚠️ AND NO CHIP IS LEFT BEHIND, which is the other half of refusing: a node
      // appended and never animated would sit at 0,0 over the page forever.
      expect(document.querySelectorAll("[data-testid='opas-fly']")).toHaveLength(0)
    } finally {
      spy.mockRestore()
      target.remove()
    }
  })

  it("when the environment has no Element.animate — jsdom", () => {
    /** ⚠️ THIS IS NOT A HYPOTHETICAL, IT IS THE TEST ENVIRONMENT. jsdom has no Web
     *  Animations API, so without the feature check every component test that typed a
     *  recognized word would throw inside the gesture instead of exercising it. */
    const onLanded = vi.fn()
    const target = document.createElement("div")
    document.body.appendChild(target)
    try {
      expect(typeof document.createElement("div").animate).not.toBe("function")
      fly({ from: box(0, 0), target, text: "hopkins", onLanded })
      expect(onLanded).toHaveBeenCalledTimes(1)
      expect(document.querySelectorAll("[data-testid='opas-fly']")).toHaveLength(0)
    } finally {
      target.remove()
    }
  })
})

describe("when it CAN fly", () => {
  /** A stub `animate` that hands back the handle, so the test can finish the animation
   *  the way a browser would.
   *
   *  ⚠️ THE HANDLE IS THE WHOLE POINT, AND MY FIRST VERSION OF THIS HELPER DID NOT
   *  RETURN IT — so the "lands when it finishes" test could not drive `onfinish`, left
   *  exploratory code behind, and leaked a chip into the next test. jsdom has no Web
   *  Animations API, so a stub is the only way to see the keyframes at all, and it has
   *  to be a stub a test can complete. */
  interface Handle {
    onfinish: (() => void) | null
    cancelled: boolean
  }

  function withAnimate(
    run: (calls: unknown[][], handles: Handle[]) => void,
  ) {
    const calls: unknown[][] = []
    const handles: Handle[] = []
    const proto = Element.prototype as unknown as {
      animate?: (...a: unknown[]) => unknown
    }
    const had = Object.prototype.hasOwnProperty.call(proto, "animate")
    const prev = proto.animate
    proto.animate = function (...a: unknown[]) {
      calls.push(a)
      const h: Handle = {
        onfinish: null,
        cancelled: false,
        cancel() {
          this.cancelled = true
        },
      } as Handle & { cancel: () => void }
      handles.push(h)
      return h
    }
    try {
      run(calls, handles)
    } finally {
      if (had) proto.animate = prev
      else delete proto.animate
      // ⚠️ EVERY CHIP REMOVED, so one test cannot leak a node into the next. The two
      // failures that produced this helper were both "expected 1, found 2".
      document
        .querySelectorAll("[data-testid='opas-fly']")
        .forEach((n) => n.remove())
    }
  }

  function chips(): number {
    return document.querySelectorAll("[data-testid='opas-fly']").length
  }

  it("uses the prototype's duration, easing and three keyframes", () => {
    withAnimate((calls) => {
      const target = document.createElement("div")
      document.body.appendChild(target)
      try {
        fly({ from: box(10, 500), target, text: "hopkins" })
        expect(calls).toHaveLength(1)
        const [frames, opts] = calls[0] as [
          Array<Record<string, unknown>>,
          Record<string, unknown>,
        ]
        expect(frames).toHaveLength(3)
        expect(opts.duration).toBe(FLY_MS)
        expect(opts.easing).toBe(FLY_EASING)
        expect(opts.fill).toBe("forwards")
        // the middle keyframe is the arc, explicitly at the halfway offset
        expect(frames[1].offset).toBe(0.5)
        // ⚠️ IT SCALES UP THERE AND DOWN ON ARRIVAL, which is what makes the word read
        // as travelling toward the reader and away again rather than just shrinking.
        expect(String(frames[1].transform)).toContain("scale(1.05)")
        expect(String(frames[2].transform)).toContain("scale(.94)")
      } finally {
        target.remove()
      }
    })
  })

  it("lands when the animation FINISHES, and not before", () => {
    withAnimate((_calls, handles) => {
      const onLanded = vi.fn()
      const target = document.createElement("div")
      document.body.appendChild(target)
      try {
        fly({ from: box(10, 500), target, text: "hopkins", onLanded })
        // ⚠️ NOT YET, and this is the half that makes the row's value appear WITH the
        // chip's arrival rather than the moment it leaves the bar.
        expect(onLanded).not.toHaveBeenCalled()
        expect(chips()).toBe(1)

        handles[0].onfinish?.()

        expect(onLanded).toHaveBeenCalledTimes(1)
        // ⚠️ AND THE CHIP IS GONE. A node left behind sits fixed over the page.
        expect(chips()).toBe(0)
      } finally {
        target.remove()
      }
    })
  })

  it("finishing TWICE lands once", () => {
    /** ⚠️ `onfinish` AND `cancel` CAN RACE on unmount, so the guard is not theoretical:
     *  landing twice would flash the row twice and, in the host, fire two state
     *  updates for one word. */
    withAnimate((_calls, handles) => {
      const onLanded = vi.fn()
      const target = document.createElement("div")
      document.body.appendChild(target)
      try {
        fly({ from: box(10, 500), target, text: "hopkins", onLanded })
        handles[0].onfinish?.()
        handles[0].onfinish?.()
        expect(onLanded).toHaveBeenCalledTimes(1)
      } finally {
        target.remove()
      }
    })
  })

  it("cancelling removes the chip and does NOT land", () => {
    /** ⚠️ THE UNMOUNT PATH. A chip whose pane has gone must not arrive — it would flash
     *  a value into a row no longer on screen, and `onLanded` would touch a component
     *  that has unmounted. */
    withAnimate((_calls, handles) => {
      const onLanded = vi.fn()
      const target = document.createElement("div")
      document.body.appendChild(target)
      try {
        const cancel = fly({ from: box(10, 500), target, text: "hopkins", onLanded })
        expect(chips()).toBe(1)
        cancel()
        expect(chips()).toBe(0)
        expect(onLanded).not.toHaveBeenCalled()
        // ⚠️ AND A FINISH AFTER A CANCEL STILL DOES NOT LAND, which is the race the
        // flag exists for rather than a second way of saying the same thing.
        handles[0].onfinish?.()
        expect(onLanded).not.toHaveBeenCalled()
        // cancelling twice is safe
        cancel()
        expect(onLanded).not.toHaveBeenCalled()
      } finally {
        target.remove()
      }
    })
  })
})

describe("finding the row a field is shown in", () => {
  /** ⚠️ THE REGRESSION THESE EXIST FOR: the leave effect looked rows up by TESTID,
   *  which carries `row_id`, and only 6 of the 12 capture rows have a `row_id` equal to
   *  their field id. The other six are composed — `cemetery` shows `cemetery_city` and
   *  `eta`; `cemetery_equipment` shows `chairs_total` and `chairs_extra`. Words bound
   *  for those fields found no target and silently never flew. */

  function surface(): () => void {
    const host = document.createElement("div")
    host.innerHTML = `
      <button data-testid="capture-row-cemetery" data-fields="cemetery cemetery_city eta">
        <span data-testid="capture-row-value">St. Mary's</span>
      </button>
      <button data-testid="capture-row-vault" data-fields="vault">
        <span data-testid="capture-row-value">Monticello</span>
      </button>`
    document.body.appendChild(host)
    return () => host.remove()
  }

  it("finds a row whose id IS the field id", () => {
    const done = surface()
    try {
      expect(rowValueFor("vault")?.textContent).toBe("Monticello")
    } finally {
      done()
    }
  })

  it("finds a COMPOSED row by one of its other fields", () => {
    /** ⚠️ THE CASE THE OLD LOOKUP RETURNED NULL FOR. `cemetery_city` has no row of its
     *  own; it is shown on the `cemetery` row, and that is where its word must fly. */
    const done = surface()
    try {
      expect(rowValueFor("cemetery_city")?.textContent).toBe("St. Mary's")
      expect(rowValueFor("eta")?.textContent).toBe("St. Mary's")
    } finally {
      done()
    }
  })

  it("does NOT match a field whose name is a PREFIX of a real one", () => {
    /** ⚠️ `~=` IS A WHOLE-TOKEN MATCH AND THAT IS LOAD-BEARING. With `*=` instead,
     *  `cemetery` would also match the row listing `cemetery_city`, and a word could
     *  fly to whichever row happened to be first in the document. */
    const done = surface()
    try {
      const host = document.createElement("div")
      host.innerHTML = `<button data-fields="cemetery_city_extra">
        <span data-testid="capture-row-value">wrong</span></button>`
      document.body.insertBefore(host, document.body.firstChild)
      try {
        expect(rowValueFor("cemetery_city")?.textContent).toBe("St. Mary's")
      } finally {
        host.remove()
      }
    } finally {
      done()
    }
  })

  it("returns null for an unknown field, and for an empty one", () => {
    const done = surface()
    try {
      expect(rowValueFor("no_such_field")).toBeNull()
      expect(rowValueFor("")).toBeNull()
    } finally {
      done()
    }
  })

  it("does not THROW on a field id carrying a quote", () => {
    /** ⚠️ A FIELD ID REACHES THIS FROM THE SERVER, and an unescaped quote ends the
     *  attribute selector early — `querySelector` then throws a SyntaxError inside the
     *  gesture, taking the whole pane down rather than one word failing to fly. */
    const done = surface()
    try {
      expect(() => rowValueFor('bad"field')).not.toThrow()
      expect(rowValueFor('bad"field')).toBeNull()
    } finally {
      done()
    }
  })
})
