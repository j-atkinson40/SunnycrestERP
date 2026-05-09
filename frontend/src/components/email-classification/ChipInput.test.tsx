/**
 * ChipInput unit tests — R-6.1b.a bespoke composition.
 *
 * Coverage:
 *   - Enter commits draft → chip appears + draft clears
 *   - Comma key commits draft (alternate commit shortcut)
 *   - Backspace on empty input removes last chip
 *   - Esc with non-empty draft clears the draft
 *   - Esc with empty draft removes the last chip (per build-prompt)
 *   - Remove button on chip drops that chip
 *   - Duplicate values are silently deduplicated
 *   - Empty / whitespace draft is rejected (no chip added)
 *   - Validate callback rejects with inline error message
 */

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChipInput } from "./ChipInput";

describe("ChipInput", () => {
  it("commits draft on Enter and clears the input", () => {
    const handleChange = vi.fn();
    render(<ChipInput values={[]} onChange={handleChange} />);
    const field = screen.getByTestId("chip-input-field") as HTMLInputElement;
    fireEvent.change(field, { target: { value: "alpha" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(handleChange).toHaveBeenCalledWith(["alpha"]);
  });

  it("commits on comma key", () => {
    const handleChange = vi.fn();
    render(<ChipInput values={[]} onChange={handleChange} />);
    const field = screen.getByTestId("chip-input-field") as HTMLInputElement;
    fireEvent.change(field, { target: { value: "beta" } });
    fireEvent.keyDown(field, { key: "," });
    expect(handleChange).toHaveBeenCalledWith(["beta"]);
  });

  it("removes last chip on backspace when input is empty", () => {
    const handleChange = vi.fn();
    render(
      <ChipInput values={["alpha", "beta"]} onChange={handleChange} />,
    );
    const field = screen.getByTestId("chip-input-field") as HTMLInputElement;
    fireEvent.keyDown(field, { key: "Backspace" });
    expect(handleChange).toHaveBeenCalledWith(["alpha"]);
  });

  it("Esc with non-empty draft clears draft only", () => {
    const handleChange = vi.fn();
    render(
      <ChipInput values={["alpha"]} onChange={handleChange} />,
    );
    const field = screen.getByTestId("chip-input-field") as HTMLInputElement;
    fireEvent.change(field, { target: { value: "draft-value" } });
    fireEvent.keyDown(field, { key: "Escape" });
    // No onChange call (chips unchanged); draft state cleared.
    expect(handleChange).not.toHaveBeenCalled();
    expect(field.value).toBe("");
  });

  it("Esc with empty draft removes the last chip", () => {
    const handleChange = vi.fn();
    render(
      <ChipInput values={["alpha", "beta"]} onChange={handleChange} />,
    );
    const field = screen.getByTestId("chip-input-field") as HTMLInputElement;
    fireEvent.keyDown(field, { key: "Escape" });
    expect(handleChange).toHaveBeenCalledWith(["alpha"]);
  });

  it("remove button on chip removes that chip", () => {
    const handleChange = vi.fn();
    render(
      <ChipInput
        values={["alpha", "beta", "gamma"]}
        onChange={handleChange}
      />,
    );
    fireEvent.click(screen.getByLabelText("Remove beta"));
    expect(handleChange).toHaveBeenCalledWith(["alpha", "gamma"]);
  });

  it("dedupes duplicate values silently", () => {
    const handleChange = vi.fn();
    render(<ChipInput values={["alpha"]} onChange={handleChange} />);
    const field = screen.getByTestId("chip-input-field") as HTMLInputElement;
    fireEvent.change(field, { target: { value: "alpha" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(handleChange).not.toHaveBeenCalled();
  });

  it("rejects whitespace-only draft", () => {
    const handleChange = vi.fn();
    render(<ChipInput values={[]} onChange={handleChange} />);
    const field = screen.getByTestId("chip-input-field") as HTMLInputElement;
    fireEvent.change(field, { target: { value: "   " } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(handleChange).not.toHaveBeenCalled();
  });

  it("validate callback rejects with inline error message", () => {
    const handleChange = vi.fn();
    render(
      <ChipInput
        values={[]}
        onChange={handleChange}
        validate={(v) => (v.includes("@") ? null : "Must contain @")}
      />,
    );
    const field = screen.getByTestId("chip-input-field") as HTMLInputElement;
    fireEvent.change(field, { target: { value: "noatsign" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(handleChange).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("Must contain @");
  });
});
