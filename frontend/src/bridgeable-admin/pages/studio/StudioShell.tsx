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
 *   /studio/live                      → Live mode landing (picker)
 *   /studio/live/:vertical            → Live mode pre-scoped to vertical
 *   /studio/live/:vertical/<tail>     → Live mode deep-link into tenant page
 *   /studio/live/<tail>               → Live mode deep-link pre-impersonation
 *
 * Studio 1a-i.B follow-up #3 — hybrid dispatch model:
 *   - Live mode uses NESTED <Routes> so React Router consumes the
 *     `live/:vertical` prefix and leaves the deep tenant tail
 *     (e.g. `dispatch/funeral-schedule`) as the unconsumed remainder
 *     that TenantRouteTree's nested <Routes> can match against.
 *   - Edit mode + overview continue to use direct-dispatch via
 *     `parseStudioPath()` inside <EditModeDispatcher>. Their dispatch
 *     does NOT need tail consumption (no nested tenant route tree).
 *
 * See docs/investigations/2026-05-13-studio-live-router-topology.md §2
 * Option A for the architectural decision.
 */
import { Suspense, lazy, useEffect, useMemo, useState } from "react"
import { Navigate, Route, Routes, useLocation } from "react-router-dom"
import { useAdminAuth } from "@/bridgeable-admin/lib/admin-auth-context"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import {
  computeInitialRailExpanded,
  parseStudioPath,
  STUDIO_RAIL_EXPANDED_KEY,
  writeLastVertical,
  type StudioEditorKey,
} from "@/bridgeable-admin/lib/studio-routes"
import { StudioTopBar } from "@/bridgeable-admin/components/studio/StudioTopBar"
import { StudioRail } from "@/bridgeable-admin/components/studio/StudioRail"
import { StudioRailContext } from "@/bridgeable-admin/components/studio/StudioRailContext"
// Builder AI Assistant Phase 1b — additive docked assistant-rail slot.
// Provider renders no DOM; the slot is null for every editor except the
// Workflow editor → byte-identical shell for the other 6 builders.
import {
  StudioAssistantSlotProvider,
  useStudioAssistantSlot,
} from "@/bridgeable-admin/components/studio/StudioAssistantSlotContext"
import StudioOverviewPage from "./StudioOverviewPage"
import StudioLiveModeWrap from "./StudioLiveModeWrap"

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
import FocusBuilderPage from "@/bridgeable-admin/components/focus-builder/FocusBuilderPage"
import WidgetBuilderPage from "@/bridgeable-admin/components/widget-builder/WidgetBuilderPage"
import WidgetListPage from "@/bridgeable-admin/components/widget-builder/WidgetListPage"


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


/**
 * Edit-mode + overview dispatcher. Reads `useLocation().pathname`,
 * runs `parseStudioPath`, and renders the matching overview or editor.
 *
 * This wrapper exists so Edit mode can continue to use the
 * direct-dispatch model (parseStudioPath classifies the URL by shape)
 * while Live mode opts into declarative nested-Routes consumption.
 * See investigation §2 Option A for the hybrid rationale.
 */
function EditModeDispatcher() {
  const location = useLocation()
  const parsed = useMemo(
    () => parseStudioPath(location.pathname.replace(/^\/bridgeable-admin/, "")),
    [location.pathname],
  )

  if (parsed.editor === null) {
    return <StudioOverviewPage activeVertical={parsed.vertical} />
  }
  const EditorPage = EDITOR_PAGES[parsed.editor]
  return <EditorPage />
}


