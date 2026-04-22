/**
 * ReturnPill — vitest tests.
 *
 * Exercises visibility logic + click-to-reopen + dismiss. Countdown
 * behavior is Session 4 scope; this file only tests the UI-only
 * scaffolding shipped in Session 1.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { FocusProvider, useFocus } from "@/contexts/focus-context";
import { Focus } from "./Focus";
import { ReturnPill } from "./ReturnPill";


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
});
