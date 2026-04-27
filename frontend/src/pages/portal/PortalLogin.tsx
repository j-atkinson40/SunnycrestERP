/**
 * PortalLogin — Workflow Arc Phase 8e.2.
 *
 * Tenant-branded portal login page at `/portal/:slug/login`.
 *
 * Rendering sequence:
 *   1. Read :slug from URL.
 *   2. PortalBrandProvider fetches + applies tenant branding.
 *   3. User enters email + password → POST login.
 *   4. On success → redirect to `/portal/:slug/driver` (the driver
 *      home page, post-8e.2 mounting).
 *   5. On failure → inline error message.
 *
 * Mobile-first: single-column form, 44px minimum touch targets,
 * large text inputs.
 */

import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { usePortalAuth } from "@/contexts/portal-auth-context";
import { usePortalBrand } from "@/contexts/portal-brand-context";

export default function PortalLogin() {
  const { slug } = useParams<{ slug: string }>();
  const { branding, isLoading: brandLoading, error: brandError } =
    usePortalBrand();
  const { login, isLoading: authLoading, me } = usePortalAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  // If already authenticated, bounce to driver home.
  if (me && slug) {
    navigate(`/portal/${slug}/driver`, { replace: true });
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!slug) return;
    setError(null);
    try {
      await login(slug, { email: email.trim(), password });
      navigate(`/portal/${slug}/driver`, { replace: true });
    } catch (err) {
      const e = err as {
        response?: { data?: { detail?: string }; status?: number };
      };
      // Surface backend's generic message. Portal auth layer
      // deliberately doesn't leak whether the email exists.
      setError(
        e?.response?.data?.detail ?? "Invalid email or password.",
      );
    }
  }

  if (brandLoading) {
    return (
      <div
        className="flex min-h-screen items-center justify-center text-body-sm text-content-muted"
        data-testid="portal-login-loading"
      >
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
      {/* Branded header area — matches the logged-in portal header
          so there's visual continuity across the login/authed
          boundary. */}
      <div
        className="flex h-14 items-center justify-center px-4"
        style={{
          backgroundColor: "var(--portal-brand, var(--accent))",
          color: "var(--portal-brand-fg, var(--content-on-accent))",
        }}
        data-testid="portal-login-header"
      >
        {branding.logo_url ? (
          <img
            src={branding.logo_url}
            alt={branding.display_name}
            className="h-8 w-auto max-w-[180px] object-contain"
          />
        ) : (
          <span className="text-body font-semibold">
            {branding.display_name}
          </span>
        )}
      </div>

      {/* Form — centered card, mobile-first. */}
      <div className="flex flex-1 items-start justify-center p-4 pt-12">
        <div
          className="w-full max-w-sm space-y-6"
          data-testid="portal-login-form-container"
        >
          <div className="space-y-1 text-center">
            <h1 className="text-h3 font-plex-serif font-medium text-content-strong">
              {branding.display_name}
            </h1>
            <p className="text-body-sm text-content-muted">
              Sign in to your driver portal.
            </p>
          </div>

          <form
            className="space-y-4"
            onSubmit={handleSubmit}
            data-testid="portal-login-form"
          >
            <div className="space-y-1">
              <Label htmlFor="portal-email">Email</Label>
              <Input
                id="portal-email"
                type="email"
                required
                autoComplete="email"
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                data-testid="portal-login-email"
                className="h-11"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="portal-password">Password</Label>
              <Input
                id="portal-password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                data-testid="portal-login-password"
                className="h-11"
              />
            </div>

            {error ? (
              <Alert variant="error" data-testid="portal-login-error">
                {error}
              </Alert>
            ) : null}

            <Button
              type="submit"
              disabled={authLoading || !email || !password}
              data-testid="portal-login-submit"
              className="w-full h-11"
              style={{
                backgroundColor:
                  "var(--portal-brand, var(--accent))",
                color: "var(--portal-brand-fg, var(--content-on-accent))",
              }}
            >
              {authLoading ? "Signing in…" : "Sign in"}
            </Button>
          </form>

          {branding.footer_text ? (
            <p className="text-center text-caption text-content-muted">
              {branding.footer_text}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
