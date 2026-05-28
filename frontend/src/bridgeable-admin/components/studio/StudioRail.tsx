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
import { useEffect, useState } from "react"
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
  Wand2,
  X,
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
  /**
   * Sub-arc F-1.1 (Q-41): non-editor entries that route to a
   * standalone URL outside the studio editor space. When set,
   * navigation bypasses studioPath() and uses this absolute path.
   * Also signals to the rail to render a dismissible "New" badge
   * gated on the F-1.1 dismissal localStorage key.
   */
  overrideHref?: string
  /** Stable id for the dismissible-affordance localStorage key. */
  newAffordanceId?: string
  /**
   * Stable testid suffix for overrideHref entries (which lack an
   * editor key to derive from). Required when multiple overrideHref
   * entries coexist so test ids don't collide. Sub-arc WB-cycle-
   * followup-1 added this for the Widget Builder rail entry.
   */
  testIdSuffix?: string
}


/**
 * Sub-arc F-1.1 (Q-41): per-operator dismissal of the "New" badge on
 * the Focus Builder rail entry. Once dismissed the affordance hides;
 * direct route still works. Single key per affordance — currently only
 * Focus Builder, but the pattern scales.
 */
export const FOCUS_BUILDER_RAIL_BANNER_KEY =
  "bridgeable.focus-builder.studio-rail-banner-dismissed"


/**
 * Sub-arc WB-cycle-followup-1: per-operator dismissal of the "New"
 * badge on the Widget Builder rail entry. Mirrors F-1.1's
 * FOCUS_BUILDER_RAIL_BANNER_KEY shape (per studio nav investigation
 * 3a019e1 Q-A3 lock).
 */
export const WIDGET_BUILDER_RAIL_BANNER_KEY =
  "bridgeable.widget-builder.studio-rail-banner-dismissed"


/**
 * Workflow Builder nav pass (discoverability polish): per-operator
 * dismissal of the "New" badge on the relabeled "Workflow Builder" rail
 * entry. Mirrors the Focus/Widget banner-key shape. Unlike those two,
 * Workflow Builder is a SINGLE editor-keyed entry (relabel, not a
 * sibling) — the rebuilt Surface 3 was already reachable at
 * /studio/workflows; this only surfaces it as a builder with a New
 * badge. The two-entry viewer+builder pattern is transitional pending a
 * signal-driven Studio nav cleanup arc, so no sibling is added here.
 */
export const WORKFLOW_BUILDER_RAIL_BANNER_KEY =
  "bridgeable.workflow-builder.studio-rail-banner-dismissed"


