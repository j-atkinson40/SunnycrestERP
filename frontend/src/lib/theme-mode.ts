/**
 * Aesthetic Arc Session 1 — Visual mode runtime API.
 *
 * DESIGN_LANGUAGE.md defines two visual modes:
 *   - light: Mediterranean garden morning (the default)
 *   - dark:  high-end cocktail lounge evening
 *
 * Mode activates via the `data-mode` attribute on the <html>
 * element. Initial mode is set by a synchronous inline script
 * in `frontend/index.html` (flash-of-wrong-mode prevention).
 * This module is the programmatic surface — read, set, toggle,
 * and subscribe to mode changes from anywhere in the React tree.
 *
 * Storage: `localStorage['bridgeable-mode']` is the user's
 * explicit preference. When unset, the initial script falls back
 * to `prefers-color-scheme`. Toggling via setMode always writes
 * to localStorage (the user has expressed a preference).
 *
 * Session 1 ships this module; Session 2 wires the visible mode
 * toggle UI. Components that need reactive mode state today can
 * already consume `useThemeMode()`.
 */

import { useCallback, useEffect, useState } from "react";

export type ThemeMode = "light" | "dark";

const STORAGE_KEY = "bridgeable-mode";
const MODE_ATTR = "data-mode";

/** Get the currently-applied mode by reading the DOM attribute.
 * Returns "light" when the attribute is absent (the default).
 * Safe to call during SSR/pre-hydration — returns "light" when
 * document is undefined. */
export function getMode(): ThemeMode {
  if (typeof document === "undefined") return "light";
  return document.documentElement.getAttribute(MODE_ATTR) === "dark"
    ? "dark"
    : "light";
}

/** Set the current mode. Persists to localStorage (the user has
 * expressed an explicit preference) and updates the <html>
 * attribute atomically so the tokens.css `[data-mode="dark"]`
 * block activates or deactivates immediately.
 *
 * Dispatches a `CustomEvent("bridgeable-mode-change", { detail:
 * mode })` on `window` so subscribers (including the React hook
 * below) are notified. */
export function setMode(mode: ThemeMode): void {
  if (typeof document === "undefined") return;
  if (mode === "dark") {
    document.documentElement.setAttribute(MODE_ATTR, "dark");
  } else {
    document.documentElement.removeAttribute(MODE_ATTR);
  }
  try {
    localStorage.setItem(STORAGE_KEY, mode);
  } catch {
    /* localStorage access denied — DOM still flipped. */
  }
  window.dispatchEvent(
    new CustomEvent<ThemeMode>("bridgeable-mode-change", { detail: mode }),
  );
}

/** Toggle between light and dark. Returns the new mode. */
export function toggleMode(): ThemeMode {
  const next: ThemeMode = getMode() === "dark" ? "light" : "dark";
  setMode(next);
  return next;
}

/** Clear the explicit user preference and revert to the system
 * preference (`prefers-color-scheme`). Useful for a "follow
 * system" option in a future settings UI. */
export function clearMode(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* localStorage denied */
  }
  if (typeof window === "undefined") return;
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  setMode(prefersDark ? "dark" : "light");
  // setMode just wrote to localStorage — undo that so the user is
  // back in "follow system" mode (no explicit preference stored).
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* localStorage denied */
  }
}

/** React hook: subscribes to mode changes. Returns the current
 * mode + a setter tuple `[mode, setMode]`. Also listens for system
 * `prefers-color-scheme` changes when the user has no explicit
 * preference (no localStorage value set).
 *
 * Ergonomic alias `useMode()` below returns `{mode, toggle}` which
 * is the preferred shape for the visible header ModeToggle button.
 * Both hooks share the same underlying state — `useMode` delegates
 * to `useThemeMode` + adds a `toggle()` helper. */
export function useThemeMode(): [ThemeMode, (mode: ThemeMode) => void] {
  const [mode, setModeState] = useState<ThemeMode>(() => getMode());

  useEffect(() => {
    const onModeChange = (e: Event) => {
      const detail = (e as CustomEvent<ThemeMode>).detail;
      if (detail === "dark" || detail === "light") {
        setModeState(detail);
      }
    };
    window.addEventListener("bridgeable-mode-change", onModeChange);

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onSystemChange = (e: MediaQueryListEvent) => {
      // Only respond when the user has no explicit preference.
      let saved: string | null = null;
      try {
        saved = localStorage.getItem(STORAGE_KEY);
      } catch {
        /* localStorage denied */
      }
      if (saved === null) {
        const systemMode: ThemeMode = e.matches ? "dark" : "light";
        // Update DOM without persisting (still "follow system").
        if (systemMode === "dark") {
          document.documentElement.setAttribute(MODE_ATTR, "dark");
        } else {
          document.documentElement.removeAttribute(MODE_ATTR);
        }
        setModeState(systemMode);
      }
    };
    media.addEventListener("change", onSystemChange);

    return () => {
      window.removeEventListener("bridgeable-mode-change", onModeChange);
      media.removeEventListener("change", onSystemChange);
    };
  }, []);

  const handleSet = useCallback((next: ThemeMode) => {
    setMode(next);
  }, []);

  return [mode, handleSet];
}

/** Nav Bar Completion (Apr 2026) — ergonomic alias returning
 * `{mode, toggle}`. The visible ModeToggle button in the AppLayout
 * top header consumes this shape directly. Delegates to
 * `useThemeMode` above; no duplicate state. */
export function useMode(): { mode: ThemeMode; toggle: () => void } {
  const [mode, set] = useThemeMode();
  const toggle = useCallback(() => {
    set(mode === "dark" ? "light" : "dark");
  }, [mode, set]);
  return { mode, toggle };
}
