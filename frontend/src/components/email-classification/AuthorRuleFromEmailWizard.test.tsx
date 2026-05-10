/**
 * Vitest — AuthorRuleFromEmailWizard (R-6.1b.b).
 *
 * Coverage:
 *   - preFillOperatorFromEmail heuristic (3 branches: domain unique,
 *     common provider falls to subject words, fallback to sender_email)
 *   - Wizard mounts TriggerConfigEditor with pre-filled draft
 *   - Save flow: createRule + suppressClassification + onComplete
 *   - createRule failure surfaces error + does NOT call onComplete
 *   - suppressClassification failure leaves rule created + still completes
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/services/email-classification-service", () => ({
  createRule: vi.fn(),
  suppressClassification: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import {
  createRule,
  suppressClassification,
} from "@/services/email-classification-service";
import { toast } from "sonner";
import type { WorkflowSummary } from "@/types/email-classification";

import {
  AuthorRuleFromEmailWizard,
  preFillOperatorFromEmail,
} from "./AuthorRuleFromEmailWizard";

const workflows: WorkflowSummary[] = [
  {
    id: "wf-mfg",
    name: "Manufacturing intake",
    description: null,
    vertical: "manufacturing",
    is_active: true,
  },
];

describe("preFillOperatorFromEmail — heuristic", () => {
  it("uses sender_domain_in for unique domains", () => {
    const result = preFillOperatorFromEmail({
      sender_email: "ops@hopkinsfh.com",
      subject: "Order request",
    });
    expect(result.sender_domain_in).toEqual(["hopkinsfh.com"]);
  });

  it("falls back to subject_contains_any for common providers", () => {
    const result = preFillOperatorFromEmail({
      sender_email: "alice@gmail.com",
      subject: "Refund request for invoice number 1234",
    });
    expect(result.sender_domain_in).toBeUndefined();
    expect(result.subject_contains_any).toBeDefined();
    expect(result.subject_contains_any!.length).toBeGreaterThan(0);
    expect(result.subject_contains_any!.length).toBeLessThanOrEqual(3);
    // Stopwords should be excluded
    expect(result.subject_contains_any!).not.toContain("for");
  });

  it("falls back to sender_email_in when no distinctive words", () => {
    const result = preFillOperatorFromEmail({
      sender_email: "bob@gmail.com",
      subject: "Re: Hi",
    });
    expect(result.sender_email_in).toEqual(["bob@gmail.com"]);
  });

  it("filters short words (<4 chars) from subject heuristic", () => {
    const result = preFillOperatorFromEmail({
      sender_email: "test@gmail.com",
      subject: "Hi go now please refund",
    });
    expect(result.subject_contains_any).toBeDefined();
    // "Hi", "go", "now" are <4 chars; "please" + "refund" qualify
    expect(
      result.subject_contains_any!.every((w) => w.length >= 4),
    ).toBe(true);
  });

  it("treats outlook.com as a common provider too", () => {
    const result = preFillOperatorFromEmail({
      sender_email: "boss@outlook.com",
      subject: "Quarterly report",
    });
    expect(result.sender_domain_in).toBeUndefined();
  });
});

describe("AuthorRuleFromEmailWizard", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("mounts TriggerConfigEditor with pre-filled name + operator", () => {
    render(
      <AuthorRuleFromEmailWizard
        open
        onOpenChange={() => {}}
        sourceEmail={{
          classification_id: "cls_42",
          subject: "Big urgent order from Hopkins",
          sender_email: "ops@hopkinsfh.com",
        }}
        workflows={workflows}
        tenantVertical="manufacturing"
        onComplete={vi.fn()}
      />,
    );
    // Pre-filled name surfaces in the input
    const nameInput = screen.getByTestId("trigger-name-input") as HTMLInputElement;
    expect(nameInput.value).toContain("Rule from email");
    expect(nameInput.value).toContain("Big urgent order from Hopkins");
  });

  it("renders nothing when closed", () => {
    render(
      <AuthorRuleFromEmailWizard
        open={false}
        onOpenChange={() => {}}
        sourceEmail={{
          classification_id: "cls_42",
          subject: "x",
          sender_email: "a@b.com",
        }}
        workflows={workflows}
        tenantVertical="manufacturing"
        onComplete={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("trigger-name-input")).toBeNull();
  });

  it("Save flow: createRule + suppressClassification + onComplete", async () => {
    vi.mocked(createRule).mockResolvedValue({
      id: "rule_99",
      name: "Rule from email — test",
    } as never);
    vi.mocked(suppressClassification).mockResolvedValue({} as never);
    const onComplete = vi.fn();
    const onOpenChange = vi.fn();
    render(
      <AuthorRuleFromEmailWizard
        open
        onOpenChange={onOpenChange}
        sourceEmail={{
          classification_id: "cls_42",
          subject: "Order from Hopkins",
          sender_email: "ops@hopkinsfh.com",
        }}
        workflows={workflows}
        tenantVertical="manufacturing"
        onComplete={onComplete}
      />,
    );
    // Pick a workflow so validation passes
    const picker = screen.getByTestId("trigger-workflow-picker");
    expect(picker).toBeTruthy();
    fireEvent.click(picker);
    await waitFor(() =>
      expect(
        screen.getByTestId("workflow-picker-option-wf-mfg"),
      ).toBeTruthy(),
    );
    fireEvent.click(screen.getByTestId("workflow-picker-option-wf-mfg"));
    // Save
    fireEvent.click(screen.getByTestId("trigger-save"));
    await waitFor(() => expect(createRule).toHaveBeenCalled());
    await waitFor(() =>
      expect(suppressClassification).toHaveBeenCalledWith("cls_42", {
        reason: "Rule authored from this email",
      }),
    );
    await waitFor(() => expect(onComplete).toHaveBeenCalled());
    expect(toast.success).toHaveBeenCalled();
  });

  it("createRule failure does NOT call suppress or onComplete", async () => {
    vi.mocked(createRule).mockRejectedValue(new Error("create boom"));
    const onComplete = vi.fn();
    render(
      <AuthorRuleFromEmailWizard
        open
        onOpenChange={() => {}}
        sourceEmail={{
          classification_id: "cls_42",
          subject: "Order from Hopkins",
          sender_email: "ops@hopkinsfh.com",
        }}
        workflows={workflows}
        tenantVertical="manufacturing"
        onComplete={onComplete}
      />,
    );
    fireEvent.click(screen.getByTestId("trigger-workflow-picker"));
    await waitFor(() =>
      expect(
        screen.getByTestId("workflow-picker-option-wf-mfg"),
      ).toBeTruthy(),
    );
    fireEvent.click(screen.getByTestId("workflow-picker-option-wf-mfg"));
    fireEvent.click(screen.getByTestId("trigger-save"));
    await waitFor(() => expect(createRule).toHaveBeenCalled());
    expect(suppressClassification).not.toHaveBeenCalled();
    expect(onComplete).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalled();
  });

  it("suppress failure still calls onComplete (rule already created)", async () => {
    vi.mocked(createRule).mockResolvedValue({
      id: "rule_99",
      name: "x",
    } as never);
    vi.mocked(suppressClassification).mockRejectedValue(
      new Error("suppress boom"),
    );
    const onComplete = vi.fn();
    render(
      <AuthorRuleFromEmailWizard
        open
        onOpenChange={() => {}}
        sourceEmail={{
          classification_id: "cls_42",
          subject: "Order from Hopkins",
          sender_email: "ops@hopkinsfh.com",
        }}
        workflows={workflows}
        tenantVertical="manufacturing"
        onComplete={onComplete}
      />,
    );
    fireEvent.click(screen.getByTestId("trigger-workflow-picker"));
    await waitFor(() =>
      expect(
        screen.getByTestId("workflow-picker-option-wf-mfg"),
      ).toBeTruthy(),
    );
    fireEvent.click(screen.getByTestId("workflow-picker-option-wf-mfg"));
    fireEvent.click(screen.getByTestId("trigger-save"));
    await waitFor(() => expect(createRule).toHaveBeenCalled());
    await waitFor(() => expect(onComplete).toHaveBeenCalled());
    // Both errors and success toasts fire
    expect(toast.error).toHaveBeenCalledWith(
      expect.stringContaining("Rule created but suppress failed"),
    );
    expect(toast.success).toHaveBeenCalled();
  });
});