export default function StudioShell() {
  const { user, loading } = useAdminAuth()
  const location = useLocation()

  const parsed = useMemo(
    () => parseStudioPath(location.pathname.replace(/^\/bridgeable-admin/, "")),
    [location.pathname],
  )

  // Rail-initial-state precedence (Studio 1a-i.B follow-up):
  //   1. localStorage["studio.railExpanded"] if set — operator's saved choice.
  //   2. Route-dependent default — expanded on overview, collapsed on editor / Live.
  // Once the operator toggles the rail at runtime, `setRailExpanded` writes
  // to localStorage (via StudioRail's onExpandedChange), so subsequent
  // navigations honor that choice regardless of route.
  const [railExpanded, setRailExpanded] = useState<boolean>(() => {
    if (typeof window !== "undefined") {
      try {
        const raw = window.localStorage.getItem(STUDIO_RAIL_EXPANDED_KEY)
        if (raw !== null) return raw === "true"
      } catch {
        // Fall through to route-based default.
      }
    }
    return computeInitialRailExpanded(location.pathname)
  })

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
  // Studio 1a-i.B follow-up #2 — auth gate delegation for Live mode.
  //
  // Edit-mode routes (/studio, /studio/:vertical, /studio/:editor,
  // /studio/:vertical/:editor, /studio/admin/*) redirect unauth users
  // to /login as before.
  //
  // Live-mode routes (/studio/live[/:vertical][/<tail>]) DELEGATE auth
  // handling to RuntimeEditorShell, which renders its own
  // `runtime-editor-unauth` / `runtime-editor-forbidden` surfaces with
  // mode-specific recovery affordances (sign-in CTA, admin-home CTA,
  // restart-impersonation CTA). Studio chrome is suppressed in this
  // case so the operator focuses on resolving auth rather than seeing
  // a teasing-but-inaccessible shell.
  //
  // See DECISIONS.md 2026-05-13 (PM) — "Studio mode-specific auth gate
  // delegation" for the rationale + future-mode pattern.
  if (!user && !parsed.isLive) {
    return <Navigate to={adminPath("/login")} replace />
  }

  const mode: "edit" | "live" = parsed.isLive ? "live" : "edit"

  // Live mode + unauthenticated: render the wrap directly without Studio
  // chrome. RuntimeEditorShell renders its own unauth/forbidden recovery
  // surface inside StudioLiveModeWrap.
  if (!user && parsed.isLive) {
    return (
      <div
        className="min-h-screen bg-surface-base text-content-base"
        data-studio-shell="true"
        data-studio-chrome="suppressed"
        data-mode="live"
      >
        <Suspense
          fallback={
            <div
              className="flex h-screen items-center justify-center text-content-muted"
              data-testid="studio-child-suspense"
            >
              Loading…
            </div>
          }
        >
          {/* Live wrap inside suppressed-chrome path still uses the
              same component; it reads vertical from useParams() now. */}
          <Routes>
            <Route path="live/:vertical/*" element={<StudioLiveModeWrap />} />
            <Route path="live/*" element={<StudioLiveModeWrap />} />
            <Route path="live" element={<StudioLiveModeWrap />} />
            <Route path="*" element={<StudioLiveModeWrap />} />
          </Routes>
        </Suspense>
      </div>
    )
  }

  return (
    <StudioAssistantSlotProvider>
    <StudioRailContext.Provider
      value={{ railExpanded, inStudioContext: true }}
    >
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
              {/* Hybrid dispatch (Studio 1a-i.B follow-up #3):
                  - Live mode uses nested <Routes> so React Router
                    consumes the `live/:vertical` prefix; the deep
                    tail flows to TenantRouteTree's nested Routes.
                  - Edit + overview routes fall through to the
                    direct-dispatch via parseStudioPath inside
                    <EditModeDispatcher>. */}
              <Routes>
                <Route
                  path="live/:vertical/*"
                  element={<StudioLiveModeWrap />}
                />
                <Route path="live/*" element={<StudioLiveModeWrap />} />
                <Route path="live" element={<StudioLiveModeWrap />} />
                {/* Sub-arc F-1: Focus Builder mounts at
                    /studio/builder/focuses. Explicit Route precedes
                    the EditModeDispatcher catch-all so the
                    parseStudioPath classifier doesn't see "builder"
                    as a vertical slug. */}
                <Route
                  path="builder/focuses"
                  element={<FocusBuilderPage />}
                />
                {/* WB-4a: Widget Builder mounts at
                    /studio/widget-builder[/:slug]. Slug-optional —
                    no slug shows the create landing card. Explicit
                    Routes precede the EditModeDispatcher catch-all
                    so parseStudioPath doesn't see "widget-builder" as
                    a vertical slug. */}
                <Route
                  path="widget-builder/:slug"
                  element={<WidgetBuilderPage />}
                />
                <Route
                  path="widget-builder"
                  element={<WidgetBuilderPage />}
                />
                {/* WB-4b: widget list view replaces the legacy
                    WidgetEditorPage at /studio/widgets. The legacy
                    editor remains on disk for the class-config sub-
                    flow until widget-class authoring migrates. */}
                <Route path="widgets" element={<WidgetListPage />} />
                <Route path="*" element={<EditModeDispatcher />} />
              </Routes>
            </Suspense>
          </main>
          {/* Phase 1b — additive docked assistant-rail slot. Null for every
              editor except Workflow → renders nothing → byte-identical shell
              for the other 6 builders. Rendered as a flex sibling after
              <main> so the rail docks to the right when present. */}
          <AssistantSlotOutlet />
        </div>
      </div>
    </StudioRailContext.Provider>
    </StudioAssistantSlotProvider>
  )
}


/**
 * Renders the Phase 1b assistant-rail slot. A separate component so it can read
 * the slot context (which lives INSIDE StudioAssistantSlotProvider — the
 * StudioShell body is the provider's parent and can't read it directly).
 * `rail` is null unless the active editor pushed one → byte-identical when empty.
 */
function AssistantSlotOutlet() {
  const { rail } = useStudioAssistantSlot()
  return <>{rail}</>
}


/* Lazy-mount export retained for cases where the admin app boundary
 * wants a Suspense fallback at the route level rather than inside the
 * shell. Currently unused; BridgeableAdminApp imports the default. */
export const StudioShellLazy = lazy(() => Promise.resolve({ default: StudioShell }))
