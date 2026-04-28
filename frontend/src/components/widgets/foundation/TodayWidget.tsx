/**
 * TodayWidget — Phase W-3a cross-vertical foundation widget.
 *
 * Shows today's relevant work items as a count + breakdown. Cross-
 * vertical visibility (every tenant sees the widget); per-vertical-
 * and-line content (Sunnycrest manufacturing+vault sees vault
 * deliveries + ancillary pool + unscheduled count; other verticals
 * land on a thoughtful empty state with a CTA to their primary
 * work surface).
 *
 * Three-component shape per [AncillaryPoolPin precedent](../../dispatch/scheduling-focus/AncillaryPoolPin.tsx)
 * (canonical pattern for variant-aware widgets):
 *   1. `TodayGlanceTablet` — Pattern 1 frosted-glass tablet for
 *      sidebar (`spaces_pin` surface). Compact 60px row: today's
 *      date + total count + click-to-summon affordance.
 *   2. `TodayBriefCard` — Pattern 2 solid-fill card for grid
 *      (`pulse_grid` / `dashboard_grid` / `focus_canvas`). Header
 *      with date + 3-5 row breakdown + click-through per row.
 *   3. `TodayWidget` (top-level dispatcher) — switches between
 *      Glance and Brief based on `surface` + `variant_id` props.
 *
 * Data source: `GET /api/v1/widget-data/today` with auto-refresh
 * every 5 minutes (long enough not to thrash; short enough that
 * a freshly-arrived delivery surfaces on the next page reload's
 * widget poll).
 *
 * Per [DESIGN_LANGUAGE.md §12.10](../../../../DESIGN_LANGUAGE.md):
 * Glance + Brief variants. No Detail variant — `today` is a
 * reference widget, not a workspace. Detail-tier work routes to
 * the relevant primary work surface (Dispatch, Cases, etc.).
 *
 * Per [§12.6a Widget Interactivity Discipline](../../../../DESIGN_LANGUAGE.md):
 * view-only with click-through navigation. No state-flip
 * interactions; no in-place editing. Decisions belong in Focus.
 */

import { useNavigate } from "react-router-dom"
import { Calendar, CalendarDays } from "lucide-react"

import { useWidgetData } from "../useWidgetData"
import { cn } from "@/lib/utils"
import type { VariantId } from "@/components/widgets/types"


// ── Data shape (mirrors backend `get_today_summary` response) ───────


interface TodayCategory {
  key: string
  label: string
  count: number
  navigation_target: string | null
}


interface TodayWidgetData {
  date: string
  total_count: number
  categories: TodayCategory[]
  primary_navigation_target: string | null
}


// ── Date formatting ────────────────────────────────────────────────


function formatTodayHeader(isoDate: string): string {
  // Use user's locale for the long form: "Monday, April 27"
  const d = new Date(`${isoDate}T00:00:00`)
  return d.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  })
}


function formatTodayShort(isoDate: string): string {
  // Compact form for Glance variant: "Apr 27"
  const d = new Date(`${isoDate}T00:00:00`)
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  })
}


// ── Glance variant (Pattern 1 frosted-glass tablet, sidebar) ────────


interface GlanceProps {
  data: TodayWidgetData | null
  isLoading: boolean
  onSummon: () => void
}


/**
 * Glance variant — same Pattern 1 chrome as AncillaryPoolPin Glance:
 * frosted-glass surface + 28px bezel column with grip indicator +
 * eyebrow/body/count row. 60px tall to match the sidebar Glance
 * compatibility-matrix shape.
 *
 * Cross-surface visual continuity with AncillaryPoolPin is intentional
 * — every Glance tablet shares the same chrome vocabulary so the
 * sidebar reads as a cohesive surface family, not a per-widget
 * patchwork.
 */
