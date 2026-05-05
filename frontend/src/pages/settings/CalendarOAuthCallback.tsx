/**
 * /settings/calendar/oauth-callback — Phase W-4b Layer 1 Calendar Step 2.
 *
 * Real OAuth code-exchange handler.
 *
 * Flow:
 *   1. Page loads with ``?code=<auth_code>&state=<csrf_state>`` query
 *      params from the provider redirect.
 *   2. POST /api/v1/calendar-accounts/oauth/callback with code + state
 *      + the primary_email_address pre-stashed in localStorage from
 *      the CalendarAccountsPage Connect dialog.
 *   3. Backend validates state nonce (CSRF + replay protection),
 *      exchanges code → tokens, persists encrypted credentials,
 *      returns the new CalendarAccount.
 *   4. Surface success + initial backfill status; navigate back to
 *      /settings/calendar.
 *
 * Mirrors EmailOAuthCallback shape — same pre-stashed metadata
 * pattern. Calendar primitive uses a Calendar-specific localStorage
 * key (separate from Email's) so concurrent OAuth flows for both
 * primitives don't collide.
 */

import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { postCalendarOAuthCallback } from "@/services/calendar-account-service";
import type { OAuthCallbackResponse } from "@/types/calendar-account";

interface PendingCalendarConnect {
  provider_type: "google_calendar" | "msgraph";
  primary_email_address: string;
  display_name?: string;
  account_type?: "shared" | "personal";
  redirect_uri: string;
}

const STORAGE_KEY = "calendar_oauth_pending_connect";

export function getPendingCalendarConnect(): PendingCalendarConnect | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as PendingCalendarConnect;
  } catch {
    return null;
  }
}

export function setPendingCalendarConnect(value: PendingCalendarConnect): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
}

export function clearPendingCalendarConnect(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}

export default function CalendarOAuthCallback() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<
    "loading" | "success" | "error" | "no-code"
  >("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [result, setResult] = useState<OAuthCallbackResponse | null>(null);

  useEffect(() => {
    const code = params.get("code");
    const state = params.get("state");
    const providerError = params.get("error");

    if (providerError) {
      setStatus("error");
      setErrorMessage(`Provider returned error: ${providerError}`);
      return;
    }
    if (!code || !state) {
      setStatus("no-code");
      return;
    }

    const pending = getPendingCalendarConnect();
    if (!pending) {
      setStatus("error");
      setErrorMessage(
        "Pre-flight metadata missing — please restart the OAuth flow " +
          "from the Calendar accounts page.",
      );
      return;
    }

    void postCalendarOAuthCallback({
      provider_type: pending.provider_type,
      code,
      state,
      redirect_uri: pending.redirect_uri,
      primary_email_address: pending.primary_email_address,
      display_name: pending.display_name,
      account_type: pending.account_type,
    })
      .then((r) => {
        clearPendingCalendarConnect();
        setResult(r);
        setStatus("success");
        // Auto-navigate after 2s so the operator sees the success state.
        setTimeout(() => navigate("/settings/calendar"), 2000);
      })
      .catch((err) => {
        setStatus("error");
        setErrorMessage(
          err instanceof Error
            ? err.message
            : "Failed to complete OAuth exchange",
        );
      });
  }, [params, navigate]);

  return (
    <div className="space-y-6 p-6 max-w-2xl mx-auto">
      <Card>
        <CardContent className="py-12 space-y-4">
          {status === "loading" && (
            <div className="text-center">
              <h1 className="text-h2 font-plex-serif font-medium text-content-strong">
                Connecting calendar account…
              </h1>
              <p className="text-body-sm text-content-muted mt-2">
                Exchanging authorization code for tokens.
              </p>
            </div>
          )}

          {status === "success" && result && (
            <Alert variant="success">
              <AlertTitle>Calendar connected</AlertTitle>
              <AlertDescription>
                <div className="space-y-1">
                  <div>
                    <strong>{result.primary_email_address}</strong> is now
                    linked. Backfill status:{" "}
                    <code className="text-body-sm">
                      {result.backfill_status}
                    </code>
                    .
                  </div>
                  <div className="text-content-muted">
                    Returning to Calendar accounts page…
                  </div>
                </div>
              </AlertDescription>
            </Alert>
          )}

          {status === "no-code" && (
            <Alert variant="warning">
              <AlertTitle>No authorization code</AlertTitle>
              <AlertDescription>
                The provider redirect didn't include a ``code`` query
                parameter. Restart the OAuth flow from the Calendar
                accounts page.
              </AlertDescription>
            </Alert>
          )}

          {status === "error" && (
            <Alert variant="error">
              <AlertTitle>OAuth failed</AlertTitle>
              <AlertDescription>
                {errorMessage ?? "Unknown error during OAuth exchange."}
              </AlertDescription>
            </Alert>
          )}

          {status !== "loading" && status !== "success" && (
            <div className="flex justify-end">
              <Button onClick={() => navigate("/settings/calendar")}>
                Back to Calendar accounts
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
