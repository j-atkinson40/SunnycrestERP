/**
 * Gate 11: Bundle delta within +5% of R-1.5 baseline for non-runtime-
 * editor chunks.
 *
 * R-1.6 reads `tests/e2e/runtime-editor/fixtures/bundle-baseline.json`
 * + scans the local `dist/` directory for matching chunks. For each
 * chunk: assert size is within tolerance.
 *
 * Runtime-editor chunks (RuntimeEditorShell, TenantUserPicker, etc.)
 * are excluded — they're EXPECTED to change as R-2+ ships. The
 * baseline fixture's `excluded_runtime_editor_chunks` field
 * documents the exclusion list.
 *
 * The spec runs locally against `frontend/dist/` (post `vite build`).
 * In the CI workflow, this spec gates on the build artifact existing.
 */
import { test, expect } from "@playwright/test"
import { readFileSync, readdirSync, statSync } from "node:fs"
import { join, resolve, dirname } from "node:path"
import { fileURLToPath } from "node:url"


// Playwright runs specs as ESM modules; __dirname is undefined.
// Derive it from import.meta.url.
const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)


interface BaselineChunk {
  pattern: string
  baseline_bytes: number
  description: string
}

interface BaselineFixture {
  _tolerance_pct: number
  _baseline_commit: string
  chunks: Record<string, BaselineChunk>
  excluded_runtime_editor_chunks: string[]
}


function loadBaseline(): BaselineFixture {
  const fixturePath = resolve(
    __dirname,
    "fixtures",
    "bundle-baseline.json",
  )
  return JSON.parse(readFileSync(fixturePath, "utf-8"))
}


function findChunkSize(distDir: string, pattern: string): number | null {
  // Pattern is like "index-*.js" — strip the wildcard and find the
  // first file in dist/assets/ whose name starts with the prefix
  // and ends with the suffix.
  const [prefix, suffix] = pattern.split("*")
  const assetsDir = join(distDir, "assets")
  let files: string[]
  try {
    files = readdirSync(assetsDir)
  } catch {
    return null
  }
  const match = files.find(
    (f) => f.startsWith(prefix) && f.endsWith(suffix),
  )
  if (!match) return null
  return statSync(join(assetsDir, match)).size
}


test.describe("Gate 11 — bundle delta within +5%", () => {
  test("each non-runtime-editor chunk size is within tolerance", async () => {
    const baseline = loadBaseline()
    const distDir = resolve(__dirname, "..", "..", "..", "dist")
    const tolerance = baseline._tolerance_pct / 100

    let distExists = true
    try {
      statSync(distDir)
    } catch {
      distExists = false
    }
    test.skip(
      !distExists,
      `Skipping bundle-delta gate — ${distDir} not present. ` +
        `Run "npx vite build" before this spec.`,
    )

    const failures: string[] = []
    for (const [name, chunk] of Object.entries(baseline.chunks)) {
      const size = findChunkSize(distDir, chunk.pattern)
      if (size === null) {
        failures.push(
          `Chunk '${name}' (${chunk.pattern}) not found in dist/assets/`,
        )
        continue
      }
      const delta = (size - chunk.baseline_bytes) / chunk.baseline_bytes
      const ceiling = chunk.baseline_bytes * (1 + tolerance)
      if (size > ceiling) {
        failures.push(
          `Chunk '${name}' grew ${(delta * 100).toFixed(2)}% — ${size} bytes ` +
            `vs baseline ${chunk.baseline_bytes} (ceiling ${Math.floor(ceiling)}). ` +
            `If intentional: update fixtures/bundle-baseline.json + add ` +
            `justification to commit message.`,
        )
      }
    }
    expect(failures).toEqual([])
  })
})
