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
import { useLocation, useNavigate, useSearchParams } from "react-router-dom"

import { useAdminAuth } from "@/bridgeable-admin/lib/admin-auth-context"
import { Button } from "@/components/ui/button"
import { themesService } from "@/bridgeable-admin/services/themes-service"
import { Focus } from "@/components/focus/Focus"
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
import {
  applyThemeToElement,
  composeEffective,
  stackFromResolved,
} from "@/lib/visual-editor/themes/theme-resolver"
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
  const navigate = useNavigate()
  const location = useLocation()

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

  // R-1.6.14 — resolve + apply the active theme on shell mount so
  // committed vertical_default / tenant_override token overrides
  // (written via `runtime-writers/theme` to `platform_themes`) take
  // effect on reload, not only when the operator opens the inspector
  // Theme tab. Pre-R-1.6.14, `applyThemeToElement` only fired from
  // `ThemeTab.tsx:130-137` which mounts only when inspector is open
  // AND Theme tab selected AND `editMode.isEditing` is true. Spec 7's
  // "commit → reload → readback `--accent`" flow asserted before any
  // of those gates fired, so the read returned the static `tokens.css`
  // default. Mirrors `ThemeTab`'s resolve+apply chain verbatim,
  // unconditionally on shell mount.
  //
  // Scope discipline: this hook is mounted ONLY inside the runtime
  // editor shell. Production tenant boot (PresetThemeProvider on
  // `/home`, `/dashboard`, etc.) is unchanged — the question of
  // whether regular operators see vertical_default theme overrides
  // applied is a separate architectural concern (post-arc).
  useEffect(() => {
    if (typeof document === "undefined") return
    if (!company?.vertical) return
    let cancelled = false
    themesService
      .resolve({
        mode: themeMode,
        vertical: company.vertical,
        tenant_id: company.id ?? undefined,
      })
      .then((resolved) => {
        if (cancelled) return
        const stack = stackFromResolved(resolved, {})
        const effective = composeEffective(themeMode, stack)
        applyThemeToElement(effective, document.documentElement)
      })
      .catch((err) => {
        // eslint-disable-next-line no-console
        console.warn(
          "[runtime-editor-shell] theme resolve failed; falling back to tokens.css defaults",
          err,
        )
      })
    return () => {
      cancelled = true
    }
  }, [company?.vertical, company?.id, themeMode])

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
          {/* R-7-α: recovery affordance — strip query params so the
           *  outer RuntimeEditorShell falls through to the
           *  TenantUserPicker per R-1.6.1's picker-as-child
           *  arrangement. */}
          <div className="mt-4 flex justify-center">
            <Button
              data-testid="runtime-editor-impersonation-restart"
              onClick={() => navigate(location.pathname, { replace: true })}
              aria-label="Restart impersonation session"
            >
              Restart impersonation
            </Button>
          </div>
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
      {/* R-2.0.4: Focus modal mount inside the editor shell.
       *
       *  Pre-R-2.0.4, <Focus /> was mounted only in App.tsx's tenant
       *  branch (App.tsx:474) — the BridgeableAdminApp branch (which
       *  hosts the runtime editor at /bridgeable-admin/runtime-editor/*)
       *  did not include a Focus modal mount. URL `?focus=funeral-
       *  scheduling` updated FocusContext state but no modal rendered;
       *  SchedulingFocusWithAccessories never mounted; AncillaryCard
       *  never appeared in DOM. Spec 15's `[data-component-name=
       *  "ancillary-card"]` waitFor timed out at 20s.
       *
       *  Mounting Focus here gives the editor shell its own portal-
       *  rendered modal that respects the editor's TenantProviders
       *  subtree — useAuth() inside SchedulingFocusWithAccessories
       *  resolves to the impersonated tenant context, useFocus() reads
       *  the inner FocusProvider's URL-driven state, and the SelectionOverlay
       *  capture-phase walker still resolves clicks inside the Focus
       *  modal because Focus's Dialog.Portal renders into document.body
       *  but is React-tree-wise a descendant of EditModeProvider. */}
      <Focus />
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


