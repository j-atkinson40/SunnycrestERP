/**
 * What a note line opens, and with what scope.
 *
 * ⚠️ **THE DEFECT THIS PINS, FOUND BY BREAK-TESTING ON 2026-11-17.** The note's
 * new open-week prompt addresses a week that has NO ROW — the row is created by
 * the upload the line is asking for — so its subject id is a DATE. `focusTarget`
 * mapped every `payroll_week` subject to `week_id=<subject_id>`, so the line
 * would have linked to `week_id=2026-11-14`: a Focus that cannot fetch that
 * week, landing on "could not be loaded" from the one line whose job is to
 * offer the upload.
 *
 * The line rendered perfectly. Only the href was wrong, and nothing rendered it.
 */
import { describe, expect, it } from "vitest"

import { focusTarget } from "./NotePage"

/**
 * ⚠️ **NO MOCK OF THE FOCUS REGISTRY, DELIBERATELY — AND THE FIRST VERSION HAD
 * A DEAD ONE.** It mocked `@/components/focus/registry`; the real import is
 * `@/contexts/focus-registry`, so the mock never applied and the test silently
 * ran against the real registry while appearing to control it.
 *
 * Left running against the real one, because that is the stronger test: it
 * asserts `weekly-payroll` is genuinely registered and `not-a-focus` genuinely
 * is not. A double would have passed either way — which is how a target_key
 * typo once made the note's Open link silently vanish.
 */

const base = {
  fragment_id: "f",
  instance_key: "k",
  kind: "prompt",
  title: "t",
  text: "x",
  spans: [],
  target_surface: "focus",
  target_key: "weekly-payroll",
  openable: false,
} as never

describe("focusTarget", () => {
  it("⚠️ a week addressed by its END becomes week_end, not week_id", () => {
    const href = focusTarget({
      ...(base as object),
      subject_kind: "payroll_week_end",
      subject_id: "2026-11-14",
    } as never)
    expect(href).toBe("/home?focus=weekly-payroll&week_end=2026-11-14")
    expect(href).not.toContain("week_id")
  })

  it("a week addressed by its ROW still becomes week_id", () => {
    // The positive control: the fix must not have moved the existing case.
    expect(
      focusTarget({
        ...(base as object),
        subject_kind: "payroll_week",
        subject_id: "wk-uuid-1",
      } as never),
    ).toBe("/home?focus=weekly-payroll&week_id=wk-uuid-1")
  })

  it("⚠️ links at /home, never /, because a redirect DROPS the query string", () => {
    const href = focusTarget({
      ...(base as object),
      subject_kind: "payroll_week_end",
      subject_id: "2026-11-14",
    } as never)
    expect(href!.startsWith("/home?")).toBe(true)
  })

  it("an unregistered Focus opens nothing rather than a dead link", () => {
    expect(
      focusTarget({
        ...(base as object),
        target_key: "not-a-focus",
        subject_kind: "payroll_week_end",
        subject_id: "2026-11-14",
      } as never),
    ).toBeNull()
  })

  it("no subject means no link — there would be nothing to scope to", () => {
    expect(
      focusTarget({
        ...(base as object),
        subject_kind: "payroll_week_end",
        subject_id: null,
      } as never),
    ).toBeNull()
  })
})
