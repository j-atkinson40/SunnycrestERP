/**
 * ReturnPill — vitest tests.
 *
 * Exercises visibility logic + click-to-reopen + dismiss. Countdown
 * behavior is Session 4 scope; this file only tests the UI-only
 * scaffolding shipped in Session 1.
 */

import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { FocusProvider, useFocus } from "@/contexts/focus-context";
import { Focus } from "./Focus";
import { ReturnPill } from "./ReturnPill";

// Mock the focus-service HTTP client so tests don't hit the backend.
// Persistence is tested separately in test_focus_session.py (backend)
// and focus-session-api.test.ts (frontend contract).
vi.mock("@/services/focus-service", () => ({
  openFocusSession: vi.fn(async () => ({
    session: {
      id: "test-session-id",
      focus_type: "test-kanban",
      layout_state: {},
      is_active: true,
      opened_at: new Date().toISOString(),
      closed_at: null,
      last_interacted_at: new Date().toISOString(),
    },
    layout_state: null,
    source: null,
  })),
  closeFocusSession: vi.fn(async () => ({
    id: "test-session-id",
    focus_type: "test-kanban",
    layout_state: {},
    is_active: false,
    opened_at: new Date().toISOString(),
    closed_at: new Date().toISOString(),
    last_interacted_at: new Date().toISOString(),
  })),
  updateFocusLayout: vi.fn(async () => ({
    id: "test-session-id",
    focus_type: "test-kanban",
    layout_state: {},
    is_active: true,
    opened_at: new Date().toISOString(),
    closed_at: null,
    last_interacted_at: new Date().toISOString(),
  })),
  fetchFocusLayout: vi.fn(async () => ({ layout_state: null, source: null })),
  listRecentFocusSessions: vi.fn(async () => []),
}));


function Harness() {
  return (
    <MemoryRouter initialEntries={["/"]}>
      <FocusProvider>
        <Controls />
        <Focus />
        <ReturnPill />
      </FocusProvider>
    </MemoryRouter>
  );
}

function Controls() {
  const { open, close } = useFocus();
  return (
    <div>
      <button data-testid="open-a" onClick={() => open("test-kanban")}>
        open a
      </button>
      <button data-testid="close" onClick={close}>
        close
      </button>
    </div>
  );
}


describe("ReturnPill", () => {
  it("renders nothing when there is no recently-closed Focus", () => {
    render(<Harness />);
    expect(
      screen.queryByRole("button", { name: /return to/i }),
    ).not.toBeInTheDocument();
  });

  it("renders after a Focus closes, with the closed Focus's id", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByTestId("open-a"));
    await user.click(screen.getByTestId("close"));

    const returnBtn = await screen.findByRole("button", {
      name: /return to test-kanban/i,
    });
    expect(returnBtn).toBeInTheDocument();
  });

  it("clicking the pill body re-opens the previous Focus", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByTestId("open-a"));
    await user.click(screen.getByTestId("close"));

    const returnBtn = await screen.findByRole("button", {
      name: /return to test-kanban/i,
    });
    await user.click(returnBtn);

    // Focus dialog re-appears; pill disappears.
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /return to/i }),
    ).not.toBeInTheDocument();
  });

  it("clicking the X dismisses the pill without re-entering", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByTestId("open-a"));
    await user.click(screen.getByTestId("close"));

    const dismissBtn = await screen.findByRole("button", {
      name: /dismiss return pill/i,
    });
    await user.click(dismissBtn);

    expect(
      screen.queryByRole("button", { name: /return to/i }),
    ).not.toBeInTheDocument();
    // No Focus dialog should be open after dismiss.
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("hides when a new Focus is opened directly (skipping the pill)", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByTestId("open-a"));
    await user.click(screen.getByTestId("close"));
    await screen.findByRole("button", { name: /return to test-kanban/i });

    // Simulate user clicking a different entry point to open a new
    // Focus (via the same test control, since it's the same id —
    // but the same id still counts as "opening a Focus", which
    // should clear the pill).
    await user.click(screen.getByTestId("open-a"));

    expect(
      screen.queryByRole("button", { name: /return to/i }),
    ).not.toBeInTheDocument();
  });

  describe("Session 4 countdown", () => {
    beforeEach(() => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
    });
    afterEach(() => {
      vi.useRealTimers();
    });

    it("renders a countdown bar that starts at full width", async () => {
      const user = userEvent.setup({
        advanceTimers: vi.advanceTimersByTime,
      });
      render(<Harness />);
      await user.click(screen.getByTestId("open-a"));
      await user.click(screen.getByTestId("close"));
      const bar = await screen.findByTestId("focus-return-pill-countdown-bar");
      // At t=0 the bar width should be ~100%.
      expect(bar.style.width).toBe("100%");
    });

    it("auto-dismisses after 15s via the countdown expiry", async () => {
      const user = userEvent.setup({
        advanceTimers: vi.advanceTimersByTime,
      });
      render(<Harness />);
      await user.click(screen.getByTestId("open-a"));
      await user.click(screen.getByTestId("close"));
      await screen.findByTestId("focus-return-pill");
      // Advance past the 15s countdown.
      await act(async () => {
        vi.advanceTimersByTime(15_100);
      });
      expect(screen.queryByTestId("focus-return-pill")).not.toBeInTheDocument();
    });
  });
});
