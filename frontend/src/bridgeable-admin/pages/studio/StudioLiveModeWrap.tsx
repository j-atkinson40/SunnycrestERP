/**
 * StudioLiveModeWrap — Studio 1a-i.A2 + Studio test maintenance (2026-05-13).
 *
 * Wraps RuntimeEditorShell inside Studio so the operator drops into
 * Live mode without leaving the Studio shell. The Studio shell dispatches
 * this child based on `parseStudioPath()` output; the `vertical` prop is
 * the parsed second segment of `/studio/live/:vertical?` and drives the
 * tenant picker's pre-filter.
 *
 * Admin-chrome conflict resolution (investigation §4): passes
 * `studioContext={true}` to suppress the legacy yellow admin ribbon —
 * Studio's own top bar (rendered by StudioShell above this wrap) takes
 * the ribbon's role.
 *
 * Lazy boundary (Studio test maintenance, 2026-05-13): RuntimeEditorShell
 * is loaded via React.lazy() so the runtime-editor chunk (TenantProviders,
 * TenantRouteTree, inspector substrate) does NOT enter the main admin
 * bundle. Pre-fix, eager import grew main_bundle 7.54% over the
 * pre-A2 baseline; lazy boundary restores within tolerance. The Studio
 * shell entry into Live mode pays a one-time chunk fetch, same shape as
 * the rest of the admin tree's lazy routes (RuntimeHostTestPage,
 * StudioShell itself in BridgeableAdminApp).
 *
 * Element layering inside Studio Live mode (no duplication):
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


const RuntimeEditorShell = lazy(
  () => import("@/bridgeable-admin/pages/runtime-editor/RuntimeEditorShell"),
)


export interface StudioLiveModeWrapProps {
  /**
   * Vertical slug pulled from `/studio/live/:vertical?` by the Studio
   * shell's parser. Null when the URL is bare `/studio/live` (no
   * pre-filter); operator picks any tenant.
   */
  vertical: string | null
}


export default function StudioLiveModeWrap({ vertical }: StudioLiveModeWrapProps) {
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
