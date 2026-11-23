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
 * ⚠️ **CONTENT HASHES, NOT COMMIT SHAs — AND THE FIRST VERSION USED SHAs AND
 * CI CAUGHT IT.** `git merge-base --is-ancestor` reads beautifully and has two
 * faults that only show up off a developer's laptop:
 *
 *   1. `actions/checkout@v4` is shallow by default, so the stamped commits are
 *      not in the clone at all. CI failed with "<sha> is not a commit in this
 *      repository" — correctly, because the guard refuses rather than passing
 *      when it cannot see.
 *   2. **This repo squash-merges.** The branch commits are discarded on merge,
 *      so a SHA stamped on a branch is unreachable from `main` afterwards. The
 *      guard would have gone permanently red one commit after landing, which
 *      is the dark channel again wearing the opposite colour.
 *
 * A hash over the bytes answers the same question — *has any of this changed
 * since the walk was last run green?* — and is immune to shallow clones,
 * squashes, rebases and cherry-picks, because it never asks about history.
 *
 * ⚠️ **NO TIME COMPONENT, DELIBERATELY.** "Re-run every N days" would be red
 * whenever nobody happened to run them, which is most weeks — and a check that
 * is usually red is the dark channel again. The trigger is a CHANGE.
 */
import { createHash } from "node:crypto"
import { readFileSync, readdirSync, statSync } from "node:fs"
import { join, relative } from "node:path"

import { describe, expect, it } from "vitest"

/** ⚠️ **LIVES UNDER `src/lib/`, NOT NEXT TO THE WALKS, AND THAT IS LOAD-BEARING.**
 *  vitest's `include` is `src/**` — a guard written beside the walks in
 *  `tests/local/` is never collected, so it would be a check that cannot run
 *  sitting next to the checks it watches. `prod-intercept-fail-closed.test.ts`
 *  is the precedent: a repo-hygiene guard here, reading files from elsewhere. */
const FRONTEND = join(__dirname, "..", "..")
const WALKS_DIR = join(FRONTEND, "tests", "local")

interface WalkEntry {
  walk: string
  what: string
  verified_on: string
  verified_at_commit: string
  /** path → sha256 of its bytes, for a file; of its concatenated tree, for a
   *  directory. Per-path rather than one digest so a failure can NAME what
   *  moved, which is the whole value of the check. */
  fingerprints: Record<string, string>
}

/** Every file under a path, sorted, so a directory hashes deterministically. */
function filesUnder(abs: string): string[] {
  if (!statSync(abs).isDirectory()) return [abs]
  const out: string[] = []
  for (const name of readdirSync(abs).sort()) {
    out.push(...filesUnder(join(abs, name)))
  }
  return out
}

/** ⚠️ A DIRECTORY'S HASH COVERS ITS FILE NAMES AS WELL AS THEIR BYTES, so
 *  adding, deleting or renaming a file inside a declared dependency moves the
 *  hash. Hashing only the contents would miss a new file entirely. */
export function fingerprintOf(relPath: string): string {
  const abs = join(FRONTEND, relPath)
  const h = createHash("sha256")
  for (const f of filesUnder(abs)) {
    h.update(relative(FRONTEND, f))
    h.update("\0")
    h.update(readFileSync(f))
    h.update("\0")
  }
  return h.digest("hex")
}

function manifest(): WalkEntry[] {
  const text = readFileSync(join(WALKS_DIR, "WALKS.md"), "utf8")
  const m = /<!-- walks:begin -->\s*```json\s*([\s\S]*?)```\s*<!-- walks:end -->/.exec(
    text,
  )
  expect(m, "WALKS.md has no walks:begin/walks:end JSON block").toBeTruthy()
  return JSON.parse(m![1]) as WalkEntry[]
}


describe("the walk-through manifest", () => {
  it("is parseable, and holds every walk in the directory", () => {
    const entries = manifest()
    expect(entries.length).toBeGreaterThan(0)

    // ⚠️ MEMBERSHIP, like the backend's CI gate — and for the same reason. A
    // manifest maintained by adding what somebody remembered converges on
    // covering what somebody remembered. A new walk that lands unstamped is a
    // walk nothing is watching, so its absence is the failure.
    const onDisk = readdirSync(WALKS_DIR)
      .filter((f) => f.endsWith("-walkthrough.spec.ts"))
      .sort()
    expect(
      entries.map((e) => e.walk).sort(),
      "every *-walkthrough.spec.ts must be stamped in WALKS.md — a walk that " +
        "is not listed is a walk no check is watching",
    ).toEqual(onDisk)
  })

  it("fingerprints each walk's own file and at least one dependency", () => {
    for (const e of manifest()) {
      const paths = Object.keys(e.fingerprints)
      expect(
        paths,
        `${e.walk}: its own file must be fingerprinted — an edited walk has ` +
          "not been re-run",
      ).toContain(`tests/local/${e.walk}`)
      expect(
        paths.length,
        `${e.walk}: fingerprint at least one dependency, or this entry ` +
          "watches nothing but itself",
      ).toBeGreaterThan(1)
      expect(
        e.verified_at_commit,
        `${e.walk}: record the commit it was run at, read from ` +
          "`git rev-parse HEAD` — never typed. It is provenance for a human, " +
          "not an input to this check, because squash-merging discards it.",
      ).toMatch(/^[0-9a-f]{40}$/)
    }
  })
})


describe("nothing a walk depends on may change without the walk being re-run", () => {
  it("names every path whose bytes have moved since its walk ran green", () => {
    const stale: string[] = []

    for (const e of manifest()) {
      for (const [relPath, stamped] of Object.entries(e.fingerprints)) {
        let actual: string
        try {
          actual = fingerprintOf(relPath)
        } catch {
          // ⚠️ A DEPENDENCY THAT NO LONGER EXISTS IS A SILENT HOLE: a missing
          // path hashes to nothing, which looks exactly like "unchanged" if it
          // is tolerated. Named instead, so a rename cannot blind the guard.
          stale.push(
            `${e.walk}\n  depends on ${relPath}, which no longer exists — a ` +
              "stale dependency path makes this guard pass by seeing nothing",
          )
          continue
        }
        if (actual !== stamped) {
          stale.push(
            `${e.walk}\n  ${relPath} has changed since the walk was last run ` +
              `green (${e.verified_on}, ${e.verified_at_commit.slice(0, 8)})\n` +
              `    stamped ${stamped.slice(0, 16)}…\n` +
              `    now     ${actual.slice(0, 16)}…`,
          )
        }
      }
    }

    expect(
      stale,
      "These walks may no longer be checking what they claim. Re-run each one " +
        "locally, confirm it green, then re-stamp its fingerprints in " +
        "frontend/tests/local/WALKS.md — `npm run walks:stamp` prints the " +
        "block to paste. See that file for the exact command.\n\n" +
        stale.join("\n\n"),
    ).toEqual([])
  })
})
