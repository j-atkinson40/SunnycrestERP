/**
 * Vitest setup — runs once before every test file.
 *
 * - Wires up @testing-library/jest-dom matchers (toBeInTheDocument,
 *   toHaveTextContent, etc.)
 * - Configures automatic cleanup after each test (testing-library v13+
 *   does this via the vitest plugin, but we pin it explicitly for clarity)
 * - Polyfills jsdom gaps: `window.matchMedia` (not provided by default)
 *   and a working `localStorage` (vitest v4's `--localstorage-file`
 *   feature produces a broken localStorage when the flag is malformed
 *   — see Nav Bar Completion session log, April 2026).
 */

import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});

// ── jsdom polyfills ────────────────────────────────────────────────

// `window.matchMedia` isn't provided by jsdom. Tests that check
// `prefers-color-scheme` (e.g. theme-mode useMode hook, Portal
// ResetPassword system-pref fallback) need a stub.
if (typeof window !== "undefined" && !window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string): MediaQueryList => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    }),
  });
}

// In-memory localStorage shim. jsdom normally provides one, but
// vitest v4's `--localstorage-file` opt-in (surfaced by the
// `Warning: --localstorage-file was provided without a valid path`
// message) can leave it in a broken state where `.getItem` is
// undefined. This installs an always-working in-memory Storage
// implementation if the current one is missing any method.
// `ResizeObserver` isn't provided by jsdom. Phase R-1's
// SelectionOverlay observes the selected widget's bounding rect, and
// any other component using ResizeObserver in tests needs this stub.
if (typeof globalThis !== "undefined" && !(globalThis as { ResizeObserver?: unknown }).ResizeObserver) {
  class ResizeObserverStub {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  ;(globalThis as { ResizeObserver?: unknown }).ResizeObserver =
    ResizeObserverStub
}

if (
  typeof window !== "undefined" &&
  (typeof window.localStorage?.getItem !== "function" ||
    typeof window.localStorage?.setItem !== "function")
) {
  const store = new Map<string, string>();
  const shim: Storage = {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (key: string) => (store.has(key) ? store.get(key)! : null),
    key: (idx: number) => Array.from(store.keys())[idx] ?? null,
    removeItem: (key: string) => {
      store.delete(key);
    },
    setItem: (key: string, value: string) => {
      store.set(key, String(value));
    },
  };
  Object.defineProperty(window, "localStorage", {
    writable: true,
    value: shim,
  });
}
