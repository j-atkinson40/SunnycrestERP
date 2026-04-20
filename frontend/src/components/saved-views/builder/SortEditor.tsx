/**
 * SortEditor — ordered sort list.
 *
 * Order matters — first sort is primary, second is tiebreaker, etc.
 * No drag-reorder UI in Phase 2; users add in the order they want.
 * Remove-and-re-add to change ordering.
 */

import { Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  EntityTypeMetadata,
  Sort,
  SortDirection,
} from "@/types/saved-views";

export interface SortEditorProps {
  sort: Sort[];
  entity: EntityTypeMetadata;
  onChange: (sort: Sort[]) => void;
}

export function SortEditor({ sort, entity, onChange }: SortEditorProps) {
  const sortableFields = entity.available_fields.filter(
    (f) => f.sortable !== false,
  );

  const add = () => {
    onChange([
      ...sort,
      {
        field: sortableFields[0]?.field_name ?? "",
        direction: "desc",
      },
    ]);
  };

  const update = (idx: number, patch: Partial<Sort>) => {
    onChange(sort.map((s, i) => (i === idx ? { ...s, ...patch } : s)));
  };

  const remove = (idx: number) => {
    onChange(sort.filter((_, i) => i !== idx));
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium">Sort</h4>
        <Button size="sm" variant="outline" onClick={add}>
          <Plus className="mr-1 h-3 w-3" /> Add sort
        </Button>
      </div>
      {sort.length === 0 && (
        <div className="rounded-md border border-dashed px-3 py-4 text-center text-xs text-muted-foreground">
          No sort. Falls back to entity default.
        </div>
      )}
      {sort.map((s, i) => (
        <div key={i} className="flex items-center gap-2">
          <Select
            value={s.field}
            onValueChange={(v) => update(i, { field: v ?? "" })}
          >
            <SelectTrigger className="flex-1">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {sortableFields.map((fld) => (
                <SelectItem key={fld.field_name} value={fld.field_name}>
                  {fld.display_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={s.direction}
            onValueChange={(v) =>
              update(i, { direction: (v ?? "asc") as SortDirection })
            }
          >
            <SelectTrigger className="w-[110px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="asc">Ascending</SelectItem>
              <SelectItem value="desc">Descending</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => remove(i)}
            aria-label="Remove sort"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      ))}
    </div>
  );
}