function TodayGlanceTablet({ data, isLoading, onSummon }: GlanceProps) {
  const total = data?.total_count ?? 0
  const dateLabel = data ? formatTodayShort(data.date) : "Today"
  const subtext = isLoading
    ? "Loading…"
    : total === 0
    ? "Nothing scheduled"
    : total === 1
    ? "1 item today"
    : `${total} items today`

  return (
    <div
      data-slot="today-widget"
      data-variant="glance"
      data-surface="spaces_pin"
      style={{ transform: "var(--widget-tablet-transform)" }}
      className={cn(
        // Pattern 1 frosted-glass surface — same as AncillaryPoolPin
        // Glance for cross-surface continuity. Section 11 §11
        // Pattern 1 reference.
        "relative flex items-center overflow-hidden",
        "bg-surface-elevated/85 supports-[backdrop-filter]:backdrop-blur-sm",
        "rounded-none",
        "shadow-[var(--shadow-widget-tablet)]",
        // Glance dimensions per WIDGET_DEFINITIONS catalog.
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
      aria-label={`${dateLabel}. ${subtext}. Open for details.`}
    >
      {/* Bezel column — same 28px structural left edge as
          AncillaryPoolPin. Two short vertical grip lines per
          Pattern 1 doc-spec. */}
      <div
        aria-hidden
        data-slot="today-widget-bezel-grip"
        className={cn(
          "flex h-full w-7 shrink-0 items-center justify-center",
          "border-r border-border-subtle/30",
          "gap-0.5",
        )}
      >
        <span className="block h-3 w-0.5 rounded-full bg-content-muted/30" />
        <span className="block h-3 w-0.5 rounded-full bg-content-muted/30" />
      </div>
      {/* Content — eyebrow (date) + subtext (count) + count chip if > 0 */}
      <div className="flex min-w-0 flex-1 items-center justify-between gap-2 px-3">
        <div className="min-w-0 flex-1">
          <p
            className={cn(
              "text-micro uppercase tracking-wider",
              "text-content-muted font-mono",
              "truncate",
            )}
            data-slot="today-widget-eyebrow"
          >
            {dateLabel}
          </p>
          <p
            className={cn(
              "mt-0.5 text-caption leading-tight",
              "text-content-muted font-sans",
              "truncate",
            )}
            data-slot="today-widget-glance-subtext"
          >
            {subtext}
          </p>
        </div>
        {total > 0 && (
          <span
            data-slot="today-widget-count"
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


// ── Brief variant (Pattern 2 solid-fill card, grid) ─────────────────


interface BriefProps {
  data: TodayWidgetData | null
  isLoading: boolean
  error: string | null
  onNavigate: (target: string | null) => void
}


/**
 * Brief variant — solid-fill card with header + breakdown rows.
 *
 * Pattern 2 chrome (NOT the frosted-glass tablet) per Section 11 §11
 * — grid widgets sit AS PART OF the work surface, not floating above
 * it. Same surface treatment as the existing dashboard widgets
 * (RecentDocumentsWidget, ActivityFeedWidget, etc.) — Pattern 2
 * solid-fill card via the implicit WidgetWrapper used by dashboards.
 *
 * Note: the WidgetWrapper itself is supplied by the host (the grid
 * dispatcher); this component renders the INTERIOR content only.
 * That keeps the chrome consistent with other dashboard widgets
 * via composition.
 */
function TodayBriefCard({
  data,
  isLoading,
  error,
  onNavigate,
}: BriefProps) {
  if (error) {
    return (
      <div
        data-slot="today-widget-error"
        className="p-4 text-caption text-status-error"
      >
        Couldn't load today's summary. Pull to refresh.
      </div>
    )
  }

  const dateLabel = data ? formatTodayHeader(data.date) : "Today"
  const total = data?.total_count ?? 0
  const categories = data?.categories ?? []

  return (
    <div
      data-slot="today-widget"
      data-variant="brief"
      className={cn(
        "flex flex-col h-full",
        isLoading && "opacity-80",
      )}
    >
      {/* Header — eyebrow (TODAY) + date + total chip */}
      <div
        data-slot="today-widget-header"
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
            Today
          </p>
          <h3
            className={cn(
              "mt-0.5 text-body-sm font-medium leading-tight",
              "text-content-strong font-sans truncate",
            )}
          >
            {dateLabel}
          </h3>
        </div>
        {total > 0 && (
          <span
            data-slot="today-widget-count"
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

      {/* Body — category breakdown OR empty state */}
      <div data-slot="today-widget-body" className="flex-1 px-4 py-3">
        {!isLoading && total === 0 && (
          <div
            data-slot="today-widget-empty"
            className="flex flex-col items-center justify-center gap-2 py-4 text-center"
          >
            <Calendar
              className="h-6 w-6 text-content-subtle"
              aria-hidden
            />
            <p className="text-caption text-content-muted font-sans leading-tight">
              Nothing scheduled today
            </p>
            {data?.primary_navigation_target && (
              <button
                onClick={() => onNavigate(data.primary_navigation_target)}
                className={cn(
                  "mt-1 text-caption text-accent font-sans",
                  "hover:text-accent-hover",
                  "transition-colors duration-quick ease-settle",
                  "focus-ring-accent outline-none rounded-sm",
                )}
                data-slot="today-widget-empty-cta"
              >
                Open schedule →
              </button>
            )}
          </div>
        )}
        {categories.length > 0 && (
          <ul
            data-slot="today-widget-categories"
            className="space-y-1.5"
          >
            {categories.map((cat) => (
              <li key={cat.key}>
                <button
                  onClick={() => onNavigate(cat.navigation_target)}
                  className={cn(
                    "flex w-full items-center justify-between gap-2",
                    "px-2 py-1.5 rounded-sm",
                    "text-body-sm text-content-base",
                    "hover:bg-accent-subtle/40",
                    "transition-colors duration-quick ease-settle",
                    "focus-ring-accent outline-none",
                  )}
                  data-slot={`today-widget-category-${cat.key}`}
                  data-category-key={cat.key}
                >
                  <span className="truncate text-left">{cat.label}</span>
                  <span
                    aria-hidden
                    className="shrink-0 text-content-subtle"
                  >
                    →
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}


// ── Glance variant (Pulse grid — Phase W-4a Step 6 Commit 2) ─────────


/**
 * Pulse-grid Glance render with §13.4.1 three-tier density dispatch.
 *
 * Sidebar (spaces_pin) keeps the Pattern 1 frosted-glass tablet
 * (`TodayGlanceTablet` above) — that's the cross-surface continuity
 * with AncillaryPoolPin Glance. Pulse needs a distinct render because
 * (a) PulsePiece already supplies Pattern 2 chrome at its root, so
 * any nested Pattern 1 frosted-glass would be wrong, and (b) the
 * canon mandates three density tiers per cell-height range.
 *
 * Three nested density variants share the same underlying data; the
 * @container query CSS in `pulse-density.css` dispatches which one
 * displays at each cell-height range.
 */
function TodayPulseGlance({
  data,
  isLoading,
  onSummon,
}: GlanceProps) {
  const total = data?.total_count ?? 0
  const dateLabel = data ? formatTodayShort(data.date) : "Today"
  const dateLabelLong = data ? formatTodayHeader(data.date) : "Today"
  const subtext = isLoading
    ? "Loading…"
    : total === 0
    ? "Nothing scheduled"
    : total === 1
    ? "1 item today"
    : `${total} items today`

  return (
    <button
      type="button"
      onClick={onSummon}
      data-slot="today-widget"
      data-variant="glance"
      data-surface="pulse_grid"
      aria-label={`${dateLabelLong}. ${subtext}. Open for details.`}
      className={cn(
        "relative h-full w-full text-left",
        "hover:bg-accent-subtle/30",
        "transition-colors duration-quick ease-settle",
        "focus-ring-accent outline-none",
        isLoading && "opacity-80",
      )}
    >
      {/* Default tier (≥ 121 px) — eyebrow + long date + count chip */}
      <div
        data-slot="today-widget-pulse-default"
        className="today-widget-pulse-default flex-col items-stretch h-full px-4 py-3 gap-1"
      >
        <p
          className={cn(
            "text-micro uppercase tracking-wider",
            "text-content-muted font-mono",
          )}
          data-slot="today-widget-eyebrow"
        >
          Today
        </p>
        <h3
          className={cn(
            "text-body-sm font-medium leading-tight",
            "text-content-strong font-sans truncate",
          )}
        >
          {dateLabelLong}
        </h3>
        <div className="mt-auto flex items-baseline justify-between gap-2">
          <span
            className={cn(
              "text-caption text-content-muted font-sans truncate",
            )}
            data-slot="today-widget-glance-subtext"
          >
            {subtext}
          </span>
          {total > 0 && (
            <span
              data-slot="today-widget-count"
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

      {/* Compact tier (101–120 px) — short date + count, no eyebrow */}
      <div
        data-slot="today-widget-pulse-compact"
        className="today-widget-pulse-compact items-center h-full w-full px-3 gap-2"
      >
        <CalendarDays
          className="h-4 w-4 shrink-0 text-accent"
          aria-hidden
        />
        <div className="min-w-0 flex-1">
          <span className="text-body-sm font-medium text-content-strong font-sans truncate block">
            {dateLabel}
          </span>
          <span className="text-caption text-content-muted font-sans truncate block">
            {subtext}
          </span>
        </div>
        {total > 0 && (
          <span
            className={cn(
              "inline-flex items-center justify-center",
              "min-w-[20px] h-5 px-1.5 rounded-full shrink-0",
              "bg-accent text-content-on-accent text-caption font-medium",
              "font-mono tabular-nums",
            )}
          >
            {total}
          </span>
        )}
      </div>

      {/* Ultra-compact tier (80–100 px) — single line */}
      <div
        data-slot="today-widget-pulse-ultra-compact"
        className="today-widget-pulse-ultra-compact items-center h-full w-full px-3 gap-2"
      >
        <Calendar
          className="h-4 w-4 shrink-0 text-accent"
          aria-hidden
        />
        <span className="min-w-0 flex-1 truncate text-content-strong font-medium text-body-sm">
          {dateLabel.toUpperCase()}
          <span className="text-content-muted font-normal"> · {subtext}</span>
        </span>
        {total > 0 && (
          <span aria-hidden className="shrink-0 text-accent text-caption">
            →
          </span>
        )}
      </div>
    </button>
  )
}


// ── Top-level dispatcher ────────────────────────────────────────────


export interface TodayWidgetProps {
  widgetId?: string
  variant_id?: VariantId
  surface?: "focus_canvas" | "focus_stack" | "spaces_pin" | "pulse_grid"
}


/**
 * Top-level dispatcher — Widget Library Phase W-3a.
 *
 * Selects between Glance and Brief based on `surface === "spaces_pin"`
 * OR `variant_id === "glance"` (mirrors AncillaryPoolPin discriminator
 * pattern). The dispatcher itself calls no hooks; each variant component
 * owns its hook order, so React's rules-of-hooks are satisfied across
 * renders that flip between variants.
 *
 * Brief is the default for non-sidebar surfaces (canvas, grid).
 * Detail + Deep variants fall through to Brief (Phase W-3a Phase 1 —
 * no Detail variant declared per §12.10 reference).
 *
 * Phase W-4a Step 6 Commit 2 — Pulse-grid + Glance routes to
 * TodayPulseGlance with §13.4.1 density-tier dispatch. Sidebar
 * (spaces_pin) keeps the Pattern 1 frosted-glass tablet for
 * cross-surface continuity with AncillaryPoolPin.
 */
export function TodayWidget(props: TodayWidgetProps) {
  const isGlance =
    props.surface === "spaces_pin" || props.variant_id === "glance"
  if (isGlance) {
    return <TodayGlanceVariant surface={props.surface} />
  }
  return <TodayBriefVariant />
}


/** Variant wrapper — fetches data + handles summon. Picks the
 *  surface-appropriate Glance shape (Pattern 1 tablet for sidebar;
 *  Pulse-grid 3-density-tier render for Pulse). */
function TodayGlanceVariant({
  surface,
}: {
  surface?: TodayWidgetProps["surface"]
}) {
  const navigate = useNavigate()
  // 5-minute auto-refresh — long enough not to thrash, short enough
  // that the surface reflects fresh state on next browser idle.
  const { data, isLoading } = useWidgetData<TodayWidgetData>(
    "/widget-data/today",
    { refreshInterval: 5 * 60 * 1000 },
  )
  const onSummon = () => {
    const target = data?.primary_navigation_target ?? "/dashboard"
    navigate(target)
  }
  if (surface === "pulse_grid") {
    return (
      <TodayPulseGlance
        data={data}
        isLoading={isLoading}
        onSummon={onSummon}
      />
    )
  }
  return (
    <TodayGlanceTablet
      data={data}
      isLoading={isLoading}
      onSummon={onSummon}
    />
  )
}


/** Variant wrapper — fetches data + handles per-row navigation. */
function TodayBriefVariant() {
  const navigate = useNavigate()
  const { data, isLoading, error } = useWidgetData<TodayWidgetData>(
    "/widget-data/today",
    { refreshInterval: 5 * 60 * 1000 },
  )
  return (
    <TodayBriefCard
      data={data}
      isLoading={isLoading}
      error={error}
      onNavigate={(target) => {
        if (target) navigate(target)
      }}
    />
  )
}


// Default export for registry registration symmetry.
export default TodayWidget
