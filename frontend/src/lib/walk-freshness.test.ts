/**
 * A walk cannot stop checking without saying so.
 *
 * ⚠️ **WRITTEN AFTER THE 5a WALK WAS RED FOR FIVE DAYS AND NOBODY KNEW.**
 * `5dd34500` removed the sidebar for area-limited users — correctly — and
 * `payroll-week44-walkthrough.spec.ts` went on asserting it, dying on its third
 * assertion and verifying nothing past that point. The shell change was right,
 * the walk was right when written, and **no instrument in the repo related the
 * two.** This is that instrument.
 *
 * ⚠️ **IT DOES NOT RUN THE WALKS, AND THAT IS NOT A COMPROMISE.** They need two
 * local servers, a seeded database and a real payroll export that is not in the
 * repository. A CI job that cannot run is a channel that cannot report, which
 * is the exact failure this file exists to prevent — so instead of pretending,
 * it checks the one thing that IS checkable from a clone:
 *
 *     nothing a walk depends on may change without the walk being re-run.
 *
 * Run on `5dd34500` this goes red, because `limited-shell.tsx` is in the 5a
 * walk's declared dependencies and that commit is not in its stamp.
 *
 * ⚠️ **NO TIME COMPONENT, DELIBERATELY.** "Re-run every N days" would be red
 * whenever nobody happened to run them, which is most weeks — and a check that
 * is usually red is the dark channel again. The trigger is a CHANGE.
 *
 * ⚠️ **AND THE STAMP IS A COMMIT, NOT A DATE.** `git merge-base --is-ancestor`
 * answers "has this dependency moved since?" exactly, where a date comparison
 * would be wrong on every rebase, cherry-pick and out-of-order merge.
 */
import { execFileSync } from "node:child_process"
import { readdirSync, readFileSync } from "node:fs"
import { join } from "node:path"

import { describe, expect, it } from "vitest"

/** ⚠️ **LIVES UNDER `src/lib/`, NOT NEXT TO THE WALKS, AND THAT IS LOAD-BEARING.**
 *  vitest's `include` is `src/**` — a guard written beside the walks in
 *  `tests/local/` is never collected, so it would be a check that cannot run
 *  sitting next to the checks it watches. `prod-intercept-fail-closed.test.ts`
 *  is the precedent: a repo-hygiene guard here, reading files from elsewhere. */
const ROOT = join(__dirname, "..", "..", "..")
const HERE = join(ROOT, "frontend", "tests", "local")

interface WalkEntry {
  walk: string
  what: string
  verified_at: string
  verified_on: string
  depends_on: string[]
}

function git(args: string[]): string {
  return execFileSync("git", args, { cwd: ROOT, encoding: "utf8" }).trim()
}

function manifest(): WalkEntry[] {
  const text = readFileSync(join(HERE, "WALKS.md"), "utf8")
  const m = /<!-- walks:begin -->\s*```json\s*([\s\S]*?)```\s*<!-- walks:end -->/.exec(
    text,
  )
  expect(m, "WALKS.md has no walks:begin/walks:end JSON block").toBeTruthy()
  return JSON.parse(m![1]) as WalkEntry[]
}

/** Is this a git checkout at all? A guard that silently passes outside one
 *  would be the absent instrument it was written to replace. */
function inGitRepo(): boolean {
  try {
    git(["rev-parse", "--git-dir"])
    return true
  } catch {
    return false
  }
}


describe("the walk-through manifest", () => {
  it("is parseable, and holds every walk in the directory", () => {
    const entries = manifest()
    expect(entries.length).toBeGreaterThan(0)

    // ⚠️ MEMBERSHIP, like the backend's CI gate — and for the same reason. A
    // manifest maintained by adding what somebody remembered converges on
    // covering what somebody remembered. A new walk that lands unstamped is
    // a walk nothing is watching, so its absence is the failure.
    const onDisk = readdirSync(HERE)
      .filter((f) => f.endsWith("-walkthrough.spec.ts"))
      .sort()
    const listed = entries.map((e) => e.walk).sort()
    expect(
      listed,
      "every *-walkthrough.spec.ts must be stamped in WALKS.md — a walk that " +
        "is not listed is a walk no check is watching",
    ).toEqual(onDisk)
  })

  it("names a real file for every walk and every dependency", () => {
    for (const e of manifest()) {
      expect(
        readdirSync(HERE).includes(e.walk),
        `${e.walk} is stamped but does not exist`,
      ).toBe(true)
      for (const dep of e.depends_on) {
        // ⚠️ A DEPENDENCY THAT NO LONGER EXISTS IS A SILENT HOLE: `git log` on
        // a deleted path returns nothing, which looks exactly like "nothing
        // changed". Checked explicitly so a rename cannot blind the guard.
        const n = git(["ls-files", "--", join("frontend", dep)])
        expect(
          n.length,
          `${e.walk} depends on "${dep}", which git does not track — a stale ` +
            "dependency path makes this guard pass by seeing nothing",
        ).toBeGreaterThan(0)
      }
    }
  })

  it("stamps each walk at a commit this repo contains", () => {
    for (const e of manifest()) {
      expect(
        e.verified_at,
        `${e.walk}: verified_at must be a full 40-character SHA read from ` +
          "`git rev-parse HEAD`, never typed",
      ).toMatch(/^[0-9a-f]{40}$/)
      const known = (() => {
        try {
          git(["cat-file", "-e", `${e.verified_at}^{commit}`])
          return true
        } catch {
          return false
        }
      })()
      expect(
        known,
        `${e.walk}: ${e.verified_at} is not a commit in this repository`,
      ).toBe(true)
    }
  })
})


describe("nothing a walk depends on may change without the walk being re-run", () => {
  it("reports every dependency that has moved past its walk's stamp", () => {
    if (!inGitRepo()) {
      throw new Error(
        "not a git checkout, so this guard cannot see anything — it fails " +
          "rather than passing, because a silent pass here is the condition " +
          "it was written to detect",
      )
    }

    const stale: string[] = []
    for (const e of manifest()) {
      for (const dep of e.depends_on) {
        // Commits touching this dependency that the stamp does NOT contain.
        const since = git([
          "log",
          "--format=%h %s",
          `${e.verified_at}..HEAD`,
          "--",
          join("frontend", dep),
        ])
        if (since) {
          stale.push(
            `${e.walk}\n  depends on ${dep}, changed since it was last run ` +
              `green (${e.verified_at.slice(0, 8)}, ${e.verified_on}):\n` +
              since
                .split("\n")
                .map((l) => `    ${l}`)
                .join("\n"),
          )
        }
      }
      // The walk's own file counts too: an edited walk has not been re-run.
      const own = git([
        "log",
        "--format=%h %s",
        `${e.verified_at}..HEAD`,
        "--",
        join("frontend", "tests", "local", e.walk),
      ])
      if (own) {
        stale.push(
          `${e.walk}\n  was edited since it was last run green ` +
            `(${e.verified_at.slice(0, 8)}, ${e.verified_on}):\n` +
            own
              .split("\n")
              .map((l) => `    ${l}`)
              .join("\n"),
        )
      }
    }

    expect(
      stale,
      "These walks may no longer be checking what they claim. Re-run each one " +
        "locally, confirm it green, and re-stamp `verified_at` in " +
        "frontend/tests/local/WALKS.md with `git rev-parse HEAD`. See that " +
        "file for the exact command.\n\n" +
        stale.join("\n\n"),
    ).toEqual([])
  })
})
