/**
 * BriefingWidget — Phase W-3b cross-vertical foundation widget.
 *
 * Promotes the Phase 6 `BriefingCard` to the widget contract.
 * Per-user scoped: every user sees their own latest briefing via the
 * Phase 6 `/briefings/v2/latest` endpoint (which enforces
 * `user_id == current_user.id` server-side — users cannot see other
 * users' briefings).
 *
 * Per [DESIGN_LANGUAGE.md §12.10](../../../../DESIGN_LANGUAGE.md):
 * Glance + Brief + Detail variants — bounded by §12.6a interactivity
 * discipline (view-only with click-through to /briefing for
 * Mark-read + Regenerate). The widget surfaces the briefing; the
 * dedicated page owns the heavy actions.
 *
 * Three-component shape per established Phase W-3a precedent:
 *   1. Variant tablets (presentation, render-only)
 *   2. Top-level dispatcher (selects variant via surface +
 *      variant_id + briefing_type config)
 *
 * Reuse over rebuild: existing `useBriefing` hook + `BriefingSummary`
 * type + `/briefings/v2/latest` endpoint power the widget. The
 * legacy `BriefingCard` component stays alive for callers that want
 * a card-styled rendering outside the widget contract; this widget
 * provides the variant-aware grid/sidebar/canvas-ready rendering.
 *
 * Per-instance briefing_type via `config.briefing_type` ("morning"
 * or "evening") with default "morning". Future instances can pin
 * "evening" for end-of-day-summary surfaces.
 */

import { ChevronRight, Sunrise, Sunset } from "lucide-react"
import { Link } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { SkeletonLines } from "@/components/ui/skeleton"
import { useBriefing } from "@/hooks/useBriefing"
import { cn } from "@/lib/utils"
import type { BriefingType } from "@/types/briefing"
import type { VariantId } from "@/components/widgets/types"


// ── Config shape ────────────────────────────────────────────────────


interface BriefingConfig {
  briefing_type?: BriefingType
}


function readBriefingType(
  config: Record<string, unknown> | undefined,
): BriefingType {
  if (!config) return "morning"
  const c = config as BriefingConfig
  if (c.briefing_type === "evening") return "evening"
  return "morning"
}


// ── Helpers ─────────────────────────────────────────────────────────


function truncate(s: string, n: number): string {
  if (s.length <= n) return s
  const cut = s.slice(0, n)
  const lastSpace = cut.lastIndexOf(" ")
  return (lastSpace > 0 ? cut.slice(0, lastSpace) : cut) + "…"
}


function briefingTitle(briefingType: BriefingType): string {
  return briefingType === "morning"
    ? "Morning briefing"
    : "End of day summary"
}


function BriefingIcon({
  briefingType,
  className,
}: {
  briefingType: BriefingType
  className?: string
}) {
  if (briefingType === "morning") {
    return <Sunrise className={className} aria-hidden />
  }
  return <Sunset className={className} aria-hidden />
}


// ── Variant tablets ─────────────────────────────────────────────────


interface VariantProps {
  briefingType: BriefingType
  variant: "glance" | "brief" | "detail"
}


/**
 * Glance variant — sidebar-density single-line strip.
 *
 * Per Section 12.10: Glance = "always-visible micro-summary, no
 * interaction". The Glance shows briefing-type icon + unread state
 * + 1-line excerpt OR an empty-state hint. View-only per §12.6a.
 *
 * Frosted-glass tablet treatment per Pattern 1 (sidebar Glance) —
 * the parent container provides the chrome; the tablet is
 * structurally minimal.
 */
