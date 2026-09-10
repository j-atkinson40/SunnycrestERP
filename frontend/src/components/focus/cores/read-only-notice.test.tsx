/**
 * ⚠️ THE REFUSAL HAS TO BE VISIBLE AND HAVE A REASON.
 *
 * "Cannot act" is satisfied perfectly by hiding every control, and that is the
 * wrong answer: a Focus whose actions vanished is indistinguishable from one
 * that is broken, and the user has nothing to act on — not even "ask for the
 * permission". These pin the reason, not just the absence of an action.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ReadOnlyNotice } from "./_shared";

describe("ReadOnlyNotice", () => {
  it("says the user may see and not change", () => {
    render(<ReadOnlyNotice permission="delivery.edit" />);
    const el = screen.getByTestId("focus-read-only-notice");
    expect(el.textContent).toMatch(/view only/i);
    expect(el.textContent).toMatch(/not change/i);
  });

  it("names the permission that is missing", () => {
    // ⚠️ Without this the notice reads as "broken", which is a different and
    // unactionable message. Naming the key tells the user to ask for it.
    render(<ReadOnlyNotice permission="ar.create_quote" />);
    expect(
      screen.getByTestId("focus-read-only-notice").textContent,
    ).toContain("ar.create_quote");
  });

  it("still renders when no permission is named", () => {
    // The state is real even when the reason cannot be named; the notice must
    // not disappear and leave a silently-inert surface.
    render(<ReadOnlyNotice />);
    expect(screen.getByTestId("focus-read-only-notice")).toBeTruthy();
  });
});
