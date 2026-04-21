/**
 * theme-mode — vitest unit tests (Nav Bar Completion, April 2026).
 *
 * Covers the runtime API + both hook variants:
 *   - getMode reads from DOM
 *   - setMode applies attribute + persists to localStorage
 *   - toggleMode flips between modes
 *   - clearMode removes storage + reverts to system preference
 *   - useThemeMode returns [mode, setter] tuple
 *   - useMode returns {mode, toggle} object (ergonomic alias)
 *
 * The existing flash-mitigation script in index.html uses the same
 * `bridgeable-mode` localStorage key; this module must stay compatible.
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  clearMode,
  getMode,
  setMode,
  toggleMode,
  useMode,
  useThemeMode,
} from "./theme-mode";

const STORAGE_KEY = "bridgeable-mode";

beforeEach(() => {
  document.documentElement.removeAttribute("data-mode");
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* noop */
  }
});

afterEach(() => {
  document.documentElement.removeAttribute("data-mode");
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* noop */
  }
});

describe("getMode", () => {
  it("returns 'light' when data-mode attribute absent", () => {
    expect(getMode()).toBe("light");
  });

  it("returns 'dark' when data-mode='dark' on <html>", () => {
    document.documentElement.setAttribute("data-mode", "dark");
    expect(getMode()).toBe("dark");
  });
});

describe("setMode", () => {
  it("applies data-mode='dark' when set to 'dark'", () => {
    setMode("dark");
    expect(document.documentElement.getAttribute("data-mode")).toBe("dark");
  });

  it("removes data-mode when set to 'light' (absence = light)", () => {
    setMode("dark");
    setMode("light");
    expect(document.documentElement.getAttribute("data-mode")).toBeNull();
  });

  it("persists the canonical localStorage key 'bridgeable-mode'", () => {
    // Key MUST match the flash-mitigation script in index.html.
    setMode("dark");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("dark");
    setMode("light");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("light");
  });
});

describe("toggleMode", () => {
  it("flips light → dark", () => {
    expect(getMode()).toBe("light");
    expect(toggleMode()).toBe("dark");
    expect(document.documentElement.getAttribute("data-mode")).toBe("dark");
  });

  it("flips dark → light", () => {
    setMode("dark");
    expect(toggleMode()).toBe("light");
    expect(document.documentElement.getAttribute("data-mode")).toBeNull();
  });
});

describe("clearMode", () => {
  it("removes the stored user preference", () => {
    setMode("dark");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("dark");
    clearMode();
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });
});

describe("useThemeMode hook", () => {
  it("returns a tuple [mode, setter] reflecting current DOM state", () => {
    const { result } = renderHook(() => useThemeMode());
    expect(result.current[0]).toBe("light");
    act(() => {
      result.current[1]("dark");
    });
    expect(result.current[0]).toBe("dark");
    expect(document.documentElement.getAttribute("data-mode")).toBe("dark");
  });
});

describe("useMode ergonomic alias", () => {
  it("returns {mode, toggle} shape and toggle flips mode", () => {
    const { result } = renderHook(() => useMode());
    expect(result.current.mode).toBe("light");
    expect(typeof result.current.toggle).toBe("function");
    act(() => {
      result.current.toggle();
    });
    expect(result.current.mode).toBe("dark");
    expect(document.documentElement.getAttribute("data-mode")).toBe("dark");
  });

  it("toggle persists mode to localStorage", () => {
    const { result } = renderHook(() => useMode());
    act(() => {
      result.current.toggle();
    });
    expect(localStorage.getItem(STORAGE_KEY)).toBe("dark");
  });
});
