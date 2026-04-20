/**
 * Cards mode — responsive card grid.
 *
 * `CardConfig` drives: title_field (required), subtitle_field
 * (optional, shown under the title), body_fields (array of
 * label/value pairs under the subtitle), image_field (optional URL;
 * rendered as a thumbnail at the top of the card).
 */

import { Link } from "react-router";
import { LayoutGrid } from "lucide-react";

import type {
  CardConfig,
  EntityTypeMetadata,
  SavedViewResult,
} from "@/types/saved-views";
import { EmptyState } from "@/components/ui/empty-state";
import { formatCellValue, indexFields } from "../formatters";

export interface CardsRendererProps {
  result: SavedViewResult;
  entity: EntityTypeMetadata;
  cardConfig: CardConfig;
}

function buildHref(template: string, row: Record<string, unknown>): string {
  return template.replace(/\{(\w+)\}/g, (_, key) => {
    const v = row[key];
    return v === undefined || v === null ? "" : String(v);
  });
}

export function CardsRenderer({
  result,
  entity,
  cardConfig,
}: CardsRendererProps) {
  const fieldIndex = indexFields(entity.available_fields);

  if (result.rows.length === 0) {
    return (
      <EmptyState
        icon={LayoutGrid}
        title={`No ${entity.display_name.toLowerCase()} match your filters`}
        description="Adjust filters, or clear them to see everything."
        tone="filtered"
        size="sm"
        data-testid="cards-renderer-empty"
      />
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {result.rows.map((row, i) => {
        const id = row.id as string | undefined;
        const href = id ? buildHref(entity.navigate_url_template, row) : null;
        const title = formatCellValue(
          row[cardConfig.title_field],
          fieldIndex[cardConfig.title_field]?.field_type,
        );
        const subtitle = cardConfig.subtitle_field
          ? formatCellValue(
              row[cardConfig.subtitle_field],
              fieldIndex[cardConfig.subtitle_field]?.field_type,
            )
          : null;
        const image =
          cardConfig.image_field &&
          typeof row[cardConfig.image_field] === "string"
            ? (row[cardConfig.image_field] as string)
            : null;
        const body = (
          <div className="h-full overflow-hidden rounded-md border bg-card hover:bg-accent/40">
            {image && (
              <img
                src={image}
                alt=""
                className="h-32 w-full object-cover"
                loading="lazy"
              />
            )}
            <div className="space-y-1 p-3">
              <div className="font-medium truncate">{title}</div>
              {subtitle && (
                <div className="text-xs text-muted-foreground truncate">
                  {subtitle}
                </div>
              )}
              {cardConfig.body_fields.length > 0 && (
                <dl className="mt-2 space-y-0.5 text-xs">
                  {cardConfig.body_fields.map((f) => {
                    const meta = fieldIndex[f];
                    return (
                      <div key={f} className="flex justify-between gap-2">
                        <dt className="text-muted-foreground">
                          {meta?.display_name ?? f}
                        </dt>
                        <dd className="truncate">
                          {formatCellValue(row[f], meta?.field_type)}
                        </dd>
                      </div>
                    );
                  })}
                </dl>
              )}
            </div>
          </div>
        );
        return (
          <div key={id ?? i}>
            {href ? (
              <Link to={href} className="block h-full">
                {body}
              </Link>
            ) : (
              body
            )}
          </div>
        );
      })}
    </div>
  );
}
