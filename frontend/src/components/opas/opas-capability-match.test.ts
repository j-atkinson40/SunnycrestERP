/**
 * The client half of Opas's phrase matcher, against the SHARED case table.
 *
 * ⚠️ **WHY A SHARED TABLE AND NOT TWO TEST FILES.** The rule is implemented
 * twice — `services/opas-capabilities-service.ts::matchCapability` here and
 * `services/opas/capabilities.py::match_phrase` on the server — because
 * resolving a typed phrase is pure string work and a round trip per keystroke
 * would be worse. Two implementations of one rule need something holding them
 * together, or they drift silently and the client opens a different surface
 * from the one the server would have named. `capability-match-cases.json` is
 * that thing: this file reads it, and so does
 * `backend/tests/test_opas_capabilities.py`.
 */
import { readFileSync } from "node:fs"
import { resolve } from "node:path"

import { describe, expect, it } from "vitest"

import {
  matchCapability,
  hrefForTarget,
  type OpasCapability,
} from "@/services/opas-capabilities-service"

/** The entries the server composes, as the payload shapes them. Phrases are
 *  the registry's; this is the one place they are restated on the client side,
 *  and the agreement test below is what keeps that restatement honest. */
const WEEK: OpasCapability = {
  id: "payroll_week_review", label: "This week's payroll", area: "payroll", level: "view",
  phrases: ["this week's payroll", "this weeks payroll", "weekly payroll", "payroll",
            "the week", "review the week", "dues", "union dues"],
  target: "focus:weekly-payroll?week_end=2026-11-14",
}
const UPLOAD: OpasCapability = {
  id: "payroll_hours_upload", label: "Upload hours", area: "payroll", level: "change",
  phrases: ["upload hours", "upload the hours", "upload employee hours", "hours",
            "employee hours", "add hours", "upload this week's hours"],
  target: "focus:weekly-payroll?week_end=2026-11-14#upload",
}
const REPORT: OpasCapability = {
  id: "payroll_dues_report", label: "Dues reports", area: "payroll", level: "view",
  phrases: ["dues report", "dues reports", "past weeks", "previous weeks",
            "monthly dues", "union report", "reports"],
  target: "/payroll",
}

const SETS: Record<string, OpasCapability[]> = {
  all: [WEEK, UPLOAD, REPORT],
  none: [],
  view_only: [WEEK, REPORT],
}

interface Case { typed: string; entries: string; expect: string | null; why?: string }

const cases: Case[] = JSON.parse(
  readFileSync(
    resolve(process.cwd(), "src/components/opas/capability-match-cases.json"),
    "utf8",
  ),
).cases

describe("matchCapability, against the shared table", () => {
  it("read the table it claims to read", () => {
    // Positive control: a path typo would make `cases` empty and every
    // generated test below simply not exist, which looks identical to passing.
    expect(cases.length).toBeGreaterThanOrEqual(14)
    expect(cases.some((c) => c.typed === "dues report")).toBe(true)
  })

  for (const c of cases) {
    const name = `"${c.typed}" over ${c.entries} -> ${c.expect ?? "nothing"}`
    it(name, () => {
      const got = matchCapability(c.typed, SETS[c.entries])
      expect(got?.id ?? null).toBe(c.expect)
    })
  }
})

describe("hrefForTarget", () => {
  it("sends a focus target to /home as a QUERY PARAM, not a path", () => {
    // ⚠️ `/focus/weekly-payroll` is not a route. Shape 9 in CLAUDE.md §11 is a
    // widget whose call-to-action pointed at a path that never existed for four
    // and a half months, asserted by 55 green literals.
    expect(hrefForTarget("focus:weekly-payroll")).toBe("/home?focus=weekly-payroll")
  })

  it("⚠️ CARRIES THE SCOPE, because an unscoped Focus opens NOTHING", () => {
    // Found in the PR C walk-through: `/home?focus=weekly-payroll` rendered the
    // note and no Focus. The server fills the week; this must not drop it.
    expect(hrefForTarget("focus:weekly-payroll?week_end=2026-11-14")).toBe(
      "/home?focus=weekly-payroll&week_end=2026-11-14",
    )
  })

  it("carries a step as well as the scope", () => {
    expect(hrefForTarget("focus:weekly-payroll?week_end=2026-11-14#upload")).toBe(
      "/home?focus=weekly-payroll&week_end=2026-11-14&step=upload",
    )
  })

  it("passes a plain route through untouched", () => {
    expect(hrefForTarget("/payroll")).toBe("/payroll")
  })

  it("every shipped target resolves to a path the app actually serves", () => {
    // ⚠️ CHECKED AGAINST `App.tsx`, NOT AGAINST A LIST IN THIS FILE. The whole
    // point of shape 9 is that a literal written from the implementation is a
    // transcription of whatever the implementation got wrong.
    const app = readFileSync(resolve(process.cwd(), "src/App.tsx"), "utf8")
    expect(app.length).toBeGreaterThan(10_000) // control: the file was read
    for (const t of [WEEK.target, UPLOAD.target, REPORT.target]) {
      const href = hrefForTarget(t)
      const path = href.split("?")[0]
      if (path === "/home") {
        expect(app).toContain('path="home"')
      } else {
        expect(app).toContain(`path="${path.replace(/^\//, "")}"`)
      }
    }
  })
})
