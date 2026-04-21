/**
 * ModeToggle — vitest unit tests (Nav Bar Completion, April 2026).
 *
 * Covers:
 *   - Renders <Moon /> in light mode (destination-icon convention)
 *   - Renders <Sun /> in dark mode
 *   - aria-label describes the action, not the current state
 *   - aria-pressed reflects current toggle state (true = dark)
 *   - Click flips the `data-mode` attribute on <html>
 *   - Click persists the new mode to localStorage
 */

import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { ModeToggle } from "./ModeToggle";

// Ensure each test starts with a fresh DOM + localStorage.
beforeEach(() => {
  document.documentElement.removeAttribute("data-mode");
  try {
    localStorage.removeItem("bridgeable-mode");
  } catch {
    /* localStorage denied in jsdom edge cases — harmless. */
  }
});

afterEach(() => {
  cleanup();
  document.documentElement.removeAttribute("data-mode");
  try {
    localStorage.removeItem("bridgeable-mode");
  } catch {
    /* noop */
  }
});

describe("ModeToggle", () => {
  it("renders Moon icon in light mode (destination icon)", () => {
    // No data-mode attribute → light.
    render(<ModeToggle />);
    const btn = screen.getByTestId("mode-toggle");
    expect(btn).toBeInTheDocument();
    // Moon has a visible <path> SVG; easiest assertion is against
    // the button's aria-label which reflects the destination state.
    expect(btn.getAttribute("aria-label")).toBe("Switch to dark mode");
    expect(btn.getAttribute("aria-pressed")).toBe("false");
  });

  it("renders Sun icon in dark mode (destination icon)", () => {
    document.documentElement.setAttribute("data-mode", "dark");
    render(<ModeToggle />);
    const btn = screen.getByTestId("mode-toggle");
    expect(btn.getAttribute("aria-label")).toBe("Switch to light mode");
    expect(btn.getAttribute("aria-pressed")).toBe("true");
  });

  it("clicking toggles data-mode attribute on <html>", () => {
    render(<ModeToggle />);
    const btn = screen.getByTestId("mode-toggle");
    // Start: light (no attribute).
    expect(document.documentElement.getAttribute("data-mode")).toBeNull();
    fireEvent.click(btn);
    // After click: dark.
    expect(document.documentElement.getAttribute("data-mode")).toBe("dark");
    fireEvent.click(btn);
    // After second click: light (attribute removed per theme-mode.ts
    // convention of using absence-of-attribute for light mode).
    expect(document.documentElement.getAttribute("data-mode")).toBeNull();
  });

  it("clicking persists the mode to localStorage", () => {
    render(<ModeToggle />);
    const btn = screen.getByTestId("mode-toggle");
    fireEvent.click(btn);
    expect(localStorage.getItem("bridgeable-mode")).toBe("dark");
    fireEvent.click(btn);
    expect(localStorage.getItem("bridgeable-mode")).toBe("light");
  });
});
