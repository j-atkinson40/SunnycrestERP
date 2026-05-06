/**
 * Visual Editor landing page — describes the seven editor surfaces +
 * provides quick stats from the in-memory component registry.
 *
 * Lives at /visual-editor (admin subdomain) or
 * /bridgeable-admin/visual-editor (path-based entry).
 *
 * Reorganized May 2026: previous Component Editor + Compositions
 * pages dismantled in favor of purpose-specific surfaces (Focus
 * Editor combines composition + per-template config; Widget Editor
 * handles class + individual widget editing in one surface).
 * Documents tab is placeholder for next-phase document authoring.
 */
import { useMemo } from "react"
import { Link } from "react-router-dom"
import {
  Boxes,
  FileText,
  Focus as FocusIcon,
  GitBranch,
  Layers,
  LayoutDashboard,
  Palette,
} from "lucide-react"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import { getAllRegistered, getKnownTokens } from "@/lib/visual-editor/registry"


export default function VisualEditorIndex() {
  const stats = useMemo(() => {
    const components = getAllRegistered()
    const tokens = getKnownTokens()
    const widgetCount = components.filter(
      (c) => c.metadata.type === "widget",
    ).length
    const focusTypeCount = components.filter(
      (c) => c.metadata.type === "focus",
    ).length
    const focusTemplateCount = components.filter(
      (c) => c.metadata.type === "focus-template",
    ).length
    return {
      componentCount: components.length,
      tokenCount: tokens.length,
      widgetCount,
      focusTypeCount,
      focusTemplateCount,
    }
  }, [])

  return (
    <div className="mx-auto max-w-[1200px] px-6 py-8">
      <div className="mb-8">
        <h1 className="text-h1 font-plex-serif font-medium text-content-strong">
          Visual Editor
        </h1>
        <p className="mt-2 text-body text-content-muted">
          Author the platform's visual + behavioral defaults — themes,
          Focus layouts, widget configurations, and workflow templates —
          at platform, vertical, or tenant-override scope. Edits cascade
          through the same READ-time inheritance model the runtime app
          reads.
        </p>
      </div>

      <div className="mb-8 grid grid-cols-3 gap-4">
        <div className="rounded-md border border-border-subtle bg-surface-elevated p-4">
          <div className="text-caption text-content-muted">Design tokens</div>
          <div className="text-h2 font-plex-serif text-content-strong">
            {stats.tokenCount}
          </div>
        </div>
        <div className="rounded-md border border-border-subtle bg-surface-elevated p-4">
          <div className="text-caption text-content-muted">Components</div>
          <div className="text-h2 font-plex-serif text-content-strong">
            {stats.componentCount}
          </div>
        </div>
        <div className="rounded-md border border-border-subtle bg-surface-elevated p-4">
          <div className="text-caption text-content-muted">Widgets registered</div>
          <div className="text-h2 font-plex-serif text-content-strong">
            {stats.widgetCount}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <EditorCard
          to="/visual-editor/themes"
          icon={Palette}
          title="Themes"
          description="Token-level editing — colors, surfaces, shadows, motion. Full-platform live preview against the canonical 17 reference components. Inheritance: platform → vertical → tenant."
          testId="ve-card-themes"
          stats={`${stats.tokenCount} tokens`}
        />
        <EditorCard
          to="/visual-editor/focuses"
          icon={FocusIcon}
          title="Focus Editor"
          description="Author Focus templates and their accessory-layer composition. Combines per-template configuration and composition authoring in one surface. Five Focus types: Decision, Coordination, Execution, Review, Generation."
          testId="ve-card-focuses"
          stats={`${stats.focusTypeCount} types · ${stats.focusTemplateCount} templates`}
        />
        <EditorCard
          to="/visual-editor/widgets"
          icon={LayoutDashboard}
          title="Widget Editor"
          description="Edit widgets at class level (cross-cutting widget defaults) or individually (per-widget configuration). Mode toggle keeps both authoring activities in one surface."
          testId="ve-card-widgets"
          stats={`${stats.widgetCount} widgets`}
        />
        <EditorCard
          to="/visual-editor/documents"
          icon={FileText}
          title="Documents"
          description="Document template authoring — price lists, invoices, BOLs, certificates. Built on the existing Documents arc substrate. Comprehensive editor with block library, variable binding, conditional sections, vertical-default templates, and live preview."
          testId="ve-card-documents"
          stats="Coming in Phase 2"
        />
        <EditorCard
          to="/visual-editor/classes"
          icon={Boxes}
          title="Classes"
          description="Cross-class defaults — shared shadow elevations, density, accent treatments, etc. Inherits to per-component scopes. Cross-class view of every component class in one surface."
          testId="ve-card-classes"
        />
        <EditorCard
          to="/visual-editor/workflows"
          icon={GitBranch}
          title="Workflows"
          description="Canvas authoring for vertical_default workflow templates. Hierarchical browser categorizes by workflow type. Locked-to-fork merge semantics for tenant customization."
          testId="ve-card-workflows"
        />
        <EditorCard
          to="/visual-editor/registry"
          icon={Layers}
          title="Registry inspector"
          description="In-memory component registry browser. Verify metadata coverage + reverse-lookup tokens to consumers."
          testId="ve-card-registry"
        />
      </div>
    </div>
  )
}


interface EditorCardProps {
  to: string
  icon: typeof Palette
  title: string
  description: string
  testId: string
  stats?: string
}


function EditorCard({
  to,
  icon: Icon,
  title,
  description,
  testId,
  stats,
}: EditorCardProps) {
  return (
    <Link
      to={adminPath(to)}
      data-testid={testId}
      className="flex flex-col gap-2 rounded-md border border-border-subtle bg-surface-elevated p-5 transition-shadow hover:shadow-level-1"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon size={18} className="text-accent" />
          <span className="text-h4 font-plex-serif text-content-strong">
            {title}
          </span>
        </div>
        {stats && (
          <span className="rounded-sm bg-surface-sunken px-2 py-0.5 text-caption font-plex-mono text-content-muted">
            {stats}
          </span>
        )}
      </div>
      <p className="text-body-sm text-content-muted">{description}</p>
    </Link>
  )
}
