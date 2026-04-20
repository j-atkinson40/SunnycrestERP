/**
 * Kanban mode — column-per-group, card-per-row.
 *
 * Uses result.groups when the executor pre-grouped (any view with
 * grouping in the query produces this). Falls back to deriving
 * buckets client-side from config.presentation.kanban_config.group_by_field
 * if the backend didn't emit groups (unexpected; defensive).
 *
 * Phase 2 is drag-drop-free — re-ordering / moving cards across
 * columns is a Phase 3 concern (requires an update endpoint that
 * mutates the source record's group-by field). Users who want to
 * change status still go to the detail page.
 */

import { Link } from "react-router";
import { Kanban } from "lucide-react";

import type {
  EntityTypeMetadata,
  KanbanConfig,
  SavedViewResult,
} from "@/types/saved-views";
import { EmptyState } from "@/components/ui/empty-state";
import { formatCellValue, indexFields } from "../formatters";

export interface KanbanRendererProps {
  result: SavedViewResult;
  entity: EntityTypeMetadata;
  kanbanConfig: KanbanConfig;
}

function deriveGroups(
  rows: Record<string, unknown>[],
  groupBy: string,
): Record<string, Record<string, unknown>[]> {
  const out: Record<string, Record<string, unknown>[]> = {};
  for (const r of rows) {
    const key = String(r[groupBy] ?? "—");
    (out[key] ??= []).push(r);
  }
  return out;
}

function buildHref(template: string, row: Record<string, unknown>): string {
  return template.replace(/\{(\w+)\}/g, (_, key) => {
    const v = row[key];
    return v === undefined || v === null ? "" : String(v);
  });
}

export function KanbanRenderer({
  result,
  entity,
  kanbanConfig,
}: KanbanRendererProps) {
  const fieldIndex = indexFields(entity.available_fields);
  const groups =
    result.groups ?? deriveGroups(result.rows, kanbanConfig.group_by_field);

  const keys = kanbanConfig.columns_order ?? Object.keys(groups).sort();
  if (keys.length === 0) {
    return (
      <EmptyState
        icon={Kanban}
        title="All lanes are empty"
        description={`No ${entity.display_name.toLowerCase()} to show across any status right now.`}
        size="sm"
        data-testid="kanban-renderer-empty"
      />
    );
  }

  return (
    <div className="flex gap-3 overflow-x-auto pb-2">
      {keys.map((key) => {
        const rows = groups[key] ?? [];
        return (
          <div
            key={key}
            className="flex min-w-[240px] max-w-[280px] flex-col gap-2 rounded-md bg-muted/30 p-2"
          >
            <div className="flex items-center justify-between px-1 pb-1">
              <span className="text-xs font-medium uppercase tracking-wide">
                {key}
              </span>
              <span className="text-xs text-muted-foreground">
                {rows.length}
              </span>
            </div>
            <div className="flex flex-col gap-2">
              {rows.map((row, i) => {
                const id = row.id as string | undefined;
                const href = id
                  ? buildHref(entity.navigate_url_template, row)
                  : null;
                const titleVal = formatCellValue(
                  row[kanbanConfig.card_title_field],
                  fieldIndex[kanbanConfig.card_title_field]?.field_type,
                );
                const body = (
                  <div className="rounded border bg-card px-2.5 py-2 text-sm hover:bg-accent/40">
                    <div className="font-medium truncate">{titleVal}</div>
                    {kanbanConfig.card_meta_fields.map((mf) => {
                      const meta = fieldIndex[mf];
                      const label = meta?.display_name ?? mf;
                      return (
                        <div
                          key={mf}
                          className="mt-0.5 text-xs text-muted-foreground truncate"
                        >
                          <span className="opacity-60">{label}: </span>
                          {formatCellValue(row[mf], meta?.field_type)}
                        </div>
                      );
                    })}
                  </div>
                );
                return (
                  <div key={id ?? i}>
                    {href ? <Link to={href}>{body}</Link> : body}
                  </div>
                );
              })}
              {rows.length === 0 && (
                <div className="px-1 py-3 text-center text-xs text-muted-foreground">
                  Empty
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
