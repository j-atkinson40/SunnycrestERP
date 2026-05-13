/**
 * Studio routing — URL scheme + redirect translation helpers.
 *
 * Studio shell substrate (Studio 1a-i.A1). Path-segment-canonical:
 *
 *   /studio                               → Platform-scope overview
 *   /studio/:vertical                     → Vertical-scope overview
 *   /studio/:editor                       → Platform-scope, specific editor
 *   /studio/:vertical/:editor             → Vertical-scope, specific editor
 *   /studio/live                          → Live mode (placeholder in A1)
 *   /studio/live/:vertical                → Live mode pre-filtered (A2)
 *
 * First path segment after `/studio/` is disambiguated against the
 * `RESERVED_FIRST_SEGMENTS` set:
 *   - `live` reserved for Live mode (1a-i.A2)
 *   - `admin` reserved for future Studio admin sub-pages
 *   - Editor keys (themes, focuses, ...) → Platform scope, that editor
 *   - Anything else → vertical slug (if not a known editor key)
 *
 * Per the 2026-05-13 investigation §1, the four canonical vertical
 * slugs (`manufacturing`, `funeral_home`, `cemetery`, `crematory`)
 * are already non-colliding with the editor + reserved keys. The
 * `assertSafeVerticalSlug` helper is forward-defense for any future
 * vertical slug authoring path.
 */


/** Canonical Studio editor keys. Order is the display order in the rail. */
export const STUDIO_EDITOR_KEYS = [
  "themes",
  "focuses",
  "widgets",
  "documents",
  "classes",
  "workflows",
  "edge-panels",
  "registry",
  "plugin-registry",
] as const

export type StudioEditorKey = (typeof STUDIO_EDITOR_KEYS)[number]

/** Reserved first-position path segments (NOT vertical slugs). */
export const RESERVED_FIRST_SEGMENTS = new Set<string>([
  ...STUDIO_EDITOR_KEYS,
  "live",
  "admin",
])

/** Editors that are platform-only (no vertical scope). */
export const PLATFORM_ONLY_EDITORS = new Set<StudioEditorKey>([
  "classes",
  "registry",
  "plugin-registry",
])


export function isStudioEditorKey(value: string): value is StudioEditorKey {
  return (STUDIO_EDITOR_KEYS as readonly string[]).includes(value)
}


/**
 * Forward-defense for new vertical slugs. Rejects slugs that collide
 * with reserved first-position segments. The current 4 canonical
 * slugs already pass; this guards future additions (e.g. wastewater,
 * paving, vet).
 */
export function assertSafeVerticalSlug(slug: string): void {
  if (RESERVED_FIRST_SEGMENTS.has(slug)) {
    throw new Error(
      `Invalid vertical slug "${slug}" — collides with reserved Studio path segment.`,
    )
  }
}


export function isReservedSlug(slug: string): boolean {
  return RESERVED_FIRST_SEGMENTS.has(slug)
}


export interface StudioPathArgs {
  /** null | undefined → Platform scope. */
  vertical?: string | null
  editor?: StudioEditorKey | null
  /** Optional query params appended unchanged. */
  query?: Record<string, string | undefined | null>
}


/**
 * Build a Studio URL pathname (plus optional query string).
 *
 *   studioPath({})                                  → "/studio"
 *   studioPath({ vertical: "manufacturing" })       → "/studio/manufacturing"
 *   studioPath({ editor: "themes" })                → "/studio/themes"
 *   studioPath({ vertical: "manufacturing", editor: "focuses" })
 *                                                   → "/studio/manufacturing/focuses"
 *   studioPath({ editor: "focuses", query: { template: "X" } })
 *                                                   → "/studio/focuses?template=X"
 *
 * Platform-only editors (classes/registry/plugin-registry) drop any
 * supplied vertical at construction time per investigation §1.
 */
