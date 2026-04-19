import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

export default defineConfig({
  plugins: [react(), tailwindcss()],
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
