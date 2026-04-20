/**
 * Phase 5 — Registry-derived NL intent detector.
 *
 * Supersedes the Phase 4 hand-maintained ENTITY_PATTERNS table. The
 * `services/actions` registry is the single source of truth: every
 * entry with `supports_nl_creation: true` contributes an entry here,
 * using its `nl_aliases` list + its `route` as the tab fallback URL.
 *
 * If a create action's `entity_type` does not match an `NLEntityType`
 * literal, it is silently skipped — only entities the Phase 4 NL
 * overlay actually understands qualify. Unknown alias → NLEntityType
 * mappings are filtered by the switch in `_entityTypeFor(actionId)`.
 *
 * Contract:
 *   Input:  raw user query string
 *   Output: { entityType, nlContent, tabFallbackUrl } or null
 *
 * Recognizes "new <entity>" / "create <entity>" / "add <entity>" /
 * "start" / "draft" / "compose" prefixes followed by non-empty content.
 */

import type { NLEntityType } from "@/types/nl-creation";
import {
  getActionsSupportingNLCreation,
  type ActionRegistryEntry,
} from "@/services/actions";

const CREATE_VERBS = new Set([
  "new",
  "create",
  "add",
  "start",
  "draft",
  "compose",
]);

const MIN_NL_CONTENT_CHARS = 3;

export interface NLIntentMatch {
  entityType: NLEntityType;
  nlContent: string;
  tabFallbackUrl: string;
}

interface DerivedPattern {
  entityType: NLEntityType;
  aliases: string[];
  tabFallbackUrl: string;
}

/**
 * Map a create action's id (or inferred entity name) to the Phase 4
 * NLEntityType literal. Guards against unknown entity types reaching
 * the backend `/nl-creation/*` endpoints.
 */
function _entityTypeFor(
  entry: ActionRegistryEntry,
): NLEntityType | null {
  // Convention: create.X action id = `create_X` where X is the entity
  // key. Explicit mapping table for the small fixed set Phase 4 + 5
  // actually supports.
  const map: Record<string, NLEntityType> = {
    create_case: "case",
    fh_new_arrangement: "case",
    create_event: "event",
    create_contact: "contact",
    create_task: "task",
  };
  return map[entry.id] ?? null;
}

function _derivePatterns(): DerivedPattern[] {
  const out: DerivedPattern[] = [];
  for (const e of getActionsSupportingNLCreation()) {
    const t = _entityTypeFor(e);
    if (!t) continue;
    const aliases = e.nl_aliases ?? [];
    if (aliases.length === 0) continue;
    out.push({
      entityType: t,
      aliases,
      tabFallbackUrl: e.route ?? "/",
    });
  }
  return out;
}

export function detectNLIntent(query: string): NLIntentMatch | null {
  const raw = (query ?? "").trim();
  if (!raw) return null;
  const lowered = raw.toLowerCase();
  const [firstWord, ...restTokens] = lowered.split(/\s+/);
  if (!firstWord || !CREATE_VERBS.has(firstWord)) return null;
  if (restTokens.length === 0) return null;

  const rest = lowered.slice(firstWord.length + 1);
  const verbLen = firstWord.length + 1;
  const rawRest = raw.slice(verbLen).trim();
  if (!rawRest) return null;

  // Find the longest matching alias (prefer "calendar event" over "event").
  let bestMatch:
    | { entityType: NLEntityType; aliasLen: number; tabFallbackUrl: string }
    | null = null;

  const patterns = _derivePatterns();
  for (const pattern of patterns) {
    for (const alias of pattern.aliases) {
      const aliasLc = alias.toLowerCase();
      if (
        rest.startsWith(aliasLc) &&
        (rest.length === aliasLc.length || rest[aliasLc.length] === " ")
      ) {
        if (bestMatch === null || aliasLc.length > bestMatch.aliasLen) {
          bestMatch = {
            entityType: pattern.entityType,
            aliasLen: aliasLc.length,
            tabFallbackUrl: pattern.tabFallbackUrl,
          };
        }
      }
    }
  }

  if (bestMatch === null) return null;

  const nlContent = rawRest.slice(bestMatch.aliasLen).trim();
  if (nlContent.length < MIN_NL_CONTENT_CHARS) return null;

  return {
    entityType: bestMatch.entityType,
    nlContent,
    tabFallbackUrl: bestMatch.tabFallbackUrl,
  };
}
