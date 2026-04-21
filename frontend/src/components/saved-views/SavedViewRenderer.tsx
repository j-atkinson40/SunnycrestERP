/**
 * SavedViewRenderer — dispatch to the right presentation mode.
 *
 * One component, seven mode targets. Consumers (SavedViewPage,
 * SavedViewWidget, hub dashboards, command-bar VIEW landing pages)
 * all go through this one place — keeps the renderers swappable
 * and gives cross-tenant masking + empty-state one home.
 *
 * Chart is code-split via React.lazy — the recharts chunk is ~60kb
 * gzipped and only ~5% of saved views use it. The Suspense
 * fallback is a tight spinner inside a same-size container so
 * layout doesn't thrash.
 */

import { Suspense, lazy } from "react";

import type {
  EntityTypeMetadata,
  PresentationMode,
  SavedViewConfig,
  SavedViewResult,
} from "@/types/saved-views";
import { CalendarRenderer } from "./renderers/CalendarRenderer";
import { CardsRenderer } from "./renderers/CardsRenderer";
import { KanbanRenderer } from "./renderers/KanbanRenderer";
import { ListRenderer } from "./renderers/ListRenderer";
import { StatRenderer } from "./renderers/StatRenderer";
import { TableRenderer } from "./renderers/TableRenderer";

// Lazy — keeps recharts out of the initial bundle.
const ChartRenderer = lazy(() => import("./renderers/ChartRenderer"));

// Follow-up 4 — when caller provides onPeek, the title-cell of each
// row in supported renderers (List, Table, Cards, Kanban) becomes a
// click-to-peek trigger. Detail-page + widget callers don't pass
// the prop; those surfaces keep title clicks navigating as before.
// Build preview surface (follow-up 3) opts in to surface peeks
// inline as users scrub through configs.
export type SavedViewPeekHandler = (
  entityType: string,
  entityId: string,
  anchorElement: HTMLElement,
) => void;


export interface SavedViewRendererProps {
  config: SavedViewConfig;
  result: SavedViewResult;
  entity: EntityTypeMetadata;
  onPeek?: SavedViewPeekHandler;
}

function MaskedBanner({ fields }: { fields: string[] }) {
  if (fields.length === 0) return null;
  return (
    <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
      Cross-tenant view — some fields are masked:{" "}
      <span className="font-medium">{fields.join(", ")}</span>
    </div>
  );
}

function ModeFallback({ mode }: { mode: PresentationMode }) {
  return (
    <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
      Unsupported presentation mode: {mode}
    </div>
  );
}

export function SavedViewRenderer({
  config,
  result,
  entity,
  onPeek,
}: SavedViewRendererProps) {
  const mode = config.presentation.mode;

  const body = (() => {
    switch (mode) {
      case "list":
        return (
          <ListRenderer result={result} entity={entity} onPeek={onPeek} />
        );
      case "table":
        return (
          <TableRenderer
            result={result}
            entity={entity}
            tableConfig={config.presentation.table_config}
            onPeek={onPeek}
          />
        );
      case "kanban":
        if (!config.presentation.kanban_config) {
          return <ModeFallback mode="kanban" />;
        }
        return (
          <KanbanRenderer
            result={result}
            entity={entity}
            kanbanConfig={config.presentation.kanban_config}
          />
        );
      case "calendar":
        if (!config.presentation.calendar_config) {
          return <ModeFallback mode="calendar" />;
        }
        return (
          <CalendarRenderer
            result={result}
            entity={entity}
            calendarConfig={config.presentation.calendar_config}
          />
        );
      case "cards":
        if (!config.presentation.card_config) {
          return <ModeFallback mode="cards" />;
        }
        return (
          <CardsRenderer
            result={result}
            entity={entity}
            cardConfig={config.presentation.card_config}
          />
        );
      case "chart":
        if (!config.presentation.chart_config) {
          return <ModeFallback mode="chart" />;
        }
        return (
          <Suspense
            fallback={
              <div className="flex h-[320px] items-center justify-center text-sm text-muted-foreground">
                Loading chart…
              </div>
            }
          >
            <ChartRenderer
              result={result}
              chartConfig={config.presentation.chart_config}
            />
          </Suspense>
        );
      case "stat":
        if (!config.presentation.stat_config) {
          return <ModeFallback mode="stat" />;
        }
        return (
          <StatRenderer
            result={result}
            entity={entity}
            statConfig={config.presentation.stat_config}
          />
        );
      default:
        return <ModeFallback mode={mode} />;
    }
  })();

  return (
    <div className="space-y-2">
      {result.permission_mode === "cross_tenant_masked" && (
        <MaskedBanner fields={result.masked_fields} />
      )}
      {body}
    </div>
  );
}
