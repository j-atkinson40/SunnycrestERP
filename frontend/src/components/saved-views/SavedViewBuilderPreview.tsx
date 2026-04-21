/**
 * SavedViewBuilderPreview — live preview pane for the saved-view
 * builder (UI/UX arc follow-up 3).
 *
 * Composition:
 *   useDebouncedValue(config, 300ms)  ← absorbs keystrokes
 *     → effect fires previewSavedView(debouncedConfig)
 *     → in-flight request cancelled on new debounced change
 *       (AbortController)
 *     → result goes into local state + cached by query fingerprint
 *       (mode-only swaps reuse the cache — no re-fetch for
 *        list↔table↔kanban↔calendar↔cards swaps when the query is
 *        unchanged; chart/stat require re-fetch because the
 *        response includes per-mode aggregations)
 *     → SavedViewRenderer renders (or a targeted mode-hint when
 *       required sub-config is missing)
 *
 * Mode-hint pre-render guard lives here (NOT in SavedViewRenderer)
 * per the arc approval — the renderer stays lean for the detail
 * page + widget callers. Preview uniquely knows the user is still
 * editing and can suggest which panel to visit next.
 *
 * Row cap: server enforces max 100. Client derives
 * `truncated = rows.length < total_count` and surfaces "Showing X
 * of Y results" in the header.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import {
  ChevronLeft,
  ChevronRight,
  Eye,
  Layers,
  RefreshCw,
  Sparkles,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { InlineError } from "@/components/ui/inline-error";
import { SkeletonCard } from "@/components/ui/skeleton";
import { SavedViewRenderer } from "@/components/saved-views/SavedViewRenderer";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { previewSavedView } from "@/services/saved-views-service";
import { usePeekOptional } from "@/contexts/peek-context";
import type { PeekEntityType } from "@/types/peek";
import type {
  EntityTypeMetadata,
  PresentationMode,
  SavedViewConfig,
  SavedViewResult,
} from "@/types/saved-views";
import { cn } from "@/lib/utils";


export interface SavedViewBuilderPreviewProps {
  config: SavedViewConfig;
  entity: EntityTypeMetadata | null;
  /** When true, the debounce window is skipped for the next fire —
   *  used by the manual refresh button. Reset internally. */
  className?: string;
}


// 300ms chosen to match the NL overlay debounce (follow-up 2 /
// Phase 4 precedent). Wide enough to absorb typing, tight enough
// that users see a refresh within ~0.5s of pausing.
const DEBOUNCE_MS = 300;


// ── Component ───────────────────────────────────────────────────────


