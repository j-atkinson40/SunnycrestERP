/**
 * RecentActivityWidget — Phase W-3a cross-vertical foundation widget.
 *
 * Tenant-wide activity feed. Cross-vertical visibility (every tenant
 * sees the widget); cross-line (no per-product-line scoping).
 *
 * Per [DESIGN_LANGUAGE.md §12.10](../../../../DESIGN_LANGUAGE.md):
 * Glance + Brief + Detail variants. View-only per §12.6a Widget
 * Interactivity Discipline — no state-flip interactions; click-through
 * navigation only. Used inside peek panels at Brief variant per
 * §12.5 composition rules (peek_inline surface).
 *
 * Three-component shape per established Phase W-3a precedent
 * (TodayWidget, OperatorProfileWidget, AncillaryPoolPin):
 *   1. Presentation tablets/cards — render-only, no hooks
 *   2. Variant wrappers — fetch data + handle navigation
 *   3. Top-level dispatcher — selects variant via surface + variant_id
 *
 * Data source: `GET /api/v1/vault/activity/recent` (V-1c endpoint
 * extended Phase W-3a with `actor_name` shim). 5-minute auto-refresh
 * via `useWidgetData`.
 */

import { useMemo, useState } from "react"
// R-1.5: handlers gated behind _editMode for runtime editor safety.
// Defense-in-depth over SelectionOverlay's capture-phase click suppression.
import { useNavigate } from "react-router-dom"
import { useEditMode } from "@/lib/runtime-host/edit-mode-context"
import { Activity } from "lucide-react"

import { useWidgetData } from "../useWidgetData"
import { cn } from "@/lib/utils"
import type { VariantId } from "@/components/widgets/types"


// ── Data shape ──────────────────────────────────────────────────────


interface ActivityItem {
  id: string
  activity_type: string
  title: string | null
  body: string | null
  is_system_generated: boolean
  company_id: string
  company_name: string
  created_at: string
  logged_by: string | null
  actor_name: string | null
}


interface RecentActivityResponse {
  activities: ActivityItem[]
}


// ── Helpers ─────────────────────────────────────────────────────────


/** Display label for the actor — falls back gracefully through
 *  actor_name → "System" for system-generated → "Someone" otherwise. */
function actorLabel(item: ActivityItem): string {
  if (item.actor_name) return item.actor_name
  if (item.is_system_generated) return "System"
  return "Someone"
}


/** Activity type → human verb. Falls back to the raw enum string
 *  when no mapping exists (defensive for future activity types). */
function activityVerb(activity_type: string): string {
  const map: Record<string, string> = {
    note: "added a note",
    call: "logged a call",
    email: "logged an email",
    // Phase W-4b Calendar Step 5 — V-1c CRM activity feed integration.
    // Title carries the lifecycle-aware shape ("Scheduled / Modified /
    // Cancelled / Responded to · {subject}"); the verb here just
    // anchors the activity_type kind.
    calendar: "updated a calendar event",
    meeting: "logged a meeting",
    document: "uploaded a document",
    follow_up: "scheduled a follow-up",
    status_change: "changed status",
    delivery: "updated a delivery",
    invoice: "updated an invoice",
    order: "updated an order",
    payment: "logged a payment",
    proof: "updated a proof",
    case: "updated a case",
  }
  return map[activity_type] || activity_type.replace(/_/g, " ")
}


