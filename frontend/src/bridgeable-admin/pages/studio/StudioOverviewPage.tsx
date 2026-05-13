/**
 * StudioOverviewPage — live overview surface.
 *
 * Studio 1a-i.A1 shipped a static section list with descriptions.
 * Studio 1a-ii adds live data:
 *   - Per-section counts on each card (omitted when null)
 *   - Recent edits feed below the card grid
 *
 * Renders at:
 *   /studio                            — Platform overview
 *   /studio/:vertical                  — Vertical overview
 *
 * Vertical scope changes the breadcrumb, card target URLs, and the
 * scope of the live data fetched from the inventory endpoint.
 *
 * Recent-edits source: per-table `updated_at` (Studio 1a-ii Path A
 * pivot per locked decision 6). Editor attribution silently omitted
 * when null — no "by —" placeholder. Card count display omitted
 * when count is null (Registry inspector + Plugin Registry under
 * vertical scope).
 */
import { useEffect, useState } from "react"
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
import {
  getStudioInventory,
  StudioInventoryError,
  type InventoryResponse,
  type RecentEditEntry,
} from "@/bridgeable-admin/lib/studio-inventory-client"


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


// Section labels for the recent-edits feed. Mirrors A1's SECTIONS
// titles so "Edited X in {section}" reads naturally regardless of
// which underlying table the row came from.
const SECTION_LABEL_BY_KEY: Record<string, string> = SECTIONS.reduce(
  (acc, s) => {
    acc[s.editor] = s.title
    return acc
  },
  {} as Record<string, string>,
)


export default function StudioOverviewPage({
  activeVertical,
}: StudioOverviewPageProps) {
  const scopeLabel = activeVertical
    ? `${activeVertical} vertical`
    : "Platform scope"

  const [inventory, setInventory] = useState<InventoryResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getStudioInventory(activeVertical)
      .then((data) => {
        if (cancelled) return
        setInventory(data)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const msg =
          err instanceof StudioInventoryError
            ? err.message
            : "Failed to load inventory."
        setError(msg)
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [activeVertical])

  // Build a count lookup. When inventory isn't loaded yet, every
  // card renders with count omitted (loading state).
  const countByKey: Record<string, number | null> =
    inventory?.sections.reduce(
      (acc, s) => {
        acc[s.key] = s.count
        return acc
      },
      {} as Record<string, number | null>,
    ) ?? {}

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
          const count =
            inventory && section.editor in countByKey
              ? countByKey[section.editor]
              : null
          const showCount = inventory != null && count !== null
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
                <div className="flex items-center gap-2">
                  {showCount && (
                    <span
                      className="rounded-sm bg-surface-sunken px-2 py-0.5 text-caption font-plex-mono text-content-strong"
                      data-testid={`${section.testId}-count`}
                    >
                      {count}
                    </span>
                  )}
                  {isPlatformOnly && (
                    <span className="rounded-sm bg-surface-sunken px-2 py-0.5 text-caption font-plex-mono text-content-muted">
                      Platform
                    </span>
                  )}
                </div>
              </div>
              <p className="text-body-sm text-content-muted">
                {section.description}
              </p>
            </Link>
          )
        })}
      </div>

      <div
        className="mt-8"
        data-testid="studio-overview-recent-edits"
      >
        <h2 className="mb-3 text-h4 font-plex-serif font-medium text-content-strong">
          Recent edits
        </h2>
        {loading && (
          <div
            className="rounded-md border border-dashed border-border-subtle bg-surface-sunken p-5 text-caption text-content-muted"
            data-testid="studio-overview-recent-edits-loading"
          >
            Loading recent edits…
          </div>
        )}
        {!loading && error && (
          <div
            className="rounded-md border border-border-subtle bg-surface-sunken p-5 text-body-sm text-status-error"
            data-testid="studio-overview-recent-edits-error"
          >
            {error}
          </div>
        )}
        {!loading && !error && inventory && inventory.recent_edits.length === 0 && (
          <div
            className="rounded-md border border-dashed border-border-subtle bg-surface-sunken p-5 text-caption text-content-muted"
            data-testid="studio-overview-recent-edits-empty"
          >
            No recent edits.
          </div>
        )}
        {!loading && !error && inventory && inventory.recent_edits.length > 0 && (
          <ul
            className="flex flex-col gap-1 rounded-md border border-border-subtle bg-surface-elevated p-2"
            data-testid="studio-overview-recent-edits-list"
          >
            {inventory.recent_edits.map((entry) => (
              <RecentEditRow key={`${entry.section}:${entry.entity_id}`} entry={entry} />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}


function RecentEditRow({ entry }: { entry: RecentEditEntry }) {
  const sectionLabel = SECTION_LABEL_BY_KEY[entry.section] ?? entry.section
  const relative = formatRelativeTime(entry.edited_at)
  return (
    <li>
      <Link
        to={adminPath(entry.deep_link_path)}
        className="flex flex-wrap items-baseline gap-x-2 rounded-sm px-3 py-2 text-body-sm text-content-base hover:bg-surface-sunken"
        data-testid="studio-overview-recent-edit-row"
        data-section={entry.section}
        data-entity-id={entry.entity_id}
      >
        <span>
          Edited <strong className="text-content-strong">{entry.entity_name}</strong>{" "}
          in <span className="text-content-muted">{sectionLabel}</span> —{" "}
          <span className="text-content-muted">{relative}</span>
        </span>
        {entry.editor_email && (
          <span className="text-caption text-content-subtle">
            by {entry.editor_email}
          </span>
        )}
      </Link>
    </li>
  )
}


/**
 * Lightweight relative-time formatter. No new dep — internal-only
 * mapping. Falls back to ISO date when older than 7 days (shouldn't
 * occur given the 7-day server-side cutoff, but defensive).
 */
function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return iso
  const now = Date.now()
  const deltaMs = now - then
  if (deltaMs < 0) return "just now"
  const minutes = Math.floor(deltaMs / (60 * 1000))
  if (minutes < 1) return "just now"
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(iso).toISOString().slice(0, 10)
}