export function SavedViewBuilderPreview({
  config,
  entity,
  className,
}: SavedViewBuilderPreviewProps) {
  const debouncedConfig = useDebouncedValue(config, DEBOUNCE_MS);
  // Follow-up 4 — when PeekProvider is in scope, the renderer's
  // title cells become click-to-peek. Builder lives inside the
  // tenant tree so this is generally non-null.
  const peek = usePeekOptional();
  const [result, setResult] = useState<SavedViewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);

  // Abort the previous in-flight request when a new debounced config
  // lands. Without this, a slow request from config N-1 can overwrite
  // the fresher result from config N if responses arrive out of order.
  const abortRef = useRef<AbortController | null>(null);

  // Mode-switch cache: keyed on a fingerprint that collapses
  // mode-only swaps among non-aggregation modes to a single entry.
  // Switching into chart/stat (different aggregation_mode) or
  // changing the query invalidates the cache.
  const cacheRef = useRef<{
    fingerprint: string;
    result: SavedViewResult;
  } | null>(null);

  const fingerprint = useMemo(
    () => computeFingerprint(debouncedConfig),
    [debouncedConfig],
  );

  const entityTypeForEmpty = entity?.display_name ?? "records";

  // Pre-render mode-hint guard. Returns a hint string if the current
  // presentation requires sub-config that's missing, or null if the
  // renderer is free to run.
  const modeHint = useMemo(
    () => requiredSubConfigHint(config),
    [config],
  );

  // ── Fetch effect ──────────────────────────────────────────────────

  useEffect(() => {
    // Don't fire for configs that can't run (unknown entity, etc.).
    if (!entity) {
      setLoading(false);
      return;
    }

    // Cache hit — skip network, reuse last result.
    const cached = cacheRef.current;
    if (cached && cached.fingerprint === fingerprint) {
      setResult(cached.result);
      setError(null);
      setLoading(false);
      return;
    }

    // Cancel any in-flight request from a superseded config.
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    previewSavedView(debouncedConfig, { signal: controller.signal })
      .then((fresh) => {
        if (controller.signal.aborted) return;
        setResult(fresh);
        cacheRef.current = { fingerprint, result: fresh };
        setLoading(false);
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        if (axios.isCancel(err)) return;
        const detail =
          (err as { response?: { data?: { detail?: string } } })?.response
            ?.data?.detail ?? "Preview failed.";
        setError(String(detail));
        setLoading(false);
      });

    return () => {
      // Component unmount OR effect re-run — cancel in flight.
      controller.abort();
    };
    // fingerprint captures query + aggregation_mode; refreshTick
    // forces a re-run when the user clicks the manual refresh
    // button.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fingerprint, entity, refreshTick]);

  const handleRefresh = useCallback(() => {
    cacheRef.current = null; // force re-fetch on the next tick
    setRefreshTick((t) => t + 1);
  }, []);

  // ── Render ────────────────────────────────────────────────────────

  const truncated =
    result !== null && result.rows.length < result.total_count;

  return (
    <div
      className={cn("space-y-2", className)}
      data-testid="saved-view-builder-preview"
    >
      <header className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Eye className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-medium">Preview</h3>
          {result !== null && (
            <span
              className="text-xs text-muted-foreground"
              data-testid="saved-view-builder-preview-count"
            >
              {truncated
                ? `Showing ${result.rows.length} of ${result.total_count} results`
                : `${result.total_count} ${result.total_count === 1 ? "result" : "results"}`}
            </span>
          )}
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleRefresh}
          disabled={loading || !entity}
          className="h-7 gap-1.5"
          data-testid="saved-view-builder-preview-refresh"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
          Refresh
        </Button>
      </header>

      <div
        className="min-h-[320px] rounded-md border bg-card p-3"
        data-testid="saved-view-builder-preview-body"
      >
        {!entity ? (
          <EmptyState
            icon={Layers}
            title="Select an entity type to preview"
            description="Set the entity type on the left to see matching records."
          />
        ) : modeHint ? (
          <EmptyState
            icon={Sparkles}
            title={modeHint.title}
            description={modeHint.description}
            data-testid="saved-view-builder-preview-mode-hint"
          />
        ) : loading && result === null ? (
          <SkeletonCard lines={4} />
        ) : error ? (
          <InlineError
            message="Couldn't run preview."
            hint={error}
            onRetry={handleRefresh}
          />
        ) : result === null ? (
          <EmptyState
            icon={Layers}
            title="Preview not ready"
            description={`Add filters or adjust presentation to see ${entityTypeForEmpty}.`}
          />
        ) : result.rows.length === 0 ? (
          <EmptyState
            icon={Layers}
            title="No matching records"
            description={`No ${entityTypeForEmpty} match these filters.`}
          />
        ) : (
          <SavedViewRenderer
            config={config}
            result={result}
            entity={entity}
            onPeek={
              peek
                ? (et, eid, anchor) =>
                    peek.openPeek({
                      entityType: et as PeekEntityType,
                      entityId: eid,
                      triggerType: "click",
                      anchorElement: anchor,
                    })
                : undefined
            }
          />
        )}
      </div>
    </div>
  );
}


// ── Mobile wrapper ──────────────────────────────────────────────────

export interface SavedViewBuilderPreviewPanelProps
  extends SavedViewBuilderPreviewProps {
  /** Collapsed state — hides the body, keeps the header toggle
   *  visible. Client-side only, persisted via localStorage by the
   *  parent. */
  collapsed: boolean;
  onToggleCollapsed: () => void;
}


/**
 * Slim wrapper that adds a toggle header for mobile/narrow
 * viewports. At `lg+` the parent renders the preview directly; at
 * `<lg` the parent uses this wrapper to render a collapsible shell.
 */