/** Compact relative timestamp: "5 min ago" / "2h ago" / "3d ago". */
function relativeTime(iso: string): string {
  const then = new Date(iso).getTime()
  const now = Date.now()
  const diff = Math.max(0, now - then)
  const min = Math.floor(diff / 60_000)
  if (min < 1) return "just now"
  if (min < 60) return `${min} min ago`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h ago`
  const day = Math.floor(hr / 24)
  if (day < 7) return `${day}d ago`
  // Older — fall back to a date.
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  })
}


/** Time window label for Glance subtext — picks the smallest fitting
 *  window based on the actual newest event. */
function eventCountSubtext(activities: ActivityItem[]): string {
  if (activities.length === 0) return "Nothing recent"
  const count = activities.length
  return count === 1 ? "1 event" : `${count} events`
}


// ── Glance variant (Pattern 1 frosted-glass tablet) ─────────────────


interface GlanceProps {
  data: RecentActivityResponse | null
  isLoading: boolean
  onSummon: () => void
}


function RecentActivityGlanceTablet({
  data,
  isLoading,
  onSummon,
}: GlanceProps) {
  const activities = data?.activities ?? []
  const total = activities.length
  const subtext = isLoading
    ? "Loading…"
    : eventCountSubtext(activities)
  return (
    <div
      data-slot="recent-activity-widget"
      data-variant="glance"
      data-surface="spaces_pin"
      style={{ transform: "var(--widget-tablet-transform)" }}
      className={cn(
        // Pattern 1 frosted-glass surface — same chrome as
        // TodayWidget Glance + AncillaryPoolPin Glance for cross-
        // surface visual continuity.
        "relative flex items-center overflow-hidden",
        "bg-surface-elevated/85 supports-[backdrop-filter]:backdrop-blur-sm",
        "rounded-none",
        "shadow-[var(--shadow-widget-tablet)]",
        "h-15 w-full",
        "cursor-pointer",
        "hover:bg-surface-elevated/95",
        "transition-colors duration-quick ease-settle",
        "focus-ring-accent outline-none",
        isLoading && "opacity-80",
      )}
      onClick={onSummon}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          onSummon()
        }
      }}
      role="button"
      tabIndex={0}
      aria-label={`Recent activity, ${subtext}. Open for details.`}
    >
      {/* Bezel column — same 28px structural left edge as other
          Pattern 1 widgets. */}
      <div
        aria-hidden
        data-slot="recent-activity-widget-bezel-grip"
        className={cn(
          "flex h-full w-7 shrink-0 items-center justify-center",
          "border-r border-border-subtle/30",
          "gap-0.5",
        )}
      >
        <span className="block h-3 w-0.5 rounded-full bg-content-muted/30" />
        <span className="block h-3 w-0.5 rounded-full bg-content-muted/30" />
      </div>
      {/* Content — eyebrow (RECENT ACTIVITY) + subtext (count) + count chip if > 0 */}
      <div className="flex min-w-0 flex-1 items-center justify-between gap-2 px-3">
        <div className="min-w-0 flex-1">
          <p
            className={cn(
              "text-micro uppercase tracking-wider",
              "text-content-muted font-mono",
              "truncate",
            )}
            data-slot="recent-activity-widget-eyebrow"
          >
            Recent activity
          </p>
          <p
            className={cn(
              "mt-0.5 text-caption leading-tight",
              "text-content-muted font-sans",
              "truncate",
            )}
            data-slot="recent-activity-widget-subtext"
          >
            {subtext}
          </p>
        </div>
        {total > 0 && (
          <span
            data-slot="recent-activity-widget-count"
            className={cn(
              "inline-flex items-center justify-center",
              "min-w-[20px] h-5 px-1.5 rounded-full",
              "bg-accent text-content-on-accent text-caption font-medium",
              "font-mono tabular-nums shrink-0",
            )}
          >
            {total}
          </span>
        )}
      </div>
    </div>
  )
}


// ── Activity row (shared between Brief + Detail) ───────────────────


interface ActivityRowProps {
  item: ActivityItem
  onClick: () => void
}


function ActivityRow({ item, onClick }: ActivityRowProps) {
  const actor = actorLabel(item)
  const verb = activityVerb(item.activity_type)
  const when = relativeTime(item.created_at)
  return (
    <li>
      <button
        onClick={onClick}
        className={cn(
          "flex w-full items-baseline gap-2 px-2 py-1.5 rounded-sm",
          "text-body-sm text-content-base",
          "hover:bg-accent-subtle/40",
          "transition-colors duration-quick ease-settle",
          "focus-ring-accent outline-none",
          "text-left",
        )}
        data-slot="recent-activity-widget-row"
        data-activity-id={item.id}
        data-activity-type={item.activity_type}
      >
        <span className="min-w-0 flex-1 truncate">
          <span className="font-medium text-content-strong">
            {actor}
          </span>{" "}
          <span className="text-content-muted">{verb}</span>{" "}
          <span className="text-content-base">·</span>{" "}
          <span className="text-content-muted truncate">
            {item.company_name}
          </span>
        </span>
        <span
          className={cn(
            "shrink-0 text-caption text-content-subtle font-mono",
            "tabular-nums",
          )}
        >
          {when}
        </span>
      </button>
    </li>
  )
}


// ── Brief variant (Pattern 2 solid-fill content) ───────────────────


interface BriefProps {
  data: RecentActivityResponse | null
  isLoading: boolean
  error: string | null
  onRowClick: (item: ActivityItem) => void
  onViewAll: () => void
}


function RecentActivityBriefCard({
  data,
  isLoading,
  error,
  onRowClick,
  onViewAll,
}: BriefProps) {
  if (error) {
    return (
      <div
        data-slot="recent-activity-widget-error"
        className="p-4 text-caption text-status-error"
      >
        Couldn't load recent activity.
      </div>
    )
  }
  // Brief shows top 5 only.
  const items = (data?.activities ?? []).slice(0, 5)
  return (
    <div
      data-slot="recent-activity-widget"
      data-variant="brief"
      className={cn("flex flex-col h-full", isLoading && "opacity-80")}
    >
      {/* Header */}
      <div
        data-slot="recent-activity-widget-header"
        className={cn(
          "flex items-baseline justify-between gap-2",
          "border-b border-border-subtle/40 px-4 py-3",
        )}
      >
        <div className="min-w-0 flex-1">
          <p
            className={cn(
              "text-micro uppercase tracking-wider",
              "text-content-muted font-mono",
            )}
          >
            Recent activity
          </p>
          <h3
            className={cn(
              "mt-0.5 text-body-sm font-medium leading-tight",
              "text-content-strong font-sans",
            )}
          >
            {items.length === 0
              ? "No recent activity"
              : items.length === 1
              ? "1 event"
              : `${items.length} events`}
          </h3>
        </div>
      </div>

      {/* Body — 3-5 most recent events OR empty state */}
      <div data-slot="recent-activity-widget-body" className="flex-1">
        {!isLoading && items.length === 0 && (
          <div
            data-slot="recent-activity-widget-empty"
            className="flex flex-col items-center justify-center gap-2 px-4 py-6 text-center"
          >
            <Activity
              className="h-6 w-6 text-content-subtle"
              aria-hidden
            />
            <p className="text-caption text-content-muted font-sans leading-tight">
              No recent activity
            </p>
            <p className="text-micro text-content-subtle font-sans leading-tight">
              Activity will appear here as work happens.
            </p>
          </div>
        )}
        {items.length > 0 && (
          <ul
            data-slot="recent-activity-widget-rows"
            className="space-y-0.5 px-2 py-2"
          >
            {items.map((item) => (
              <ActivityRow
                key={item.id}
                item={item}
                onClick={() => onRowClick(item)}
              />
            ))}
          </ul>
        )}
      </div>

      {/* Footer — View all CTA */}
      {items.length > 0 && (
        <div
          data-slot="recent-activity-widget-footer"
          className="border-t border-border-subtle/40 px-4 py-2"
        >
          <button
            onClick={onViewAll}
            className={cn(
              "text-caption text-accent font-sans",
              "hover:text-accent-hover",
              "transition-colors duration-quick ease-settle",
              "focus-ring-accent outline-none rounded-sm",
            )}
            data-slot="recent-activity-widget-view-all"
          >
            View all →
          </button>
        </div>
      )}
    </div>
  )
}


// ── Detail variant (Pattern 2 with filter chips + scroll) ──────────


interface DetailProps {
  data: RecentActivityResponse | null
  isLoading: boolean
  error: string | null
  onRowClick: (item: ActivityItem) => void
}


/** Filter chip categories — collapses the activity_type taxonomy
 *  into a smaller user-facing set. Adjust as activity_type vocabulary
 *  evolves. */
type FilterCategory = "all" | "comms" | "work" | "system"


function categoryFor(activity_type: string): FilterCategory {
  if (
    activity_type === "note" ||
    activity_type === "call" ||
    activity_type === "email" ||
    activity_type === "meeting" ||
    // Phase W-4b Calendar Step 5 — calendar events are coordination/
    // comms signals per §3.26.16.10 (Communications Layer extension).
    activity_type === "calendar"
  )
    return "comms"
  if (
    activity_type === "delivery" ||
    activity_type === "invoice" ||
    activity_type === "order" ||
    activity_type === "payment" ||
    activity_type === "proof" ||
    activity_type === "case" ||
    activity_type === "status_change" ||
    activity_type === "follow_up" ||
    activity_type === "document"
  )
    return "work"
  return "system"
}


function RecentActivityDetailCard({
  data,
  isLoading,
  error,
  onRowClick,
}: DetailProps) {
  const [filter, setFilter] = useState<FilterCategory>("all")

  const activities = data?.activities ?? []
  const filtered = useMemo(
    () =>
      filter === "all"
        ? activities
        : activities.filter(
            (a) => categoryFor(a.activity_type) === filter,
          ),
    [activities, filter],
  )

  if (error) {
    return (
      <div
        data-slot="recent-activity-widget-error"
        className="p-4 text-caption text-status-error"
      >
        Couldn't load recent activity.
      </div>
    )
  }

  return (
    <div
      data-slot="recent-activity-widget"
      data-variant="detail"
      className={cn("flex flex-col h-full", isLoading && "opacity-80")}
    >
      {/* Header + filter chips */}
      <div
        data-slot="recent-activity-widget-header"
        className={cn(
          "border-b border-border-subtle/40 px-4 py-3",
        )}
      >
        <p
          className={cn(
            "text-micro uppercase tracking-wider",
            "text-content-muted font-mono",
          )}
        >
          Recent activity
        </p>
        <h3
          className={cn(
            "mt-0.5 text-body-sm font-medium leading-tight",
            "text-content-strong font-sans",
          )}
        >
          {filtered.length === activities.length
            ? `${activities.length} events`
            : `${filtered.length} of ${activities.length} events`}
        </h3>
        {/* Filter chips */}
        <div
          data-slot="recent-activity-widget-filters"
          className="mt-2 flex flex-wrap gap-1.5"
          role="tablist"
          aria-label="Filter activity by category"
        >
          {(
            [
              ["all", "All"],
              ["comms", "Comms"],
              ["work", "Work"],
              ["system", "System"],
            ] as const
          ).map(([key, label]) => {
            const active = filter === key
            return (
              <button
                key={key}
                role="tab"
                aria-selected={active}
                onClick={() => setFilter(key)}
                data-slot="recent-activity-widget-filter-chip"
                data-filter-key={key}
                data-active={active ? "true" : "false"}
                className={cn(
                  "px-2 py-0.5 rounded-full text-caption font-sans",
                  "transition-colors duration-quick ease-settle",
                  "focus-ring-accent outline-none",
                  active
                    ? "bg-accent text-content-on-accent"
                    : "bg-accent-muted/30 text-content-muted hover:bg-accent-muted/50",
                )}
              >
                {label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Body — scrollable list. No virtualization yet (Phase W-3a
          Phase 1; the V-1c endpoint caps at 200 rows max which is
          comfortable for non-virtualized rendering). Future scope:
          add virtualization when long-scroll fixtures grow.  */}
      <div
        data-slot="recent-activity-widget-body"
        className="flex-1 overflow-y-auto"
      >
        {!isLoading && filtered.length === 0 && (
          <div
            data-slot="recent-activity-widget-empty"
            className="flex flex-col items-center justify-center gap-2 px-4 py-8 text-center"
          >
            <Activity
              className="h-6 w-6 text-content-subtle"
              aria-hidden
            />
            <p className="text-caption text-content-muted font-sans leading-tight">
              {activities.length === 0
                ? "No recent activity"
                : "No activity in this filter"}
            </p>
            {activities.length === 0 && (
              <p className="text-micro text-content-subtle font-sans leading-tight">
                Activity will appear here as work happens.
              </p>
            )}
          </div>
        )}
        {filtered.length > 0 && (
          <ul
            data-slot="recent-activity-widget-rows"
            className="space-y-0.5 px-2 py-2"
          >
            {filtered.map((item) => (
              <ActivityRow
                key={item.id}
                item={item}
                onClick={() => onRowClick(item)}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}


// ── Top-level dispatcher ────────────────────────────────────────────


export interface RecentActivityWidgetProps {
  widgetId?: string
  variant_id?: VariantId
  surface?: "focus_canvas" | "focus_stack" | "spaces_pin" | "pulse_grid"
  /** R-1.5: handlers gated behind _editMode for runtime editor safety. */
  _editMode?: boolean
}


export function RecentActivityWidget(props: RecentActivityWidgetProps) {
  const isGlance =
    props.surface === "spaces_pin" || props.variant_id === "glance"
  if (isGlance) return <RecentActivityGlanceVariant _editMode={props._editMode} />
  if (props.variant_id === "detail")
    return <RecentActivityDetailVariant _editMode={props._editMode} />
  return <RecentActivityBriefVariant _editMode={props._editMode} />
}


/** Resolve navigation target for a clicked activity row. The V-1c
 *  endpoint returns `company_id` as the owning CompanyEntity; the
 *  canonical CRM detail page lives at `/vault/crm/companies/{id}`
 *  per V-1c lift-and-shift. Calendar Step 5: when activity_type is
 *  "calendar" and the body carries an `event_id={uuid}` token, route
 *  directly to the native event detail page (§14.10.3). Future
 *  enhancement: route per `activity_type` to the relevant entity
 *  (e.g. order → /orders/{id}) when the V-1c response is extended
 *  with typed entity links. */
function resolveActivityTarget(item: ActivityItem): string {
  if (item.activity_type === "calendar" && item.body) {
    const m = item.body.match(/event_id=([0-9a-f-]{36})/i)
    if (m) {
      return `/calendar/events/${m[1]}`
    }
  }
  return `/vault/crm/companies/${item.company_id}`
}


function RecentActivityGlanceVariant({
  _editMode: propEditMode,
}: {
  _editMode?: boolean
}) {
  const navigate = useNavigate()
  const { isEditing } = useEditMode()
  const editModeActive = isEditing || propEditMode === true
  const { data, isLoading } = useWidgetData<RecentActivityResponse>(
    "/vault/activity/recent?limit=10",
    { refreshInterval: 5 * 60 * 1000 },
  )
  return (
    <RecentActivityGlanceTablet
      data={data}
      isLoading={isLoading}
      onSummon={() => {
        if (editModeActive) return
        navigate("/vault/crm")
      }}
    />
  )
}


function RecentActivityBriefVariant({
  _editMode: propEditMode,
}: {
  _editMode?: boolean
}) {
  const navigate = useNavigate()
  const { isEditing } = useEditMode()
  const editModeActive = isEditing || propEditMode === true
  const { data, isLoading, error } = useWidgetData<RecentActivityResponse>(
    "/vault/activity/recent?limit=10",
    { refreshInterval: 5 * 60 * 1000 },
  )
  return (
    <RecentActivityBriefCard
      data={data}
      isLoading={isLoading}
      error={error}
      onRowClick={(item) => {
        if (editModeActive) return
        navigate(resolveActivityTarget(item))
      }}
      onViewAll={() => {
        if (editModeActive) return
        navigate("/vault/crm")
      }}
    />
  )
}


function RecentActivityDetailVariant({
  _editMode: propEditMode,
}: {
  _editMode?: boolean
}) {
  const navigate = useNavigate()
  const { isEditing } = useEditMode()
  const editModeActive = isEditing || propEditMode === true
  // Detail variant pulls more rows.
  const { data, isLoading, error } = useWidgetData<RecentActivityResponse>(
    "/vault/activity/recent?limit=50",
    { refreshInterval: 5 * 60 * 1000 },
  )
  return (
    <RecentActivityDetailCard
      data={data}
      isLoading={isLoading}
      error={error}
      onRowClick={(item) => {
        if (editModeActive) return
        navigate(resolveActivityTarget(item))
      }}
    />
  )
}


export default RecentActivityWidget
