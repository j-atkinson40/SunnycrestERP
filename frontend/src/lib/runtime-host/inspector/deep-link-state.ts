/**
 * deep-link-state.ts — Shared deep-link URL state utility for inspector
 * tabs (Workflows, Documents, Focus compositions).
 *
 * Established by Arc 3a (commit f0c8daf) inline inside
 * `FocusCompositionsTab.tsx`; extracted here by Arc-3.x-deep-link-retrofit
 * so all three tabs use ONE encoder/decoder. Per Arc 3a
 * deep-link-as-navigation-primitive canon:
 *
 *   - Inspector deep-link encodes `return_to` carrying the originating
 *     pathname + search. The standalone editor reads `return_to` and
 *     renders a "Back to runtime editor" affordance.
 *   - State preservation mechanism: deep-link uses `target="_blank"`
 *     so the runtime editor route stays mounted in the originating
 *     tab. Inspector state is preserved via React state, NOT via URL
 *     state restoration on return. Decoding `return_to` and navigating
 *     just returns to the originating URL (where the inspector still
 *     has its state).
 *
 * The 3 tabs differ in WHICH extra URL params they carry alongside
 * `return_to`:
 *   - Focus compositions: focus_type, composition_id
 *   - Workflows: workflow_type, scope
 *   - Documents: template_id, scope, document_type
 *
 * Each tab calls `buildEditorDeepLink(basePath, extraParams)` with its
 * own param shape; the helper handles `return_to` derivation +
 * URLSearchParams composition uniformly.
 */


/** Snapshot the originating URL (pathname + search) for the
 *  `return_to` URL param. Returns "/" in non-browser environments
 *  (SSR / vitest jsdom without a real location). */
export function deriveReturnToFromWindow(): string {
  if (typeof window === "undefined") return "/"
  return window.location.pathname + window.location.search
}


/** Build a standalone-editor deep-link URL. `basePath` is the editor
 *  route (e.g. `adminPath("/visual-editor/workflows")`). `extraParams`
 *  is the per-tab payload (focus_type / workflow_type / template_id /
 *  scope / etc). `returnTo` defaults to the current window URL. */
export function buildEditorDeepLink(
  basePath: string,
  extraParams: Record<string, string | null | undefined> = {},
  returnTo: string = deriveReturnToFromWindow(),
): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(extraParams)) {
    if (value === null || value === undefined || value === "") continue
    params.set(key, value)
  }
  params.set("return_to", returnTo)
  return `${basePath}?${params.toString()}`
}


/** Decode a `return_to` URL param value safely. Falls back to the
 *  raw value if decodeURIComponent throws (malformed escape). */
export function decodeReturnTo(raw: string): string {
  try {
    return decodeURIComponent(raw)
  } catch {
    return raw
  }
}
