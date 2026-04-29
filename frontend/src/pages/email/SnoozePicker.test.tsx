/**
 * SnoozePicker tests — Phase W-4b Layer 1 Step 4b.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SnoozePicker } from "./SnoozePicker";


describe("SnoozePicker", () => {
  it("renders 4 presets", () => {
    render(<SnoozePicker onPick={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByTestId("snooze-preset-1-hour")).toBeInTheDocument();
    expect(screen.getByTestId("snooze-preset-4-hours")).toBeInTheDocument();
    expect(
      screen.getByTestId("snooze-preset-tomorrow-9am"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("snooze-preset-next-week")).toBeInTheDocument();
  });

  it("clicking a preset calls onPick with future date", async () => {
    const user = userEvent.setup();
    const onPick = vi.fn();
    render(<SnoozePicker onPick={onPick} onCancel={vi.fn()} />);
    await user.click(screen.getByTestId("snooze-preset-1-hour"));
    expect(onPick).toHaveBeenCalledTimes(1);
    const callDate = onPick.mock.calls[0][0] as Date;
    expect(callDate.getTime()).toBeGreaterThan(Date.now());
  });

  it("custom datetime input + submit", async () => {
    const user = userEvent.setup();
    const onPick = vi.fn();
    render(<SnoozePicker onPick={onPick} onCancel={vi.fn()} />);
    const future = new Date(Date.now() + 48 * 3600 * 1000);
    const isoLocal = future.toISOString().slice(0, 16);
    await user.type(screen.getByTestId("snooze-custom-input"), isoLocal);
    await user.click(screen.getByTestId("snooze-custom-submit"));
    expect(onPick).toHaveBeenCalledTimes(1);
  });

  it("custom past date does not fire onPick", async () => {
    const user = userEvent.setup();
    const onPick = vi.fn();
    render(<SnoozePicker onPick={onPick} onCancel={vi.fn()} />);
    const past = new Date(Date.now() - 48 * 3600 * 1000);
    const isoLocal = past.toISOString().slice(0, 16);
    await user.type(screen.getByTestId("snooze-custom-input"), isoLocal);
    await user.click(screen.getByTestId("snooze-custom-submit"));
    expect(onPick).not.toHaveBeenCalled();
  });
});
