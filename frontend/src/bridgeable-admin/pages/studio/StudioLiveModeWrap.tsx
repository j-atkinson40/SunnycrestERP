/**
 * StudioLiveModeWrap — Studio 1a-i.A2.
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
 * Element layering inside Studio Live mode (no duplication):
 *   • Studio top bar    (StudioShell)
 *   • Studio left rail  (StudioShell, icon-strip default in Live)
 *   • this wrap → RuntimeEditorShell:
 *       • TenantProviders + impersonated route tree
 *       • <EditModeToggle /> (floating)
 *       • <SelectionOverlay /> (capture-phase click)
 *       • <InspectorPanel /> (right rail when widget selected)
 *       • <Focus /> (modal mount inside editor shell)
 */
import RuntimeEditorShell from "@/bridgeable-admin/pages/runtime-editor/RuntimeEditorShell"


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
      <RuntimeEditorShell
        studioContext={true}
        verticalFilter={vertical}
      />
    </div>
  )
}