function BriefingGlanceTablet({ briefingType }: VariantProps) {
  const { briefing, loading } = useBriefing(briefingType)

  return (
    <Link
      to={briefing ? `/briefing/${briefing.id}` : "/briefing"}
      data-slot="briefing-widget"
      data-variant="glance"
      data-briefing-type={briefingType}
      className={cn(
        "flex items-center gap-2 px-3 py-2",
        "text-sm font-sans text-content-base",
        "hover:bg-surface-muted",
        "focus-ring-accent outline-none rounded-sm",
        "transition-colors duration-quick ease-settle",
      )}
    >
      <BriefingIcon
        briefingType={briefingType}
        className="h-4 w-4 text-accent flex-shrink-0"
      />
      <span className="truncate flex-1">
        {loading
          ? "…"
          : briefing
          ? briefingTitle(briefingType)
          : "No briefing yet"}
      </span>
      {briefing && !briefing.read_at ? (
        <span
          data-slot="briefing-unread-dot"
          className="h-2 w-2 rounded-full bg-accent flex-shrink-0"
          aria-label="Unread"
        />
      ) : null}
    </Link>
  )
}


/**
 * Brief variant — condensed card.
 *
 * Per Section 12.10: Brief = "compact summary with primary action".
 * Shows narrative excerpt (~320 chars), active space pill, unread
 * pill, and "Read full briefing →" link. Mirrors the legacy
 * BriefingCard's visual pattern but inside widget chrome.
 */
function BriefingBriefTablet({ briefingType }: VariantProps) {
  const { briefing, loading, error } = useBriefing(briefingType)

  return (
    <div
      data-slot="briefing-widget"
      data-variant="brief"
      data-briefing-type={briefingType}
      className="flex flex-col h-full p-4 gap-3"
    >
      <div className="flex items-center gap-2">
        <BriefingIcon
          briefingType={briefingType}
          className="h-4 w-4 text-accent"
        />
        <h3 className="text-body-sm font-medium text-content-strong font-sans flex-1">
          {briefingTitle(briefingType)}
        </h3>
      </div>

      <div className="flex-1 min-h-0 overflow-hidden">
        {loading ? (
          <SkeletonLines count={3} />
        ) : error ? (
          <p
            className="text-caption text-status-error font-sans"
            data-slot="briefing-error"
          >
            {error}
          </p>
        ) : !briefing ? (
          <div
            className="space-y-2"
            data-slot="briefing-widget-empty"
          >
            <p className="text-body-sm text-content-muted font-sans">
              No briefing yet today.
            </p>
            <Link
              to="/briefing"
              className={cn(
                "inline-flex items-center gap-1",
                "text-caption text-accent font-sans",
                "hover:text-accent-hover",
                "focus-ring-accent outline-none rounded-sm",
              )}
              data-slot="briefing-widget-empty-cta"
            >
              Open briefing <ChevronRight className="h-3 w-3" />
            </Link>
          </div>
        ) : (
          <div className="space-y-2">
            <p
              className="text-body-sm text-content-base font-sans whitespace-pre-wrap leading-relaxed"
              data-slot="briefing-narrative"
            >
              {truncate(briefing.narrative_text, 320)}
            </p>
            <div className="flex flex-wrap items-center gap-1.5">
              {briefing.active_space_name ? (
                <Badge
                  variant="outline"
                  className="text-caption font-sans"
                  data-slot="briefing-space-badge"
                >
                  {briefing.active_space_name}
                </Badge>
              ) : null}
              {!briefing.read_at ? (
                <Badge
                  variant="outline"
                  className="text-caption font-sans bg-accent-subtle text-accent border-accent/30"
                  data-slot="briefing-unread-badge"
                >
                  Unread
                </Badge>
              ) : null}
            </div>
          </div>
        )}
      </div>

      {briefing ? (
        <Link
          to={`/briefing/${briefing.id}`}
          className={cn(
            "inline-flex items-center gap-1",
            "text-caption text-accent font-sans",
            "hover:text-accent-hover",
            "focus-ring-accent outline-none rounded-sm",
            "transition-colors duration-quick ease-settle",
          )}
          data-slot="briefing-read-full"
        >
          Read full briefing <ChevronRight className="h-3 w-3" />
        </Link>
      ) : null}
    </div>
  )
}


