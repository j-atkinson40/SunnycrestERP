/**
 * Visual Editor landing page — describes the four editors + provides
 * quick stats from the in-memory component registry.
 *
 * Lives at /visual-editor (admin subdomain) or
 * /bridgeable-admin/visual-editor (path-based entry).
 */
import { useMemo } from "react"
import { Link } from "react-router-dom"
import { Component, GitBranch, Layers, Palette } from "lucide-react"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import { getAllRegistered, getKnownTokens } from "@/lib/visual-editor/registry"


export default function VisualEditorIndex() {
  const stats = useMemo(() => {
    const components = getAllRegistered()
    const tokens = getKnownTokens()
    return {
      componentCount: components.length,
      tokenCount: tokens.length,
      byKind: components.reduce<Record<string, number>>((acc, c) => {
        const kind = c.metadata.type
        acc[kind] = (acc[kind] ?? 0) + 1
        return acc
      }, {}),
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
          component configurations, and workflow templates — at platform,
          vertical, or tenant-override scope. Edits cascade through the
          same READ-time inheritance model the runtime app reads.
        </p>
      </div>

      <div className="mb-8 grid grid-cols-3 gap-4">
        <div className="rounded-md border border-border-subtle bg-surface-elevated p-4">
          <div className="text-caption text-content-muted">Components registered</div>
          <div className="text-h2 font-plex-serif text-content-strong">
            {stats.componentCount}
          </div>
        </div>
        <div className="rounded-md border border-border-subtle bg-surface-elevated p-4">
          <div className="text-caption text-content-muted">Design tokens</div>
          <div className="text-h2 font-plex-serif text-content-strong">
            {stats.tokenCount}
          </div>
        </div>
        <div className="rounded-md border border-border-subtle bg-surface-elevated p-4">
          <div className="text-caption text-content-muted">Component kinds</div>
          <div className="text-h2 font-plex-serif text-content-strong">
            {Object.keys(stats.byKind).length}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <EditorCard
          to="/visual-editor/themes"
          icon={Palette}
          title="Theme editor"
          description="OKLCH-native token editor with full-platform live preview. Edits flow through platform_themes with platform/vertical/tenant inheritance."
          testId="ve-card-themes"
        />
        <EditorCard
          to="/visual-editor/components"
          icon={Component}
          title="Component editor"
          description="Per-component prop override editor. Auto-generated controls per ConfigPropSchema type backed by component_configurations."
          testId="ve-card-components"
        />
        <EditorCard
          to="/visual-editor/workflows"
          icon={GitBranch}
          title="Workflow editor"
          description="Canvas authoring for vertical_default workflow templates. Locked-to-fork merge semantics for tenant customization."
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
}


function EditorCard({ to, icon: Icon, title, description, testId }: EditorCardProps) {
  return (
    <Link
      to={adminPath(to)}
      data-testid={testId}
      className="flex flex-col gap-2 rounded-md border border-border-subtle bg-surface-elevated p-5 transition-shadow hover:shadow-level-1"
    >
      <div className="flex items-center gap-2">
        <Icon size={18} className="text-accent" />
        <span className="text-h4 font-plex-serif text-content-strong">
          {title}
        </span>
      </div>
      <p className="text-body-sm text-content-muted">{description}</p>
    </Link>
  )
}
