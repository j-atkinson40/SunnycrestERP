/**
 * LabelManager tests — Phase W-4b Layer 1 Step 4b.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";


const mockListLabels = vi.fn();
const mockCreateLabel = vi.fn();
const mockAddLabelToThread = vi.fn();
const mockRemoveLabelFromThread = vi.fn();

vi.mock("@/services/email-inbox-service", () => ({
  listLabels: () => mockListLabels(),
  createLabel: (...args: unknown[]) => mockCreateLabel(...args),
  addLabelToThread: (...args: unknown[]) => mockAddLabelToThread(...args),
  removeLabelFromThread: (...args: unknown[]) =>
    mockRemoveLabelFromThread(...args),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));


describe("LabelManager", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  async function renderManager(
    currentLabelIds: string[] = [],
    labels = [
      {
        id: "l1",
        name: "Priority",
        color: "#9C5640",
        icon: null,
        is_system: false,
      },
      {
        id: "l2",
        name: "Customer",
        color: "#4D7C5A",
        icon: null,
        is_system: false,
      },
    ],
  ) {
    mockListLabels.mockResolvedValue(labels);
    const onLabelsChanged = vi.fn();
    const onClose = vi.fn();
    const { LabelManager } = await import("./LabelManager");
    render(
      <LabelManager
        threadId="thread-1"
        currentLabelIds={currentLabelIds}
        onLabelsChanged={onLabelsChanged}
        onClose={onClose}
      />,
    );
    return { onLabelsChanged, onClose };
  }

  it("renders existing labels list", async () => {
    await renderManager();
    expect(await screen.findByTestId("label-toggle-l1")).toBeInTheDocument();
    expect(screen.getByTestId("label-toggle-l2")).toBeInTheDocument();
  });

  it("clicking unapplied label calls add", async () => {
    const user = userEvent.setup();
    mockAddLabelToThread.mockResolvedValue(undefined);
    const { onLabelsChanged } = await renderManager();
    await user.click(await screen.findByTestId("label-toggle-l1"));
    await waitFor(() =>
      expect(mockAddLabelToThread).toHaveBeenCalledWith("thread-1", "l1"),
    );
    await waitFor(() => expect(onLabelsChanged).toHaveBeenCalled());
  });

  it("clicking applied label calls remove", async () => {
    const user = userEvent.setup();
    mockRemoveLabelFromThread.mockResolvedValue(undefined);
    await renderManager(["l1"]);
    expect(
      await screen.findByTestId("label-applied-l1"),
    ).toBeInTheDocument();
    await user.click(screen.getByTestId("label-toggle-l1"));
    await waitFor(() =>
      expect(mockRemoveLabelFromThread).toHaveBeenCalledWith(
        "thread-1",
        "l1",
      ),
    );
  });

  it("create-new label flow opens form + submits", async () => {
    const user = userEvent.setup();
    mockCreateLabel.mockResolvedValue({
      id: "new-l",
      name: "Vendor",
      color: "#9C5640",
      icon: null,
      is_system: false,
    });
    mockAddLabelToThread.mockResolvedValue(undefined);
    await renderManager();
    await user.click(await screen.findByTestId("label-create-btn"));
    await user.type(screen.getByTestId("label-new-name"), "Vendor");
    await user.click(screen.getByTestId("label-create-submit"));
    await waitFor(() =>
      expect(mockCreateLabel).toHaveBeenCalledWith("Vendor", "#9C5640"),
    );
    // Auto-applies new label
    await waitFor(() =>
      expect(mockAddLabelToThread).toHaveBeenCalledWith("thread-1", "new-l"),
    );
  });

  it("create disabled when name empty", async () => {
    const user = userEvent.setup();
    await renderManager();
    await user.click(await screen.findByTestId("label-create-btn"));
    expect(screen.getByTestId("label-create-submit")).toBeDisabled();
  });
});