/**
 * Detail variant — full narrative + structured-section preview.
 *
 * Per Section 12.10: Detail = "full content with structured
 * preview". Renders the entire narrative + condensed cards for
 * known structured_sections (queue summaries, flags, pending
 * decisions). Heavy actions (Mark-read, Regenerate, Preferences)
 * live on /briefing per §12.6a — the widget surfaces, the page
 * owns.
 */
function BriefingDetailTablet({ briefingType }: VariantProps) {
  const { briefing, loading, error } = useBriefing(briefingType)

  // Structured-section preview — pulls known shapes when present.
  // Unknown keys are silently skipped (Phase 6 briefing.ts contract).
  const sections = briefing?.structured_sections ?? {}
  const queueSummaries = Array.isArray(
    (sections as Record<string, unknown>).queue_summaries,
  )
    ? ((sections as Record<string, unknown>).queue_summaries as Array<{
        queue_id: string
        queue_name: string
        pending_count: number
      }>)
    : []
  const flags = Array.isArray((sections as Record<string, unknown>).flags)
    ? ((sections as Record<string, unknown>).flags as Array<{
        severity: "info" | "warning" | "critical"
        title: string
      }>)
    : []
  const pendingDecisions = Array.isArray(
    (sections as Record<string, unknown>).pending_decisions,
  )
    ? ((sections as Record<string, unknown>).pending_decisions as Array<{
        title: string
      }>)
    : []

  return (
    <div
      data-slot="briefing-widget"
      data-variant="detail"
      data-briefing-type={briefingType}
      className="flex flex-col h-full p-4 gap-3 overflow-y-auto"
    >
      <div className="flex items-center gap-2">
        <BriefingIcon
          briefingType={briefingType}
          className="h-5 w-5 text-accent"
        />
        <h3 className="text-body font-medium text-content-strong font-sans flex-1">
          {briefingTitle(briefingType)}
        </h3>
        {briefing && !briefing.read_at ? (
          <Badge
            variant="outline"
            className="text-caption font-sans bg-accent-subtle text-accent border-accent/30"
            data-slot="briefing-unread-badge"
          >
            Unread
          </Badge>
        ) : null}
      </div>

      {loading ? (
        <SkeletonLines count={5} />
      ) : error ? (
        <p
          className="text-caption text-status-error font-sans"
          data-slot="briefing-error"
        >
          {error}
        </p>
      ) : !briefing ? (
        <div
          className="space-y-2"
          data-slot="briefing-widget-empty"
        >
          <p className="text-body-sm text-content-muted font-sans">
            No briefing yet today.
          </p>
          <Link
            to="/briefing"
            className={cn(
              "inline-flex items-center gap-1",
              "text-caption text-accent font-sans",
              "hover:text-accent-hover",
              "focus-ring-accent outline-none rounded-sm",
            )}
            data-slot="briefing-widget-empty-cta"
          >
            Open briefing <ChevronRight className="h-3 w-3" />
          </Link>
        </div>
      ) : (
        <>
          <p
            className="text-body-sm text-content-base font-sans whitespace-pre-wrap leading-relaxed"
            data-slot="briefing-narrative"
          >
            {briefing.narrative_text}
          </p>

          {briefing.active_space_name ? (
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge
                variant="outline"
                className="text-caption font-sans"
                data-slot="briefing-space-badge"
              >
                {briefing.active_space_name}
              </Badge>
            </div>
          ) : null}

          {queueSummaries.length > 0 ? (
            <section
              data-slot="briefing-queues-section"
              className="space-y-1.5"
            >
              <h4 className="text-caption font-medium text-content-muted font-sans uppercase tracking-wide">
                Queues
              </h4>
              <ul className="space-y-1">
                {queueSummaries.slice(0, 5).map((q) => (
                  <li
                    key={q.queue_id}
                    className="flex items-center justify-between text-caption font-sans"
                  >
                    <span className="text-content-base truncate">
                      {q.queue_name}
                    </span>
                    <span className="text-content-muted font-plex-mono">
                      {q.pending_count}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {flags.length > 0 ? (
            <section
              data-slot="briefing-flags-section"
              className="space-y-1.5"
            >
              <h4 className="text-caption font-medium text-content-muted font-sans uppercase tracking-wide">
                Flags
              </h4>
              <ul className="space-y-1">
                {flags.slice(0, 5).map((f, i) => (
                  <li
                    key={`${f.severity}-${i}`}
                    className="flex items-start gap-1.5 text-caption font-sans"
                  >
                    <span
                      className={cn(
                        "mt-1 h-1.5 w-1.5 rounded-full flex-shrink-0",
                        f.severity === "critical" &&
                          "bg-status-error",
                        f.severity === "warning" &&
                          "bg-status-warning",
                        f.severity === "info" && "bg-status-info",
                      )}
                      aria-hidden
                    />
                    <span className="text-content-base">{f.title}</span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {pendingDecisions.length > 0 ? (
            <section
              data-slot="briefing-decisions-section"
              className="space-y-1.5"
            >
              <h4 className="text-caption font-medium text-content-muted font-sans uppercase tracking-wide">
                Pending decisions
              </h4>
              <ul className="space-y-1">
                {pendingDecisions.slice(0, 5).map((d, i) => (
                  <li
                    key={`${d.title}-${i}`}
                    className="text-caption text-content-base font-sans truncate"
                  >
                    {d.title}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <Link
            to={`/briefing/${briefing.id}`}
            className={cn(
              "inline-flex items-center gap-1 mt-auto",
              "text-caption text-accent font-sans",
              "hover:text-accent-hover",
              "focus-ring-accent outline-none rounded-sm",
              "transition-colors duration-quick ease-settle",
            )}
            data-slot="briefing-read-full"
          >
            Read full briefing <ChevronRight className="h-3 w-3" />
          </Link>
        </>
      )}
    </div>
  )
}


// ── Top-level dispatcher ────────────────────────────────────────────


export interface BriefingWidgetProps {
  widgetId?: string
  variant_id?: VariantId
  surface?:
    | "focus_canvas"
    | "focus_stack"
    | "spaces_pin"
    | "pulse_grid"
    | "dashboard_grid"
  config?: Record<string, unknown>
}


/**
 * Top-level dispatcher.
 *
 * - Reads `briefing_type` from `props.config` (default "morning").
 * - Dispatches to Glance / Brief / Detail tablet based on
 *   `variant_id` (defaults to `brief` per WidgetDefinition).
 * - `spaces_pin` surface routes to Glance regardless of variant_id
 *   when surface is explicitly provided — sidebar requires Glance
 *   per §12.2 compatibility matrix. Defensive: if `variant_id` is
 *   set explicitly to glance/brief/detail, that wins.
 * - Empty/loading/error states live inside each tablet — they
 *   render coherent placeholder content, not the empty wrapper.
 */
export function BriefingWidget(props: BriefingWidgetProps) {
  const briefingType = readBriefingType(props.config)
  const variant = props.variant_id ?? "brief"

  if (variant === "glance") {
    return (
      <BriefingGlanceTablet
        briefingType={briefingType}
        variant="glance"
      />
    )
  }
  if (variant === "detail") {
    return (
      <BriefingDetailTablet
        briefingType={briefingType}
        variant="detail"
      />
    )
  }
  // Default + deep fallback: brief. Briefing widget declares no
  // Deep variant in the catalog; defensive fallback to Brief if
  // the dispatch lands here unexpectedly (legacy layout, mis-pin).
  return (
    <BriefingBriefTablet
      briefingType={briefingType}
      variant="brief"
    />
  )
}


export default BriefingWidget
