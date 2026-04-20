/**
 * Table mode — columnar grid with typed formatting.
 *
 * Column list comes from config.presentation.table_config.columns.
 * Falls back to entity.default_columns if config didn't specify.
 *
 * Masked columns (when `result.permission_mode === "cross_tenant_masked"`
 * and the column is NOT in masked_fields) are shown normally. Masked
 * cells display the "•••" sentinel formatted by formatCellValue.
 */

import { Table2 } from "lucide-react";
import type {
  EntityTypeMetadata,
  SavedViewResult,
  TableConfig,
} from "@/types/saved-views";
import { EmptyState } from "@/components/ui/empty-state";
import { formatCellValue, indexFields } from "../formatters";

export interface TableRendererProps {
  result: SavedViewResult;
  entity: EntityTypeMetadata;
  tableConfig?: TableConfig | null;
}

export function TableRenderer({
  result,
  entity,
  tableConfig,
}: TableRendererProps) {
  const fieldIndex = indexFields(entity.available_fields);
  const columns =
    tableConfig?.columns && tableConfig.columns.length > 0
      ? tableConfig.columns
      : entity.default_columns;

  if (result.rows.length === 0) {
    return (
      <EmptyState
        icon={Table2}
        title={`No ${entity.display_name.toLowerCase()} match your filters`}
        description="Adjust filters, or clear them to see everything."
        tone="filtered"
        size="sm"
        data-testid="table-renderer-empty"
      />
    );
  }

  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full text-sm">
        <thead className="bg-muted/40">
          <tr>
            {columns.map((col) => {
              const meta = fieldIndex[col];
              return (
                <th
                  key={col}
                  className="px-3 py-2 text-left font-medium whitespace-nowrap"
                >
                  {meta?.display_name ?? col}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {result.rows.map((row, i) => {
            const id = (row.id as string | undefined) ?? `row-${i}`;
            return (
              <tr key={id} className="border-t hover:bg-accent/40">
                {columns.map((col) => (
                  <td key={col} className="px-3 py-2 whitespace-nowrap">
                    {formatCellValue(row[col], fieldIndex[col]?.field_type)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
