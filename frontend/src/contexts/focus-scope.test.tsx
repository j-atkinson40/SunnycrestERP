/**
 * Scope that survives the URL.
 *
 * ⚠️ THE CLAIM IS THAT A SCOPED ENTRANCE SURVIVES A REFRESH AND A SHARED LINK.
 * Before 2026-09-10 `open()` wrote params to a ref and set only `?focus=`, so
 * scope evaporated on reload — while the module docstring called the URL the
 * source of truth. Nothing consumed params at all.
 */

import { act, render, screen } from "@testing-library/react";
// ⚠️ `react-router-dom`, matching focus-context.test.tsx. Importing
// MemoryRouter from `react-router` while the provider's hooks resolve through
// `react-router-dom` yields two separate context instances and a
// "useLocation() may be used only in the context of a <Router>" that looks
// like a missing wrapper rather than a mismatched one.
import { MemoryRouter, useSearchParams } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { FocusProvider, useFocus } from "./focus-context";

function Harness({ onReady }: { onReady?: (v: ReturnType<typeof useFocus>) => void }) {
  const focus = useFocus();
  const [sp] = useSearchParams();
  onReady?.(focus);
  return (
    <div>
      <span data-testid="url">{sp.toString()}</span>
      <span data-testid="params">{JSON.stringify(focus.currentFocus?.params ?? null)}</span>
    </div>
  );
}

function renderAt(initial: string) {
  let api: ReturnType<typeof useFocus> | null = null;
  render(
    <MemoryRouter initialEntries={[initial]}>
      <FocusProvider>
        <Harness onReady={(v) => { api = v; }} />
      </FocusProvider>
    </MemoryRouter>,
  );
  return () => api!;
}

describe("Focus scope in the URL", () => {
  it("open() writes the predicate into the URL", async () => {
    const get = renderAt("/");
    await act(async () => {
      get().open("test-kanban", { params: { due_date: "2026-09-10" } });
    });
    expect(screen.getByTestId("url").textContent).toContain("fscope");
    expect(screen.getByTestId("url").textContent).toContain("due_date");
  });

  it("⚠️ a DEEP LINK is scoped — the URL alone is enough", async () => {
    // The regression. With scope in a ref, this rendered unscoped: there is no
    // ref on a fresh load, and an unscoped landing is the
    // two-steps-to-one-thing failure the peek was reverted for.
    renderAt(
      '/?focus=test-kanban&fscope=' +
        encodeURIComponent(JSON.stringify({ due_date: "2026-09-10" })),
    );
    await act(async () => {});
    expect(screen.getByTestId("params").textContent).toContain("2026-09-10");
  });

  it("round-trips types, not just strings", async () => {
    // ⚠️ Per-key query params flatten everything to strings. A predicate that
    // round-tripped `false` as `"false"` would re-derive against a different
    // world than the sentence described.
    renderAt(
      '/?focus=test-kanban&fscope=' +
        encodeURIComponent(
          JSON.stringify({ include_resolved: false, severity_in: ["critical", "high"] }),
        ),
    );
    await act(async () => {});
    const parsed = JSON.parse(screen.getByTestId("params").textContent!);
    expect(parsed.include_resolved).toBe(false);
    expect(parsed.severity_in).toEqual(["critical", "high"]);
  });

  it("CONTROL: an unscoped Focus has empty params, not a crash", async () => {
    // Unscoped is a real state — not every entrance names a subset.
    renderAt("/?focus=test-kanban");
    await act(async () => {});
    expect(screen.getByTestId("params").textContent).toBe("{}");
  });

  it("a malformed fscope leaves the Focus openable and unscoped", async () => {
    // A hand-edited URL should degrade to unscoped, not blank the surface.
    renderAt("/?focus=test-kanban&fscope=not-json");
    await act(async () => {});
    expect(screen.getByTestId("params").textContent).toBe("{}");
  });

  it("close() removes the scope with the focus", async () => {
    const get = renderAt("/");
    await act(async () => {
      get().open("test-kanban", { params: { due_date: "2026-09-10" } });
    });
    await act(async () => { get().close(); });
    const url = screen.getByTestId("url").textContent ?? "";
    expect(url).not.toContain("fscope");
    expect(url).not.toContain("focus=");
  });
});
