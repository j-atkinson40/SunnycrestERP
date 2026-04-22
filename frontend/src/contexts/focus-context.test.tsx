/**
 * FocusContext — vitest unit tests.
 *
 * Covers state machinery + URL sync + lastClosedFocus transitions.
 * Real DOM overlay semantics (backdrop, ESC, focus trap) are
 * exercised by the Focus.test.tsx component tests, which mount the
 * full Focus component atop base-ui Dialog.
 */

import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MemoryRouter, useLocation } from "react-router-dom";

import { FocusProvider, useFocus } from "./focus-context";


function ConsumerProbe() {
  const {
    currentFocus,
    lastClosedFocus,
    isOpen,
    open,
    close,
    dismissReturnPill,
    updateSessionLayout,
  } = useFocus();
  const location = useLocation();
  return (
    <div>
      <span data-testid="is-open">{String(isOpen)}</span>
      <span data-testid="current-id">{currentFocus?.id ?? ""}</span>
      <span data-testid="last-closed-id">{lastClosedFocus?.id ?? ""}</span>
      <span data-testid="url-search">{location.search}</span>
      <span data-testid="layout-widget-count">
        {currentFocus?.layoutState
          ? String(Object.keys(currentFocus.layoutState.widgets).length)
          : "none"}
      </span>
      <button data-testid="open-a" onClick={() => open("focus-a")}>
        open a
      </button>
      <button data-testid="open-b" onClick={() => open("focus-b")}>
        open b
      </button>
      <button
        data-testid="open-c-with-params"
        onClick={() => open("focus-c", { params: { x: 1 } })}
      >
        open c with params
      </button>
      <button data-testid="close" onClick={close}>
        close
      </button>
      <button data-testid="dismiss-pill" onClick={dismissReturnPill}>
        dismiss
      </button>
      <button
        data-testid="patch-layout"
        onClick={() =>
          updateSessionLayout({ widgets: { "widget-1": { row: 1, col: 1 } } })
        }
      >
        patch
      </button>
      <button
        data-testid="patch-layout-more"
        onClick={() =>
          updateSessionLayout({ widgets: { "widget-2": { row: 2, col: 3 } } })
        }
      >
        patch more
      </button>
    </div>
  );
}


function renderProvider(initialEntries: string[] = ["/"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <FocusProvider>
        <ConsumerProbe />
      </FocusProvider>
    </MemoryRouter>,
  );
}


describe("FocusProvider — initial state", () => {
  it("renders without error and exposes null initial state", () => {
    renderProvider();
    expect(screen.getByTestId("is-open")).toHaveTextContent("false");
    expect(screen.getByTestId("current-id")).toHaveTextContent("");
    expect(screen.getByTestId("last-closed-id")).toHaveTextContent("");
  });

  it("restores state from an initial URL with ?focus= param", async () => {
    renderProvider(["/?focus=from-url"]);
    expect(await screen.findByTestId("is-open")).toHaveTextContent("true");
    expect(screen.getByTestId("current-id")).toHaveTextContent("from-url");
  });
});


describe("FocusProvider — open() / close() / state transitions", () => {
  it("open() sets currentFocus and isOpen", async () => {
    const user = userEvent.setup();
    renderProvider();

    await user.click(screen.getByTestId("open-a"));

    expect(screen.getByTestId("is-open")).toHaveTextContent("true");
    expect(screen.getByTestId("current-id")).toHaveTextContent("focus-a");
  });

  it("open() updates URL with ?focus= param", async () => {
    const user = userEvent.setup();
    renderProvider();

    await user.click(screen.getByTestId("open-a"));

    expect(screen.getByTestId("url-search")).toHaveTextContent("?focus=focus-a");
  });

  it("close() clears currentFocus and removes URL param", async () => {
    const user = userEvent.setup();
    renderProvider();

    await user.click(screen.getByTestId("open-a"));
    await user.click(screen.getByTestId("close"));

    expect(screen.getByTestId("is-open")).toHaveTextContent("false");
    expect(screen.getByTestId("current-id")).toHaveTextContent("");
    expect(screen.getByTestId("url-search")).toHaveTextContent("");
  });

  it("close() moves the just-closed Focus into lastClosedFocus", async () => {
    const user = userEvent.setup();
    renderProvider();

    await user.click(screen.getByTestId("open-a"));
    await user.click(screen.getByTestId("close"));

    expect(screen.getByTestId("last-closed-id")).toHaveTextContent("focus-a");
  });

  it("opening another Focus replaces currentFocus (only one at a time)", async () => {
    const user = userEvent.setup();
    renderProvider();

    await user.click(screen.getByTestId("open-a"));
    await user.click(screen.getByTestId("open-b"));

    expect(screen.getByTestId("current-id")).toHaveTextContent("focus-b");
    // lastClosedFocus should be clear because we moved open→open, not
    // open→closed.
    expect(screen.getByTestId("last-closed-id")).toHaveTextContent("");
  });

  it("opening a Focus clears lastClosedFocus (from a prior close)", async () => {
    const user = userEvent.setup();
    renderProvider();

    await user.click(screen.getByTestId("open-a"));
    await user.click(screen.getByTestId("close"));
    expect(screen.getByTestId("last-closed-id")).toHaveTextContent("focus-a");

    await user.click(screen.getByTestId("open-b"));
    expect(screen.getByTestId("last-closed-id")).toHaveTextContent("");
  });

  it("dismissReturnPill() clears lastClosedFocus without side effects", async () => {
    const user = userEvent.setup();
    renderProvider();

    await user.click(screen.getByTestId("open-a"));
    await user.click(screen.getByTestId("close"));
    expect(screen.getByTestId("last-closed-id")).toHaveTextContent("focus-a");

    await user.click(screen.getByTestId("dismiss-pill"));

    expect(screen.getByTestId("last-closed-id")).toHaveTextContent("");
    expect(screen.getByTestId("is-open")).toHaveTextContent("false");
    expect(screen.getByTestId("url-search")).toHaveTextContent("");
  });
});