export function studioPath(args: StudioPathArgs): string {
  const parts: string[] = ["studio"]
  const editor = args.editor ?? null
  const isPlatformOnly = editor !== null && PLATFORM_ONLY_EDITORS.has(editor)
  const vertical = isPlatformOnly ? null : args.vertical ?? null

  if (vertical) {
    parts.push(vertical)
  }
  if (editor) {
    parts.push(editor)
  }

  const pathname = `/${parts.join("/")}`
  const query = buildQueryString(args.query)
  return query ? `${pathname}?${query}` : pathname
}


export function studioLivePath(args: {
  vertical?: string | null
  query?: Record<string, string | undefined | null>
} = {}): string {
  const parts: string[] = ["studio", "live"]
  if (args.vertical) parts.push(args.vertical)
  const pathname = `/${parts.join("/")}`
  const query = buildQueryString(args.query)
  return query ? `${pathname}?${query}` : pathname
}


function buildQueryString(
  q: Record<string, string | undefined | null> | undefined,
): string {
  if (!q) return ""
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(q)) {
    if (value === undefined || value === null || value === "") continue
    params.set(key, value)
  }
  const s = params.toString()
  return s
}


/**
 * Translation table for the 10 standalone visual-editor routes →
 * Studio deep links. Path-only mapping; query strings preserved by
 * the caller (React-router `<Navigate>` automatically carries them
 * across because we use `to={fullPathWithSearch}`).
 *
 * Note: focuses + runtime-editor have richer query-param translation
 * (focus_type → category, template_id → template) handled in
 * `redirectFromStandalone()` rather than here.
 */
export const STANDALONE_TO_STUDIO_PATH: Record<string, string> = {
  "/visual-editor": "/studio",
  "/visual-editor/themes": "/studio/themes",
  "/visual-editor/focuses": "/studio/focuses",
  "/visual-editor/widgets": "/studio/widgets",
  "/visual-editor/documents": "/studio/documents",
  "/visual-editor/classes": "/studio/classes",
  "/visual-editor/workflows": "/studio/workflows",
  "/visual-editor/edge-panels": "/studio/edge-panels",
  "/visual-editor/registry": "/studio/registry",
  "/visual-editor/plugin-registry": "/studio/plugin-registry",
  "/runtime-editor": "/studio/live",
}


/**
 * Translate a standalone visual-editor URL (pathname + search) into a
 * Studio URL. Applies per-editor query-param translation. Used by the
 * redirect routes and by tests.
 *
 * Behavior:
 *   - `/visual-editor/focuses?focus_type=X&template_id=Y`
 *       → `/studio/focuses?category=X&template=Y`
 *   - `/visual-editor/documents?template_id=Y`
 *       → `/studio/documents?template=Y`
 *   - All others preserve query string unchanged.
 *
 * `lastVertical` (if supplied + path supports vertical scope) is
 * inserted as the path segment; otherwise URL stays at Platform scope.
 */
