/**
 * The mirror and the textarea must share ONE box. James 2026-10-16, step 1.
 *
 * ⚠️ THESE ARE SOURCE-LEVEL ASSERTIONS, AND THE REAL GATE WAS A MEASUREMENT IN A
 * BROWSER. jsdom does not lay text out, so no test here can tell you whether two
 * layers wrap in the same place. What these CAN do is stop the one thing that would
 * silently break it later: somebody adding a typographic property to the textarea's
 * own style block instead of to `MIRROR_BOX`.
 *
 * The browser measurement that actually gated this (computed-style diff + scrollHeight
 * equality at two widths and three zooms, with a four-way positive control) is
 * recorded in the commit body. It is not reproducible in vitest and pretending
 * otherwise would be the worse failure.
 */
import { readFileSync } from "node:fs"
import { join } from "node:path"

import { describe, expect, it } from "vitest"

import { MIRROR_BOX, MIRROR_TEXTAREA_EXTRA } from "./CaptureMirror"

/** Every property that can move a wrap point. */
const LAYOUT_CRITICAL = [
  "fontFamily", "fontSize", "fontWeight", "lineHeight", "letterSpacing",
  "padding", "border", "whiteSpace", "overflowWrap", "wordBreak", "tabSize",
] as const

describe("the mirror box", () => {
  it("declares every property that decides where a line breaks", () => {
    // ⚠️ THE CONTROL. A constant that had lost its contents would satisfy a
    // "no competing property" test trivially.
    for (const key of LAYOUT_CRITICAL) {
      expect(MIRROR_BOX, `MIRROR_BOX is missing ${key}`).toHaveProperty(key)
    }
  })

  it("wraps like a textarea rather than like a div", () => {
    // A div's default `white-space: normal` collapses runs of spaces and drops a
    // trailing newline; a textarea preserves both. `pre-wrap` is the only value that
    // both preserves and wraps.
    expect(MIRROR_BOX.whiteSpace).toBe("pre-wrap")
    // ⚠️ `break-word` MATCHES WHAT A TEXTAREA DOES WITH A LONG UNBROKEN RUN. Left at
    // `normal` a pasted URL overflows the mirror instead of wrapping, and every line
    // after it sits one line too high.
    expect(MIRROR_BOX.overflowWrap).toBe("break-word")
  })

  it("keeps the textarea's background out of the way", () => {
    expect(MIRROR_TEXTAREA_EXTRA.background).toBe("transparent")
  })

  it("is the ONLY place the bar declares those properties", () => {
    // ⚠️ THE ASSERTION THAT ACTUALLY PROTECTS THE ALIGNMENT. The browser gate passes
    // today; what would break it tomorrow is a second declaration drifting from the
    // first. This reads the bar's source and fails if the textarea's own style block
    // names a layout-critical property.
    const src = readFileSync(
      join(__dirname, "OpasHost.tsx"), "utf8",
    )
    const start = src.indexOf("<textarea")
    expect(start, "the bar no longer has a textarea — this test needs rewriting")
      .toBeGreaterThan(-1)
    const end = src.indexOf("/>", start)
    const block = src.slice(start, end)

    const offenders = LAYOUT_CRITICAL.filter((k) =>
      new RegExp(`(^|[^.\\w])${k}\\s*:`, "m").test(block),
    )
    expect(
      offenders,
      `the textarea declares ${offenders.join(", ")} itself; move it into MIRROR_BOX ` +
        `or the mirror will wrap somewhere else`,
    ).toEqual([])

    // ⚠️ AND THE CONTROL FOR *THIS* ASSERTION: the block must actually contain the
    // spread, or an empty/relocated block would satisfy the check by containing
    // nothing at all.
    expect(block).toContain("...MIRROR_BOX")
  })
})
