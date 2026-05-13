/**
 * StudioOverviewPage — placeholder overview surface.
 *
 * Studio 1a-i.A1 ships a static section list with descriptions. NO
 * inventory counts, NO recent-edits feed. Inventory service ships in
 * Studio 1a-ii.
 *
 * Renders at:
 *   /studio                            — Platform overview
 *   /studio/:vertical                  — Vertical overview
 *
 * Vertical scope just changes the breadcrumb + the cards' target URLs;
 * card descriptions stay generic until 1a-ii surfaces per-scope counts.
 */
import { Link } from "react-router-dom"
import type { LucideIcon } from "lucide-react"
import {
  Boxes,
  FileText,
  Focus as FocusIcon,
  GitBranch,
  Layers,
  LayoutDashboard,
  Palette,
  PanelRightOpen,
  Plug,
} from "lucide-react"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import {
  PLATFORM_ONLY_EDITORS,
  studioPath,
  type StudioEditorKey,
} from "@/bridgeable-admin/lib/studio-routes"


export interface StudioOverviewPageProps {
  activeVertical: string | null
}


interface SectionCard {
  editor: StudioEditorKey
  title: string
  description: string
  icon: LucideIcon
  testId: string
}


const SECTIONS: SectionCard[] = [
  {
    editor: "themes",
    title: "Themes",
    icon: Palette,
    description:
      "Token-level editing — colors, surfaces, shadows, motion. Inheritance: platform → vertical → tenant.",
    testId: "studio-overview-card-themes",
  },
  {
    editor: "focuses",
    title: "Focus Editor",
    icon: FocusIcon,
    description:
      "Author Focus templates and their accessory-layer composition. Per-template config + composition authoring in one surface.",
    testId: "studio-overview-card-focuses",
  },
  {
    editor: "widgets",
    title: "Widget Editor",
    icon: LayoutDashboard,
    description:
      "Edit widgets at class level (shared defaults) or individually. Mode toggle keeps both authoring activities together.",
    testId: "studio-overview-card-widgets",
  },
  {
    editor: "documents",
    title: "Documents",
    icon: FileText,
    description:
      "Document template authoring — price lists, invoices, BOLs, certificates. Block-based authoring on the Documents arc substrate.",
    testId: "studio-overview-card-documents",
  },
  {
    editor: "classes",
    title: "Classes",
    icon: Boxes,
    description:
      "Cross-class defaults — shared shadow elevations, density, accent treatments. Platform-scope only.",
    testId: "studio-overview-card-classes",
  },
  {
    editor: "workflows",
    title: "Workflows",
    icon: GitBranch,
    description:
      "Canvas authoring for vertical_default workflow templates. Locked-to-fork merge semantics for tenant customization.",
    testId: "studio-overview-card-workflows",
  },
  {
    editor: "edge-panels",
    title: "Edge Panels",
    icon: PanelRightOpen,
    description:
      "Multi-page action panels — Cmd+Shift+E or right-edge handle invokes a tenant-branded sliding panel of buttons.",
    testId: "studio-overview-card-edge-panels",
  },
  {
    editor: "registry",
    title: "Registry inspector",
    icon: Layers,
    description:
      "In-memory component registry browser. Verify metadata coverage + reverse-lookup tokens to consumers. Platform-scope only.",
    testId: "studio-overview-card-registry",
  },
  {
    editor: "plugin-registry",
    title: "Plugin Registry",
    icon: Plug,
    description:
      "24 canonical plugin categories from PLUGIN_CONTRACTS.md grouped by maturity. Per-category contract details. Platform-scope only.",
    testId: "studio-overview-card-plugin-registry",
  },
]


export default function StudioOverviewPage({
  activeVertical,
}: StudioOverviewPageProps) {
  const scopeLabel = activeVertical
    ? `${activeVertical} vertical`
    : "Platform scope"

  return (
    <div
      className="mx-auto max-w-[1200px] px-6 py-8"
      data-testid="studio-overview"
      data-active-vertical={activeVertical ?? "platform"}
    >
      <div className="mb-8">
        <div
          className="mb-2 text-caption uppercase tracking-wide text-content-subtle"
          data-testid="studio-overview-scope-label"
        >
          {scopeLabel}
        </div>
        <h1 className="text-h1 font-plex-serif font-medium text-content-strong">
          Bridgeable Studio
        </h1>
        <p className="mt-2 text-body text-content-muted">
          Author the platform's visual and behavioral defaults at
          platform, vertical, or tenant-override scope. Edits cascade
          through the same READ-time inheritance model the runtime app
          reads.
          {activeVertical ? (
            <>
              {" "}
              Working scope: <strong>{activeVertical}</strong> — vertical
              overrides layer on top of the platform defaults.
            </>
          ) : (
            <>
              {" "}
              Working scope: <strong>Platform</strong> — defaults seen by
              every vertical unless overridden.
            </>
          )}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {SECTIONS.map((section) => {
          const isPlatformOnly = PLATFORM_ONLY_EDITORS.has(section.editor)
          const vertical = isPlatformOnly ? null : activeVertical
          const href = adminPath(
            studioPath({ vertical, editor: section.editor }),
          )
          const Icon = section.icon
          return (
            <Link
              key={section.editor}
              to={href}
              data-testid={section.testId}
              className="flex flex-col gap-2 rounded-md border border-border-subtle bg-surface-elevated p-5 transition-shadow hover:shadow-level-1"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Icon size={18} className="text-accent" />
                  <span className="text-h4 font-plex-serif text-content-strong">
                    {section.title}
                  </span>
                </div>
                {isPlatformOnly && (
                  <span className="rounded-sm bg-surface-sunken px-2 py-0.5 text-caption font-plex-mono text-content-muted">
                    Platform
                  </span>
                )}
              </div>
              <p className="text-body-sm text-content-muted">
                {section.description}
              </p>
            </Link>
          )
        })}
      </div>

      <div
        className="mt-8 rounded-md border border-dashed border-border-subtle bg-surface-sunken p-5 text-caption text-content-muted"
        data-testid="studio-overview-inventory-placeholder"
      >
        Per-section inventory counts and recent edits ship in Studio
        1a-ii.
      </div>
    </div>
  )
}
