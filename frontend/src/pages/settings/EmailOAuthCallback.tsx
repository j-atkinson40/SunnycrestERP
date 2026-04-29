/**
 * /settings/email/oauth-callback — Phase W-4b Layer 1 Step 2.
 *
 * Real OAuth code-exchange handler (replaces Step 1 placeholder).
 *
 * Flow:
 *   1. Page loads with ``?code=<auth_code>&state=<csrf_state>`` query
 *      params from the provider redirect.
 *   2. We POST to /api/v1/email-accounts/oauth/callback with the
 *      code + state + the email_address pre-stashed in localStorage
 *      from the EmailAccountsPage Connect dialog.
 *   3. Backend validates state nonce (CSRF + replay protection),
 *      exchanges code → tokens, persists encrypted credentials,
 *      returns the new EmailAccount.
 *   4. We surface success + initial backfill status; navigate back
 *      to /settings/email.
 *
 * The pre-stashed metadata pattern (email_address, display_name,
 * provider_type) lets the user review what they're connecting BEFORE
 * leaving Bridgeable for the consent screen, then we have it to
 * pass to the callback when they return.
 */

import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  postOAuthCallback,
} from "@/services/email-account-service";
import type { OAuthCallbackResponse } from "@/types/email-account";

interface PendingConnect {
  provider_type: "gmail" | "msgraph";
  email_address: string;
  display_name?: string;
  account_type?: "shared" | "personal";
  redirect_uri: string;
}

const STORAGE_KEY = "email_oauth_pending_connect";

export function getPendingConnect(): PendingConnect | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as PendingConnect;
  } catch {
    return null;
  }
}

export function setPendingConnect(value: PendingConnect): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
}

export function clearPendingConnect(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}

export default function EmailOAuthCallback() {
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

    const pending = getPendingConnect();
    if (!pending) {
      setStatus("error");
      setErrorMessage(
        "Pre-flight metadata missing — please restart the OAuth flow " +
          "from the Email accounts page.",
      );
      return;
    }

    void postOAuthCallback({
      provider_type: pending.provider_type,
      code,
      state,
      redirect_uri: pending.redirect_uri,
      email_address: pending.email_address,
      display_name: pending.display_name ?? null,
      account_type: pending.account_type ?? "personal",
    })
      .then((response) => {
        clearPendingConnect();
        setResult(response);
        setStatus("success");
      })
      .catch((err: unknown) => {
        const detail =
          err && typeof err === "object" && "response" in err
            ? // axios shape
              ((err as { response?: { data?: { detail?: string } } })
                .response?.data?.detail ?? null)
            : null;
        setStatus("error");
        setErrorMessage(
          detail ??
            (err instanceof Error
              ? err.message
              : "OAuth code exchange failed."),
        );
      });
  }, [params]);

  return (
    <div
      className="container max-w-2xl mx-auto py-12 space-y-6"
      data-testid="oauth-callback-page"
    >
      <h1 className="text-h2 font-plex-serif font-medium text-content-strong">
        Connecting your email account…
      </h1>

      {status === "loading" && (
        <Alert variant="info">
          <AlertTitle>Exchanging authorization code</AlertTitle>
          <AlertDescription>
            Validating the authorization code from your provider and
            persisting encrypted credentials. This usually takes 1-2
            seconds.
          </AlertDescription>
        </Alert>
      )}

      {status === "success" && result && (
        <>
          <Alert variant="success">
            <AlertTitle>Connected</AlertTitle>
            <AlertDescription>
              <strong>{result.email_address}</strong> is connected. Initial
              backfill status: <strong>{result.backfill_status}</strong>{" "}
              ({result.backfill_progress_pct}%). You can monitor sync
              progress on the Email accounts page.
            </AlertDescription>
          </Alert>
          <div className="flex justify-end">
            <Button onClick={() => navigate("/settings/email")}>
              Back to Email accounts
            </Button>
          </div>
        </>
      )}

      {status === "error" && (
        <>
          <Alert variant="error">
            <AlertTitle>OAuth flow failed</AlertTitle>
            <AlertDescription>
              {errorMessage ?? "Unknown error"}
            </AlertDescription>
          </Alert>
          <Card>
            <CardContent className="space-y-3 pt-6">
              <div className="text-body-sm text-content-muted">
                Common causes:
              </div>
              <ul className="text-body-sm text-content-muted list-disc list-inside space-y-1">
                <li>Pre-flight metadata expired (browser refresh between flow start + return)</li>
                <li>State nonce expired (more than 10 min between authorize + callback)</li>
                <li>Authorization code already used (reload or replay)</li>
                <li>Provider client_id not configured (Step 2 limitation in dev environments)</li>
              </ul>
            </CardContent>
          </Card>
          <div className="flex justify-end">
            <Button onClick={() => navigate("/settings/email")}>
              Back to Email accounts
            </Button>
          </div>
        </>
      )}

      {status === "no-code" && (
        <>
          <Alert variant="warning">
            <AlertTitle>No authorization code</AlertTitle>
            <AlertDescription>
              This page expects ``?code=&state=`` query parameters from
              the provider redirect. If you arrived here directly, return
              to the Email accounts page and start the connect flow from
              there.
            </AlertDescription>
          </Alert>
          <div className="flex justify-end">
            <Button onClick={() => navigate("/settings/email")}>
              Back to Email accounts
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
