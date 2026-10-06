import fs from "fs"
import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig, type Plugin } from "vitest/config"

/**
 * Emit dist/version.json carrying the deployed commit SHA — the signal the CI
 * deploy-gate polls to confirm the FRONTEND (a separate Railway service from
 * the backend) actually built + deployed the pushed commit.
 *
 * Load-bearing property: this runs in `closeBundle`, which fires ONLY after a
 * successful `vite build` — and `npm run build` is `tsc -b && vite build`, so a
 * tsc failure (e.g. an unused import) means vite build never runs, closeBundle
 * never fires, and version.json never advances. The bundle's freshness and
 * version.json's freshness are the SAME event: a broken build leaves BOTH
 * stale, so the gate fails loudly instead of testing a stale bundle. (This
 * commit exists because exactly that build-break went invisible to CI.)
 *
 * SHA source: RAILWAY_GIT_COMMIT_SHA (the same var the backend /api/health
 * reports), read at build time in Railway's build env. "unknown" locally —
 * which the gate treats as not-matching: fail-closed, never false-green.
 */
function emitVersionJson(): Plugin {
  return {
    name: "emit-version-json",
    apply: "build",
    closeBundle() {
      const commit = process.env.RAILWAY_GIT_COMMIT_SHA || "unknown"
      const outDir = path.resolve(__dirname, "dist")
      fs.mkdirSync(outDir, { recursive: true })
      fs.writeFileSync(
        path.join(outDir, "version.json"),
        JSON.stringify({ commit }) + "\n",
      )
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), emitVersionJson()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // Vitest config — component + pure-function unit tests. Separate from
  // the Playwright E2E suite under tests/e2e (which runs against staging).
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // Match *.test.ts(x) + *.spec.ts(x) under src/. Exclude Playwright
    // tests under tests/e2e explicitly.
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["node_modules", "tests/e2e", "dist"],
    css: false,

    // ⚠️ THIS IS WHAT KEPT FRONTEND CI RED, AND CLAUDE.md SAID IT DIDN'T MATTER.
    //
    // Vitest forwards every console call from the worker to the main process over
    // rpc (`onUserConsoleLog`). When a worker closes with one of those still in
    // flight it raises:
    //
    //   EnvironmentTeardownError: [vitest-worker]: Closing rpc while
    //   "onUserConsoleLog" was pending
    //
    // CLAUDE.md §"Build discipline" characterises that as environmental, notes
    // "0 test failures", and says not to let it block a commit. Both halves are
    // true and the conclusion does not follow for CI: **vitest exits 1 on an
    // unhandled error regardless of how many tests passed.** Measured on run
    // 37457088736 — `338 passed (338)`, `4435 passed | 3 skipped | 1 todo`,
    // `Errors 1 error`, `Process completed with exit code 1`. The job was red
    // with nothing failing, and the documented advice was to proceed.
    //
    // Disabling interception means the rpc is never made — logs go straight to
    // the worker's own stdout/stderr — so the pending call cannot exist. That is
    // a removal, not a suppression: `dangerouslyIgnoreUnhandledErrors` would have
    // made the job green while silencing every OTHER unhandled error too, which
    // is a loud failure traded for a quiet one.
    //
    // ⚠️ THE COST, STATED: vitest can no longer attribute console output to the
    // test that emitted it — no `stderr | file > test name` header. Output still
    // appears, unlabelled. Accepted because the alternative is a channel that
    // cannot report a new failure.
    //
    // ⚠️ AND THIS IS NOT VERIFIED BY A LOCAL RUN. The race is intermittent and
    // did not fire locally in either direction, so a green local suite is not
    // evidence. The first green CI run is a BASELINE, not a confirmation.
    disableConsoleIntercept: true,
  },
})
