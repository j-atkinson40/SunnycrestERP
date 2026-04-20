/**
 * Stat mode — a single scalar with optional comparison.
 *
 * Backend returns the value in `result.aggregations` keyed as
 * `{aggregation}_{metric_field}` (e.g. `sum_total`). We look up
 * that key; if absent, fall back to rows[0][metric_field] or 0.
 */

import type {
  EntityTypeMetadata,
  SavedViewResult,
  StatConfig,
} from "@/types/saved-views";
import { formatCellValue, indexFields } from "../formatters";

export interface StatRendererProps {
  result: SavedViewResult;
  entity: EntityTypeMetadata;
  statConfig: StatConfig;
}

function resolveAggKey(statConfig: StatConfig): string {
  return `${statConfig.aggregation}_${statConfig.metric_field}`;
}

export function StatRenderer({
  result,
  entity,
  statConfig,
}: StatRendererProps) {
  const fieldIndex = indexFields(entity.available_fields);
  const aggKey = resolveAggKey(statConfig);

  let value: unknown = undefined;
  if (result.aggregations && aggKey in result.aggregations) {
    value = result.aggregations[aggKey];
  } else if (result.rows.length > 0) {
    value = result.rows[0][statConfig.metric_field];
  }

  const meta = fieldIndex[statConfig.metric_field];
  const label = statConfig.label ?? meta?.display_name ?? statConfig.metric_field;
  const hasValue = value !== undefined && value !== null;
  const formatted = hasValue ? formatCellValue(value, meta?.field_type) : "—";

  return (
    <div
      className="flex flex-col items-start gap-1 rounded-md border bg-card p-4"
      data-testid="stat-renderer"
    >
      <div className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="text-3xl font-semibold tabular-nums">{formatted}</div>
      {hasValue && result.total_count > 0 ? (
        <div className="text-xs text-muted-foreground">
          across {result.total_count} records
        </div>
      ) : !hasValue ? (
        <div className="text-xs text-muted-foreground">
          No data for the selected period.
        </div>
      ) : null}
    </div>
  );
}
