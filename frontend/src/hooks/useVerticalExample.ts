/**
 * Vertical-aware example language.
 *
 * Reads the current tenant's `Company.vertical` from `useAuth()` and
 * returns entity-name / verb language appropriate to the vertical.
 * The single source of truth for all vertical-aware user-facing text:
 * tooltip bodies, command-bar hints, empty-state messages, keyboard
 * help examples, briefing prompts.
 *
 * Hardcoded strings like "new case" are a platform bug — they break
 * trust for manufacturing tenants who immediately register the
 * platform doesn't know what business they're in.
 *
 * Defaults to "manufacturing" when the company's vertical is null.
 * Matches the existing defensive pattern in `CommandBar.tsx` that
 * falls back to manufacturing when `company?.vertical` is unset.
 *
 * Exports two shapes:
 *   - `useVerticalExample(category)` — React hook, single value
 *   - `getVerticalExample(vertical, category)` — pure function, for
 *     callers that already have the vertical in hand (e.g. the
 *     CommandBar's internal no-results-hints builder, which reads
 *     tenantVertical once and maps 3 categories in sequence)
 */

import { useAuth } from "@/contexts/auth-context";

export type VerticalName =
  | "manufacturing"
  | "funeral_home"
  | "cemetery"
  | "crematory";

export type ExampleCategory =
  // Noun forms
  | "primary_entity"        // "order" | "case" | "burial" | "cremation"
  | "primary_entity_plural" // "orders" | "cases" | "burials" | "cremations"
  | "primary_detail_term"   // "order details" | "case file" | "burial record" | "cremation record"
  | "secondary_entity"      // "quote" | "service" | "plot" | "service"
  // Create-verb forms
  | "new_primary"           // "new order" | "new case" | "new burial" | "new cremation"
  | "new_secondary"         // "new quote" | "new service" | "new plot" | "new service"
  // Verb
  | "workflow_verb"         // "process" | "arrange" | "coordinate" | "schedule"
  // Triage-queue-focused noun
  | "queue_primary";        // "invoice" | "approval" | "approval" | "certificate"

const DEFAULT_VERTICAL: VerticalName = "manufacturing";

// Canonical per-vertical × per-category table.
// Refinements from the approved spec:
//   - cemetery primary_entity: "burial" (operational default, more
//     natural in tooltip contexts than "interment")
//   - crematory secondary_entity: "service" is INTENTIONAL — a
//     crematory-only tenant has no FH context collision, and
//     crematory operators talk about memorial/committal services
const EXAMPLES: Record<VerticalName, Record<ExampleCategory, string>> = {
  manufacturing: {
    primary_entity: "order",
    primary_entity_plural: "orders",
    primary_detail_term: "order details",
    secondary_entity: "quote",
    new_primary: "new order",
    new_secondary: "new quote",
    workflow_verb: "process",
    queue_primary: "invoice",
  },
  funeral_home: {
    primary_entity: "case",
    primary_entity_plural: "cases",
    primary_detail_term: "case file",
    secondary_entity: "service",
    new_primary: "new case",
    new_secondary: "new service",
    workflow_verb: "arrange",
    queue_primary: "approval",
  },
  cemetery: {
    primary_entity: "burial",
    primary_entity_plural: "burials",
    primary_detail_term: "burial record",
    secondary_entity: "plot",
    new_primary: "new burial",
    new_secondary: "new plot",
    workflow_verb: "coordinate",
    queue_primary: "approval",
  },
  crematory: {
    primary_entity: "cremation",
    primary_entity_plural: "cremations",
    primary_detail_term: "cremation record",
    // "service" is intentional — a crematory-only tenant has no FH
    // context collision, and the industry term for the ceremonial
    // component is "service" (memorial service, committal service).
    secondary_entity: "service",
    new_primary: "new cremation",
    new_secondary: "new service",
    workflow_verb: "schedule",
    queue_primary: "certificate",
  },
};


/**
 * Normalize an unknown vertical string to a valid VerticalName.
 * Case-insensitive on input; falls back to manufacturing.
 */
function normalizeVertical(raw: string | null | undefined): VerticalName {
  if (!raw) return DEFAULT_VERTICAL;
  const lowered = raw.toLowerCase();
  if (lowered === "manufacturing") return "manufacturing";
  if (lowered === "funeral_home" || lowered === "funeralhome")
    return "funeral_home";
  if (lowered === "cemetery") return "cemetery";
  if (lowered === "crematory") return "crematory";
  return DEFAULT_VERTICAL;
}


/** Pure lookup — use from non-React callers (e.g. building a hint list). */
export function getVerticalExample(
  vertical: string | null | undefined,
  category: ExampleCategory,
): string {
  const v = normalizeVertical(vertical);
  return EXAMPLES[v][category];
}


/** React hook form — reads vertical from the auth context. */
export function useVerticalExample(category: ExampleCategory): string {
  const { company } = useAuth();
  const vertical = (company as { vertical?: string | null } | null)?.vertical;
  return getVerticalExample(vertical, category);
}


/**
 * Convenience: return the full mapping for the current tenant.
 * Used by CommandBar.tsx's no-results-hints builder which needs 2-3
 * categories in sequence; cleaner than calling the hook 3 times.
 */
export function useVerticalExamples(): Record<ExampleCategory, string> {
  const { company } = useAuth();
  const vertical = (company as { vertical?: string | null } | null)?.vertical;
  const v = normalizeVertical(vertical);
  return EXAMPLES[v];
}


// ── Test exports ────────────────────────────────────────────────────
// Exposed so the vitest file can parametrize against the same table
// the runtime uses.
export const _TEST_EXAMPLES_TABLE = EXAMPLES;
export const _TEST_VERTICALS: VerticalName[] = [
  "manufacturing",
  "funeral_home",
  "cemetery",
  "crematory",
];
export const _TEST_CATEGORIES: ExampleCategory[] = [
  "primary_entity",
  "primary_entity_plural",
  "primary_detail_term",
  "secondary_entity",
  "new_primary",
  "new_secondary",
  "workflow_verb",
  "queue_primary",
];
