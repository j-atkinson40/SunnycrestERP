/**
 * StudioShell — the top-level Studio surface.
 *
 * Wraps the Studio top bar + persistent left rail around a child page
 * dispatched from the current URL. Path-segment-canonical URL scheme
 * (see lib/studio-routes.ts):
 *
 *   /studio                           → Platform overview
 *   /studio/:vertical                 → Vertical overview
 *   /studio/:editor                   → Platform-scope editor
 *   /studio/:vertical/:editor         → Vertical-scope editor
 *   /studio/live                      → Live mode placeholder (1a-i.A1)
 *
 * Studio 1a-i.A1 substrate. Editor pages mount in-place via lazy
 * import; editor adaptation to the rail-expand signal ships in 1a-i.B
 * (today the editors just render with their own existing chrome / left
 * panes; rail collapses-to-icon-strip on editor click so editors keep
 * room for their own left pane per investigation §2).
 */
import { Suspense, lazy, useEffect, useMemo, useState } from "react"
import { Navigate, useLocation } from "react-router-dom"
import { useAdminAuth } from "@/bridgeable-admin/lib/admin-auth-context"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import {
  parseStudioPath,
  readRailExpanded,
  writeLastVertical,
  type StudioEditorKey,
} from "@/bridgeable-admin/lib/studio-routes"
import { StudioTopBar } from "@/bridgeable-admin/components/studio/StudioTopBar"
import { StudioRail } from "@/bridgeable-admin/components/studio/StudioRail"
import StudioOverviewPage from "./StudioOverviewPage"
import StudioLivePlaceholderPage from "./StudioLivePlaceholderPage"

// Eager imports for the existing visual editor pages. They are small
// enough that lazy-loading per-editor inside Studio doesn't pay for
// itself yet — and they share the registry import that has to happen
// at admin tree bootstrap anyway.
import ThemeEditorPage from "@/bridgeable-admin/pages/visual-editor/themes/ThemeEditorPage"
import FocusEditorPage from "@/bridgeable-admin/pages/visual-editor/FocusEditorPage"
import WidgetEditorPage from "@/bridgeable-admin/pages/visual-editor/WidgetEditorPage"
import DocumentsEditorPage from "@/bridgeable-admin/pages/visual-editor/DocumentsEditorPage"
import ClassEditorPage from "@/bridgeable-admin/pages/visual-editor/ClassEditorPage"
import WorkflowEditorPage from "@/bridgeable-admin/pages/visual-editor/WorkflowEditorPage"
import EdgePanelEditorPage from "@/bridgeable-admin/pages/visual-editor/EdgePanelEditorPage"
import RegistryDebugPage from "@/bridgeable-admin/pages/visual-editor/RegistryDebugPage"
import PluginRegistryBrowser from "@/bridgeable-admin/pages/visual-editor/PluginRegistryBrowser"


const EDITOR_PAGES: Record<StudioEditorKey, React.ComponentType> = {
  themes: ThemeEditorPage,
  focuses: FocusEditorPage,
  widgets: WidgetEditorPage,
  documents: DocumentsEditorPage,
  classes: ClassEditorPage,
  workflows: WorkflowEditorPage,
  "edge-panels": EdgePanelEditorPage,
  registry: RegistryDebugPage,
  "plugin-registry": PluginRegistryBrowser,
}


export default function StudioShell() {
  const { user, loading } = useAdminAuth()
  const location = useLocation()

  const parsed = useMemo(
    () => parseStudioPath(location.pathname.replace(/^\/bridgeable-admin/, "")),
    [location.pathname],
  )

  const [railExpanded, setRailExpanded] = useState<boolean>(() =>
    readRailExpanded(true),
  )

  // Remember last vertical for cross-session pickup.
  useEffect(() => {
    if (parsed.vertical) {
      writeLastVertical(parsed.vertical)
    }
  }, [parsed.vertical])

  if (loading) {
    return (
      <div
        className="flex min-h-screen items-center justify-center bg-surface-base text-content-muted"
        data-testid="studio-loading"
      >
        Loading…
      </div>
    )
  }
  if (!user) {
    return <Navigate to={adminPath("/login")} replace />
  }

  const mode: "edit" | "live" = parsed.isLive ? "live" : "edit"

  let child: React.ReactNode
  if (parsed.isLive) {
    child = <StudioLivePlaceholderPage />
  } else if (parsed.editor === null) {
    child = <StudioOverviewPage activeVertical={parsed.vertical} />
  } else {
    const EditorPage = EDITOR_PAGES[parsed.editor]
    child = <EditorPage />
  }

  return (
    <div
      className="min-h-screen bg-surface-base text-content-base"
      data-studio-shell="true"
      data-active-vertical={parsed.vertical ?? "platform"}
      data-active-editor={parsed.editor ?? "overview"}
      data-mode={mode}
    >
      <StudioTopBar
        mode={mode}
        activeVertical={parsed.vertical}
        activeEditor={parsed.editor}
      />
      <div className="flex">
        <StudioRail
          expanded={railExpanded}
          onExpandedChange={setRailExpanded}
          activeVertical={parsed.vertical}
          activeEditor={parsed.editor}
          mode={mode}
        />
        <main
          className="min-w-0 flex-1"
          data-testid="studio-main"
          data-rail-expanded={railExpanded ? "true" : "false"}
        >
          <Suspense
            fallback={
              <div
                className="flex h-64 items-center justify-center text-content-muted"
                data-testid="studio-child-suspense"
              >
                Loading…
              </div>
            }
          >
            {child}
          </Suspense>
        </main>
      </div>
    </div>
  )
}


/* Lazy-mount export retained for cases where the admin app boundary
 * wants a Suspense fallback at the route level rather than inside the
 * shell. Currently unused; BridgeableAdminApp imports the default. */
export const StudioShellLazy = lazy(() => Promise.resolve({ default: StudioShell }))