export interface RuntimeEditorShellProps {
  /**
   * Studio 1a-i.A2 — when true, suppresses the admin chrome ribbon
   * (the yellow h-8 bar) because the Studio shell renders its own
   * top bar above the runtime editor. Defaults false for standalone
   * `/runtime-editor` usage (now legacy; redirects to `/studio/live`).
   */
  studioContext?: boolean
  /**
   * Studio 1a-i.A2 — vertical slug pre-filter for the TenantUserPicker
   * when no impersonation params are present. Studio's `/studio/live/
   * :vertical` route uses this to pre-scope the tenant list.
   */
  verticalFilter?: string | null
}


export default function RuntimeEditorShell({
  studioContext = false,
  verticalFilter = null,
}: RuntimeEditorShellProps = {}) {
  const { user, loading } = useAdminAuth()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const location = useLocation()
  const tenantSlug = searchParams.get("tenant")
  const userQuery = searchParams.get("user")
  const [themeMode] = useState<"light" | "dark">("light")
  // R-7-α: surface a recovery affordance after 10s of admin-session
  // loading. Long-running loads are rare in practice but indicate
  // network/admin-token issues; without this, operators stare at a
  // spinner indefinitely.
  const [loadingTimedOut, setLoadingTimedOut] = useState(false)
  useEffect(() => {
    if (!loading) {
      setLoadingTimedOut(false)
      return
    }
    const timer = setTimeout(() => setLoadingTimedOut(true), 10_000)
    return () => clearTimeout(timer)
  }, [loading])

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
        <div className="max-w-md text-center">
          <div>Loading admin session…</div>
          {/* R-7-α: surface cancel affordance after 10s so operators
           *  aren't stuck on indefinite spinner. Strips query params
           *  and returns to the picker. */}
          {loadingTimedOut && (
            <div className="mt-4 flex justify-center">
              <Button
                variant="outline"
                size="sm"
                data-testid="runtime-editor-loading-cancel"
                onClick={() => navigate(location.pathname, { replace: true })}
                aria-label="Cancel loading and return to runtime editor picker"
              >
                Cancel and return to picker
              </Button>
            </div>
          )}
        </div>
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
          {/* R-7-α: recovery affordance — route to /login. */}
          <div className="mt-4 flex justify-center">
            <Button
              data-testid="runtime-editor-unauth-signin"
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
          {/* R-7-α: recovery affordance — route to admin home. */}
          <div className="mt-4 flex justify-center">
            <Button
              data-testid="runtime-editor-forbidden-admin-home"
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

  if (!tenantSlug || !userQuery) {
    // R-1.6.1 — render the picker as a child instead of an
    // empty-state. The picker drives the impersonation flow + calls
    // navigate("/runtime-editor/?tenant=...&user=..."); since this
    // shell handles the splat route exclusively, the navigate
    // resolves cleanly to the same route + this branch falls through
    // to the editor body when params are present.
    //
    // Studio 1a-i.A2 — when mounted inside Studio (`studioContext`),
    // the StudioLiveModeWrap reads the `:vertical` URL param and
    // passes it down via the picker's `verticalFilter` to pre-filter
    // the tenant list. The picker also navigates to a Studio-shaped
    // URL when `studioContext` is true so the impersonation handshake
    // returns to `/studio/live/:vertical?...` rather than the
    // standalone `/runtime-editor/?...` path.
    return (
      <div
        className="min-h-screen bg-surface-base"
        data-testid="runtime-editor-missing-params"
      >
        <TenantUserPicker
          studioContext={studioContext}
          verticalFilter={verticalFilter}
        />
      </div>
    )
  }

  return (
    <div
      className="relative h-screen w-screen overflow-hidden bg-surface-base"
      data-testid="runtime-editor-shell"
      data-studio-context={studioContext ? "true" : "false"}
    >
      {/* Admin chrome ribbon — distinct from tenant chrome so it's
       *  obvious the platform admin is rendering tenant content.
       *  Studio 1a-i.A2: suppressed when `studioContext` is true
       *  because the Studio shell renders its own top bar above. */}
      {!studioContext && (
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
      )}

      <div
        className={
          studioContext
            ? "absolute inset-0 overflow-hidden"
            : "absolute inset-0 mt-8 overflow-hidden"
        }
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
