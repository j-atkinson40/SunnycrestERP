/**
 * /settings/email/oauth-callback — Phase W-4b Layer 1 Step 1.
 *
 * Step 1 SCAFFOLDING ONLY. Real OAuth code-exchange happens in Step 2
 * once Gmail / Microsoft client credentials are wired into settings.
 *
 * Step 1 captures the redirect's ``code`` + ``state`` params and renders
 * a "Connection in progress" advisory pointing at Step 2 for the actual
 * exchange. Returning the user to /settings/email after acknowledging
 * is sufficient — no account row is created until Step 2 wires the
 * provider.connect() flow.
 */

import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function EmailOAuthCallback() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [code, setCode] = useState<string | null>(null);
  const [state, setState] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const c = params.get("code");
    const s = params.get("state");
    const err = params.get("error");
    if (err) {
      setError(`Provider returned error: ${err}`);
      return;
    }
    setCode(c);
    setState(s);
  }, [params]);

  return (
    <div
      className="container max-w-2xl mx-auto py-12 space-y-6"
      data-testid="oauth-callback-page"
    >
      <h1 className="text-h2 font-plex-serif font-medium text-content-strong">
        Email account OAuth callback
      </h1>

      {error ? (
        <Alert variant="error" title="OAuth flow failed">
          {error}
        </Alert>
      ) : (
        <Alert variant="info" title="OAuth scaffolding (Step 1)">
          The Step 1 OAuth flow is scaffolding only. Real code exchange
          + token persistence + sync subscription land in Step 2 when
          provider client credentials are configured. This page captured
          the redirect successfully — no account was created.
        </Alert>
      )}

      <Card>
        <CardContent className="space-y-3 pt-6">
          <div>
            <div className="text-body-sm font-medium text-content-muted">
              Authorization code (truncated)
            </div>
            <div className="font-plex-mono text-body-sm">
              {code ? `${code.slice(0, 20)}…` : "(none)"}
            </div>
          </div>
          <div>
            <div className="text-body-sm font-medium text-content-muted">
              CSRF state token
            </div>
            <div className="font-plex-mono text-body-sm">
              {state ? `${state.slice(0, 20)}…` : "(none)"}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={() => navigate("/settings/email")}>
          Back to Email accounts
        </Button>
      </div>
    </div>
  );
}
