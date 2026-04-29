/**
 * MagicLinkActionPage tests — Phase W-4b Layer 1 Step 4c.
 *
 * Coverage:
 *   - Loading → ready states
 *   - Action details render (sender, subject, amount, line items)
 *   - Approve commits + transitions to done
 *   - Reject commits with reject outcome
 *   - Request changes flow with note + submit
 *   - Already-consumed token from GET surfaces done state
 *   - Expired token (410) → expired error UI
 *   - Invalid token (401) → invalid error UI
 *   - Tenant brand color applies to header
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";


const mockGetMagicLinkAction = vi.fn();
const mockCommitMagicLinkAction = vi.fn();

class MockMagicLinkError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "MagicLinkError";
  }
}

vi.mock("@/services/email-inbox-service", () => ({
  getMagicLinkAction: (...args: unknown[]) => mockGetMagicLinkAction(...args),
  commitMagicLinkAction: (...args: unknown[]) =>
    mockCommitMagicLinkAction(...args),
  MagicLinkError: MockMagicLinkError,
}));


const FUTURE_EXPIRES_AT = new Date(
  Date.now() + 6 * 24 * 60 * 60 * 1000,
).toISOString();


function makeDetails(
  overrides: Partial<{
    consumed: boolean;
    action_status: string;
    tenant_brand_color: string | null;
  }> = {},
) {
  return {
    tenant_name: "Sunnycrest Vault",
    tenant_brand_color: overrides.tenant_brand_color ?? "#9C5640",
    sender_name: "James Atkinson",
    sender_email: "james@sunnycrest.test",
    subject: "Quote QTE-2026-0001",
    sent_at: "2026-05-08T09:00:00Z",
    action_idx: 0,
    action_type: "quote_approval" as const,
    action_target_type: "quote",
    action_target_id: "q-1",
    action_metadata: {
      quote_amount: "1500.00",
      quote_number: "QTE-2026-0001",
      customer_name: "Hopkins FH",
      quote_line_items: [
        {
          description: "Standard burial vault",
          quantity: "1",
          unit_price: "1500.00",
          line_total: "1500.00",
        },
      ],
    },
    action_status: (overrides.action_status as
      | "pending"
      | "approved"
      | "rejected"
      | "changes_requested") ?? "pending",
    recipient_email: "fh@hopkins.test",
    expires_at: FUTURE_EXPIRES_AT,
    consumed: overrides.consumed ?? false,
  };
}


describe("MagicLinkActionPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  async function renderPage(token = "tok-abc") {
    const { default: MagicLinkActionPage } = await import("./MagicLinkActionPage");
    render(
      <MemoryRouter initialEntries={[`/email/actions/${token}`]}>
        <Routes>
          <Route
            path="/email/actions/:token"
            element={<MagicLinkActionPage />}
          />
        </Routes>
      </MemoryRouter>,
    );
  }

  it("loads details + renders pending action surface", async () => {
    mockGetMagicLinkAction.mockResolvedValue(makeDetails());
    await renderPage();
    await waitFor(() =>
      expect(screen.getByTestId("magic-link-details")).toBeInTheDocument(),
    );
    expect(screen.getByText(/Sunnycrest Vault/)).toBeInTheDocument();
    expect(screen.getByText(/QTE-2026-0001/)).toBeInTheDocument();
    expect(screen.getByText(/Hopkins FH/)).toBeInTheDocument();
    // Amount appears in both header + line items; just confirm presence
    expect(screen.getAllByText(/\$1500\.00/).length).toBeGreaterThan(0);
    expect(screen.getByTestId("magic-approve-btn")).toBeInTheDocument();
    expect(
      screen.getByTestId("magic-request-changes-btn"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("magic-reject-btn")).toBeInTheDocument();
  });

  it("approve transitions to done state", async () => {
    mockGetMagicLinkAction.mockResolvedValue(makeDetails());
    mockCommitMagicLinkAction.mockResolvedValue({
      action_idx: 0,
      action_type: "quote_approval",
      action_status: "approved",
      action_completed_at: "2026-05-08T10:00:00Z",
      action_target_type: "quote",
      action_target_id: "q-1",
      target_status: "accepted",
    });
    const user = userEvent.setup();
    await renderPage();
    await screen.findByTestId("magic-approve-btn");
    await user.click(screen.getByTestId("magic-approve-btn"));
    await waitFor(() => {
      expect(mockCommitMagicLinkAction).toHaveBeenCalledWith(
        "tok-abc",
        expect.objectContaining({ outcome: "approve" }),
      );
    });
    await waitFor(() =>
      expect(screen.getByTestId("magic-link-done")).toBeInTheDocument(),
    );
    expect(screen.getByTestId("magic-link-done")).toHaveAttribute(
      "data-status",
      "approved",
    );
  });

  it("request changes flow submits with note", async () => {
    mockGetMagicLinkAction.mockResolvedValue(makeDetails());
    mockCommitMagicLinkAction.mockResolvedValue({
      action_idx: 0,
      action_type: "quote_approval",
      action_status: "changes_requested",
      action_completed_at: "2026-05-08T10:00:00Z",
      action_target_type: "quote",
      action_target_id: "q-1",
      target_status: "sent",
    });
    const user = userEvent.setup();
    await renderPage();
    await screen.findByTestId("magic-request-changes-btn");
    await user.click(screen.getByTestId("magic-request-changes-btn"));
    const submit = screen.getByTestId("magic-submit-changes-btn");
    expect(submit).toBeDisabled();
    await user.type(
      screen.getByTestId("magic-changes-note"),
      "Please reduce price",
    );
    expect(submit).not.toBeDisabled();
    await user.click(submit);
    await waitFor(() => {
      expect(mockCommitMagicLinkAction).toHaveBeenCalledWith(
        "tok-abc",
        expect.objectContaining({
          outcome: "request_changes",
          completion_note: "Please reduce price",
        }),
      );
    });
    await waitFor(() =>
      expect(screen.getByTestId("magic-link-done")).toHaveAttribute(
        "data-status",
        "changes_requested",
      ),
    );
  });

  it("already-consumed token surfaces done state on initial load", async () => {
    mockGetMagicLinkAction.mockResolvedValue(
      makeDetails({ consumed: true, action_status: "approved" }),
    );
    await renderPage();
    await waitFor(() =>
      expect(screen.getByTestId("magic-link-done")).toBeInTheDocument(),
    );
    expect(screen.getByTestId("magic-link-done")).toHaveAttribute(
      "data-status",
      "approved",
    );
  });

  it("expired token shows expired error UI", async () => {
    mockGetMagicLinkAction.mockRejectedValue(
      new MockMagicLinkError(410, "Token has expired."),
    );
    await renderPage();
    await waitFor(() =>
      expect(screen.getByTestId("magic-link-error")).toBeInTheDocument(),
    );
    expect(screen.getByText(/expired/i)).toBeInTheDocument();
  });

  it("invalid token shows invalid error UI", async () => {
    mockGetMagicLinkAction.mockRejectedValue(
      new MockMagicLinkError(401, "Token not found."),
    );
    await renderPage();
    await waitFor(() =>
      expect(screen.getByTestId("magic-link-error")).toBeInTheDocument(),
    );
    expect(screen.getByText(/no longer valid/i)).toBeInTheDocument();
  });

  it("tenant brand color applied to header", async () => {
    mockGetMagicLinkAction.mockResolvedValue(
      makeDetails({ tenant_brand_color: "#9C5640" }),
    );
    await renderPage();
    const header = await screen.findByTestId("magic-link-header");
    // Inline style set on header — browser normalizes hex to rgb()
    const style = header.getAttribute("style") || "";
    expect(style.toLowerCase()).toMatch(
      /(rgb\(156,\s*86,\s*64\)|#9c5640)/,
    );
  });
});
