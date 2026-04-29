/**
 * InlineActionBar tests — Phase W-4b Layer 1 Step 4c.
 *
 * Coverage:
 *   - Pending action: 3 buttons render (approve / request changes / reject)
 *   - Approve click → POST + onCommitted callback fires
 *   - Reject click → POST + onCommitted
 *   - Request changes flow: clicking opens textarea; submit disabled
 *     until note non-empty; submit fires with note
 *   - Terminal states render summary chrome (no buttons)
 *   - Unknown action_type renders nothing
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { EmailMessageAction } from "@/types/email-inbox";


const mockCommitInlineAction = vi.fn();

vi.mock("@/services/email-inbox-service", () => ({
  commitInlineAction: (...args: unknown[]) => mockCommitInlineAction(...args),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));


function makeAction(
  status: EmailMessageAction["action_status"] = "pending",
): EmailMessageAction {
  return {
    action_type: "quote_approval",
    action_target_type: "quote",
    action_target_id: "q-1",
    action_metadata: {
      quote_amount: "1500.00",
      quote_number: "QTE-2026-0001",
      customer_name: "Hopkins FH",
    },
    action_status: status,
    action_completed_at: status === "pending" ? null : "2026-05-08T10:00:00Z",
    action_completed_by: status === "pending" ? null : "user-1",
    action_completion_metadata:
      status === "changes_requested"
        ? { note: "Please reduce price." }
        : null,
  };
}


describe("InlineActionBar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  async function renderBar(action: EmailMessageAction) {
    const { default: InlineActionBar } = await import("./InlineActionBar");
    const onCommitted = vi.fn();
    render(
      <InlineActionBar
        messageId="msg-1"
        actionIdx={0}
        action={action}
        onCommitted={onCommitted}
      />,
    );
    return { onCommitted };
  }

  it("pending action shows three buttons + metadata", async () => {
    await renderBar(makeAction("pending"));
    expect(
      screen.getByTestId("inline-action-bar"),
    ).toHaveAttribute("data-action-status", "pending");
    expect(screen.getByTestId("action-approve-btn")).toBeInTheDocument();
    expect(
      screen.getByTestId("action-request-changes-btn"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("action-reject-btn")).toBeInTheDocument();
    expect(screen.getByText(/QTE-2026-0001/)).toBeInTheDocument();
    expect(screen.getByText(/Hopkins FH/)).toBeInTheDocument();
    expect(screen.getByText(/\$1500\.00/)).toBeInTheDocument();
  });

  it("approve click calls API + onCommitted", async () => {
    const user = userEvent.setup();
    mockCommitInlineAction.mockResolvedValue({
      action_idx: 0,
      action_type: "quote_approval",
      action_status: "approved",
      action_completed_at: "2026-05-08T10:00:00Z",
      action_target_type: "quote",
      action_target_id: "q-1",
      target_status: "accepted",
    });
    const { onCommitted } = await renderBar(makeAction("pending"));
    await user.click(screen.getByTestId("action-approve-btn"));
    await waitFor(() => {
      expect(mockCommitInlineAction).toHaveBeenCalledWith(
        "msg-1",
        0,
        expect.objectContaining({ outcome: "approve" }),
      );
    });
    await waitFor(() => expect(onCommitted).toHaveBeenCalled());
  });

  it("reject click calls API with reject outcome", async () => {
    const user = userEvent.setup();
    mockCommitInlineAction.mockResolvedValue({
      action_status: "rejected",
      action_idx: 0,
      action_type: "quote_approval",
      action_completed_at: "2026-05-08T10:00:00Z",
      action_target_type: "quote",
      action_target_id: "q-1",
      target_status: "rejected",
    });
    const { onCommitted } = await renderBar(makeAction("pending"));
    await user.click(screen.getByTestId("action-reject-btn"));
    await waitFor(() =>
      expect(mockCommitInlineAction).toHaveBeenCalledWith(
        "msg-1",
        0,
        expect.objectContaining({ outcome: "reject" }),
      ),
    );
    await waitFor(() => expect(onCommitted).toHaveBeenCalled());
  });

  it("request changes shows textarea + send disabled until note typed", async () => {
    const user = userEvent.setup();
    await renderBar(makeAction("pending"));
    await user.click(screen.getByTestId("action-request-changes-btn"));
    const submit = screen.getByTestId("action-submit-changes-btn");
    expect(submit).toBeDisabled();
    await user.type(
      screen.getByTestId("action-changes-note"),
      "Please reduce price",
    );
    expect(submit).not.toBeDisabled();
  });

  it("submit changes fires API with note", async () => {
    const user = userEvent.setup();
    mockCommitInlineAction.mockResolvedValue({
      action_status: "changes_requested",
      action_idx: 0,
      action_type: "quote_approval",
      action_completed_at: "2026-05-08T10:00:00Z",
      action_target_type: "quote",
      action_target_id: "q-1",
      target_status: "sent",
    });
    const { onCommitted } = await renderBar(makeAction("pending"));
    await user.click(screen.getByTestId("action-request-changes-btn"));
    await user.type(
      screen.getByTestId("action-changes-note"),
      "Reduce price by 5%",
    );
    await user.click(screen.getByTestId("action-submit-changes-btn"));
    await waitFor(() =>
      expect(mockCommitInlineAction).toHaveBeenCalledWith(
        "msg-1",
        0,
        expect.objectContaining({
          outcome: "request_changes",
          completion_note: "Reduce price by 5%",
        }),
      ),
    );
    await waitFor(() => expect(onCommitted).toHaveBeenCalled());
  });

  it("approved terminal state shows summary, no buttons", async () => {
    await renderBar(makeAction("approved"));
    expect(screen.getByTestId("inline-action-bar")).toHaveAttribute(
      "data-action-status",
      "approved",
    );
    expect(screen.getByText(/Approved/)).toBeInTheDocument();
    expect(
      screen.queryByTestId("action-approve-btn"),
    ).not.toBeInTheDocument();
  });

  it("changes_requested terminal state shows note", async () => {
    await renderBar(makeAction("changes_requested"));
    expect(
      screen.getByTestId("inline-action-bar"),
    ).toHaveAttribute("data-action-status", "changes_requested");
    expect(screen.getByText(/Please reduce price\./)).toBeInTheDocument();
  });

  it("unknown action_type renders nothing", async () => {
    const action = makeAction("pending");
    // @ts-expect-error — testing forward-compat
    action.action_type = "unknown_future_type";
    await renderBar(action);
    expect(
      screen.queryByTestId("inline-action-bar"),
    ).not.toBeInTheDocument();
  });
});
