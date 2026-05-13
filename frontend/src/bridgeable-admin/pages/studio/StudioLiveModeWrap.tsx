/**
 * StudioLiveModeWrap — Studio 1a-i.A2 + Studio test maintenance (2026-05-13)
 * + Studio 1a-i.B follow-up #3 (nested-Routes vertical from useParams)
 * + Studio 1a-i.B follow-up #4 (verticals-registry disambiguation).
 *
 * Wraps RuntimeEditorShell inside Studio so the operator drops into
 * Live mode without leaving the Studio shell. StudioShell dispatches
 * Live-mode URLs via nested <Routes> (`live/:vertical/*` etc.), so
 * React Router exposes the first post-`live` segment as `:vertical`.
 *
 * Follow-up #4 disambiguation:
 *   React Router's `<Route path="live/:vertical/*">` matches greedily —
 *   a URL like `/studio/live/dispatch/funeral-schedule` captures
 *   `:vertical = "dispatch"` (a tenant route segment, NOT a real vertical
 *   slug). Pre-#4, the wrap trusted the param and reported the wrong
 *   scope (the screenshot showed "Vertical: dispatch" in the top bar).
 *   Post-#4, the wrap loads the verticals registry via `useVerticals()`
 *   and validates the captured slug against it: if not a known
 *   vertical, the captured value is treated as the first segment of
 *   the tenant route tail instead of a vertical scope.
 *
 * Admin-chrome conflict resolution (investigation §4): passes
 * `studioContext={true}` to suppress the legacy yellow admin ribbon —
 * Studio's own top bar (rendered by StudioShell above this wrap) takes
 * the ribbon's role.
 *
 * Lazy boundary (Studio test maintenance, 2026-05-13): RuntimeEditorShell
 * is loaded via React.lazy() so the runtime-editor chunk (TenantProviders,
 * TenantRouteTree, inspector substrate) does NOT enter the main admin
 * bundle. The Studio shell entry into Live mode pays a one-time chunk
 * fetch.
 *
 * Loading strategy (#4): blocks render until the verticals list resolves.
 * Verticals load is small (~4 rows), cached at module level via the hook,
 * and only blocks the first mount. Optimistic-as-if-tail was considered
 * but would render the wrong RuntimeEditorShell verticalFilter during the
 * load window for legitimate URLs (e.g. `/studio/live/manufacturing`
 * would temporarily mount with verticalFilter=null + tail="manufacturing",
 * causing the picker to query an invalid tenant slug). Blocking on
 * verticals load is correct.
 */
import { lazy, Suspense } from "react"
import { useLocation } from "react-router-dom"

import { disambiguateStudioLive } from "@/bridgeable-admin/lib/studio-routes"
import { useVerticals } from "@/bridgeable-admin/hooks/useVerticals"


const RuntimeEditorShell = lazy(
  () => import("@/bridgeable-admin/pages/runtime-editor/RuntimeEditorShell"),
)


export default function StudioLiveModeWrap() {
  const location = useLocation()
  const { loaded, knownSlugs } = useVerticals()

  // Block render until the verticals registry resolves. The hook
  // treats load failure as "loaded with empty list" so a permanent
  // verticals-fetch error still unblocks the wrap (every captured
  // segment becomes tail; the picker handles vertical resolution at
  // impersonation time).
  if (!loaded) {
    return (
      <div
        data-testid="studio-live-mode-wrap"
        data-loading="true"
        className="relative"
      >
        <div
          className="flex h-screen items-center justify-center bg-surface-base text-content-muted"
          data-testid="studio-live-loading"
        >
          <span>Loading Live mode…</span>
        </div>
      </div>
    )
  }

  const { vertical, tail } = disambiguateStudioLive(
    location.pathname,
    knownSlugs,
  )

  return (
    <div
      data-testid="studio-live-mode-wrap"
      data-vertical-filter={vertical ?? "any"}
      data-deep-tail={tail || "none"}
      className="relative"
    >
      <Suspense
        fallback={
          <div
            className="flex h-screen items-center justify-center bg-surface-base text-content-muted"
            data-testid="studio-live-loading"
          >
            <span>Loading Live mode…</span>
          </div>
        }
      >
        <RuntimeEditorShell
          studioContext={true}
          verticalFilter={vertical}
        />
      </Suspense>
    </div>
  )
}