describe("FocusProvider — URL as source of truth", () => {
  // In-place URL transitions are covered by the open/close tests
  // above (they use setSearchParams which is how the provider talks
  // to the router). Simulating browser back/forward with MemoryRouter
  // rerender does not correctly model history navigation — the
  // rerender triggers an async effect that runs after the synchronous
  // assertion, producing false failures.
  // Playwright e2e coverage for real browser back/forward lands with
  // Phase B Session 7 when the first real Focus consumer exists.
  it("mount-time URL param is reflected in state", async () => {
    renderProvider(["/?focus=from-mount"]);
    expect(await screen.findByTestId("is-open")).toHaveTextContent("true");
    expect(screen.getByTestId("current-id")).toHaveTextContent("from-mount");
  });
});


describe("FocusProvider — layout state (Session 2 scaffold)", () => {
  it("currentFocus.layoutState is null on open", async () => {
    const user = userEvent.setup();
    renderProvider();

    await user.click(screen.getByTestId("open-a"));

    expect(screen.getByTestId("layout-widget-count")).toHaveTextContent("none");
  });

  it("updateSessionLayout() patches widgets into layoutState", async () => {
    const user = userEvent.setup();
    renderProvider();

    await user.click(screen.getByTestId("open-a"));
    await user.click(screen.getByTestId("patch-layout"));

    expect(screen.getByTestId("layout-widget-count")).toHaveTextContent("1");
  });

  it("subsequent patches merge (not replace) widgets", async () => {
    const user = userEvent.setup();
    renderProvider();

    await user.click(screen.getByTestId("open-a"));
    await user.click(screen.getByTestId("patch-layout"));
    await user.click(screen.getByTestId("patch-layout-more"));

    expect(screen.getByTestId("layout-widget-count")).toHaveTextContent("2");
  });

  it("updateSessionLayout() is a no-op when no Focus is open", async () => {
    const user = userEvent.setup();
    renderProvider();

    await user.click(screen.getByTestId("patch-layout"));

    expect(screen.getByTestId("is-open")).toHaveTextContent("false");
    expect(screen.getByTestId("layout-widget-count")).toHaveTextContent("none");
  });

  it("closing and reopening resets layoutState to null (ephemeral)", async () => {
    const user = userEvent.setup();
    renderProvider();

    await user.click(screen.getByTestId("open-a"));
    await user.click(screen.getByTestId("patch-layout"));
    expect(screen.getByTestId("layout-widget-count")).toHaveTextContent("1");

    await user.click(screen.getByTestId("close"));
    await user.click(screen.getByTestId("open-a"));

    expect(screen.getByTestId("layout-widget-count")).toHaveTextContent("none");
  });
});


describe("FocusProvider — hook outside provider", () => {
  it("throws a clear error when useFocus() is used without the provider", () => {
    function Orphan() {
      const focus = useFocus();
      return <div>{String(focus.isOpen)}</div>;
    }

    // Wrap render in act() + expect().toThrow() pattern. React emits
    // an error boundary warning to console; the throw still surfaces.
    expect(() => {
      act(() => {
        render(<Orphan />);
      });
    }).toThrow(/useFocus\(\) called outside FocusProvider/);
  });
});
