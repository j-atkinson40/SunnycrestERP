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

  it("selecting Gmail kicks off OAuth flow", async () => {
    const user = userEvent.setup();
    mockListAccounts.mockResolvedValue([]);
    mockGetOAuthAuthorizeUrl.mockResolvedValue({
      authorize_url: "https://accounts.google.com/o/oauth2/v2/auth?client_id=REPLACE_IN_STEP_2",
      state: "abc123",
    });

    // Stub window.location.href assignment so the test doesn't navigate.
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

    await waitFor(() => {
      expect(mockGetOAuthAuthorizeUrl).toHaveBeenCalledWith(
        "gmail",
        "https://app.test/settings/email/oauth-callback",
      );
    });

    // Restore window.location
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