export function SavedViewBuilderPreviewPanel({
  collapsed,
  onToggleCollapsed,
  ...inner
}: SavedViewBuilderPreviewPanelProps) {
  return (
    <div
      className={cn(
        "rounded-md border bg-card",
        collapsed ? "p-0" : "p-3",
      )}
      data-testid="saved-view-builder-preview-panel"
      data-collapsed={collapsed ? "true" : "false"}
    >
      <button
        type="button"
        onClick={onToggleCollapsed}
        className="flex w-full items-center justify-between px-3 py-2 text-sm font-medium hover:bg-muted/50"
        data-testid="saved-view-builder-preview-toggle"
      >
        <span className="flex items-center gap-2">
          <Eye className="h-4 w-4" /> Preview
        </span>
        {collapsed ? (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronLeft className="h-4 w-4 text-muted-foreground" />
        )}
      </button>
      {!collapsed && (
        <div className="border-t pt-3 px-3 pb-3">
          <SavedViewBuilderPreview {...inner} />
        </div>
      )}
    </div>
  );
}


// ── Helpers (exported for tests) ────────────────────────────────────


/**
 * Collapse a config into a stable fingerprint that identifies the
 * underlying query plus whether the executor call itself will
 * differ. Mode-only swaps within the non-aggregation family
 * (list / table / kanban / calendar / cards) preserve the
 * fingerprint so the cache can serve them without a new network
 * round-trip.
 *
 * Exported for vitest — the test suite asserts:
 *   - same query + different non-aggregation mode → same fingerprint
 *   - same query + chart/stat swap-in → different fingerprint
 *   - changed filter value → different fingerprint
 */
export function computeFingerprint(config: SavedViewConfig): string {
  const aggregationMode = aggregationModeOf(config.presentation.mode);
  const queryPart = JSON.stringify({
    entity_type: config.query.entity_type,
    filters: config.query.filters ?? [],
    sort: config.query.sort ?? [],
    grouping: config.query.grouping ?? null,
    limit: config.query.limit ?? null,
  });
  // Chart/stat configs contribute their own aggregation spec to the
  // fingerprint because switching x_field/y_field/aggregation WITHIN
  // chart mode demands a new fetch.
  let aggPart = "none";
  if (aggregationMode === "chart") {
    aggPart = JSON.stringify(config.presentation.chart_config ?? null);
  } else if (aggregationMode === "stat") {
    aggPart = JSON.stringify(config.presentation.stat_config ?? null);
  }
  return `${queryPart}::${aggregationMode}::${aggPart}`;
}


export function aggregationModeOf(
  mode: PresentationMode,
): "none" | "chart" | "stat" {
  if (mode === "chart") return "chart";
  if (mode === "stat") return "stat";
  return "none";
}


/**
 * If the current presentation mode requires sub-config that's
 * missing, return a targeted hint. Otherwise return null — the
 * renderer is free to run.
 *
 * Hint text deliberately points at the Presentation panel — these
 * are the panels the user needs to fill in to unblock the preview.
 */
export function requiredSubConfigHint(
  config: SavedViewConfig,
): { title: string; description: string } | null {
  const p = config.presentation;
  switch (p.mode) {
    case "kanban":
      if (!p.kanban_config?.group_by_field) {
        return {
          title: "Kanban needs a Group-by field",
          description:
            "Pick a group-by field in Presentation to render the kanban columns.",
        };
      }
      if (!p.kanban_config?.card_title_field) {
        return {
          title: "Kanban needs a card title field",
          description:
            "Pick a card title field in Presentation to label each card.",
        };
      }
      return null;
    case "calendar":
      if (!p.calendar_config?.date_field) {
        return {
          title: "Calendar needs a date field",
          description:
            "Pick a date field in Presentation to position events on the calendar.",
        };
      }
      if (!p.calendar_config?.label_field) {
        return {
          title: "Calendar needs a label field",
          description:
            "Pick a label field in Presentation so events have readable titles.",
        };
      }
      return null;
    case "cards":
      if (!p.card_config?.title_field) {
        return {
          title: "Cards need a title field",
          description:
            "Pick a title field in Presentation so each card has a heading.",
        };
      }
      return null;
    case "chart":
      if (
        !p.chart_config?.chart_type
        || !p.chart_config?.x_field
        || !p.chart_config?.y_aggregation
      ) {
        return {
          title: "Chart needs type + axes + aggregation",
          description:
            "Pick chart type, X axis, and aggregation in Presentation to render the chart.",
        };
      }
      return null;
    case "stat":
      if (!p.stat_config?.metric_field || !p.stat_config?.aggregation) {
        return {
          title: "Stat needs metric + aggregation",
          description:
            "Pick a metric field and aggregation in Presentation to render the stat.",
        };
      }
      return null;
    case "list":
    case "table":
    default:
      return null;
  }
}