export function redirectFromStandalone(
  pathname: string,
  search: string,
  options: { lastVertical?: string | null } = {},
): string {
  // Tolerate the `/bridgeable-admin` prefix so the admin tree mount
  // path is preserved end-to-end (caller decides whether to re-prefix).
  const adminPrefix = pathname.startsWith("/bridgeable-admin")
    ? "/bridgeable-admin"
    : ""
  const pathSansAdmin = adminPrefix
    ? pathname.slice(adminPrefix.length) || "/"
    : pathname
  const cleanPath = pathSansAdmin.replace(/\/+$/, "") || "/"

  // Studio 1a-i.B follow-up #3 — deep-path runtime-editor preservation.
  // `/runtime-editor/<tail>` translates to `/studio/live/<tail>` with
  // NO vertical inserted. The TenantUserPicker resolves the vertical
  // post-impersonation and replays the URL with vertical spliced in
  // (pickup-and-replay). Bare `/runtime-editor` + `/runtime-editor/`
  // continue to map via STANDALONE_TO_STUDIO_PATH → `/studio/live`.
  if (
    cleanPath !== "/runtime-editor" &&
    cleanPath.startsWith("/runtime-editor/")
  ) {
    const tail = cleanPath.slice("/runtime-editor/".length).replace(/^\/+/, "")
    const params = new URLSearchParams(search)
    const finalSearch = params.toString()
    const target = tail
      ? `${adminPrefix}/studio/live/${tail}`
      : `${adminPrefix}/studio/live`
    return finalSearch ? `${target}?${finalSearch}` : target
  }

  const targetBase = STANDALONE_TO_STUDIO_PATH[cleanPath] ?? "/studio"

  // Decide whether to splice a vertical segment in. Platform-only
  // editors stay Platform-scope. The bare /visual-editor index goes
  // to /studio (Platform overview) — investigation §1.
  let targetPath = targetBase
  const editorMatch = targetBase.match(/^\/studio\/([^/]+)$/)
  if (
    options.lastVertical &&
    editorMatch &&
    isStudioEditorKey(editorMatch[1] as string) &&
    !PLATFORM_ONLY_EDITORS.has(editorMatch[1] as StudioEditorKey)
  ) {
    targetPath = `/studio/${options.lastVertical}/${editorMatch[1]}`
  }

  // Translate query params per-editor.
  const params = new URLSearchParams(search)
  if (cleanPath === "/visual-editor/focuses") {
    const focusType = params.get("focus_type")
    const templateId = params.get("template_id")
    params.delete("focus_type")
    params.delete("template_id")
    if (focusType) params.set("category", focusType)
    if (templateId) params.set("template", templateId)
  } else if (cleanPath === "/visual-editor/documents") {
    const templateId = params.get("template_id")
    params.delete("template_id")
    if (templateId) params.set("template", templateId)
  }

  const finalSearch = params.toString()
  return finalSearch ? `${targetPath}?${finalSearch}` : targetPath
}


/* ---------- localStorage helpers (rail expand + last vertical) ---------- */

export const STUDIO_RAIL_EXPANDED_KEY = "studio.railExpanded"
export const STUDIO_LAST_VERTICAL_KEY = "studio.lastVertical"


export function readRailExpanded(defaultValue = true): boolean {
  if (typeof window === "undefined") return defaultValue
  try {
    const raw = window.localStorage.getItem(STUDIO_RAIL_EXPANDED_KEY)
    if (raw === null) return defaultValue
    return raw === "true"
  } catch {
    return defaultValue
  }
}


/**
 * Studio 1a-i.B follow-up — pathname-classifies whether the current URL
 * is an "overview" surface (rail-defaults-expanded) vs. an editor / Live
 * surface (rail-defaults-collapsed).
 *
 * Overview routes:
 *   /studio                       → Platform overview
 *   /studio/:vertical             → Vertical overview (where :vertical is
 *                                   NOT a reserved editor key or `live`)
 *
 * Non-overview (editor or Live):
 *   /studio/:editor               → Platform-scope editor
 *   /studio/:vertical/:editor     → Vertical-scope editor
 *   /studio/live[/:vertical]      → Live mode
 *   /studio/admin/...             → Reserved future area (treated as non-overview)
 *
 * Non-Studio routes return `false` — the rail-expanded route default is
 * Studio-only so non-Studio surfaces don't get an unintended override.
 *
 * Tolerates `/bridgeable-admin` prefix per existing helper conventions.
 */
export function isOverviewRoute(pathname: string): boolean {
  const cleanPath = pathname.replace(/^\/bridgeable-admin/, "")
  const stripped = cleanPath.replace(/^\/+/, "").replace(/\/+$/, "")
  const parts = stripped.split("/").filter(Boolean)
  if (parts[0] !== "studio") return false
  const parsed = parseStudioPath(cleanPath)
  if (parsed.isLive) return false
  if (parsed.editor !== null) return false
  // `/studio/admin` parses to Platform overview today but is reserved
  // for a future admin sub-area; treat as non-overview so when admin
  // sub-pages land the rail-default doesn't have to be revisited.
  if (parts[1] === "admin") return false
  return true
}


