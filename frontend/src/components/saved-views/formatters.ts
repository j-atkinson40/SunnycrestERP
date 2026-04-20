/**
 * Shared value formatters for saved-view renderers.
 *
 * Every renderer funnels individual field values through
 * `formatCellValue()` so the same number/date/masked/null gets the
 * same presentation in a table, a kanban card, a list row, and a
 * card-grid card.
 */

import type { FieldMetadata, FieldType } from "@/types/saved-views";
import { MASK_SENTINEL } from "@/types/saved-views";

export function isMasked(value: unknown): boolean {
  return value === MASK_SENTINEL;
}

function formatNumber(n: number, fractionDigits = 0): string {
  return n.toLocaleString(undefined, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

function formatCurrency(n: number): string {
  return n.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
  });
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString();
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.toLocaleDateString()} ${d.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

/**
 * Format a single cell value given its field-type metadata.
 *
 * Fallback rules:
 *   - null/undefined → "—"
 *   - MASK_SENTINEL → "•••" (matches the masking indicator shown in
 *     headers)
 *   - unknown field_type → JSON.stringify for object/array, else String()
 */
export function formatCellValue(
  value: unknown,
  fieldType: FieldType | undefined,
): string {
  if (value === null || value === undefined) return "—";
  if (isMasked(value)) return "•••";

  switch (fieldType) {
    case "currency":
      return typeof value === "number"
        ? formatCurrency(value)
        : formatCurrency(Number(value));
    case "number":
      return typeof value === "number"
        ? formatNumber(value)
        : formatNumber(Number(value));
    case "date":
      return typeof value === "string" ? formatDate(value) : String(value);
    case "datetime":
      return typeof value === "string" ? formatDateTime(value) : String(value);
    case "boolean":
      return value ? "Yes" : "No";
    case "enum":
    case "text":
    case "relation":
      return String(value);
    default:
      if (typeof value === "object") return JSON.stringify(value);
      return String(value);
  }
}

/**
 * Resolve a field's display metadata from an entity's available
 * fields. Returns undefined if the field isn't in the entity
 * registry — caller should fall back to String(value).
 */
export function getFieldMeta(
  fields: FieldMetadata[],
  fieldName: string,
): FieldMetadata | undefined {
  return fields.find((f) => f.field_name === fieldName);
}

/**
 * Build a lookup map keyed by field_name for O(1) access in tight
 * render loops (tables with hundreds of rows).
 */
export function indexFields(
  fields: FieldMetadata[],
): Record<string, FieldMetadata> {
  const out: Record<string, FieldMetadata> = {};
  for (const f of fields) {
    out[f.field_name] = f;
  }
  return out;
}
