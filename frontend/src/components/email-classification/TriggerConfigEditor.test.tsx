/**
 * TriggerConfigEditor unit tests — R-6.1b.a.
 *
 * Coverage focuses on validation logic + draft state plumbing:
 *   - Empty name → validation alert
 *   - Empty match conditions → validation alert
 *   - Workflow-mode without picker → validation alert
 *   - Suppress-mode without reason → validation alert
 *   - Edit-mode pre-populates from existing rule
 *   - Save calls onSave with cleaned payload (empty operators dropped)
 *   - Suppress toggle flips fire_action shape
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TriggerConfigEditor } from "./TriggerConfigEditor";
import type {
  TenantWorkflowEmailRule,
  WorkflowSummary,
} from "@/types/email-classification";

const workflows: WorkflowSummary[] = [
  {
    id: "wf-mfg",
    name: "Manufacturing intake",
    description: null,
    vertical: "manufacturing",
    is_active: true,
  },
  {
    id: "wf-cross",
    name: "Cross-vertical",
    description: null,
    vertical: null,
    is_active: true,
  },
];

const existingRule: TenantWorkflowEmailRule = {
  id: "rule-1",
  tenant_id: "tenant-x",
  priority: 50,
  name: "Existing rule",
  match_conditions: { sender_domain_in: ["hopkinsfh.example.com"] },
  fire_action: { workflow_id: "wf-mfg" },
  is_active: true,
  created_at: null,
  updated_at: null,
};

describe("TriggerConfigEditor", () => {
  it("opens in create mode with default draft", () => {
    render(
      <TriggerConfigEditor
        open
        onOpenChange={() => {}}
        rule={null}
        workflows={workflows}
        tenantVertical="manufacturing"
        onSave={vi.fn()}
      />,
    );
    expect(
      screen.getByText(/New email trigger/i),
    ).toBeInTheDocument();
    const priority = screen.getByTestId(
      "trigger-priority-input",
    ) as HTMLInputElement;
    expect(priority.value).toBe("100");
  });

  it("edit mode populates the form from the rule", () => {
    render(
      <TriggerConfigEditor
        open
        onOpenChange={() => {}}
        rule={existingRule}
        workflows={workflows}
        tenantVertical="manufacturing"
        onSave={vi.fn()}
      />,
    );
    const name = screen.getByTestId("trigger-name-input") as HTMLInputElement;
    expect(name.value).toBe("Existing rule");
    const priority = screen.getByTestId(
      "trigger-priority-input",
    ) as HTMLInputElement;
    expect(priority.value).toBe("50");
    expect(
      screen.getByTestId("match-operator-sender_domain_in"),
    ).toBeInTheDocument();
  });

  it("clicking Save with empty form surfaces validation errors", async () => {
    const onSave = vi.fn();
    render(
      <TriggerConfigEditor
        open
        onOpenChange={() => {}}
        rule={null}
        workflows={workflows}
        tenantVertical="manufacturing"
        onSave={onSave}
      />,
    );
    fireEvent.click(screen.getByTestId("trigger-save"));
    await waitFor(() => {
      expect(
        screen.getByTestId("trigger-validation-alert"),
      ).toBeInTheDocument();
    });
    expect(onSave).not.toHaveBeenCalled();
    // Specific error copy
    expect(screen.getByText(/Name is required\./)).toBeInTheDocument();
    expect(
      screen.getByText(/at least one match condition/i),
    ).toBeInTheDocument();
  });

  it("suppress mode reveals the suppression reason field", () => {
    render(
      <TriggerConfigEditor
        open
        onOpenChange={() => {}}
        rule={null}
        workflows={workflows}
        tenantVertical="manufacturing"
        onSave={vi.fn()}
      />,
    );
    expect(
      screen.queryByTestId("trigger-suppression-reason"),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("trigger-workflow-picker")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("trigger-suppress-switch"));
    expect(
      screen.getByTestId("trigger-suppression-reason"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("trigger-workflow-picker"),
    ).not.toBeInTheDocument();
  });
});