/**
 * Studio 1a-i.B follow-up — computes the rail's initial-expanded value
 * for a given pathname when localStorage has no opinion.
 *
 * Overview routes (Platform overview / vertical overview) default to
 * EXPANDED so first-time operators see the section list immediately.
 * Editor + Live routes default to COLLAPSED so the editor content gets
 * the full canvas instead of the rail covering it.
 *
 * Once the operator clicks the rail toggle the choice persists to
 * localStorage; `readRailExpanded()` returns the persisted value and
 * this function's route-default is bypassed. Route-default is only the
 * initial-mount value on a clean localStorage.
 */
export function computeInitialRailExpanded(pathname: string): boolean {
  return isOverviewRoute(pathname)
}


export function writeRailExpanded(expanded: boolean): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(STUDIO_RAIL_EXPANDED_KEY, String(expanded))
  } catch {
    // Ignore — localStorage write failure is non-critical UI state.
  }
}


export function readLastVertical(): string | null {
  if (typeof window === "undefined") return null
  try {
    const raw = window.localStorage.getItem(STUDIO_LAST_VERTICAL_KEY)
    return raw && raw.length > 0 ? raw : null
  } catch {
    return null
  }
}


export function writeLastVertical(slug: string | null): void {
  if (typeof window === "undefined") return
  try {
    if (slug) {
      window.localStorage.setItem(STUDIO_LAST_VERTICAL_KEY, slug)
    } else {
      window.localStorage.removeItem(STUDIO_LAST_VERTICAL_KEY)
    }
  } catch {
    // Ignore.
  }
}


/* ---------- Mode toggle (Edit ↔ Live) ---------- */

/**
 * Translate a current Studio URL into the target URL for the opposite
 * mode. Studio 1a-i.A2.
 *
 * Edit → Live: preserve scope (vertical or Platform); drop editor key
 *   since Live mode has no editor concept. Tenant impersonation params
 *   are not relevant in Edit mode (the operator picks tenant inside
 *   Live mode) so they're not added.
 *
 * Live → Edit: preserve scope (vertical or Platform); drop tenant +
 *   user impersonation params. Editor key is not in the source URL
 *   (Live mode has no editor), so the result lands at the scope
 *   overview.
 *
 * 5 canonical translation rules per investigation §4:
 *   /studio/themes              → /studio/live
 *   /studio/wastewater/themes   → /studio/live/wastewater
 *   /studio/live/wastewater?... → /studio/wastewater       (drop ?tenant&user)
 *   /studio/live                → /studio
 *   /studio/live/wastewater     → /studio/wastewater
 *
 * Edge: live → edit from `/studio/live` lands at `/studio`, NOT
 * `/studio/` (no trailing slash).
 */
export function toggleMode(pathname: string, _search: string): string {
  const cleanPath = pathname.replace(/^\/bridgeable-admin/, "")
  const parsed = parseStudioPath(cleanPath)
  if (parsed.isLive) {
    // Live → Edit. Preserve vertical scope; drop tenant + user.
    return studioPath({ vertical: parsed.vertical, editor: null })
  }
  // Edit → Live. Preserve vertical scope; drop editor.
  return studioLivePath({ vertical: parsed.vertical })
}


/* ---------- Studio Live deep-tail extraction (Studio 1a-i.B follow-up #3) ---------- */

/**
 * Pull the tenant-route deep tail out of a Studio Live URL pathname,
 * given a known resolved vertical (or null for the pre-resolution case).
 *
 * Used by TenantUserPicker after impersonation resolves the operator's
 * vertical: the picker preserves any deep tenant-route tail from the
 * source URL and replays it under the canonical
 *   /studio/live/<resolved-vertical>/<tail>
 * URL shape.
 *
 * The known-vertical parameter is what disambiguates the two ambiguous
 * URL shapes the router can't distinguish on its own:
 *
 *   pathname = "/studio/live/dispatch/funeral-schedule" (no resolved vertical)
 *     resolvedVertical=null      → tail = "dispatch/funeral-schedule"
 *     resolvedVertical="dispatch" → tail = "funeral-schedule" (vertical assumed
 *                                   to be present; first segment is vertical)
 *
 *   pathname = "/studio/live/manufacturing/dispatch/funeral-schedule"
 *     resolvedVertical="manufacturing" → tail = "dispatch/funeral-schedule"
 *     resolvedVertical=null            → tail = "manufacturing/dispatch/funeral-schedule"
 *
 * Picker contract: pre-impersonation, the source URL never has a
 * resolved vertical (the operator hasn't picked a tenant yet), so the
 * picker calls this with `resolvedVertical=null` to capture the full
 * post-`live` segments as the tail.
 *
 *   "/studio/live"                                            → ""
 *   "/studio/live/manufacturing"                              → "manufacturing"
 *   "/studio/live/manufacturing/dispatch/funeral-schedule"    → "manufacturing/dispatch/funeral-schedule"
 *   "/studio/live/dispatch/funeral-schedule"                  → "dispatch/funeral-schedule"
 *   "/bridgeable-admin/studio/live/dispatch/funeral-schedule" → "dispatch/funeral-schedule"
 *
 * Returns the empty string when no tail exists.
 */
