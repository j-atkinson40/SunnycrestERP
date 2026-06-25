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
  },
})
