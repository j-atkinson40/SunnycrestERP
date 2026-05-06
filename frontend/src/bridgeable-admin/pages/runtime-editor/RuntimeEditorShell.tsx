/**
 * Phase R-1 — Runtime Editor Shell.
 *
 * Successor to R-0's `RuntimeHostTestPage`. The R-0 page validated the
 * shared-bundle refactor (admin tree mounts tenant providers + route
 * tree under impersonation); R-1 turns it into the actual editor by
 * adding:
 *   - <EditModeProvider>: stages + commits overrides through real
 *     platform-token writers via `buildRuntimeWriters(ctx)` (Part 6).
 *   - <EditModeToggle>: floating toggle synced to `?edit=1`.
 *   - <SelectionOverlay>: capture-phase click handler + brass border
 *     around selected widget; gated on isEditing.
 *   - <InspectorPanel>: right-rail when a component is selected.
 *
 * Auth gate: platform_admin OR support — both roles can drive the
 * editor (R-0 was super_admin-only by phase scope; R-1 widens
 * because the impersonation API itself accepts {super_admin, support}
 * and tenant overrides are well-bounded by tenant scope).
 *
 * The shell forwards the impersonation context (vertical, tenant id,
 * impersonated user id) into the writers so theme + component +
 * class writes target the correct (scope, vertical, tenant_id, mode)
 * tuple at vertical_default scope.
 */
