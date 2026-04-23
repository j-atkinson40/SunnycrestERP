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
      {/* Uses a registered Session-2 stub id so the dispatcher
          resolves to KanbanCore instead of the unknown-focus
          error state. Session 1 used an ad-hoc id; Session 2's
          dispatcher requires registry presence. */}
      <button data-testid="open-a" onClick={() => open("test-kanban")}>
        open kanban
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
    render(<Harness openOnMount="test-kanban" />);

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("aria-label", "Focus: test-kanban");
  });

  it("opening a Focus renders the dispatched core for its mode", async () => {
    render(<Harness openOnMount={null} />);

    const user = userEvent.setup();
    await user.click(screen.getByTestId("open-a"));

    // KanbanCore renders its displayName as title + "Core mode · kanban" eyebrow.
    expect(await screen.findByText("Kanban stub")).toBeInTheDocument();
    expect(screen.getByText(/Core mode.*kanban/i)).toBeInTheDocument();
  });

  it("pressing Escape closes the Focus", async () => {
    render(<Harness openOnMount="test-kanban" />);

    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("sets aria-modal via the base-ui dialog primitive", async () => {
    render(<Harness openOnMount="test-kanban" />);

    const dialog = await screen.findByRole("dialog");
    // base-ui Dialog.Popup renders role="dialog" with aria-modal="true"
    // when the Dialog.Root is modal (default). This guards against
    // accidental non-modal configuration.
    expect(dialog).toHaveAttribute("aria-modal", "true");
  });

  it("Canvas renders AFTER Popup in DOM (Session 3.8.1 layering fix)", async () => {
    // Issues 2 + 3 regression guard. Pre-Session-3.8.1, Canvas was
    // mounted BEFORE Popup in the Dialog.Portal — both at z-index=
    // var(--z-focus), DOM order determines paint order, Popup won.
    // That made the icon button (rendered inside Canvas) invisible
    // behind the viewport-filling core in icon tier, and made the
    // stack rail appear "under" the growing core during
    // stack↔canvas transitions. Swapping DOM order puts accessories
    // (canvas widgets, stack rail, icon) in front of core — correct
    // for every tier. This test catches any future re-reordering.
    render(<Harness openOnMount="test-kanban" />);

    const dialog = await screen.findByRole("dialog");
    const canvas = document.querySelector('[data-slot="focus-canvas"]');
    expect(canvas).toBeInTheDocument();

    // Verify compareDocumentPosition: canvas FOLLOWS dialog in DOM.
    // DOCUMENT_POSITION_FOLLOWING bit (4) set when second arg comes
    // after first in tree order.
    expect(
      dialog.compareDocumentPosition(canvas!) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });
});
