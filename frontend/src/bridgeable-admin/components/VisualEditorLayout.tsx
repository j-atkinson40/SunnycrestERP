/**
 * VisualEditorLayout — chrome for the four visual editor pages
 * (themes / components / workflows / registry) inside the Bridgeable
 * admin platform.
 *
 * Distinct from AdminLayout: this layout uses the warm Bridgeable
 * design tokens (--surface-base, --content-strong, --accent, etc.)
 * because the editors are previewing those tokens. The operational
 * admin pages (Health Dashboard, Tenants Kanban, etc.) keep
 * AdminLayout's slate chrome — the two layouts coexist.
 *
 * Auth gating mirrors AdminLayout: redirects to AdminLogin when no
 * platform user is authenticated. Both layouts share AdminAuthProvider
 * which is mounted at BridgeableAdminApp's root.
 */
import type { ReactNode } from "react"
import { Link, Navigate, useLocation } from "react-router-dom"
import {
  ArrowLeft,
  Boxes,
  FileText,
  Focus as FocusIcon,
  GitBranch,
  Layers,
  LayoutDashboard,
  Library,
  Palette,
  Plug,
} from "lucide-react"
import { useAdminAuth } from "../lib/admin-auth-context"
import { adminPath } from "../lib/admin-routes"
import { EnvironmentBanner } from "./EnvironmentBanner"


type EditorTab = {
  to: string
  label: string
  icon: typeof Palette
  testId: string
}


const EDITOR_TABS: EditorTab[] = [
  { to: "/visual-editor", label: "Overview", icon: Library, testId: "ve-tab-overview" },
  { to: "/visual-editor/themes", label: "Themes", icon: Palette, testId: "ve-tab-themes" },
  { to: "/visual-editor/focuses", label: "Focus Editor", icon: FocusIcon, testId: "ve-tab-focuses" },
  { to: "/visual-editor/widgets", label: "Widget Editor", icon: LayoutDashboard, testId: "ve-tab-widgets" },
  { to: "/visual-editor/documents", label: "Documents", icon: FileText, testId: "ve-tab-documents" },
  { to: "/visual-editor/classes", label: "Classes", icon: Boxes, testId: "ve-tab-classes" },
  { to: "/visual-editor/workflows", label: "Workflows", icon: GitBranch, testId: "ve-tab-workflows" },
  { to: "/visual-editor/registry", label: "Registry", icon: Layers, testId: "ve-tab-registry" },
  { to: "/visual-editor/plugin-registry", label: "Plugin Registry", icon: Plug, testId: "ve-tab-plugin-registry" },
]


function isActive(tabPath: string, currentPath: string): boolean {
  // Strip the /bridgeable-admin prefix if present so logic works
  // identically across path-based + subdomain-based entry.
  const stripped = currentPath.replace(/^\/bridgeable-admin/, "") || "/"
  if (tabPath === "/visual-editor") {
    return stripped === "/visual-editor" || stripped === "/visual-editor/"
  }
  return stripped === tabPath || stripped.startsWith(`${tabPath}/`)
}


interface VisualEditorLayoutProps {
  children: ReactNode
  /**
   * Optional scope indicator content. When the editor is in
   * vertical_default or tenant_override scope, pass a string like
   * "Editing Tenant Override for: Hopkins Funeral Home (funeral_home)"
   * and it will render as a persistent banner above the page content.
   */
  scopeIndicator?: ReactNode
}


export function VisualEditorLayout({
  children,
  scopeIndicator,
}: VisualEditorLayoutProps) {
  const { user, loading } = useAdminAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-base text-content-muted">
        Loading…
      </div>
    )
  }
  if (!user) {
    return <Navigate to={adminPath("/login")} replace />
  }

  return (
    <div
      className="min-h-screen bg-surface-base text-content-base"
      data-visual-editor-layout="true"
    >
      <EnvironmentBanner />
      <header className="border-b border-border-subtle bg-surface-elevated">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4 px-6 py-3">
          <div className="flex items-center gap-3">
            <Link
              to={adminPath("/")}
              className="flex items-center gap-1.5 text-caption text-content-muted hover:text-content-strong"
              data-testid="ve-back-to-admin"
            >
              <ArrowLeft size={12} />
              Back to Admin
            </Link>
            <span className="text-content-subtle">·</span>
            <span className="text-h4 font-plex-serif text-content-strong">
              Visual Editor
            </span>
          </div>
          <nav className="flex items-center gap-1" data-testid="ve-nav">
            {EDITOR_TABS.map((tab) => {
              const Icon = tab.icon
              const active = isActive(tab.to, location.pathname)
              return (
                <Link
                  key={tab.to}
                  to={adminPath(tab.to)}
                  className={
                    active
                      ? "flex items-center gap-1.5 rounded-sm bg-accent-subtle px-3 py-1.5 text-body-sm font-medium text-accent"
                      : "flex items-center gap-1.5 rounded-sm px-3 py-1.5 text-body-sm text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong"
                  }
                  data-testid={tab.testId}
                  data-active={active ? "true" : "false"}
                >
                  <Icon size={14} />
                  {tab.label}
                </Link>
              )
            })}
          </nav>
        </div>
        {scopeIndicator && (
          <div
            className="mx-auto max-w-[1600px] border-t border-border-subtle bg-surface-sunken px-6 py-2 text-caption text-content-muted"
            data-testid="ve-scope-indicator"
          >
            {scopeIndicator}
          </div>
        )}
      </header>
      <main className="px-0">{children}</main>
    </div>
  )
}
