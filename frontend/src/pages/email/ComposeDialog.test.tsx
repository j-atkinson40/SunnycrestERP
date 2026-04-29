/**
 * ComposeDialog tests — Phase W-4b Layer 1 Step 4b.
 *
 * Coverage:
 *   - New thread mode renders empty
 *   - Forward mode pre-fills subject (Fwd: prefix idempotent)
 *   - Forward mode quotes original body
 *   - Recipient strip type-ahead with mocked resolution
 *   - Email validation rejects invalid free-text
 *   - Send routes through sendMessage with correct shape
 *   - Send disabled when To/subject/body empty
 *   - Esc closes dialog
 *   - Subject/body helpers exported + idempotent
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  EmailAccount,
} from "@/types/email-account";
import type { MessageDetail } from "@/types/email-inbox";


// ── Mocks ────────────────────────────────────────────────────────────

const mockResolveRecipients = vi.fn();
const mockListRoleRecipients = vi.fn();
const mockExpandRoleRecipient = vi.fn();
const mockSendMessage = vi.fn();

vi.mock("@/services/email-inbox-service", () => ({
  resolveRecipients: (...args: unknown[]) => mockResolveRecipients(...args),
  listRoleRecipients: (...args: unknown[]) => mockListRoleRecipients(...args),
  expandRoleRecipient: (...args: unknown[]) =>
    mockExpandRoleRecipient(...args),
}));

vi.mock("@/services/email-account-service", () => ({
  sendMessage: (...args: unknown[]) => mockSendMessage(...args),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));


// ── Fixtures ─────────────────────────────────────────────────────────

const ACCOUNT: EmailAccount = {
  id: "acc-1",
  tenant_id: "t-1",
  account_type: "shared",
  display_name: "Sales",
  email_address: "sales@example.com",
  provider_type: "gmail",
  provider_config_keys: [],
  signature_html: null,
  reply_to_override: null,
  is_active: true,
  is_default: false,
  outbound_enabled: true,
  sync_status: "synced",
  created_by_user_id: null,
  created_at: "2026-05-07T00:00:00+00:00",
  updated_at: "2026-05-07T00:00:00+00:00",
};

const FORWARD_SOURCE: MessageDetail = {
  id: "msg-original",
  thread_id: "thread-original",
  sender_email: "external@example.com",
  sender_name: "External Sender",
  subject: "Original subject",
  body_text: "Original body text content",
  body_html: null,
  sent_at: "2026-05-07T10:00:00+00:00",
  received_at: "2026-05-07T10:00:00+00:00",
  direction: "inbound",
  is_read: true,
  is_flagged: false,
  in_reply_to_message_id: null,
  provider_message_id: "p-original",
  to: [{ email_address: "sales@example.com", display_name: null }],
  cc: [],
  bcc: [],
};


// ── Helper subject/body ──────────────────────────────────────────────


describe("buildForwardSubject + buildForwardQuotedBody helpers", () => {
  it("Fwd: prefix idempotent", async () => {
    const { buildForwardSubject } = await import("./ComposeDialog");
    expect(buildForwardSubject("Hello")).toBe("Fwd: Hello");
    expect(buildForwardSubject("Fwd: Hello")).toBe("Fwd: Hello");
    expect(buildForwardSubject("Fw: Hello")).toBe("Fw: Hello");
    expect(buildForwardSubject(null)).toBe("Fwd:");
    // Re: prefix preserved per RFC 5322 reply-tree marker
    expect(buildForwardSubject("Re: Hello")).toBe("Fwd: Re: Hello");
  });

  it("buildForwardQuotedBody includes sender + body", async () => {
    const { buildForwardQuotedBody } = await import("./ComposeDialog");
    const quoted = buildForwardQuotedBody(FORWARD_SOURCE);
    expect(quoted).toContain("Forwarded message");
    expect(quoted).toContain("External Sender");
    expect(quoted).toContain("Original body text content");
  });
});


// ── ComposeDialog render + flow ──────────────────────────────────────


describe("ComposeDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockResolveRecipients.mockResolvedValue([]);
    mockListRoleRecipients.mockResolvedValue([]);
  });

  async function renderCompose(props: Partial<{
    forwardSource: MessageDetail | null;
    initialTo: { email_address: string; display_name: string | null }[];
  }> = {}) {
    const { ComposeDialog } = await import("./ComposeDialog");
    const onClose = vi.fn();
    const onSent = vi.fn();
    render(
      <ComposeDialog
        accounts={[ACCOUNT]}
        defaultAccountId={ACCOUNT.id}
        forwardSource={props.forwardSource ?? null}
        initialTo={props.initialTo}
        onClose={onClose}
        onSent={onSent}
      />,
    );
    return { onClose, onSent };
  }

  it("renders new-thread mode with empty fields", async () => {
    await renderCompose();
    expect(await screen.findByTestId("compose-dialog")).toBeInTheDocument();
    expect(screen.getByText(/^New thread$/i)).toBeInTheDocument();
    const subj = screen.getByTestId("compose-subject") as HTMLInputElement;
    expect(subj.value).toBe("");
  });

  it("renders forward mode with pre-filled subject + quoted body", async () => {
    await renderCompose({ forwardSource: FORWARD_SOURCE });
    const subj = (await screen.findByTestId(
      "compose-subject",
    )) as HTMLInputElement;
    expect(subj.value).toBe("Fwd: Original subject");
    const body = screen.getByTestId("compose-body") as HTMLTextAreaElement;
    expect(body.value).toContain("Forwarded message");
    expect(body.value).toContain("Original body text content");
  });

  it("Send disabled when To/subject/body empty", async () => {
    await renderCompose();
    expect(screen.getByTestId("compose-send-btn")).toBeDisabled();
  });

  it("type-ahead resolves recipients via mocked endpoint", async () => {
    const user = userEvent.setup();
    mockResolveRecipients.mockResolvedValue([
      {
        email_address: "hopkins@example.com",
        display_name: "Hopkins FH",
        source_type: "crm_contact",
        resolution_id: "c-1",
        rank_score: 0.95,
      },
    ]);
    await renderCompose();
    const toInput = await screen.findByTestId("compose-to-input");
    await user.type(toInput, "Hopkins");
    await waitFor(
      () => {
        expect(mockResolveRecipients).toHaveBeenCalled();
      },
      { timeout: 600 },
    );
    expect(
      await screen.findByTestId("compose-suggestion-hopkins@example.com"),
    ).toBeInTheDocument();
  });

  it("free-text Enter commits valid email; rejects invalid", async () => {
    const user = userEvent.setup();
    const { toast } = await import("sonner");
    await renderCompose();
    const toInput = await screen.findByTestId("compose-to-input");

    // Invalid
    await user.type(toInput, "not-an-email{Enter}");
    expect(toast.error).toHaveBeenCalledWith("Invalid email address");

    // Valid
    await user.clear(toInput);
    await user.type(toInput, "valid@example.com{Enter}");
    expect(
      await screen.findByTestId("compose-chip-to-0"),
    ).toBeInTheDocument();
  });

  it("Send routes through sendMessage with chips + subject + body", async () => {
    const user = userEvent.setup();
    mockSendMessage.mockResolvedValue({
      message_id: "new-msg",
      thread_id: "new-thread",
      provider_message_id: "p-new",
      sent_at: "2026-05-07T11:00:00+00:00",
      direction: "outbound",
    });
    const { onSent } = await renderCompose();

    const toInput = await screen.findByTestId("compose-to-input");
    await user.type(toInput, "recipient@example.com{Enter}");
    await user.type(screen.getByTestId("compose-subject"), "Hello");
    await user.type(screen.getByTestId("compose-body"), "Body content");
    await user.click(screen.getByTestId("compose-send-btn"));

    await waitFor(() => {
      expect(mockSendMessage).toHaveBeenCalledWith(
        ACCOUNT.id,
        expect.objectContaining({
          to: [
            { email_address: "recipient@example.com", display_name: null },
          ],
          subject: "Hello",
          body_text: "Body content",
        }),
      );
    });
    await waitFor(() => expect(onSent).toHaveBeenCalled());
  });

  it("Esc closes dialog", async () => {
    const user = userEvent.setup();
    const { onClose } = await renderCompose();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });
});
