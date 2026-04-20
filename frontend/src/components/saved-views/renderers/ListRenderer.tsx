/**
 * List mode — simple stacked rows with a clickable title.
 *
 * The thinnest renderer. Shows each row's default-title field
 * (first "text" field in the entity registry, or "title"/"name"
 * heuristic) and falls back to JSON if no obvious title field.
 *
 * Click → navigate via EntityTypeMetadata.navigate_url_template.
 */

import { Link } from "react-router";
import { Inbox } from "lucide-react";

import type {
  EntityTypeMetadata,
  SavedViewResult,
} from "@/types/saved-views";
import { EmptyState } from "@/components/ui/empty-state";
import { formatCellValue, indexFields } from "../formatters";

export interface ListRendererProps {
  result: SavedViewResult;
  entity: EntityTypeMetadata;
}

function pickTitleField(entity: EntityTypeMetadata): string {
  const byName = entity.available_fields.find((f) =>
    ["title", "name", "number", "case_number", "sku"].includes(f.field_name),
  );
  return byName?.field_name ?? entity.available_fields[0]?.field_name ?? "id";
}

function pickSubtitleField(
  entity: EntityTypeMetadata,
  titleField: string,
): string | null {
  const candidates = ["status", "customer_id", "event_start", "total"];
  for (const c of candidates) {
    const match = entity.available_fields.find((f) => f.field_name === c);
    if (match && match.field_name !== titleField) return match.field_name;
  }
  return null;
}

function buildHref(template: string, row: Record<string, unknown>): string {
  return template.replace(/\{(\w+)\}/g, (_, key) => {
    const v = row[key];
    return v === undefined || v === null ? "" : String(v);
  });
}

export function ListRenderer({ result, entity }: ListRendererProps) {
  const fieldIndex = indexFields(entity.available_fields);
  const titleField = pickTitleField(entity);
  const subtitleField = pickSubtitleField(entity, titleField);

  if (result.rows.length === 0) {
    return (
      <EmptyState
        icon={Inbox}
        title={`No ${entity.display_name.toLowerCase()} match your filters`}
        description="Adjust filters, or clear them to see everything."
        tone="filtered"
        size="sm"
        data-testid="list-renderer-empty"
      />
    );
  }

  return (
    <ul className="divide-y rounded-md border">
      {result.rows.map((row, i) => {
        const id = row.id as string | undefined;
        const href = id ? buildHref(entity.navigate_url_template, row) : null;
        const titleVal = formatCellValue(
          row[titleField],
          fieldIndex[titleField]?.field_type,
        );
        const subtitleVal = subtitleField
          ? formatCellValue(
              row[subtitleField],
              fieldIndex[subtitleField]?.field_type,
            )
          : null;
        const content = (
          <div className="flex items-baseline justify-between gap-3 px-4 py-2.5">
            <span className="font-medium truncate">{titleVal}</span>
            {subtitleVal && (
              <span className="text-xs text-muted-foreground truncate">
                {subtitleVal}
              </span>
            )}
          </div>
        );
        return (
          <li key={id ?? i}>
            {href ? (
              <Link to={href} className="block hover:bg-accent/40">
                {content}
              </Link>
            ) : (
              content
            )}
          </li>
        );
      })}
    </ul>
  );
}
