/**
 * Command Bar Platform Layer Phase 1 — adapter.
 *
 * Interface translation only. No added functionality.
 *
 * The backend `/api/v1/command-bar/query` endpoint returns its own
 * spec-defined shape (see `QueryResponseBody` in
 * `backend/app/api/routes/command_bar.py`). The existing frontend
 * `CommandBar.tsx` renders `CommandAction` objects from
 * `actionRegistry.ts`. This adapter converts between the two so the
 * UI rendering code stays untouched.
 *
 * Full frontend registry reshape is deferred to Phase 5 (Triage
 * Workspace). For Phase 1 this adapter stays small: one input
 * shape → one output shape, zero logic branches.
 */

import type { CommandAction } from "@/services/actions";

// Response shape from POST /api/v1/command-bar/query
export interface CommandBarQueryResultItem {
  id: string;
  type: "navigate" | "create" | "search_result" | "action" | "saved_view";
  entity_type: string | null;
  primary_label: string;
  secondary_context: string | null;
  icon: string;
  url: string | null;
  action_id: string | null;
  score: number;
}

export interface CommandBarQueryResponse {
  intent: "navigate" | "search" | "create" | "action" | "empty";
  results: CommandBarQueryResultItem[];
  total: number;
}

export interface CommandBarQueryRequest {
  query: string;
  max_results?: number;
  context?: {
    current_page?: string;
    current_entity_type?: string;
    current_entity_id?: string;
  };
}

// Map backend `ResultType` → frontend `CommandAction.type`.
// search_result → RECORD (the closest pre-existing type for a vault
// entity hit with an entity type + nav URL).
// saved_view → VIEW (Phase 2 — slot 5 in TYPE_RANK, between RECORD 3
// and NAV 6, so saved-view hits surface above raw navigation but
// below exact record matches).
function mapResultType(
  t: CommandBarQueryResultItem["type"],
): CommandAction["type"] {
  switch (t) {
    case "navigate":
      return "NAV";
    case "create":
      return "ACTION";
    case "search_result":
      return "RECORD";
    case "saved_view":
      return "VIEW";
    case "action":
    default:
      return "ACTION";
  }
}

/**
 * Convert one backend result item into a CommandAction. The command
 * bar UI consumes `CommandAction` objects directly for rendering,
 * shortcut assignment, and invocation.
 */
export function adaptQueryResult(
  item: CommandBarQueryResultItem,
  vertical: string,
): CommandAction {
  return {
    id: item.id,
    // keywords aren't used for client-side ranking when the item
    // came from the server; the server did the ranking. Populating
    // from primary_label gives the local fuzzy matcher something
    // useful if the user scrolls + re-filters offline.
    keywords: [item.primary_label.toLowerCase()],
    title: item.primary_label,
    subtitle: item.secondary_context ?? undefined,
    icon: item.icon,
    type: mapResultType(item.type),
    route: item.url ?? undefined,
    roles: [],
    vertical,
    confidence: item.score,
  };
}

/** Convert a whole response to an ordered list of CommandActions. */
export function adaptQueryResponse(
  response: CommandBarQueryResponse,
  vertical: string,
): CommandAction[] {
  return response.results.map((r) => adaptQueryResult(r, vertical));
}