export function extractStudioLiveDeepTail(
  pathname: string,
  resolvedVertical: string | null = null,
): string {
  const cleanPath = pathname.replace(/^\/bridgeable-admin/, "")
  const stripped = cleanPath.replace(/^\/+/, "").replace(/\/+$/, "")
  const parts = stripped.split("/").filter(Boolean)

  // Must be /studio/live[/...]
  if (parts[0] !== "studio" || parts[1] !== "live") return ""

  const afterLive = parts.slice(2)
  if (afterLive.length === 0) return ""

  // If a resolved vertical is supplied AND it matches the first
  // post-`live` segment, treat that segment as the vertical and the
  // remainder as the tail.
  if (resolvedVertical && afterLive[0] === resolvedVertical) {
    return afterLive.slice(1).join("/")
  }

  // Otherwise (no resolved vertical OR first segment doesn't match):
  // the full post-`live` content is the tail. The picker uses this
  // shape pre-impersonation.
  return afterLive.join("/")
}


/* ---------- URL parsing (for shell mount-time scope detection) ---------- */

export interface StudioRouteParsed {
  /** When true, the URL is Live mode (`/studio/live[/...]`). */
  isLive: boolean
  /** Vertical slug if URL carries one; null = Platform scope. */
  vertical: string | null
  /** Editor key if URL carries one; null = overview. */
  editor: StudioEditorKey | null
  /**
   * True iff the URL was malformed (first segment looked like a
   * vertical slug but the second segment, if present, wasn't a known
   * editor key). Caller can choose to redirect.
   */
  malformed: boolean
}


/**
 * Parse a `/studio/...` pathname (NOT including search). Returns a
 * normalized view of {scope, editor, isLive}. Used by the Studio shell
 * to decide which child page to render.
 */
export function parseStudioPath(pathname: string): StudioRouteParsed {
  const stripped = pathname.replace(/^\/+/, "").replace(/\/+$/, "")
  const parts = stripped.split("/").filter(Boolean)
  // parts[0] === "studio" by routing precondition; tolerate missing.
  const tail = parts[0] === "studio" ? parts.slice(1) : parts

  if (tail.length === 0) {
    return { isLive: false, vertical: null, editor: null, malformed: false }
  }

  const first = tail[0]

  if (first === "live") {
    return {
      isLive: true,
      vertical: tail[1] && !isReservedSlug(tail[1]) ? tail[1] : null,
      editor: null,
      malformed: false,
    }
  }

  if (first === "admin") {
    // Reserved for future use; treated as Platform overview for A1.
    return { isLive: false, vertical: null, editor: null, malformed: false }
  }

  if (isStudioEditorKey(first)) {
    return {
      isLive: false,
      vertical: null,
      editor: first,
      malformed: false,
    }
  }

  // First segment is a candidate vertical slug.
  if (tail.length === 1) {
    return {
      isLive: false,
      vertical: first,
      editor: null,
      malformed: false,
    }
  }
  const second = tail[1]
  if (isStudioEditorKey(second)) {
    return {
      isLive: false,
      vertical: first,
      editor: second,
      malformed: false,
    }
  }

  return {
    isLive: false,
    vertical: first,
    editor: null,
    malformed: true,
  }
}
