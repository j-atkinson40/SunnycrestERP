/**
 * Vitest — WorkflowEmailTriggersSection (R-6.1b.b).
 *
 * Coverage:
 *   - Mounts header + inline copy + Add CTA (when not readOnly)
 *   - Empty state when no rules
 *   - Lists rules filtered by workflow_id
 *   - Add rule opens TriggerConfigEditor
 *   - Tier 3 toggle calls setTier3Enrollment
 *   - Tier 3 toggle reverts on failure
 *   - Read-only mode hides Add + edit buttons
 *   - Delete asks for confirmation
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/services/email-classification-service", () => ({
  listRules: vi.fn(),
  createRule: vi.fn(),
  updateRule: vi.fn(),
  deleteRule: vi.fn(),
  setTier3Enrollment: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import {
  deleteRule,
  listRules,
  setTier3Enrollment,
} from "@/services/email-classification-service";
import type {
  TenantWorkflowEmailRule,
  WorkflowSummary,
} from "@/types/email-classification";

import { WorkflowEmailTriggersSection } from "./WorkflowEmailTriggersSection";

const workflows: WorkflowSummary[] = [
  {
    id: "wf-1",
    name: "Hopkins intake",
    description: null,
    vertical: "manufacturing",
    is_active: true,
  },
];

const rule1: TenantWorkflowEmailRule = {
  id: "rule_1",
  tenant_id: "t1",
  priority: 100,
  name: "Hopkins ops",
  match_conditions: { sender_domain_in: ["hopkinsfh.com"] },
  fire_action: { workflow_id: "wf-1" },
  is_active: true,
  created_at: null,
  updated_at: null,
};

beforeEach(() => {
  // Default: no rules.
  vi.mocked(listRules).mockResolvedValue([]);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("WorkflowEmailTriggersSection", () => {
  it("renders header + inline copy + Add CTA", async () => {
    render(
      <WorkflowEmailTriggersSection
        workflowId="wf-1"
        workflowName="Hopkins intake"
        workflows={workflows}
        tenantVertical="manufacturing"
        initialTier3Enrolled={false}
      />,
    );
    expect(screen.getByText("Email triggers")).toBeTruthy();
    expect(screen.getByText(/route inbound messages/i)).toBeTruthy();
    expect(screen.getByTestId("workflow-email-triggers-add")).toBeTruthy();
  });

  it("filters listRules call by workflow_id", async () => {
    render(
      <WorkflowEmailTriggersSection
        workflowId="wf-99"
        workflowName="Other"
        workflows={workflows}
        tenantVertical="manufacturing"
        initialTier3Enrolled={false}
      />,
    );
    await waitFor(() => {
      expect(listRules).toHaveBeenCalledWith({ workflow_id: "wf-99" });
    });
  });

  it("renders empty state when no rules", async () => {
    render(
      <WorkflowEmailTriggersSection
        workflowId="wf-1"
        workflowName="Hopkins intake"
        workflows={workflows}
        tenantVertical="manufacturing"
        initialTier3Enrolled={false}
      />,
    );
    await waitFor(() =>
      expect(
        screen.getByTestId("workflow-email-triggers-empty"),
      ).toBeTruthy(),
    );
  });

  it("renders rules list when rules exist", async () => {
    vi.mocked(listRules).mockResolvedValue([rule1]);
    render(
      <WorkflowEmailTriggersSection
        workflowId="wf-1"
        workflowName="Hopkins intake"
        workflows={workflows}
        tenantVertical="manufacturing"
        initialTier3Enrolled={false}
      />,
    );
    await waitFor(() =>
      expect(
        screen.getByTestId("workflow-email-triggers-row-rule_1"),
      ).toBeTruthy(),
    );
    expect(screen.getByText("Hopkins ops")).toBeTruthy();
  });

  it("Add rule opens TriggerConfigEditor", async () => {
    render(
      <WorkflowEmailTriggersSection
        workflowId="wf-1"
        workflowName="Hopkins intake"
        workflows={workflows}
        tenantVertical="manufacturing"
        initialTier3Enrolled={false}
      />,
    );
    await waitFor(() =>
      expect(
        screen.getByTestId("workflow-email-triggers-add"),
      ).toBeTruthy(),
    );
    fireEvent.click(screen.getByTestId("workflow-email-triggers-add"));
    await waitFor(() =>
      expect(screen.getByText(/New email trigger/i)).toBeTruthy(),
    );
  });

  it("Tier 3 toggle calls setTier3Enrollment", async () => {
    vi.mocked(setTier3Enrollment).mockResolvedValue({
      workflow_id: "wf-1",
      tier3_enrolled: true,
    } as never);
    render(
      <WorkflowEmailTriggersSection
        workflowId="wf-1"
        workflowName="Hopkins intake"
        workflows={workflows}
        tenantVertical="manufacturing"
        initialTier3Enrolled={false}
      />,
    );
    const toggle = screen.getByTestId("workflow-email-triggers-tier3-switch");
    fireEvent.click(toggle);
    await waitFor(() => {
      expect(setTier3Enrollment).toHaveBeenCalledWith("wf-1", true);
    });
  });

  it("Tier 3 toggle reverts state on failure", async () => {
    vi.mocked(setTier3Enrollment).mockRejectedValue(new Error("nope"));
    render(
      <WorkflowEmailTriggersSection
        workflowId="wf-1"
        workflowName="Hopkins intake"
        workflows={workflows}
        tenantVertical="manufacturing"
        initialTier3Enrolled={false}
      />,
    );
    const toggle = screen.getByTestId(
      "workflow-email-triggers-tier3-switch",
    ) as HTMLButtonElement;
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    fireEvent.click(toggle);
    await waitFor(() => expect(setTier3Enrollment).toHaveBeenCalled());
    // Reverts to unchecked after failure.
    await waitFor(() =>
      expect(toggle.getAttribute("aria-checked")).toBe("false"),
    );
  });

  it("read-only mode hides Add + edit buttons", async () => {
    vi.mocked(listRules).mockResolvedValue([rule1]);
    render(
      <WorkflowEmailTriggersSection
        workflowId="wf-1"
        workflowName="Hopkins intake"
        workflows={workflows}
        tenantVertical="manufacturing"
        initialTier3Enrolled={false}
        readOnly
      />,
    );
    await waitFor(() =>
      expect(
        screen.getByTestId("workflow-email-triggers-row-rule_1"),
      ).toBeTruthy(),
    );
    expect(
      screen.queryByTestId("workflow-email-triggers-add"),
    ).toBeNull();
    expect(
      screen.queryByTestId("workflow-email-triggers-edit-rule_1"),
    ).toBeNull();
  });

  it("delete asks confirmation + calls deleteRule on accept", async () => {
    vi.mocked(listRules).mockResolvedValue([rule1]);
    vi.mocked(deleteRule).mockResolvedValue({
      deleted: true,
      rule_id: "rule_1",
    });
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(
      <WorkflowEmailTriggersSection
        workflowId="wf-1"
        workflowName="Hopkins intake"
        workflows={workflows}
        tenantVertical="manufacturing"
        initialTier3Enrolled={false}
      />,
    );
    await waitFor(() =>
      expect(
        screen.getByTestId("workflow-email-triggers-delete-rule_1"),
      ).toBeTruthy(),
    );
    fireEvent.click(
      screen.getByTestId("workflow-email-triggers-delete-rule_1"),
    );
    expect(confirmSpy).toHaveBeenCalled();
    await waitFor(() => expect(deleteRule).toHaveBeenCalledWith("rule_1"));
    confirmSpy.mockRestore();
  });

  it("delete cancellation does NOT call deleteRule", async () => {
    vi.mocked(listRules).mockResolvedValue([rule1]);
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(
      <WorkflowEmailTriggersSection
        workflowId="wf-1"
        workflowName="Hopkins intake"
        workflows={workflows}
        tenantVertical="manufacturing"
        initialTier3Enrolled={false}
      />,
    );
    await waitFor(() =>
      expect(
        screen.getByTestId("workflow-email-triggers-delete-rule_1"),
      ).toBeTruthy(),
    );
    fireEvent.click(
      screen.getByTestId("workflow-email-triggers-delete-rule_1"),
    );
    expect(confirmSpy).toHaveBeenCalled();
    expect(deleteRule).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it("re-syncs tier3 state when initialTier3Enrolled prop changes", async () => {
    const { rerender } = render(
      <WorkflowEmailTriggersSection
        workflowId="wf-1"
        workflowName="Hopkins intake"
        workflows={workflows}
        tenantVertical="manufacturing"
        initialTier3Enrolled={false}
      />,
    );
    let toggle = screen.getByTestId(
      "workflow-email-triggers-tier3-switch",
    ) as HTMLButtonElement;
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    rerender(
      <WorkflowEmailTriggersSection
        workflowId="wf-1"
        workflowName="Hopkins intake"
        workflows={workflows}
        tenantVertical="manufacturing"
        initialTier3Enrolled
      />,
    );
    toggle = screen.getByTestId(
      "workflow-email-triggers-tier3-switch",
    ) as HTMLButtonElement;
    await waitFor(() =>
      expect(toggle.getAttribute("aria-checked")).toBe("true"),
    );
  });
});
