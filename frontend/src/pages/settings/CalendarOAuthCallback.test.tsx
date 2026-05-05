/**
 * CalendarOAuthCallback tests — Phase W-4b Layer 1 Calendar Step 2.
 *
 * Coverage:
 *   - Loading state when code + state present + callback in flight
 *   - Success state after successful exchange
 *   - Error state when no code in URL
 *   - Error state when pending metadata missing in localStorage
 *   - Error state when provider returns error param
 */
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import CalendarOAuthCallback, {
  setPendingCalendarConnect,
  clearPendingCalendarConnect,
} from "./CalendarOAuthCallback";

const mockPostCallback = vi.fn();

vi.mock("@/services/calendar-account-service", () => ({
  postCalendarOAuthCallback: (...args: unknown[]) => mockPostCallback(...args),
}));

beforeEach(() => {
  mockPostCallback.mockReset();
  clearPendingCalendarConnect();
});

afterEach(() => {
  clearPendingCalendarConnect();
});

function renderWithSearchParams(search: string) {
  return render(
    <MemoryRouter initialEntries={[`/settings/calendar/oauth-callback${search}`]}>
      <Routes>
        <Route
          path="/settings/calendar/oauth-callback"
          element={<CalendarOAuthCallback />}
        />
        <Route path="/settings/calendar" element={<div>Calendar list</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("CalendarOAuthCallback", () => {
  it("shows error when no code in URL", async () => {
    renderWithSearchParams("");
    expect(
      await screen.findByText(/No authorization code/i),
    ).toBeInTheDocument();
  });

  it("shows error when provider returns error param", async () => {
    renderWithSearchParams("?error=access_denied");
    expect(
      await screen.findByText(/access_denied/i),
    ).toBeInTheDocument();
  });

  it("shows error when pending metadata missing", async () => {
    // Don't call setPendingCalendarConnect.
    renderWithSearchParams("?code=abc&state=def");
    expect(
      await screen.findByText(/Pre-flight metadata missing/i),
    ).toBeInTheDocument();
  });

  it("calls postCalendarOAuthCallback on success path", async () => {
    setPendingCalendarConnect({
      provider_type: "google_calendar",
      primary_email_address: "test@example.com",
      account_type: "personal",
      redirect_uri: "http://localhost:5173/settings/calendar/oauth-callback",
    });
    mockPostCallback.mockResolvedValue({
      account_id: "cal-1",
      primary_email_address: "test@example.com",
      backfill_status: "completed",
      backfill_progress_pct: 100,
    });

    renderWithSearchParams("?code=auth_code_123&state=state_xyz");

    await waitFor(() => {
      expect(mockPostCallback).toHaveBeenCalledWith({
        provider_type: "google_calendar",
        code: "auth_code_123",
        state: "state_xyz",
        redirect_uri: "http://localhost:5173/settings/calendar/oauth-callback",
        primary_email_address: "test@example.com",
        display_name: undefined,
        account_type: "personal",
      });
    });

    // Success message rendered.
    expect(
      await screen.findByText(/Calendar connected/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/test@example.com/i)).toBeInTheDocument();
  });

  it("shows error on callback API failure", async () => {
    setPendingCalendarConnect({
      provider_type: "msgraph",
      primary_email_address: "ms@example.com",
      account_type: "shared",
      redirect_uri: "http://localhost:5173/settings/calendar/oauth-callback",
    });
    mockPostCallback.mockRejectedValue(
      new Error("Token exchange failed (401)"),
    );

    renderWithSearchParams("?code=bad_code&state=bad_state");

    expect(
      await screen.findByText(/OAuth failed/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Token exchange failed/i),
    ).toBeInTheDocument();
  });
});
