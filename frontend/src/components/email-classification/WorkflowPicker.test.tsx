/**
 * WorkflowPicker unit tests — R-6.1b.a.
 *
 * Coverage focuses on the pure `filterWorkflowsForPicker` predicate
 * because the Base UI Select primitive renders inside a Portal and
 * jsdom's snapshot doesn't reach the popup content reliably for the
 * SelectItem assertions. Filter semantics are the load-bearing
 * contract; render-time test ensures the trigger mounts.
 *
 * Coverage:
 *   - Universal-fallback when tenantVertical is null/undefined
 *   - Vertical-match filter respects null vertical (cross-vertical
 *     workflows always visible)
 *   - Inactive workflows excluded
 *   - SelectTrigger mounts in render shape
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  filterWorkflowsForPicker,
  WorkflowPicker,
} from "./WorkflowPicker";
import type { WorkflowSummary } from "@/types/email-classification";

const fixtures: WorkflowSummary[] = [
  {
    id: "wf-mfg",
    name: "Mfg quote",
    description: "Manufacturing quote intake",
    vertical: "manufacturing",
    is_active: true,
  },
  {
    id: "wf-fh",
    name: "FH arrangement",
    description: "Funeral home arrangement",
    vertical: "funeral_home",
    is_active: true,
  },
  {
    id: "wf-cross",
    name: "Cross-vertical follow-up",
    description: null,
    vertical: null,
    is_active: true,
  },
  {
    id: "wf-inactive",
    name: "Old retired",
    description: null,
    vertical: "manufacturing",
    is_active: false,
  },
];

describe("filterWorkflowsForPicker", () => {
  it("null tenantVertical shows every active workflow (universal fallback)", () => {
    const out = filterWorkflowsForPicker(fixtures, null);
    expect(out.map((w) => w.id)).toEqual(["wf-mfg", "wf-fh", "wf-cross"]);
  });

  it("manufacturing tenant sees mfg + cross-vertical, not FH", () => {
    const out = filterWorkflowsForPicker(fixtures, "manufacturing");
    expect(out.map((w) => w.id).sort()).toEqual(
      ["wf-cross", "wf-mfg"].sort(),
    );
  });

  it("funeral_home tenant sees FH + cross-vertical, not mfg", () => {
    const out = filterWorkflowsForPicker(fixtures, "funeral_home");
    expect(out.map((w) => w.id).sort()).toEqual(
      ["wf-cross", "wf-fh"].sort(),
    );
  });

  it("inactive workflows always excluded", () => {
    const out = filterWorkflowsForPicker(fixtures, null);
    expect(out.find((w) => w.id === "wf-inactive")).toBeUndefined();
  });
});

describe("WorkflowPicker render", () => {
  it("renders SelectTrigger with placeholder when value=null", () => {
    render(
      <WorkflowPicker
        workflows={fixtures}
        value={null}
        onChange={vi.fn()}
        tenantVertical="manufacturing"
        placeholder="Pick one…"
      />,
    );
    expect(screen.getByTestId("workflow-picker")).toBeInTheDocument();
  });
});
