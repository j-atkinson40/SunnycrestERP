/**
 * resolveEffectiveTokens — compose BASE_TOKENS + platform_themes overrides.
 *
 * Sub-arc C-2.1 substrate plumbing (Q7 lean option b). The editor
 * fetches resolved theme overrides via /api/platform/admin/visual-
 * editor/themes/resolve and merges them on top of the canonical
 * BASE_TOKENS substrate.
 *
 *   effective_tokens = { ...BASE_TOKENS[mode], ...overrides }
 *
 * The override map may arrive with or without leading `--` on token
 * names; this module normalizes both shapes to the canonical
 * no-prefix form used by BASE_TOKENS and the TokenSwatchPicker.
 */
import {
  BASE_TOKENS,
  baseTokensForMode,
  type BaseTokenMode,
} from "./base-tokens"

/** Normalize a token key — strip leading `--` if present. */
export function normalizeTokenKey(key: string): string {
  return key.startsWith("--") ? key.slice(2) : key
}

/**
 * Compose the effective token map for a given mode + override
 * dict. Returns `Record<string, string>` (not the BaseTokenMap
 * type) because overrides may introduce keys outside the canonical
 * set — the resolver layer must tolerate this gracefully.
 */
export function resolveEffectiveTokens(
  mode: BaseTokenMode | string,
  overrides: Record<string, string> | null | undefined,
): Record<string, string> {
  const base = baseTokensForMode(mode)
  const merged: Record<string, string> = { ...base }
  if (!overrides) return merged
  for (const [rawKey, value] of Object.entries(overrides)) {
    if (value === null || value === undefined) continue
    merged[normalizeTokenKey(rawKey)] = value
  }
  return merged
}

/**
 * Build an effective-tokens map directly from a BASE_TOKENS snapshot
 * without overrides. Convenience for tests + fallback paths.
 */
export function baseOnly(mode: BaseTokenMode): Record<string, string> {
  return { ...BASE_TOKENS[mode] }
}

export default resolveEffectiveTokens
