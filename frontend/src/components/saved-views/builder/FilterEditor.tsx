/**
 * FilterEditor — add/remove/edit query filters.
 *
 * One row per filter. Field dropdown is populated from the
 * currently-selected entity's `available_fields`. Operator dropdown
 * is full vocabulary — backend rejects nonsensical combinations
 * (eq on relation, between on text, etc). Value input is a raw
 * text box for Phase 2; future work could specialize per field type
 * (date picker, enum select).
 *
 * Values:
 *   - Single-value ops (eq, ne, contains, gt, lt, gte, lte) → string
 *   - Multi-value ops (in, not_in) → comma-split on submit
 *   - Nullary ops (is_null, is_not_null) → no value input
 *   - between → two inputs; stored as [lo, hi]
 */

import { Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  EntityTypeMetadata,
  Filter,
  FilterOperator,
} from "@/types/saved-views";

const ALL_OPS: FilterOperator[] = [
  "eq",
  "ne",
  "contains",
  "in",
  "not_in",
  "gt",
  "lt",
  "gte",
  "lte",
  "between",
  "is_null",
  "is_not_null",
];

const NULLARY_OPS: FilterOperator[] = ["is_null", "is_not_null"];
const MULTI_OPS: FilterOperator[] = ["in", "not_in"];
const RANGE_OPS: FilterOperator[] = ["between"];

function toInputValue(f: Filter): string {
  if (NULLARY_OPS.includes(f.operator)) return "";
  if (MULTI_OPS.includes(f.operator)) {
    if (Array.isArray(f.value)) return f.value.join(", ");
    return f.value !== undefined && f.value !== null ? String(f.value) : "";
  }
  if (RANGE_OPS.includes(f.operator)) {
    if (Array.isArray(f.value)) return f.value.join(", ");
    return "";
  }
  return f.value !== undefined && f.value !== null ? String(f.value) : "";
}

function parseInputValue(op: FilterOperator, input: string): unknown {
  if (NULLARY_OPS.includes(op)) return null;
  if (MULTI_OPS.includes(op)) {
    return input
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }
  if (RANGE_OPS.includes(op)) {
    const parts = input.split(",").map((s) => s.trim());
    return parts.length === 2 ? parts : input;
  }
  return input;
}

export interface FilterEditorProps {
  filters: Filter[];
  entity: EntityTypeMetadata;
  onChange: (filters: Filter[]) => void;
}

export function FilterEditor({ filters, entity, onChange }: FilterEditorProps) {
  const filterableFields = entity.available_fields.filter(
    (f) => f.filterable !== false,
  );

  const add = () => {
    onChange([
      ...filters,
      {
        field: filterableFields[0]?.field_name ?? "",
        operator: "eq",
        value: "",
      },
    ]);
  };

  const update = (idx: number, patch: Partial<Filter>) => {
    onChange(filters.map((f, i) => (i === idx ? { ...f, ...patch } : f)));
  };

  const remove = (idx: number) => {
    onChange(filters.filter((_, i) => i !== idx));
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium">Filters</h4>
        <Button size="sm" variant="outline" onClick={add}>
          <Plus className="mr-1 h-3 w-3" /> Add filter
        </Button>
      </div>
      {filters.length === 0 && (
        <div className="rounded-md border border-dashed px-3 py-4 text-center text-xs text-muted-foreground">
          No filters. Saved view will return all records.
        </div>
      )}
      {filters.map((f, i) => (
        <div key={i} className="flex items-center gap-2">
          <Select
            value={f.field}
            onValueChange={(v) => update(i, { field: v ?? "" })}
          >
            <SelectTrigger className="w-[180px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {filterableFields.map((fld) => (
                <SelectItem key={fld.field_name} value={fld.field_name}>
                  {fld.display_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={f.operator}
            onValueChange={(v) => {
              const op = (v ?? "eq") as FilterOperator;
              update(i, {
                operator: op,
                value: NULLARY_OPS.includes(op) ? null : f.value,
              });
            }}
          >
            <SelectTrigger className="w-[140px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ALL_OPS.map((op) => (
                <SelectItem key={op} value={op}>
                  {op}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {!NULLARY_OPS.includes(f.operator) && (
            <Input
              className="flex-1"
              placeholder={
                MULTI_OPS.includes(f.operator)
                  ? "comma-separated values"
                  : RANGE_OPS.includes(f.operator)
                    ? "lo, hi"
                    : "value"
              }
              value={toInputValue(f)}
              onChange={(e) =>
                update(i, { value: parseInputValue(f.operator, e.target.value) })
              }
            />
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => remove(i)}
            aria-label="Remove filter"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      ))}
    </div>
  );
}
