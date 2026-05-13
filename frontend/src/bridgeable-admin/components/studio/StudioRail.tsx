/**
 * StudioRail — persistent left rail.
 *
 * Two render modes via shared state:
 *   - expanded (~240px) — section list with labels + active highlight
 *   - icon strip (~48px) — vertical stack of icons only
 *
 * Rail collapses (not replaces) when the operator clicks into an
 * editor: clicking a section navigates to that editor's URL AND
 * collapses to icon-strip so the editor's own left pane has room.
 * The operator clicks the icon strip to expand the rail back.
 *
 * Per Studio 1a-i.A1 build prompt: rail-collapses-not-replaces is the
 * canonical model. Editor adaptation to "hide their left pane when
 * rail is expanded" is deferred to 1a-i.B.
 *
 * Rail expand state persists to localStorage (key `studio.railExpanded`).
 */
import { useEffect } from "react"
import { Link, useNavigate } from "react-router-dom"
import {
  Boxes,
  ChevronLeft,
  ChevronRight,
  FileText,
  Focus as FocusIcon,
  GitBranch,
  Layers,
  LayoutDashboard,
  Layout as OverviewIcon,
  PanelRightOpen,
  Palette,
  Plug,
  Sparkles,
  type LucideIcon,
} from "lucide-react"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import {
  PLATFORM_ONLY_EDITORS,
  STUDIO_RAIL_EXPANDED_KEY,
  studioPath,
  type StudioEditorKey,
  writeRailExpanded,
} from "@/bridgeable-admin/lib/studio-routes"


interface RailEntry {
  /** null = overview link, otherwise editor key. */
  editor: StudioEditorKey | null
  label: string
  icon: LucideIcon
  /** Disabled state — renders dimmed + non-clickable. */
  disabled?: boolean
  /** Label suffix (e.g. "Coming soon"). */
  badge?: string
}


/** Order = display order in the rail. Mirrors VisualEditorIndex card order. */
const RAIL_ENTRIES: RailEntry[] = [
  { editor: null, label: "Overview", icon: OverviewIcon },
  { editor: "themes", label: "Themes", icon: Palette },
  { editor: "focuses", label: "Focuses", icon: FocusIcon },
  { editor: "widgets", label: "Widgets", icon: LayoutDashboard },
  { editor: "documents", label: "Documents", icon: FileText },
  { editor: "classes", label: "Classes", icon: Boxes },
  { editor: "workflows", label: "Workflows", icon: GitBranch },
  { editor: "edge-panels", label: "Edge Panels", icon: PanelRightOpen },
  { editor: "registry", label: "Registry", icon: Layers },
  { editor: "plugin-registry", label: "Plugin Registry", icon: Plug },
]


export interface StudioRailProps {
  expanded: boolean
  onExpandedChange: (next: boolean) => void
  activeVertical: string | null
  activeEditor: StudioEditorKey | null
  /** Currently active mode — drives Spaces "Coming soon" badge etc. */
  mode: "edit" | "live"
}


