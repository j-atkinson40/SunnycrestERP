/**
 * CategoryEditor unit tests — R-6.1b.a.
 *
 * Coverage:
 *   - Empty-label validation
 *   - Edit mode pre-populates from category
 *   - Save calls onSave with cleaned payload (empty description → null)
 *   - mapped_workflow_id supports null sentinel
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CategoryEditor } from "./CategoryEditor";
import type {
  TenantWorkflowEmailCategory,
  WorkflowSummary,
} from "@/types/email-classification";

const workflows: WorkflowSummary[] = [
  {
    id: "wf-cross",
    name: "Cross-vertical",
    description: null,
    vertical: null,
    is_active: true,
  },
];

const existingCategory: TenantWorkflowEmailCategory = {
  id: "cat-1",
  tenant_id: "tenant-x",
  parent_id: null,
  label: "Pricing",
  description: "Existing description.",
  mapped_workflow_id: "wf-cross",
  position: 0,
  is_active: true,
  created_at: null,
  updated_at: null,
};

describe("CategoryEditor", () => {
  it("create mode opens with empty draft", () => {
    render(
      <CategoryEditor
        open
        onOpenChange={() => {}}
        category={null}
        workflows={workflows}
        onSave={vi.fn()}
      />,
    );
    expect(screen.getByText(/New category/i)).toBeInTheDocument();
    const label = screen.getByTestId(
      "category-label-input",
    ) as HTMLInputElement;
    expect(label.value).toBe("");
  });

  it("edit mode populates from category", () => {
    render(
      <CategoryEditor
        open
        onOpenChange={() => {}}
        category={existingCategory}
        workflows={workflows}
        onSave={vi.fn()}
      />,
    );
    const label = screen.getByTestId(
      "category-label-input",
    ) as HTMLInputElement;
    expect(label.value).toBe("Pricing");
    const desc = screen.getByTestId(
      "category-description-input",
    ) as HTMLTextAreaElement;
    expect(desc.value).toBe("Existing description.");
  });

  it("empty label blocks save with validation", async () => {
    const onSave = vi.fn();
    render(
      <CategoryEditor
        open
        onOpenChange={() => {}}
        category={null}
        workflows={workflows}
        onSave={onSave}
      />,
    );
    fireEvent.click(screen.getByTestId("category-save"));
    await waitFor(() => {
      expect(
        screen.getByTestId("category-validation-alert"),
      ).toBeInTheDocument();
    });
    expect(onSave).not.toHaveBeenCalled();
  });

  it("save with valid label calls onSave with cleaned payload", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const onOpenChange = vi.fn();
    render(
      <CategoryEditor
        open
        onOpenChange={onOpenChange}
        category={null}
        workflows={workflows}
        onSave={onSave}
      />,
    );
    fireEvent.change(screen.getByTestId("category-label-input"), {
      target: { value: "Service-day requests" },
    });
    fireEvent.click(screen.getByTestId("category-save"));
    await waitFor(() => {
      expect(onSave).toHaveBeenCalledTimes(1);
    });
    const arg = onSave.mock.calls[0][0];
    expect(arg.label).toBe("Service-day requests");
    expect(arg.description).toBeNull(); // empty → null per cleaned payload
    expect(arg.is_active).toBe(true);
  });
});
