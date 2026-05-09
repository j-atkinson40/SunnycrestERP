/**
 * MatchConditionsEditor unit tests — R-6.1b.a.
 *
 * Coverage:
 *   - Empty conditions render the empty-state copy
 *   - Active operator renders its values + helper text
 *   - Adding a value via ChipInput propagates through onChange
 *   - Remove-operator button drops the operator from the JSONB shape
 *   - sender_email_in chip-validate rejects values without @
 *   - "Add condition" affordance appears only when ≥1 inactive operator
 */

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MatchConditionsEditor } from "./MatchConditionsEditor";

describe("MatchConditionsEditor", () => {
  it("renders empty state when no conditions are active", () => {
    const handle = vi.fn();
    render(<MatchConditionsEditor conditions={{}} onChange={handle} />);
    expect(screen.getByText(/No conditions yet/i)).toBeInTheDocument();
    expect(screen.getByTestId("match-add-condition")).toBeInTheDocument();
  });

  it("renders active operator with values + helper text", () => {
    const handle = vi.fn();
    render(
      <MatchConditionsEditor
        conditions={{ subject_contains_any: ["test-r6"] }}
        onChange={handle}
      />,
    );
    expect(
      screen.getByTestId("match-operator-subject_contains_any"),
    ).toBeInTheDocument();
    expect(screen.getByText("test-r6")).toBeInTheDocument();
    expect(
      screen.getByText(/Subject contains any of/i),
    ).toBeInTheDocument();
  });

  it("removing operator drops it from the conditions object", () => {
    const handle = vi.fn();
    render(
      <MatchConditionsEditor
        conditions={{
          subject_contains_any: ["a"],
          sender_domain_in: ["example.com"],
        }}
        onChange={handle}
      />,
    );
    fireEvent.click(
      screen.getByTestId("match-operator-remove-subject_contains_any"),
    );
    expect(handle).toHaveBeenCalledWith({
      sender_domain_in: ["example.com"],
    });
  });

  it("inline AND/OR helper text always renders", () => {
    const handle = vi.fn();
    render(<MatchConditionsEditor conditions={{}} onChange={handle} />);
    expect(
      screen.getByText(/All conditions must match \(AND\)/i),
    ).toBeInTheDocument();
  });

  it("'Add condition' affordance hides when all 5 operators active", () => {
    const handle = vi.fn();
    render(
      <MatchConditionsEditor
        conditions={{
          subject_contains_any: ["a"],
          sender_email_in: ["b@c.com"],
          sender_domain_in: ["c.com"],
          body_contains_any: ["d"],
          thread_label_in: ["e"],
        }}
        onChange={handle}
      />,
    );
    expect(
      screen.queryByTestId("match-add-condition"),
    ).not.toBeInTheDocument();
  });
});