export function StudioRail({
  expanded,
  onExpandedChange,
  activeVertical,
  activeEditor,
  mode,
}: StudioRailProps) {
  // Persist on change.
  useEffect(() => {
    writeRailExpanded(expanded)
  }, [expanded])

  const navigate = useNavigate()

  const handleEntryClick = (entry: RailEntry) => {
    if (entry.disabled) return
    // Navigate to the editor's URL.
    const isPlatformOnly =
      entry.editor !== null && PLATFORM_ONLY_EDITORS.has(entry.editor)
    const vertical = isPlatformOnly ? null : activeVertical
    navigate(studioPath({ vertical, editor: entry.editor }))
    // Rail-collapses-not-replaces: when an editor opens, collapse to
    // icon strip so the editor's left pane can take the space.
    // Overview clicks DON'T collapse the rail.
    if (entry.editor !== null) {
      onExpandedChange(false)
    }
  }

  if (!expanded) {
    return (
      <aside
        className="flex w-12 flex-col items-center gap-1 border-r border-border-subtle bg-surface-sunken py-3"
        data-testid="studio-rail"
        data-rail-expanded="false"
        data-rail-mode={mode}
      >
        <button
          type="button"
          onClick={() => onExpandedChange(true)}
          data-testid="studio-rail-expand"
          title="Expand rail"
          className="mb-2 flex h-8 w-8 items-center justify-center rounded-sm text-content-muted hover:bg-accent-subtle hover:text-content-strong"
        >
          <ChevronRight size={16} />
        </button>
        {RAIL_ENTRIES.map((entry) => {
          const Icon = entry.icon
          const active = entry.editor === activeEditor
          const isOverview = entry.editor === null && activeEditor === null
          return (
            <button
              key={entry.label}
              type="button"
              disabled={entry.disabled}
              onClick={() => handleEntryClick(entry)}
              data-testid={`studio-rail-icon-${entry.editor ?? "overview"}`}
              data-active={active || isOverview ? "true" : "false"}
              title={entry.label}
              className={
                active || isOverview
                  ? "flex h-8 w-8 items-center justify-center rounded-sm bg-accent-subtle text-accent"
                  : entry.disabled
                    ? "flex h-8 w-8 items-center justify-center rounded-sm text-content-subtle opacity-50"
                    : "flex h-8 w-8 items-center justify-center rounded-sm text-content-muted hover:bg-accent-subtle hover:text-content-strong"
              }
            >
              <Icon size={16} />
            </button>
          )
        })}
        {/* Spaces stub — "Coming soon", disabled. */}
        <div
          className="mt-auto flex h-8 w-8 items-center justify-center rounded-sm text-content-subtle opacity-50"
          title="Spaces — coming soon"
          data-testid="studio-rail-icon-spaces"
        >
          <Sparkles size={16} />
        </div>
      </aside>
    )
  }

  return (
    <aside
      className="flex w-60 flex-col gap-1 border-r border-border-subtle bg-surface-sunken px-2 py-3"
      data-testid="studio-rail"
      data-rail-expanded="true"
      data-rail-mode={mode}
    >
      <div className="mb-2 flex items-center justify-between px-2">
        <span
          className="text-caption font-medium uppercase tracking-wide text-content-subtle"
          data-localstorage-key={STUDIO_RAIL_EXPANDED_KEY}
        >
          Studio
        </span>
        <button
          type="button"
          onClick={() => onExpandedChange(false)}
          data-testid="studio-rail-collapse"
          title="Collapse rail"
          className="flex h-6 w-6 items-center justify-center rounded-sm text-content-muted hover:bg-accent-subtle hover:text-content-strong"
        >
          <ChevronLeft size={14} />
        </button>
      </div>
      {RAIL_ENTRIES.map((entry) => {
        const Icon = entry.icon
        const active = entry.editor === activeEditor
        const isOverview = entry.editor === null && activeEditor === null
        const isPlatformOnly =
          entry.editor !== null && PLATFORM_ONLY_EDITORS.has(entry.editor)
        const vertical = isPlatformOnly ? null : activeVertical
        const to = adminPath(studioPath({ vertical, editor: entry.editor }))
        if (entry.disabled) {
          return (
            <div
              key={entry.label}
              data-testid={`studio-rail-entry-${entry.editor ?? "overview"}`}
              className="flex items-center gap-2 rounded-sm px-2 py-1.5 text-body-sm text-content-subtle opacity-50"
            >
              <Icon size={14} />
              <span>{entry.label}</span>
              {entry.badge && (
                <span className="ml-auto rounded-sm bg-surface-base px-1.5 py-0.5 text-caption text-content-subtle">
                  {entry.badge}
                </span>
              )}
            </div>
          )
        }
        return (
          <Link
            key={entry.label}
            to={to}
            data-testid={`studio-rail-entry-${entry.editor ?? "overview"}`}
            data-active={active || isOverview ? "true" : "false"}
            onClick={(e) => {
              // Use explicit handler so the rail collapse-on-editor-open
              // logic runs regardless of React-router link click default.
              e.preventDefault()
              handleEntryClick(entry)
            }}
            className={
              active || isOverview
                ? "flex items-center gap-2 rounded-sm bg-accent-subtle px-2 py-1.5 text-body-sm font-medium text-accent"
                : "flex items-center gap-2 rounded-sm px-2 py-1.5 text-body-sm text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong"
            }
          >
            <Icon size={14} />
            <span>{entry.label}</span>
            {isPlatformOnly && (
              <span className="ml-auto rounded-sm bg-surface-base px-1.5 py-0.5 text-caption text-content-subtle font-plex-mono">
                Platform
              </span>
            )}
          </Link>
        )
      })}
      <div className="mt-2 border-t border-border-subtle pt-2">
        <div
          className="flex items-center gap-2 rounded-sm px-2 py-1.5 text-body-sm text-content-subtle opacity-60"
          data-testid="studio-rail-entry-spaces"
        >
          <Sparkles size={14} />
          <span>Spaces</span>
          <span className="ml-auto rounded-sm bg-surface-base px-1.5 py-0.5 text-caption text-content-subtle">
            Soon
          </span>
        </div>
      </div>
    </aside>
  )
}
