/**
 * StudioLiveModeWrap — Studio 1a-i.A2 + Studio test maintenance (2026-05-13)
 * + Studio 1a-i.B follow-up #3 (nested-Routes vertical from useParams).
 *
 * Wraps RuntimeEditorShell inside Studio so the operator drops into
 * Live mode without leaving the Studio shell. StudioShell dispatches
 * Live-mode URLs via nested <Routes> (`live/:vertical/*` etc.), so the
 * `:vertical` param is read from `useParams()` rather than passed as
 * a prop.
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
 * Element layering inside Studio Live mode:
 *   • Studio top bar    (StudioShell)
 *   • Studio left rail  (StudioShell, icon-strip default in Live)
 *   • this wrap → Suspense → RuntimeEditorShell:
 *       • TenantProviders + impersonated route tree
 *       • <EditModeToggle /> (floating)
 *       • <SelectionOverlay /> (capture-phase click)
 *       • <InspectorPanel /> (right rail when widget selected)
 *       • <Focus /> (modal mount inside editor shell)
 */
import { lazy, Suspense } from "react"
import { useParams } from "react-router-dom"

import { isReservedSlug } from "@/bridgeable-admin/lib/studio-routes"


const RuntimeEditorShell = lazy(
  () => import("@/bridgeable-admin/pages/runtime-editor/RuntimeEditorShell"),
)


export default function StudioLiveModeWrap() {
  // Studio 1a-i.B follow-up #3: vertical is read from URL params
  // populated by StudioShell's nested <Route path="live/:vertical/*">
  // declaration. The bare `/studio/live` and `/studio/live/<tail>`
  // (no vertical) cases match `live/*` / `live` instead, so
  // useParams().vertical is undefined.
  //
  // Defense-in-depth: if the captured `:vertical` segment is actually
  // a reserved keyword (e.g. accidental match against `admin` or an
  // editor key), treat as no-vertical. The current route declarations
  // don't allow this in practice, but the guard mirrors parseStudioPath
  // semantics for symmetry.
  const params = useParams<{ vertical?: string }>()
  const rawVertical = params.vertical
  const vertical =
    rawVertical && !isReservedSlug(rawVertical) ? rawVertical : null

  return (
    <div
      data-testid="studio-live-mode-wrap"
      data-vertical-filter={vertical ?? "any"}
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