/** Order = display order in the rail. Mirrors VisualEditorIndex card order. */
const RAIL_ENTRIES: RailEntry[] = [
  { editor: null, label: "Overview", icon: OverviewIcon },
  { editor: "themes", label: "Themes", icon: Palette },
  { editor: "focuses", label: "Focuses", icon: FocusIcon },
  // Sub-arc F-1.1 (Q-41 LOCKED, Implementation B): separate Focus
  // Builder rail entry alongside existing Focuses. Both routes are
  // reachable; this entry surfaces /studio/builder/focuses with a
  // dismissible "New" badge so operators discover the new surface.
  {
    editor: null,
    label: "Focus Builder",
    icon: Sparkles,
    overrideHref: "/studio/builder/focuses",
    newAffordanceId: FOCUS_BUILDER_RAIL_BANNER_KEY,
    testIdSuffix: "focus-builder",
  },
  { editor: "widgets", label: "Widgets", icon: LayoutDashboard },
  // Sub-arc WB-cycle-followup-1 (studio nav investigation 3a019e1):
  // Widget Builder rail entry surfaces the WB-1..WB-8 cycle authoring
  // tool. Routes to /studio/widgets list view (Q-A4 lock) which
  // exposes both existing widgets and the "+ New Widget" affordance.
  // Mirrors F-1.1's overrideHref + newAffordanceId substrate verbatim.
  {
    editor: null,
    label: "Widget Builder",
    icon: Wand2,
    overrideHref: "/studio/widgets",
    newAffordanceId: WIDGET_BUILDER_RAIL_BANNER_KEY,
    testIdSuffix: "widget-builder",
  },
  { editor: "documents", label: "Documents", icon: FileText },
  { editor: "classes", label: "Classes", icon: Boxes },
  // Workflow Builder nav pass: the single editor-keyed entry is
  // relabeled "Workflow Builder" + carries the dismissible "New" badge
  // (Option B — no sibling). editor:"workflows" preserved so the route
  // stays /studio/workflows → the rebuilt WorkflowEditorPage (Surface
  // 3). showNewBadge is already gated on newAffordanceId presence (not
  // overrideHref), so this editor-keyed entry gets the badge with no
  // badge-path change. GitBranch icon kept — the workflow canvas is a
  // branching graph.
  {
    editor: "workflows",
    label: "Workflow Builder",
    icon: GitBranch,
    newAffordanceId: WORKFLOW_BUILDER_RAIL_BANNER_KEY,
    testIdSuffix: "workflow-builder",
  },
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

  // Sub-arc F-1.1: per-operator dismissal of the Focus Builder "New"
  // badge. localStorage is read once on mount; setter triggers a
  // re-render via state so the badge disappears in place.
  const [dismissedAffordances, setDismissedAffordances] = useState<
    Record<string, boolean>
  >(() => {
    if (typeof window === "undefined") return {} as Record<string, boolean>
    try {
      const initial: Record<string, boolean> = {}
      initial[FOCUS_BUILDER_RAIL_BANNER_KEY] =
        window.localStorage.getItem(FOCUS_BUILDER_RAIL_BANNER_KEY) === "1"
      initial[WIDGET_BUILDER_RAIL_BANNER_KEY] =
        window.localStorage.getItem(WIDGET_BUILDER_RAIL_BANNER_KEY) === "1"
      initial[WORKFLOW_BUILDER_RAIL_BANNER_KEY] =
        window.localStorage.getItem(WORKFLOW_BUILDER_RAIL_BANNER_KEY) === "1"
      return initial
    } catch {
      return {} as Record<string, boolean>
    }
  })

  const dismissAffordance = (id: string) => {
    try {
      window.localStorage.setItem(id, "1")
    } catch {
      /* ignore (private mode etc.) */
    }
    setDismissedAffordances((prev) => ({ ...prev, [id]: true }))
  }

  const handleEntryClick = (entry: RailEntry) => {
    if (entry.disabled) return
    // Sub-arc F-1.1: overrideHref escapes the studioPath() builder for
    // entries that point at non-editor URLs (e.g. /studio/builder/focuses).
    if (entry.overrideHref) {
      navigate(entry.overrideHref)
      // Collapse rail to give the standalone surface room, mirroring
      // editor-open behavior.
      onExpandedChange(false)
      return
    }
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
          const active = entry.editor === activeEditor && !entry.overrideHref
          const isOverview =
            entry.editor === null &&
            activeEditor === null &&
            !entry.overrideHref
          // Sub-arc F-1.1: same testid scheme as expanded mode for
          // overrideHref entries. Sub-arc WB-cycle-followup-1: prefer
          // entry.testIdSuffix when present so multiple overrideHref
          // entries (Focus Builder + Widget Builder) get stable distinct
          // ids.
          const iconTestIdSuffix =
            entry.testIdSuffix ?? (entry.editor ?? "overview")
          return (
            <button
              key={entry.label}
              type="button"
              disabled={entry.disabled}
              onClick={() => handleEntryClick(entry)}
              data-testid={`studio-rail-icon-${iconTestIdSuffix}`}
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
        // Sub-arc F-1.1: overrideHref entries are never "active" via the
        // activeEditor signal (they don't have an editor key) and are
        // never the Overview entry. We treat them as routing-only.
        const active = entry.editor === activeEditor && !entry.overrideHref
        const isOverview =
          entry.editor === null &&
          activeEditor === null &&
          !entry.overrideHref
        const isPlatformOnly =
          entry.editor !== null && PLATFORM_ONLY_EDITORS.has(entry.editor)
        const vertical = isPlatformOnly ? null : activeVertical
        const to = entry.overrideHref
          ? adminPath(entry.overrideHref)
          : adminPath(studioPath({ vertical, editor: entry.editor }))
        const showNewBadge =
          !!entry.newAffordanceId &&
          !dismissedAffordances[entry.newAffordanceId]
        // Stable testid: overrideHref entries (editor=null) need a
        // distinct id from Overview (no overrideHref, editor=null).
        // Sub-arc WB-cycle-followup-1: prefer entry.testIdSuffix when
        // present so Focus Builder + Widget Builder (and future
        // overrideHref entries) get stable distinct ids.
        const testIdSuffix =
          entry.testIdSuffix ?? (entry.editor ?? "overview")
        if (entry.disabled) {
          return (
            <div
              key={entry.label}
              data-testid={`studio-rail-entry-${testIdSuffix}`}
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
            data-testid={`studio-rail-entry-${testIdSuffix}`}
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
            {showNewBadge && entry.newAffordanceId && (
              <span
                className="ml-auto inline-flex items-center gap-1 rounded-sm bg-accent-subtle px-1.5 py-0.5 text-caption text-accent"
                data-testid={`studio-rail-new-badge-${testIdSuffix}`}
              >
                New
                <button
                  type="button"
                  aria-label="Dismiss new affordance"
                  data-testid={`studio-rail-new-badge-dismiss-${testIdSuffix}`}
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    dismissAffordance(entry.newAffordanceId!)
                  }}
                  className="-mr-0.5 flex h-3 w-3 items-center justify-center rounded-sm text-accent hover:bg-accent/20"
                >
                  <X size={10} />
                </button>
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
