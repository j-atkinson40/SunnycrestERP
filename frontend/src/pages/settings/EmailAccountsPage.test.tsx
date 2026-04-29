/**
 * EmailAccountsPage tests — Phase W-4b Layer 1 Step 1.
 *
 * Coverage:
 *   - Renders empty state when no accounts
 *   - Renders provider picker on Connect dialog
 *   - Renders IMAP credential form when IMAP provider selected
 *   - OAuth providers route via authorize-url endpoint
 *   - Empty-state action triggers Connect dialog
 *
 * Tests mock the email-account-service module — they verify UI flow
 * and shape, not network. Backend tests cover service correctness.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";

import EmailAccountsPage from "./EmailAccountsPage";


// Hoisted mocks (vi.mock is hoisted; declare module-level fakes).
const mockListAccounts = vi.fn();
const mockListProviders = vi.fn();
const mockCreateAccount = vi.fn();
const mockGetOAuthAuthorizeUrl = vi.fn();

const mockSendMessage = vi.fn();
const mockSyncNow = vi.fn();

vi.mock("@/services/email-account-service", () => ({
  listAccounts: (...args: unknown[]) => mockListAccounts(...args),
  listProviders: () => mockListProviders(),
  createAccount: (...args: unknown[]) => mockCreateAccount(...args),
  deleteAccount: vi.fn(),
  updateAccount: vi.fn(),
  getOAuthAuthorizeUrl: (...args: unknown[]) =>
    mockGetOAuthAuthorizeUrl(...args),
  listAccessGrants: vi.fn().mockResolvedValue([]),
  grantAccess: vi.fn(),
  revokeAccess: vi.fn(),
  sendMessage: (...args: unknown[]) => mockSendMessage(...args),
  syncNow: (...args: unknown[]) => mockSyncNow(...args),
}));

// Toast — we don't care about output, just don't blow up.
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));


function setupProviders() {
  mockListProviders.mockResolvedValue([
    {
      provider_type: "gmail",
      display_label: "Gmail / Google Workspace",
      supports_inbound: true,
      supports_realtime: true,
    },
    {
      provider_type: "msgraph",
      display_label: "Microsoft 365 / Outlook",
      supports_inbound: true,
      supports_realtime: true,
    },
    {
      provider_type: "imap",
      display_label: "IMAP / SMTP (custom)",
      supports_inbound: true,
      supports_realtime: false,
    },
    {
      provider_type: "transactional",
      display_label: "Transactional (platform-routed, outbound only)",
      supports_inbound: false,
      supports_realtime: false,
    },
  ]);
}


describe("EmailAccountsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupProviders();
  });

  it("renders empty state when no accounts exist", async () => {
    mockListAccounts.mockResolvedValue([]);
    render(<EmailAccountsPage />);
    expect(await screen.findByText(/no email accounts yet/i)).toBeInTheDocument();
  });

  it("renders existing accounts as a table", async () => {
    mockListAccounts.mockResolvedValue([
      {
        id: "acc-1",
        tenant_id: "t-1",
        account_type: "shared",
        display_name: "Sales Inbox",
        email_address: "sales@example.com",
        provider_type: "gmail",
        provider_config_keys: [],
        signature_html: null,
        reply_to_override: null,
        is_active: true,
        is_default: true,
        sync_status: "pending",
        created_by_user_id: null,
        created_at: "2026-05-07T00:00:00+00:00",
        updated_at: "2026-05-07T00:00:00+00:00",
      },
    ]);
    render(<EmailAccountsPage />);
    expect(await screen.findByText("Sales Inbox")).toBeInTheDocument();
    expect(screen.getByText("sales@example.com")).toBeInTheDocument();
    // The provider type renders inside the table cell — there are
    // multiple "Gmail" matches across the page (table cell + connect
    // button if visible). Constrain to the row.
    const row = screen.getByTestId("account-row-acc-1");
    expect(row).toHaveTextContent(/gmail/i);
  });

  it("opens connect dialog with provider picker", async () => {
    const user = userEvent.setup();
    mockListAccounts.mockResolvedValue([]);
    render(<EmailAccountsPage />);

    await waitFor(() =>
      expect(screen.getByTestId("connect-account-btn")).toBeInTheDocument(),
    );
    // Use the header connect button (empty state shows another).
    const connectBtns = screen.getAllByRole("button", { name: /connect account/i });
    await user.click(connectBtns[0]);

    expect(await screen.findByTestId("provider-picker")).toBeInTheDocument();
    expect(screen.getByTestId("provider-gmail")).toBeInTheDocument();
    expect(screen.getByTestId("provider-msgraph")).toBeInTheDocument();
    expect(screen.getByTestId("provider-imap")).toBeInTheDocument();
    expect(screen.getByTestId("provider-transactional")).toBeInTheDocument();
  });

  it("selecting IMAP shows credential form", async () => {
    const user = userEvent.setup();
    mockListAccounts.mockResolvedValue([]);
    render(<EmailAccountsPage />);

    const connectBtns = await screen.findAllByRole("button", {
      name: /connect account/i,
    });
    await user.click(connectBtns[0]);
    await user.click(await screen.findByTestId("provider-imap"));

    // Config form appears
    expect(await screen.findByLabelText(/display name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/imap server/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/smtp server/i)).toBeInTheDocument();
  });

  it("selecting Gmail kicks off OAuth flow after email entered", async () => {
    // Step 2 changed the flow: clicking Gmail goes to config step
    // (to capture email_address for pre-flight metadata stash); user
    // then clicks "Continue to Gmail sign-in" which kicks off OAuth.
    const user = userEvent.setup();
    mockListAccounts.mockResolvedValue([]);
    mockGetOAuthAuthorizeUrl.mockResolvedValue({
      authorize_url:
        "https://accounts.google.com/o/oauth2/v2/auth?client_id=REPLACE_IN_STEP_2",
      state: "abc123",
    });

    const originalLocation = window.location;
    Object.defineProperty(window, "location", {
      writable: true,
      value: { origin: "https://app.test", href: "" },
    });

    render(<EmailAccountsPage />);
    const connectBtns = await screen.findAllByRole("button", {
      name: /connect account/i,
    });
    await user.click(connectBtns[0]);
    await user.click(await screen.findByTestId("provider-gmail"));

    // Step 2: fill in email_address before OAuth kicks off.
    await user.type(
      await screen.findByLabelText(/display name/i),
      "Sales",
    );
    await user.type(
      screen.getByLabelText(/email address/i),
      "sales@example.com",
    );
    await user.click(screen.getByTestId("submit-oauth-connect"));

    await waitFor(() => {
      expect(mockGetOAuthAuthorizeUrl).toHaveBeenCalledWith(
        "gmail",
        "https://app.test/settings/email/oauth-callback",
      );
    });

    Object.defineProperty(window, "location", {
      writable: true,
      value: originalLocation,
    });
  });

  it("submits IMAP create with proper config", async () => {
    const user = userEvent.setup();
    mockListAccounts.mockResolvedValue([]);
    mockCreateAccount.mockResolvedValue({
      id: "new-acc",
      tenant_id: "t-1",
      account_type: "shared",
      display_name: "Custom IMAP",
      email_address: "user@example.com",
      provider_type: "imap",
      provider_config_keys: ["imap_server"],
      signature_html: null,
      reply_to_override: null,
      is_active: true,
      is_default: false,
      sync_status: "pending",
      created_by_user_id: null,
      created_at: "2026-05-07T00:00:00+00:00",
      updated_at: "2026-05-07T00:00:00+00:00",
    });

    render(<EmailAccountsPage />);
    const connectBtns = await screen.findAllByRole("button", {
      name: /connect account/i,
    });
    await user.click(connectBtns[0]);
    await user.click(await screen.findByTestId("provider-imap"));

    await user.type(await screen.findByLabelText(/display name/i), "Custom IMAP");
    await user.type(screen.getByLabelText(/email address/i), "user@example.com");
    await user.type(screen.getByLabelText(/imap server/i), "imap.example.com");
    await user.type(screen.getByLabelText(/smtp server/i), "smtp.example.com");
    await user.type(screen.getByLabelText(/^username$/i), "user");
    await user.type(screen.getByLabelText(/^password$/i), "pw");

    await user.click(screen.getByTestId("submit-create-account"));

    await waitFor(() => {
      expect(mockCreateAccount).toHaveBeenCalled();
    });
    const call = mockCreateAccount.mock.calls[0][0];
    expect(call.provider_type).toBe("imap");
    expect(call.email_address).toBe("user@example.com");
    expect(call.provider_config.imap_server).toBe("imap.example.com");
  });

});

// ── Step 3 — SendTestMessageDialog tested in isolation ──────────────
//
// Note: the dropdown trigger UX (clicking a row's "..." menu →
// "Send test message" item) is intentionally exercised via Playwright
// rather than vitest. base-ui's DropdownMenu uses Popover portals
// with hover/focus event flows that jsdom + userEvent don't trigger
// reliably (verified empirically — every codebase test that touches
// per-row dropdowns runs via Playwright). The dialog logic itself
// (form state, submit, mockSendMessage call shape) is the actual
// thing worth unit-testing — and we can do that directly.

describe("SendTestMessageDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const baseAccount = {
    id: "acc-1",
    tenant_id: "t-1",
    account_type: "shared" as const,
    display_name: "Sales Inbox",
    email_address: "sales@example.com",
    provider_type: "gmail" as const,
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

  it("posts the form via sendMessage with canonical shape", async () => {
    const user = userEvent.setup();
    mockSendMessage.mockResolvedValue({
      message_id: "msg-1",
      thread_id: "thread-1",
      provider_message_id: "gmail-id",
      sent_at: "2026-05-07T12:00:00+00:00",
      direction: "outbound",
    });
    const onSent = vi.fn();
    const onClose = vi.fn();

    const { SendTestMessageDialog } = await import("./EmailAccountsPage");
    render(
      <SendTestMessageDialog
        account={baseAccount}
        onClose={onClose}
        onSent={onSent}
      />,
    );

    const recipientInput = await screen.findByTestId("send-test-to");
    await user.type(recipientInput, "recipient@example.com");
    await user.click(screen.getByTestId("send-test-submit"));

    await waitFor(() => {
      expect(mockSendMessage).toHaveBeenCalledWith("acc-1", {
        to: [{ email_address: "recipient@example.com" }],
        subject: "Test from Bridgeable",
        body_text: expect.stringContaining("Bridgeable"),
      });
    });
    await waitFor(() => expect(onSent).toHaveBeenCalled());
  });

  it("disables submit when recipient empty", async () => {
    const onSent = vi.fn();
    const onClose = vi.fn();

    const { SendTestMessageDialog } = await import("./EmailAccountsPage");
    render(
      <SendTestMessageDialog
        account={baseAccount}
        onClose={onClose}
        onSent={onSent}
      />,
    );

    expect(screen.getByTestId("send-test-submit")).toBeDisabled();
  });

  it("surfaces backend detail on send failure", async () => {
    const user = userEvent.setup();
    mockSendMessage.mockRejectedValue({
      response: {
        data: { detail: "Account has outbound_enabled=False" },
      },
    });
    const onSent = vi.fn();
    const onClose = vi.fn();
    const { toast } = await import("sonner");

    const { SendTestMessageDialog } = await import("./EmailAccountsPage");
    render(
      <SendTestMessageDialog
        account={baseAccount}
        onClose={onClose}
        onSent={onSent}
      />,
    );
    await user.type(
      screen.getByTestId("send-test-to"),
      "x@y.com",
    );
    await user.click(screen.getByTestId("send-test-submit"));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Account has outbound_enabled=False",
      );
    });
    expect(onSent).not.toHaveBeenCalled();
  });
});
