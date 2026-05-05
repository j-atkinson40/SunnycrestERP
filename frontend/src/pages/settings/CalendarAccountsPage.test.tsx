/**
 * CalendarAccountsPage tests — Phase W-4b Layer 1 Calendar Step 1.
 *
 * Coverage:
 *   - Renders empty state when no accounts
 *   - Renders provider picker on Create dialog (3 providers, no CalDAV)
 *   - Create flow with local provider (most common Step 1 path)
 *   - Empty-state action triggers Create dialog
 *   - Coexistence note rendered (Vault iCal feed reference)
 *   - Step 1 boundary banner explains deferred capabilities
 *
 * Tests mock the calendar-account-service module — they verify UI flow
 * and shape, not network. Backend tests cover service correctness.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CalendarAccountsPage from "./CalendarAccountsPage";

// Hoisted mocks.
const mockListAccounts = vi.fn();
const mockListProviders = vi.fn();
const mockCreateAccount = vi.fn();
const mockListAccessGrants = vi.fn();
const mockGrantAccess = vi.fn();
const mockRevokeAccess = vi.fn();
const mockDeleteAccount = vi.fn();
const mockGetOAuthAuthorizeUrl = vi.fn();
const mockSyncNow = vi.fn();

vi.mock("@/services/calendar-account-service", () => ({
  listCalendarAccounts: (...args: unknown[]) => mockListAccounts(...args),
  listCalendarProviders: (...args: unknown[]) => mockListProviders(...args),
  createCalendarAccount: (...args: unknown[]) => mockCreateAccount(...args),
  listCalendarAccessGrants: (...args: unknown[]) =>
    mockListAccessGrants(...args),
  grantCalendarAccess: (...args: unknown[]) => mockGrantAccess(...args),
  revokeCalendarAccess: (...args: unknown[]) => mockRevokeAccess(...args),
  deleteCalendarAccount: (...args: unknown[]) => mockDeleteAccount(...args),
  getCalendarOAuthAuthorizeUrl: (...args: unknown[]) =>
    mockGetOAuthAuthorizeUrl(...args),
  calendarSyncNow: (...args: unknown[]) => mockSyncNow(...args),
}));

// Mock toast to avoid Sonner DOM mounting in tests.
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const PROVIDERS = [
  {
    provider_type: "google_calendar" as const,
    display_label: "Google Calendar",
    supports_inbound: true,
    supports_realtime: true,
    supports_freebusy: true,
  },
  {
    provider_type: "msgraph" as const,
    display_label: "Microsoft 365 / Outlook",
    supports_inbound: true,
    supports_realtime: true,
    supports_freebusy: true,
  },
  {
    provider_type: "local" as const,
    display_label: "Bridgeable (no external sync)",
    supports_inbound: false,
    supports_realtime: false,
    supports_freebusy: true,
  },
];

beforeEach(() => {
  mockListAccounts.mockReset();
  mockListProviders.mockReset();
  mockCreateAccount.mockReset();
  mockListAccessGrants.mockReset();
  mockGrantAccess.mockReset();
  mockRevokeAccess.mockReset();
  mockDeleteAccount.mockReset();
  mockGetOAuthAuthorizeUrl.mockReset();
  mockSyncNow.mockReset();

  // Default behaviors.
  mockListAccounts.mockResolvedValue([]);
  mockListProviders.mockResolvedValue(PROVIDERS);
  mockListAccessGrants.mockResolvedValue([]);
});

describe("CalendarAccountsPage", () => {
  it("renders the page title and coexistence note", async () => {
    render(<CalendarAccountsPage />);
    expect(
      await screen.findByRole("heading", { name: /Calendar Accounts/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Coexists with the Vault iCal feed/i),
    ).toBeInTheDocument();
  });

  it("renders empty state when no accounts exist", async () => {
    render(<CalendarAccountsPage />);
    expect(
      await screen.findByText(/No calendar accounts yet/i),
    ).toBeInTheDocument();
    // CTA visible in empty state.
    expect(
      screen.getAllByRole("button", { name: /New (calendar account|local calendar)/i }).length,
    ).toBeGreaterThan(0);
  });

  it("renders the Step 2 boundary banner explaining deferred capabilities", async () => {
    render(<CalendarAccountsPage />);
    await screen.findByRole("heading", { name: /Calendar Accounts/i });
    // Step 2 banner: announces what shipped + what's next.
    expect(
      screen.getByText(/Step 2 shipped — what's next/i),
    ).toBeInTheDocument();
    // Step 2.1 webhook receivers + Step 4 cross-tenant remain deferred.
    expect(
      screen.getByText(/Provider webhook receivers/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Cross-tenant joint events/i),
    ).toBeInTheDocument();
  });

  it("opens Create dialog and shows 3 provider options (CalDAV omitted)", async () => {
    const user = userEvent.setup();
    render(<CalendarAccountsPage />);
    await screen.findByRole("heading", { name: /Calendar Accounts/i });

    // Click the top "New calendar account" button (first one in header).
    const buttons = screen.getAllByRole("button", {
      name: /New (calendar account|local calendar)/i,
    });
    await user.click(buttons[0]);

    // Dialog should be open with provider picker.
    expect(
      await screen.findByText(/New calendar account/i, {
        selector: "h2, [role=heading]",
      }),
    ).toBeInTheDocument();

    // The provider Select shows the default (local) display_label.
    // The Step 1 catalog has google / msgraph / local — NO caldav.
    expect(
      screen.queryByText(/CalDAV/i, { exact: false }),
    ).not.toBeInTheDocument();
  });

  it("submits create with local provider — happy path", async () => {
    const user = userEvent.setup();
    mockCreateAccount.mockResolvedValue({
      id: "cal-1",
      tenant_id: "t",
      account_type: "shared",
      display_name: "Production Schedule",
      primary_email_address: "production@test.test",
      provider_type: "local",
      provider_config_keys: [],
      outbound_enabled: true,
      default_event_timezone: "America/New_York",
      is_active: true,
      is_default: false,
      sync_status: null,
      created_by_user_id: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    render(<CalendarAccountsPage />);
    await screen.findByRole("heading", { name: /Calendar Accounts/i });

    // Open dialog. Step 2 added Connect-Google + Connect-Microsoft
    // buttons; the local-creation button is "New local calendar".
    const headerBtn = screen.getByRole("button", {
      name: /New local calendar/i,
    });
    await user.click(headerBtn);

    // Fill form. Display name + email are required.
    const displayInput = await screen.findByLabelText(/Display name/i);
    await user.type(displayInput, "Production Schedule");
    const emailInput = screen.getByLabelText(/Primary email address/i);
    await user.type(emailInput, "production@test.test");

    // Submit.
    const submitBtn = screen.getByRole("button", { name: /Create account/i });
    await user.click(submitBtn);

    // Verify the service was called with correct shape.
    await waitFor(() => {
      expect(mockCreateAccount).toHaveBeenCalledWith({
        account_type: "shared",
        display_name: "Production Schedule",
        primary_email_address: "production@test.test",
        provider_type: "local",
        default_event_timezone: "America/New_York",
        is_default: false,
      });
    });
  });

  it("renders existing accounts with provider label + sync placeholder", async () => {
    mockListAccounts.mockResolvedValue([
      {
        id: "cal-1",
        tenant_id: "t",
        account_type: "shared",
        display_name: "Production Schedule",
        primary_email_address: "production@test.test",
        provider_type: "local",
        provider_config_keys: [],
        outbound_enabled: true,
        default_event_timezone: "America/New_York",
        is_active: true,
        is_default: true,
        sync_status: null, // Step 1: sync not yet activated
        created_by_user_id: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ]);

    render(<CalendarAccountsPage />);
    expect(
      await screen.findByText("Production Schedule"),
    ).toBeInTheDocument();
    // Provider display label rendered (from listCalendarProviders).
    expect(
      screen.getByText(/Bridgeable \(no external sync\)/i),
    ).toBeInTheDocument();
    // Default flag rendered.
    expect(screen.getByText(/default/i, { selector: "span" })).toBeInTheDocument();
    // Step 2: when sync_status is null (no sync_state row yet), shows
    // the "Not yet synced" placeholder via the StatusPill label override.
    expect(screen.getByText(/Not yet synced/i)).toBeInTheDocument();
  });

  // ── Step 2 — OAuth + sync action tests ────────────────────────────

  it("renders Connect Google Calendar + Connect Microsoft 365 buttons (Step 2)", async () => {
    render(<CalendarAccountsPage />);
    await screen.findByRole("heading", { name: /Calendar Accounts/i });
    expect(
      screen.getByRole("button", { name: /Connect Google Calendar/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Connect Microsoft 365/i }),
    ).toBeInTheDocument();
  });

  it("Connect Google triggers OAuth authorize URL fetch + redirect (Step 2)", async () => {
    const user = userEvent.setup();
    mockGetOAuthAuthorizeUrl.mockResolvedValue({
      authorize_url: "https://accounts.google.com/o/oauth2/v2/auth?state=abc",
      state: "abc",
    });
    // Mock window.prompt + window.location.href setter.
    const originalPrompt = window.prompt;
    window.prompt = vi.fn().mockReturnValue("test@example.com");
    const hrefSetter = vi.fn();
    Object.defineProperty(window, "location", {
      writable: true,
      value: {
        ...window.location,
        origin: "http://localhost:5173",
        get href() {
          return "";
        },
        set href(value: string) {
          hrefSetter(value);
        },
      },
    });

    try {
      render(<CalendarAccountsPage />);
      await screen.findByRole("heading", { name: /Calendar Accounts/i });
      await user.click(
        screen.getByRole("button", { name: /Connect Google Calendar/i }),
      );

      await waitFor(() => {
        expect(mockGetOAuthAuthorizeUrl).toHaveBeenCalledWith(
          "google_calendar",
          "http://localhost:5173/settings/calendar/oauth-callback",
        );
        expect(hrefSetter).toHaveBeenCalledWith(
          "https://accounts.google.com/o/oauth2/v2/auth?state=abc",
        );
      });
    } finally {
      window.prompt = originalPrompt;
    }
  });

  it("Sync now action calls calendarSyncNow service (Step 2)", async () => {
    const user = userEvent.setup();
    mockSyncNow.mockResolvedValue({ status: "queued" });
    mockListAccounts.mockResolvedValue([
      {
        id: "cal-step2",
        tenant_id: "t",
        account_type: "personal",
        display_name: "OAuth Acc",
        primary_email_address: "user@example.com",
        provider_type: "google_calendar",
        provider_config_keys: ["access_token"],
        outbound_enabled: true,
        default_event_timezone: "America/New_York",
        is_active: true,
        is_default: false,
        sync_status: "synced",
        last_credential_op: "oauth_complete",
        last_credential_op_at: new Date().toISOString(),
        backfill_status: "completed",
        backfill_progress_pct: 100,
        created_by_user_id: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ]);

    render(<CalendarAccountsPage />);
    await screen.findByText("OAuth Acc");

    // Open the row's dropdown menu.
    const triggers = screen.getAllByRole("button");
    const moreBtn = triggers.find(
      (btn) => btn.querySelector("svg.lucide-ellipsis"),
    );
    expect(moreBtn).toBeDefined();
    if (moreBtn) await user.click(moreBtn);

    // Click "Sync now" menu item.
    const syncNowItem = await screen.findByText(/Sync now/i);
    await user.click(syncNowItem);

    await waitFor(() => {
      expect(mockSyncNow).toHaveBeenCalledWith("cal-step2");
    });
  });
});
