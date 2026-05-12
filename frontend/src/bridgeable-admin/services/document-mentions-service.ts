/**
 * Document mentions service — Arc 4b.2a (substrate layer).
 *
 * Wraps the dedicated mention endpoint at
 * `/api/v1/documents-v2/admin/mentions/resolve`. Goes through
 * `apiClient` (tenant axios) — same pattern as
 * `document-blocks-service.ts` because the documents substrate is
 * mounted tenant-side with `require_admin` gating.
 *
 * UI vocabulary boundary (Q-COUPLING-1):
 *   Picker subset = 4 entity types (case / order / contact / product).
 *   The substrate supports 7 entity types but this service is the
 *   picker consumer; expansion of picker subset has documented
 *   trigger criteria.
 *
 * Per per-consumer endpoint shaping canon: this service is the
 * mention-picker consumer; the command bar consumer at
 * `services/command-bar-service.ts` (Phase 1) is a parallel
 * consumer of the same Phase 1 entity resolver substrate. Endpoint
 * shapes differ; underlying resolver is shared.
 *
 * Token shape (Q-ARC4B2-1):
 *   `{{ ref("case", "<uuid>") }}` — Jinja function-call syntax,
 *   identical on backend and frontend. `buildRefToken()` is the
 *   canonical helper for serializing.
 *
 * Reference-only rendering at v1 (Q-ARC4B2-2):
 *   `preview_snippet` is returned but NOT rendered at v1 mention
 *   layer. The picker UI (Arc 4b.2b) consumes it to disambiguate
 *   matches. Hover-preview deferred to a bounded sub-arc when
 *   concrete operator signal warrants.
 */
import apiClient from "@/lib/api-client"


// ─── UI vocabulary (Q-COUPLING-1 picker subset) ───────────────


export type MentionEntityType =
  | "case"
  | "order"
  | "contact"
  | "product"


/** Picker subset, canonical order. Used to render entity-type tabs
 * + section headers in the picker UI. */
export const MENTION_ENTITY_TYPES: readonly MentionEntityType[] = [
  "case",
  "order",
  "contact",
  "product",
] as const


/** UI label for each entity type — used in section headers + the
 * entity-not-found placeholder. Singular form. */
export const MENTION_ENTITY_LABELS: Record<MentionEntityType, string> = {
  case: "Case",
  order: "Order",
  contact: "Contact",
  product: "Product",
}


/** Plural UI label — used for section headers like "Cases" in the
 * picker dropdown. */
export const MENTION_ENTITY_LABELS_PLURAL: Record<MentionEntityType, string> = {
  case: "Cases",
  order: "Orders",
  contact: "Contacts",
  product: "Products",
}


// ─── Request/Response types ───────────────────────────────────


export interface MentionResolveRequest {
  entity_type: MentionEntityType
  query: string
  limit?: number
}


export interface MentionCandidate {
  entity_type: MentionEntityType
  entity_id: string
  display_name: string
  preview_snippet: string | null
}


export interface MentionResolveResponse {
  results: MentionCandidate[]
  total: number
}


// ─── Service ──────────────────────────────────────────────────


/** Resolve entity candidates for the mention picker.
 *
 * Tenant-scoped at the backend via current_user.company_id; this
 * client passes through the tenant-realm JWT via apiClient.
 *
 * Empty/whitespace queries return `{results: [], total: 0}` without
 * hitting the resolver — picker UX surfaces empty-query state as
 * "Start typing to search…".
 */
export async function resolveMention(
  request: MentionResolveRequest,
): Promise<MentionResolveResponse> {
  const { data } = await apiClient.post<MentionResolveResponse>(
    "/documents-v2/admin/mentions/resolve",
    request,
  )
  return data
}


// ─── Token shape helpers (Q-ARC4B2-1) ─────────────────────────


/** Build a canonical Jinja `{{ ref(...) }}` token string.
 *
 * Mirrors backend `mention_filter.build_ref_token()`. The picker UI
 * (Arc 4b.2b) calls this to serialize selected entity → token text
 * that gets inserted into the body content.
 *
 * Both UI vocabulary (`case`/`order`/...) and substrate vocabulary
 * (`fh_case`/`sales_order`/...) are accepted; the Jinja filter
 * normalizes at render time.
 */
export function buildRefToken(
  entityType: string,
  entityId: string,
): string {
  // Defensive: strip quote chars that would break the token shape.
  const safeType = String(entityType).replace(/["']/g, "")
  const safeId = String(entityId).replace(/["']/g, "")
  return `{{ ref("${safeType}", "${safeId}") }}`
}


/** Pure regex used by `parseRefTokens` and tests. Matches the
 * canonical Jinja function-call form `{{ ref("...", "...") }}`
 * with flexible whitespace. */
export const REF_TOKEN_REGEX =
  /\{\{\s*ref\(\s*['"]([a-z_]+)['"]\s*,\s*['"]([A-Za-z0-9_-]+)['"]\s*\)\s*\}\}/g


/** Extract all `{{ ref(...) }}` tokens from a body string.
 *
 * Returns array of `{ entity_type, entity_id }` in document order
 * (duplicates preserved). Mirrors backend
 * `mention_filter.parse_ref_tokens()`. Used by:
 *   - tests that verify token serialization
 *   - Arc 4b.2b picker UX for highlighting existing mentions
 */
export function parseRefTokens(body: string): Array<{
  entity_type: string
  entity_id: string
}> {
  const out: Array<{ entity_type: string; entity_id: string }> = []
  if (!body) return out
  // Reset regex state because the const is shared.
  REF_TOKEN_REGEX.lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = REF_TOKEN_REGEX.exec(body)) !== null) {
    out.push({ entity_type: match[1], entity_id: match[2] })
  }
  return out
}
