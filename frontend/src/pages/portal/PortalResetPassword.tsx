/**
 * PortalResetPassword — Workflow Arc Phase 8e.2.1.
 *
 * Branded portal reset-password page. Reached via the link in the
 * invite email OR the password-recovery email:
 *
 *   /portal/<slug>/reset-password?token=...
 *
 * Flow: user enters new password (8 char min) + confirmation →
 * POST to `/api/v1/portal/<slug>/password/recover/confirm` →
 * redirect to login on success.
 *
 * Renders under PortalBrandProvider for tenant-branded chrome.
 */

import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { usePortalBrand } from "@/contexts/portal-brand-context";
import { confirmPasswordRecovery } from "@/services/portal-service";

export default function PortalResetPassword() {
  const { slug } = useParams<{ slug: string }>();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { branding, isLoading: brandLoading, error: brandError } =
    usePortalBrand();
  const token = params.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) {
      setError("Missing or invalid reset link. Contact your dispatcher.");
    }
  }, [token]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!slug) return;
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      await confirmPasswordRecovery(slug, {
        token,
        new_password: password,
      });
      setDone(true);
      setTimeout(() => {
        navigate(`/portal/${slug}/login`, { replace: true });
      }, 2000);
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? "Couldn't set password.");
    } finally {
      setBusy(false);
    }
  }

  if (brandLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-body-sm text-content-muted">
        Loading…
      </div>
    );
  }

  if (brandError || !branding) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Alert variant="error" className="max-w-sm">
          {brandError ?? "Portal not found."}
        </Alert>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-surface-base">
      <div
        className="flex h-14 items-center justify-center px-4"
        style={{
          backgroundColor: "var(--portal-brand, var(--accent-brass))",
          color: "var(--portal-brand-fg, white)",
        }}
      >
        {branding.logo_url ? (
          <img
            src={branding.logo_url}
            alt={branding.display_name}
            className="h-8 w-auto max-w-[180px] object-contain"
          />
        ) : (
          <span className="text-body font-semibold">{branding.display_name}</span>
        )}
      </div>

      <div className="flex flex-1 items-start justify-center p-4 pt-12">
        <div className="w-full max-w-sm space-y-6">
          <div className="space-y-1 text-center">
            <h1 className="text-h3 font-plex-serif font-medium text-content-strong">
              Set your password
            </h1>
            <p className="text-body-sm text-content-muted">
              Minimum 8 characters.
            </p>
          </div>

          {done ? (
            <Alert variant="success">
              Password set. Redirecting to login…
            </Alert>
          ) : (
            <form
              className="space-y-4"
              onSubmit={handleSubmit}
              data-testid="portal-reset-form"
            >
              <div className="space-y-1">
                <Label htmlFor="new-password">New password</Label>
                <Input
                  id="new-password"
                  type="password"
                  required
                  minLength={8}
                  autoComplete="new-password"
                  autoFocus
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="h-11"
                  data-testid="new-password"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="confirm-password">Confirm password</Label>
                <Input
                  id="confirm-password"
                  type="password"
                  required
                  minLength={8}
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  className="h-11"
                  data-testid="confirm-password"
                />
              </div>
              {error && (
                <Alert variant="error" data-testid="portal-reset-error">
                  {error}
                </Alert>
              )}
              <Button
                type="submit"
                disabled={busy || !token || !password || !confirm}
                className="w-full h-11"
                style={{
                  backgroundColor:
                    "var(--portal-brand, var(--accent-brass))",
                  color: "var(--portal-brand-fg, white)",
                }}
                data-testid="portal-reset-submit"
              >
                {busy ? "Saving…" : "Set password"}
              </Button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
