/** Opas's capability list — what she can do for this user, composed per area
 *  by the server.
 *
 *  ⚠️ DEFAULT IMPORT. `api-client` default-exports; `import { apiClient }`
 *  compiles to `undefined` at runtime. CLAUDE.md §11 records a mock that
 *  declared `{ apiClient }` against that module and made five tests pass
 *  against a member that does not exist.
 */
import apiClient from "@/lib/api-client"

export interface OpasCapability {
  /** The typed act. Stable: the client switches on it. */
  id: string
  label: string
  /** ⚠️ ABSENT when there is nothing to add — never `""`. The server omits the
   *  key, and "render only what exists" depends on that. */
  hint?: string
  area: string
  level: "view" | "change"
  /** What the user can type to reach this entry. Server-supplied, because the
   *  client must not hold a phrase for an entry it was not given. */
  phrases: string[]
  /** `focus:<id>`, `focus:<id>#upload`, or a route path. */
  target: string
}

export async function fetchCapabilities(): Promise<OpasCapability[] | null> {
  try {
    const r = await apiClient.get<{ capabilities: OpasCapability[] }>("/opas/capabilities")
    return r.data.capabilities
  } catch {
    /* ⚠️ `null` MEANS "COULD NOT READ", NOT "NOTHING TO OFFER". An empty array
       is a real answer — a user with nothing to do in Opas — and collapsing a
       failed read into it would make Opas silently claim she can do nothing.
       The same distinction `fetchCapturePreferences` draws, for the same
       reason: a plausible default hides the failure. */
    return null
  }
}

/** Resolve typed text against the entries THIS CALLER WAS GIVEN.
 *
 * ⚠️ **MIRRORS `services/opas/capabilities.py::match_phrase` AND IS HELD TO IT
 * BY A TEST.** Two implementations of one rule is a thing to keep in step, and
 * the alternative — a round trip per keystroke — is worse for a resolution that
 * is pure string work. `opas-capability-match.test.ts` reads the Python file
 * and asserts the two agree on the same inputs, so a change to either side
 * that is not made to both goes red.
 *
 * Exact normalised match first, then whole-phrase containment: "dues report"
 * must reach the reports entry and not the week, whose phrases include "dues".
 */
export function matchCapability(
  text: string,
  entries: OpasCapability[],
): OpasCapability | null {
  const norm = (text ?? "").trim().toLowerCase().replace(/’/g, "'").split(/\s+/).join(" ")
  if (!norm) return null
  for (const e of entries) if (e.phrases.includes(norm)) return e
  for (const e of entries) for (const p of e.phrases) if (norm.includes(p)) return e
  return null
}

/** Where an entry's `target` sends the browser.
 *
 * ⚠️ A `focus:` TARGET BECOMES A QUERY PARAM ON `/home`, NOT A PATH. Focuses
 * are opened by `?focus=<id>` on the note — `/focus/weekly-payroll` is not a
 * route and would land on the not-found page, which is the defect shape that
 * cost four and a half months on `/dispatch` (CLAUDE.md §11, shape 9).
 */
export function hrefForTarget(target: string): string {
  if (!target.startsWith("focus:")) return target
  const [beforeHash, hash] = target.slice("focus:".length).split("#")
  const [id, query] = beforeHash.split("?")
  /* ⚠️ THE SCOPE IS PART OF THE TARGET, AND AN UNSCOPED ONE OPENS NOTHING.
     Found in the PR C walk-through: `/home?focus=weekly-payroll` with no
     `week_end` rendered the note and no Focus — a URL that claimed a surface
     that was not there. The server fills `{week_end}` with the week being
     processed, and this carries it through rather than dropping it. */
  const parts = [`focus=${encodeURIComponent(id)}`]
  if (query) parts.push(query)
  if (hash) parts.push(`step=${encodeURIComponent(hash)}`)
  return `/home?${parts.join("&")}`
}
