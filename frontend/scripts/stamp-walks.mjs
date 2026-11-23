/**
 * Print the WALKS.md fingerprint block for the current tree.
 *
 * ⚠️ **RUN THIS ONLY AFTER THE WALKS HAVE ACTUALLY RUN GREEN.** It reads bytes
 * off disk and does not know whether anybody ran anything — so stamping is the
 * one step in this loop that a person has to mean. A stamp taken from a tree
 * nobody walked is a green check over an unverified surface, which is the
 * condition `walk-freshness.test.ts` exists to detect.
 *
 *   node scripts/stamp-walks.mjs            # print the block
 *   node scripts/stamp-walks.mjs --write    # rewrite WALKS.md in place
 *
 * The commit is read from `git rev-parse HEAD`, never typed.
 */
import { createHash } from "node:crypto"
import { execFileSync } from "node:child_process"
import { readFileSync, readdirSync, statSync, writeFileSync } from "node:fs"
import { dirname, join, relative } from "node:path"
import { fileURLToPath } from "node:url"

const FRONTEND = join(dirname(fileURLToPath(import.meta.url)), "..")
const WALKS_MD = join(FRONTEND, "tests", "local", "WALKS.md")

function filesUnder(abs) {
  if (!statSync(abs).isDirectory()) return [abs]
  return readdirSync(abs)
    .sort()
    .flatMap((n) => filesUnder(join(abs, n)))
}

function fingerprintOf(relPath) {
  const h = createHash("sha256")
  for (const f of filesUnder(join(FRONTEND, relPath))) {
    h.update(relative(FRONTEND, f))
    h.update("\0")
    h.update(readFileSync(f))
    h.update("\0")
  }
  return h.digest("hex")
}

const head = execFileSync("git", ["rev-parse", "HEAD"], {
  cwd: FRONTEND,
  encoding: "utf8",
}).trim()
const today = execFileSync("git", ["log", "-1", "--format=%cs"], {
  cwd: FRONTEND,
  encoding: "utf8",
}).trim()

const text = readFileSync(WALKS_MD, "utf8")
const m = /<!-- walks:begin -->\s*```json\s*([\s\S]*?)```\s*<!-- walks:end -->/.exec(text)
if (!m) throw new Error("WALKS.md has no walks:begin/walks:end JSON block")
const entries = JSON.parse(m[1])

for (const e of entries) {
  // Keep the declared dependency set; recompute every hash, and always include
  // the walk's own file — an edited walk has not been re-run.
  const paths = Object.keys(e.fingerprints ?? {})
  const deps = paths.length ? paths : [`tests/local/${e.walk}`]
  if (!deps.includes(`tests/local/${e.walk}`)) deps.unshift(`tests/local/${e.walk}`)
  e.verified_at_commit = head
  e.verified_on = today
  e.fingerprints = Object.fromEntries(deps.sort().map((p) => [p, fingerprintOf(p)]))
}

const block = JSON.stringify(entries, null, 2)
if (process.argv.includes("--write")) {
  writeFileSync(
    WALKS_MD,
    text.replace(
      m[0],
      `<!-- walks:begin -->\n\`\`\`json\n${block}\n\`\`\`\n<!-- walks:end -->`,
    ),
  )
  console.error(`WALKS.md rewritten at ${head} (${today})`)
} else {
  console.log(block)
}
