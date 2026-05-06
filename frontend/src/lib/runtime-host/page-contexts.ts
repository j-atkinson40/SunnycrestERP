/**
 * Phase R-1 — Page-context registry.
 *
 * Maps tenant-app route patterns to canonical page_context strings
 * the runtime editor uses to scope authoring (theme overrides apply
 * platform-wide; component / class overrides apply per-page-context;
 * dashboard layouts are keyed by page_context). Mirrors the
 * `WIDGET_DEFINITIONS.page_contexts` server-side registry.
 *
 * V1 covers the most-trafficked tenant routes. Unmapped routes fall
 * through to `unmapped:{path}` — theme + class edits still work
 * (they're page-context-agnostic) but per-component prop overrides
 * are scoped to a placeholder page_context that's harmless if saved.
 *
 * To extend: append entries to PAGE_CONTEXT_MAP. Order matters —
 * earlier entries match first. Dynamic segments use `:param` pattern
 * matching `path-to-regexp` shape.
 */


export interface PageContextEntry {
  /** Route pattern. Param tokens are `:name`. Wildcards `*` match
   *  the rest of the path. */
  pattern: string
  /** Canonical page_context the runtime editor scopes overrides to. */
  pageContext: string
  /** Human-readable label for inspector header / picker. */
  label: string
}


/** V1 page-context map — covers ~20 most-trafficked tenant routes
 *  for runtime editor authoring. Unmapped routes fall through to
 *  `unmapped:{path}` page_context. */
export const PAGE_CONTEXT_MAP: ReadonlyArray<PageContextEntry> = [
  { pattern: "/dashboard", pageContext: "dashboard", label: "Dashboard" },
  { pattern: "/home", pageContext: "home", label: "Home Pulse" },
  {
    pattern: "/funeral-home/dashboard",
    pageContext: "funeral_home_dashboard",
    label: "Funeral Home Dashboard",
  },
  {
    pattern: "/scheduling",
    pageContext: "funeral_scheduling_focus",
    label: "Funeral Scheduling Focus",
  },
  { pattern: "/cases", pageContext: "fh_case_list", label: "FH Case List" },
  {
    pattern: "/cases/:id",
    pageContext: "fh_case_detail",
    label: "FH Case Detail",
  },
  { pattern: "/triage", pageContext: "triage_index", label: "Triage Index" },
  {
    pattern: "/triage/:queueId",
    pageContext: "triage_queue",
    label: "Triage Queue",
  },
  { pattern: "/briefing", pageContext: "briefing", label: "Briefing" },
  { pattern: "/inbox", pageContext: "inbox", label: "Email Inbox" },
  {
    pattern: "/production",
    pageContext: "production_board",
    label: "Production Board",
  },
  { pattern: "/agents", pageContext: "agents_dashboard", label: "Agents" },
  {
    pattern: "/financials/board",
    pageContext: "financials_board",
    label: "Financials Board",
  },
  { pattern: "/calls", pageContext: "calls_log", label: "Call Log" },
  { pattern: "/safety", pageContext: "safety_dashboard", label: "Safety" },
  { pattern: "/vault", pageContext: "vault_overview", label: "Vault" },
  { pattern: "/saved-views", pageContext: "saved_views_index", label: "Saved Views" },
  { pattern: "/tasks", pageContext: "tasks_list", label: "Tasks" },
  { pattern: "/calendar", pageContext: "calendar", label: "Calendar" },
  { pattern: "/order-station", pageContext: "order_station", label: "Order Station" },
] as const


/** Resolve a pathname to its canonical page_context. Returns
 *  the `pageContext` string if mapped; else `unmapped:{path}`
 *  (still resolvable but signals R-1 doesn't cover this surface). */
export function resolvePageContext(pathname: string): {
  pageContext: string
  label: string
  mapped: boolean
} {
  for (const entry of PAGE_CONTEXT_MAP) {
    if (matchesPattern(entry.pattern, pathname)) {
      return {
        pageContext: entry.pageContext,
        label: entry.label,
        mapped: true,
      }
    }
  }
  return {
    pageContext: `unmapped:${pathname}`,
    label: pathname,
    mapped: false,
  }
}


/** Internal — matches a pathname against a pattern. Supports `:param`
 *  segments (any non-`/` value) and trailing `*` wildcard. */
export function matchesPattern(pattern: string, pathname: string): boolean {
  // Empty / root-only special case.
  if (pattern === "/" && pathname === "/") return true
  // Strip trailing slashes for normalization.
  const cleanPath = pathname.replace(/\/+$/, "")
  const cleanPattern = pattern.replace(/\/+$/, "")
  const pSegs = cleanPattern.split("/").filter(Boolean)
  const xSegs = cleanPath.split("/").filter(Boolean)
  // Wildcard support — `*` at end means "match any remaining path".
  const lastP = pSegs[pSegs.length - 1]
  if (lastP === "*") {
    if (xSegs.length < pSegs.length - 1) return false
    return pSegs.slice(0, -1).every((seg, i) => {
      if (seg.startsWith(":")) return xSegs[i] !== undefined
      return seg === xSegs[i]
    })
  }
  if (pSegs.length !== xSegs.length) return false
  return pSegs.every((seg, i) => {
    if (seg.startsWith(":")) return xSegs[i] !== undefined
    return seg === xSegs[i]
  })
}
