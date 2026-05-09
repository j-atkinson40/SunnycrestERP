/**
 * ConfidenceFloorEditor unit tests — R-6.1b.a.
 *
 * Coverage:
 *   - getFloorWarning bands (low / mid / high)
 *   - Default state mirrors persisted floors
 *   - Dirty detection enables Save; clean disables
 *   - Save calls onSave with parsed values
 *   - Discard reverts to persisted values
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  ConfidenceFloorEditor,
  getFloorWarning,
} from "./ConfidenceFloorEditor";

describe("getFloorWarning", () => {
  it("flags very low values", () => {
    expect(getFloorWarning(0.1)).toMatch(/Very low/);
    expect(getFloorWarning(0.29)).toMatch(/Very low/);
  });

  it("returns null for canonical band", () => {
    expect(getFloorWarning(0.55)).toBeNull();
    expect(getFloorWarning(0.65)).toBeNull();
    expect(getFloorWarning(0.85)).toBeNull();
  });

  it("flags very high values", () => {
    expect(getFloorWarning(0.91)).toMatch(/Very high/);
    expect(getFloorWarning(0.99)).toMatch(/Very high/);
  });
});

describe("ConfidenceFloorEditor", () => {
  it("renders default values + disables Save when not dirty", () => {
    render(
      <ConfidenceFloorEditor
        floors={{ tier_2: 0.55, tier_3: 0.65 }}
        onSave={vi.fn()}
      />,
    );
    const saveBtn = screen.getByTestId("floor-save") as HTMLButtonElement;
    expect(saveBtn.disabled).toBe(true);
    const tier2 = screen.getByTestId(
      "floor-tier-2-input",
    ) as HTMLInputElement;
    expect(parseFloat(tier2.value)).toBeCloseTo(0.55);
  });

  it("changing input enables Save", () => {
    render(
      <ConfidenceFloorEditor
        floors={{ tier_2: 0.55, tier_3: 0.65 }}
        onSave={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByTestId("floor-tier-2-input"), {
      target: { value: "0.7" },
    });
    const saveBtn = screen.getByTestId("floor-save") as HTMLButtonElement;
    expect(saveBtn.disabled).toBe(false);
  });

  it("very low input renders the warning chip", () => {
    render(
      <ConfidenceFloorEditor
        floors={{ tier_2: 0.55, tier_3: 0.65 }}
        onSave={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByTestId("floor-tier-2-input"), {
      target: { value: "0.2" },
    });
    expect(
      screen.getByTestId("floor-tier-2-warning"),
    ).toHaveTextContent(/Very low/);
  });

  it("Save calls onSave with parsed values", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <ConfidenceFloorEditor
        floors={{ tier_2: 0.55, tier_3: 0.65 }}
        onSave={onSave}
      />,
    );
    fireEvent.change(screen.getByTestId("floor-tier-2-input"), {
      target: { value: "0.7" },
    });
    fireEvent.change(screen.getByTestId("floor-tier-3-input"), {
      target: { value: "0.8" },
    });
    fireEvent.click(screen.getByTestId("floor-save"));
    await waitFor(() => {
      expect(onSave).toHaveBeenCalledTimes(1);
    });
    expect(onSave).toHaveBeenCalledWith({ tier_2: 0.7, tier_3: 0.8 });
  });

  it("Discard reverts to persisted floors", () => {
    render(
      <ConfidenceFloorEditor
        floors={{ tier_2: 0.55, tier_3: 0.65 }}
        onSave={vi.fn()}
      />,
    );
    const tier2 = screen.getByTestId(
      "floor-tier-2-input",
    ) as HTMLInputElement;
    fireEvent.change(tier2, { target: { value: "0.7" } });
    fireEvent.click(screen.getByTestId("floor-discard"));
    expect(parseFloat(tier2.value)).toBeCloseTo(0.55);
  });
});