import { Suspense, useEffect, useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"

import { useAdminAuth } from "@/bridgeable-admin/lib/admin-auth-context"
import { useAuth } from "@/contexts/auth-context"
import { TenantProviders } from "@/lib/runtime-host/TenantProviders"
import TenantRouteTree from "@/lib/runtime-host/TenantRouteTree"
import { EditModeProvider } from "@/lib/runtime-host/edit-mode-context"
import { EditModeToggle } from "@/lib/runtime-host/EditModeToggle"
import { SelectionOverlay } from "@/lib/runtime-host/SelectionOverlay"
import { InspectorPanel } from "@/lib/runtime-host/inspector/InspectorPanel"
import {
  buildRuntimeWriters,
  type RuntimeWriteContext,
} from "@/lib/runtime-host/runtime-writers"
// R-1.6.1 — picker is rendered as a child of this shell when
// impersonation params are absent, NOT a sibling route. See the
// header comment block in BridgeableAdminApp.tsx for the route-
// specificity-conflict rationale.
import TenantUserPicker from "./TenantUserPicker"


/** Inner shell component — runs INSIDE TenantProviders so it can
 *  read the impersonated tenant's vertical via useAuth() (the
 *  AuthProvider session is the impersonation token). */
function ShellWithTenantContext({
  tenantSlug,
  impersonatedUserId,
  themeMode,
}: {
  tenantSlug: string
  impersonatedUserId: string
  themeMode: "light" | "dark"
}) {
  const { user, company, isLoading } = useAuth()

  // Build writer registry from impersonation context — must be a
  // stable Required<…> map so EditModeProvider's writers prop
  // round-trips correctly through useMemo.
  const writers = useMemo(() => {
    const ctx: RuntimeWriteContext = {
      vertical: company?.vertical ?? null,
      tenantId: company?.id ?? null,
      impersonatedUserId,
      themeMode,
    }
    return buildRuntimeWriters(ctx)
  }, [company?.vertical, company?.id, impersonatedUserId, themeMode])

  if (isLoading) {
    return (
      <div
        className="flex h-full items-center justify-center text-content-muted"
        data-testid="runtime-editor-tenant-loading"
      >
        Loading tenant session…
      </div>
    )
  }

  if (!user || !company) {
    return (
      <div
        className="flex h-full items-center justify-center px-6 text-center text-content-strong"
        data-testid="runtime-editor-impersonation-missing"
      >
        <div className="max-w-md">
          <div className="text-h3 font-plex-serif text-status-error">
            No active impersonation
          </div>
          <p className="mt-2 text-content-muted">
            Open the runtime editor entry page to start a new
            impersonation session — the tenant token expired or the
            page was refreshed without the entry handshake.
          </p>
        </div>
      </div>
    )
  }

  return (
    <EditModeProvider
      tenantSlug={tenantSlug}
      impersonatedUserId={impersonatedUserId}
      writers={writers}
    >
      <SelectionOverlay />
      <EditModeToggle />
      <InspectorPanel
        vertical={company.vertical}
        tenantId={company.id}
        themeMode={themeMode}
      />
      {/* Tenant route tree carries the impersonated user's view.
       *  data-runtime-host-root marks the boundary the SelectionOverlay
       *  walks up to so toggle / inspector clicks don't get hijacked
       *  by the capture-phase selection handler. */}
      <div data-runtime-host-root="true" className="h-full overflow-auto">
        <TenantRouteTree />
      </div>
    </EditModeProvider>
  )
}


export default function RuntimeEditorShell() {
  const { user, loading } = useAdminAuth()
  const [searchParams] = useSearchParams()
  const tenantSlug = searchParams.get("tenant")
  const userQuery = searchParams.get("user")
  const [themeMode] = useState<"light" | "dark">("light")

  // Honor the impersonation token on every nav into the shell — if
  // it's missing we render an explicit "go back to picker" prompt
  // rather than silently mounting the tenant tree (which would 401
  // on every API call).
  useEffect(() => {
    if (typeof document === "undefined") return
    document.title = tenantSlug
      ? `Runtime editor — ${tenantSlug}`
      : "Runtime editor"
  }, [tenantSlug])

  if (loading) {
    return (
      <div
        className="flex h-screen items-center justify-center bg-surface-base text-content-muted"
        data-testid="runtime-editor-loading"
      >
        Loading admin session…
      </div>
    )
  }

  if (!user) {
    return (
      <div
        className="flex h-screen items-center justify-center bg-surface-base text-content-strong"
        data-testid="runtime-editor-unauth"
      >
        <div className="max-w-md text-center">
          <div className="text-h3 font-plex-serif">
            Admin sign-in required
          </div>
          <p className="mt-2 text-content-muted">
            Sign in to the platform admin to use the runtime editor.
          </p>
        </div>
      </div>
    )
  }

  // R-1: platform_admin and support roles allowed (matches the
  // impersonation API's role gate). super_admin still passes.
  const allowed = user.role === "super_admin" || user.role === "platform_admin" || user.role === "support"
  if (!allowed) {
    return (
      <div
        className="flex h-screen items-center justify-center bg-surface-base text-content-strong"
        data-testid="runtime-editor-forbidden"
      >
        <div className="max-w-md text-center">
          <div className="text-h3 font-plex-serif text-status-error">
            Forbidden
          </div>
          <p className="mt-2 text-content-muted">
            The runtime editor requires <code>super_admin</code>,
            <code> platform_admin</code>, or <code> support</code>{" "}
            role. Your account has role <code>{user.role}</code>.
          </p>
        </div>
      </div>
    )
  }

  if (!tenantSlug || !userQuery) {
    // R-1.6.1 — render the picker as a child instead of an
    // empty-state. The picker drives the impersonation flow + calls
    // navigate("/runtime-editor/?tenant=...&user=..."); since this
    // shell handles the splat route exclusively, the navigate
    // resolves cleanly to the same route + this branch falls through
    // to the editor body when params are present.
    //
    // Wrapped in `data-testid="runtime-editor-missing-params"` for
    // R-1.5 spec contract preservation — specs that asserted the
    // missing-params state continue to find the test-id (now on the
    // picker's surrounding shell instead of an empty-state).
    return (
      <div
        className="min-h-screen bg-surface-base"
        data-testid="runtime-editor-missing-params"
      >
        <TenantUserPicker />
      </div>
    )
  }

  return (
    <div
      className="relative h-screen w-screen overflow-hidden bg-surface-base"
      data-testid="runtime-editor-shell"
    >
      {/* Admin chrome ribbon — distinct from tenant chrome so it's
       *  obvious the platform admin is rendering tenant content. */}
      <div
        className="absolute top-0 left-0 right-0 z-50 flex h-8 items-center gap-3 border-b border-status-warning/30 bg-status-warning-muted px-3 text-caption text-status-warning"
        data-testid="runtime-editor-ribbon"
      >
        <span className="font-medium">Runtime Editor (R-1)</span>
        <span className="text-content-muted">
          tenant=<code data-testid="runtime-editor-tenant">{tenantSlug}</code> ·{" "}
          user=<code data-testid="runtime-editor-user">{userQuery}</code> ·{" "}
          editing as platform admin {user.email}
        </span>
      </div>

      <div
        className="absolute inset-0 mt-8 overflow-hidden"
        data-testid="runtime-editor-tenant-content"
      >
        <TenantProviders>
          <Suspense
            fallback={
              <div className="flex h-full items-center justify-center text-content-muted">
                Loading tenant content…
              </div>
            }
          >
            <ShellWithTenantContext
              tenantSlug={tenantSlug}
              impersonatedUserId={userQuery}
              themeMode={themeMode}
            />
          </Suspense>
        </TenantProviders>
      </div>
    </div>
  )
}
