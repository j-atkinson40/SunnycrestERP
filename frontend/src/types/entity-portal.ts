/**
 * Entity-portal hydration contract — S-1 (§4.2).
 *
 * Mirrors backend `PortalResponseBody`
 * (backend/app/api/routes/command_bar.py). The envelope is
 * model-agnostic: per-type payloads ride `portal`; `pivots` and
 * `actions` are shared shapes every card renders identically.
 * S-2..S-5 consume this contract unchanged.
 */

export type PortalEntityType =
  | "company_entity"
  | "contact"
  | "fh_case"
  | "sales_order"
  | "invoice"
  | "product";

/** Entity types with a shipped S-1 portal card. `document` + `task`
 * are deliberately omitted in S-1 (thin card / peek-covered) — they
 * join additively later with zero contract change. */
export const PORTAL_SUPPORTED_TYPES: ReadonlySet<string> = new Set([
  "company_entity",
  "contact",
  "fh_case",
  "sales_order",
  "invoice",
  "product",
]);

export interface PortalPivot {
  entity_type: string;
  entity_id: string;
  label: string;
  context?: string | null;
}

export interface PortalAction {
  kind: "tel" | "mailto" | "navigate";
  label: string;
  value: string;
}

export interface PortalResponse {
  entity_type: string;
  entity_id: string;
  display_label: string;
  navigate_url: string;
  portal: Record<string, unknown>;
  pivots: PortalPivot[];
  actions: PortalAction[];
  omitted_sections: string[];
}

/** Parse a command-bar search-result id ("entity:{type}:{uuid}")
 * into a portal candidate. Returns null for non-entity ids. */
export function parseEntityResultId(
  id: string,
): { entityType: string; entityId: string } | null {
  if (!id.startsWith("entity:")) return null;
  const rest = id.slice("entity:".length);
  const sep = rest.indexOf(":");
  if (sep <= 0) return null;
  const entityType = rest.slice(0, sep);
  const entityId = rest.slice(sep + 1);
  if (!entityType || !entityId) return null;
  return { entityType, entityId };
}
