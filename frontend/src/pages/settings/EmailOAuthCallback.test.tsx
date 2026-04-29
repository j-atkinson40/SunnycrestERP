/**
 * EmailOAuthCallback tests — Phase W-4b Layer 1 Step 2.
 *
 * Coverage:
 *   - "no-code" branch when query params missing
 *   - "error" branch when provider returns ?error=
 *   - Successful exchange path with pre-flight metadata stash
 *   - Pre-flight-missing error branch
 */

import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";

import EmailOAuthCallback, {
  setPendingConnect,
  clearPendingConnect,
} from "./EmailOAuthCallback";


const mockPostOAuthCallback = vi.fn();

vi.mock("@/services/email-account-service", () => ({
  postOAuthCallback: (...args: unknown[]) => mockPostOAuthCallback(...args),
}));


function renderAt(initial: string) {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <Routes>
        <Route
          path="/settings/email/oauth-callback"
          element={<EmailOAuthCallback />}
        />
        <Route path="/settings/email" element={<div data-testid="email-list" />} />
      </Routes>
    </MemoryRouter>,
  );
}


describe("EmailOAuthCallback", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clearPendingConnect();
  });

  it("renders no-code branch when params missing", async () => {
    renderAt("/settings/email/oauth-callback");
    expect(
      await screen.findByText(/no authorization code/i),
    ).toBeInTheDocument();
  });

  it("renders provider-error branch", async () => {
    renderAt(
      "/settings/email/oauth-callback?error=access_denied",
    );
    expect(await screen.findByText(/oauth flow failed/i)).toBeInTheDocument();
    expect(screen.getByText(/access_denied/)).toBeInTheDocument();
  });

  it("renders pre-flight-missing branch", async () => {
    // No setPendingConnect call → metadata missing
    renderAt(
      "/settings/email/oauth-callback?code=auth-code&state=csrf-state",
    );
    expect(
      await screen.findByText(/pre-flight metadata missing/i),
    ).toBeInTheDocument();
    expect(mockPostOAuthCallback).not.toHaveBeenCalled();
  });

  it("posts callback + renders success when metadata + params present", async () => {
    setPendingConnect({
      provider_type: "gmail",
      email_address: "alice@example.com",
      display_name: "Alice",
      account_type: "personal",
      redirect_uri: "https://app/cb",
    });
    mockPostOAuthCallback.mockResolvedValue({
      account_id: "new-account",
      email_address: "alice@example.com",
      backfill_status: "in_progress",
      backfill_progress_pct: 0,
    });

    renderAt(
      "/settings/email/oauth-callback?code=auth-code&state=csrf-state",
    );

    await waitFor(() => {
      expect(mockPostOAuthCallback).toHaveBeenCalledWith({
        provider_type: "gmail",
        code: "auth-code",
        state: "csrf-state",
        redirect_uri: "https://app/cb",
        email_address: "alice@example.com",
        display_name: "Alice",
        account_type: "personal",
      });
    });
    // "Connected" appears multiple times (alert title + body); use
    // a more specific matcher.
    expect(
      await screen.findByText(/initial backfill status/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/alice@example.com/)).toBeInTheDocument();
  });

  it("renders error when callback throws", async () => {
    setPendingConnect({
      provider_type: "gmail",
      email_address: "x@example.com",
      redirect_uri: "https://app/cb",
    });
    mockPostOAuthCallback.mockRejectedValue({
      response: { data: { detail: "OAuth state nonce expired." } },
    });

    renderAt(
      "/settings/email/oauth-callback?code=c&state=s",
    );

    expect(
      await screen.findByText(/OAuth state nonce expired/),
    ).toBeInTheDocument();
  });
});
