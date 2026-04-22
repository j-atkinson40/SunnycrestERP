/**
 * Focus component — vitest tests.
 *
 * Exercises the render surface + base-ui Dialog integration. The
 * FocusProvider state machinery (URL sync, lastClosedFocus, etc.)
 * has its own dedicated test file at contexts/focus-context.test.tsx.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { FocusProvider, useFocus } from "@/contexts/focus-context";
import { Focus } from "./Focus";


function Harness({ openOnMount }: { openOnMount: string | null }) {
  return (
    <MemoryRouter
      initialEntries={openOnMount ? [`/?focus=${openOnMount}`] : ["/"]}
    >
      <FocusProvider>
        <OpenerButtons />
        <Focus />
      </FocusProvider>
    </MemoryRouter>
  );
}

function OpenerButtons() {
  const { open } = useFocus();
  return (
    <div>
      <button data-testid="open-a" onClick={() => open("focus-a")}>
        open a
      </button>
    </div>
  );
}


describe("Focus component", () => {
  it("renders nothing observable when currentFocus is null", () => {
    render(<Harness openOnMount={null} />);

    // Popup should not be in the DOM when closed. base-ui portals
    // mount outside the render tree but are still queryable.
    expect(
      screen.queryByRole("dialog", { hidden: true }),
    ).not.toBeInTheDocument();
  });

  it("renders backdrop + popup when a Focus is open", async () => {
    render(<Harness openOnMount="focus-a" />);

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("aria-label", "Focus: focus-a");
  });

  it("opening a Focus renders the placeholder content with the id", async () => {
    render(<Harness openOnMount={null} />);

    const user = userEvent.setup();
    await user.click(screen.getByTestId("open-a"));

    expect(await screen.findByText("focus-a")).toBeInTheDocument();
    expect(
      screen.getByText(/Anchored core placeholder/i),
    ).toBeInTheDocument();
  });

  it("pressing Escape closes the Focus", async () => {
    render(<Harness openOnMount="focus-a" />);

    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("sets aria-modal via the base-ui dialog primitive", async () => {
    render(<Harness openOnMount="focus-a" />);

    const dialog = await screen.findByRole("dialog");
    // base-ui Dialog.Popup renders role="dialog" with aria-modal="true"
    // when the Dialog.Root is modal (default). This guards against
    // accidental non-modal configuration.
    expect(dialog).toHaveAttribute("aria-modal", "true");
  });
});
