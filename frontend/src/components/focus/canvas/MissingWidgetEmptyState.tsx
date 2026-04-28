/**
 * MissingWidgetEmptyState — Phase W-4a Step 5 (May 2026).
 *
 * Honest empty state surfaced when `getWidgetRenderer(widgetType)` is
 * called with a `widgetType` that the backend declared but the
 * frontend has no registered renderer for.
 *
 * Pre-Step-5 the fallback was `MockSavedViewWidget` — a dev fixture
 * that renders fake "Recent Cases" + family mock data. In production,
 * a backend/frontend widget-id mismatch would silently render the
 * fixture, masking the bug as "looks like cross-vertical contamination"
 * (Step 5 investigation surfaced exactly this with the
 * `funeral-scheduling.ancillary-pool` → `scheduling.ancillary-pool`
 * rename: backend declared `scheduling.ancillary-pool`, frontend
 * registered `funeral-scheduling.ancillary-pool`, fallback rendered
 * fake FH-themed mock data, looked like cross-vertical contamination).
 *
 * Post-Step-5 contract:
 *   • `widgetType === undefined`: legacy / test layouts → MockSavedViewWidget
 *     (preserves existing test fixtures + back-compat)
 *   • `widgetType` registered + missing component: real production
 *     mismatch → MissingWidgetEmptyState (this component, surfaces the
 *     bug visibly so it's caught in CI / staging)
 *
 * The component renders compact + neutral — does not mimic widget
 * content, does not borrow widget-specific iconography. The goal is
 * to be CLEARLY identifiable as "this is a placeholder, something is
 * misconfigured" so QA + visual review catches the issue rather than
 * mistaking it for legitimate content.
 *
 * Surface-aware sizing: `surface` prop accepted for API symmetry.
 * Renders identically across surfaces today; future tightening could
 * adjust copy density per surface, but neutrality is the goal — keep
 * it simple.
 */
import { AlertCircle } from "lucide-react"

import type { WidgetRendererProps } from "./widget-renderers"
import { cn } from "@/lib/utils"


export function MissingWidgetEmptyState(props: WidgetRendererProps) {
  return (
    <div
      data-slot="missing-widget-empty"
      data-widget-id={props.widgetId}
      data-variant-id={props.variant_id ?? "unknown"}
      data-surface={props.surface ?? "unknown"}
      className={cn(
        "flex flex-col items-center justify-center gap-2",
        "h-full w-full p-4 text-center",
        // Use status-warning palette to surface as a misconfiguration
        // signal — distinct from regular widget content (which uses
        // surface tokens) and from regular empty states (which use
        // content-muted prose). This SHOULD look like a warning.
        "bg-status-warning-muted/40 border border-status-warning/30",
      )}
    >
      <AlertCircle
        className="h-6 w-6 text-status-warning"
        aria-hidden
      />
      <p
        className={cn(
          "text-body-sm font-medium leading-tight",
          "text-content-strong font-sans",
        )}
      >
        Widget unavailable
      </p>
      <p
        className={cn(
          "text-caption text-content-muted font-sans leading-tight",
          "max-w-[240px]",
        )}
        // Useful for QA + Sentry correlation: the widget_id is in the
        // attribute + visible body so issues are diagnostically
        // observable without devtools.
      >
        No renderer registered for this widget
        {props.widgetId ? ` (${props.widgetId})` : ""}.
      </p>
    </div>
  )
}


export default MissingWidgetEmptyState
