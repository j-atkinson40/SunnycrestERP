/**
 * Phase R-0 — Runtime Host Test Page (super_admin gated).
 *
 * NOT user-facing. Hidden from VisualEditorIndex. Validates the
 * shared-bundle refactor's architectural acceptance criterion:
 * the tenant App's route tree mounts inside the admin tree under
 * `<TenantProviders>` + an active impersonation token, and renders
 * identically to the tenant boot path.
 *
 * Usage (from a platform-admin browser session):
 *   1. Start an impersonation session for a tenant via
 *      `POST /api/platform/impersonation/impersonate` (sets
 *      localStorage.access_token to a 30-min impersonation token).
 *   2. Navigate to `/_runtime-host-test/?tenant=hopkins-fh&user=director1`.
 *   3. The Hopkins FH dashboard renders inside the admin tree shell.
 *
 * Query params (informational only — not consumed by the providers
 * directly; the impersonation token IS the source of truth for which
 * tenant + user we're rendering as):
 *   - `tenant`: tenant slug (matches localStorage.company_slug).
 *   - `user`: tenant-user identifier.
 *
 * Rendering is lazy-loaded — Vite splits the tenant chunk at the
 * `React.lazy()` boundary in BridgeableAdminApp so admin pages that
 * don't visit this route never pull the tenant chunk.
 */
import { Suspense } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"

import { useAdminAuth } from "@/bridgeable-admin/lib/admin-auth-context"
import { Button } from "@/components/ui/button"
import { TenantProviders } from "@/lib/runtime-host/TenantProviders"
import TenantRouteTree from "@/lib/runtime-host/TenantRouteTree"


export default function RuntimeHostTestPage() {
  const { user, loading } = useAdminAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const tenantSlug = searchParams.get("tenant") ?? "(unspecified)"
  const userQuery = searchParams.get("user") ?? "(unspecified)"

  // Super-admin gate: if the admin user isn't super_admin, refuse to
  // render the runtime host. Other admin roles can use the visual
  // editor's other surfaces; the runtime host's impersonation-token
  // surface is super_admin-only at R-0.
  if (loading) {
    return (
      <div
        className="flex h-screen items-center justify-center bg-surface-base text-content-muted"
        data-testid="runtime-host-test-loading"
      >
        <span>Loading admin session…</span>
      </div>
    )
  }

  if (!user) {
    return (
      <div
        className="flex h-screen items-center justify-center bg-surface-base text-content-strong"
        data-testid="runtime-host-test-unauth"
      >
        <div className="max-w-md text-center">
          <div className="text-h3 font-plex-serif">
            Admin sign-in required
          </div>
          <p className="mt-2 text-content-muted">
            The runtime-host test surface is super_admin-only.
          </p>
          {/* R-7-η: recovery affordance — route to /login.
           *  Canonical pattern from R-7-α RuntimeEditorShell unauth branch. */}
          <div className="mt-4 flex justify-center">
            <Button
              data-testid="runtime-host-test-unauth-signin"
              onClick={() => navigate("/login")}
              aria-label="Sign in to admin"
            >
              Sign in
            </Button>
          </div>
        </div>
      </div>
    )
  }

  if (user.role !== "super_admin") {
    return (
      <div
        className="flex h-screen items-center justify-center bg-surface-base text-content-strong"
        data-testid="runtime-host-test-forbidden"
      >
        <div className="max-w-md text-center">
          <div className="text-h3 font-plex-serif text-status-error">
            Forbidden
          </div>
          <p className="mt-2 text-content-muted">
            The runtime-host test surface requires the super_admin role.
            Your account has role <code>{user.role}</code>.
          </p>
          {/* R-7-η: recovery affordance — route to admin home.
           *  Canonical pattern from R-7-α RuntimeEditorShell forbidden branch. */}
          <div className="mt-4 flex justify-center">
            <Button
              data-testid="runtime-host-test-forbidden-admin-home"
              onClick={() => navigate("/bridgeable-admin")}
              aria-label="Return to admin home"
            >
              Return to admin home
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div
      className="relative h-screen w-screen overflow-hidden bg-surface-base"
      data-testid="runtime-host-test-shell"
    >
      {/* Admin chrome ribbon — distinct from tenant chrome so it's
       *  obvious the platform admin is rendering tenant content from
       *  inside the admin tree, not actually logged in as a tenant. */}
      <div
        className="absolute top-0 left-0 right-0 z-50 flex h-8 items-center gap-3 border-b border-status-warning/30 bg-status-warning-muted px-3 text-caption text-status-warning"
        data-testid="runtime-host-ribbon"
      >
        <span className="font-medium">Runtime Host (R-0)</span>
        <span className="text-content-muted">
          tenant=<code data-testid="runtime-host-tenant">{tenantSlug}</code> ·{" "}
          user=<code data-testid="runtime-host-user">{userQuery}</code> ·{" "}
          impersonating as super_admin {user.email}
        </span>
      </div>

      {/* Tenant content rendered inside its canonical providers; the
       *  impersonation token (in localStorage.access_token) drives
       *  the tenant-side AuthProvider's session resolution. */}
      <div
        className="absolute inset-0 mt-8 overflow-auto"
        data-testid="runtime-host-tenant-content"
      >
        <TenantProviders>
          <Suspense
            fallback={
              <div className="flex h-full items-center justify-center text-content-muted">
                Loading tenant content…
              </div>
            }
          >
            <TenantRouteTree />
          </Suspense>
        </TenantProviders>
      </div>
    </div>
  )
}
