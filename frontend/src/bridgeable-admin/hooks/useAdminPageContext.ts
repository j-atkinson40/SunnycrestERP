/**
 * useAdminPageContext — the authoring assistant's route-derived page context
 * (Authoring Assistant Shell-1).
 *
 * The omnipresent bar must know what page it's on so it can route a draft
 * request (Shell-2) and behave context-appropriately. The shell investigation
 * established this is fully derivable from existing route state — no provider to
 * build: Studio via `parseStudioPath`, MoC via the `/maps/:vertical` segment,
 * everything else operational. `derive()` is exported pure for unit testing.
 */
import { useMemo } from "react"
import { useLocation } from "react-router-dom"

import { parseStudioPath } from "../lib/studio-routes"

export type AdminSurface =
  | "moc"
  | "studio"
  | "visual-editor"
  | "operational"
  | "none" // login / unauthenticated — the bar hides

export interface AdminPageContext {
  surface: AdminSurface
  /** The vertical in scope (manufacturing, funeral_home, …), if any. */
  vertical: string | null
  /** The Studio/visual-editor editor in scope (workflows, focuses, …), if any. */
  editorKind: string | null
  /** Whether this surface can host artifact authoring. Shell-2 routes on this;
   *  Shell-1 uses it for the context-appropriate "armed vs generic" state. */
  canAuthor: boolean
  /** Human-readable label for the bar's page-context indicator. */
  label: string
}

const STUDIO_EDITOR_LABELS: Record<string, string> = {
  themes: "themes",
  focuses: "focus editor",
  widgets: "widget builder",
  documents: "document composer",
  classes: "component classes",
  workflows: "workflow editor",
  registry: "registry",
}

/** Pure derivation (exported for tests). `pathname` is the full router path. */
export function derive(pathname: string): AdminPageContext {
  const clean = pathname.replace(/^\/bridgeable-admin/, "") || "/"

  // Login / unauthenticated → no authoring context (the bar hides).
  if (clean === "/login" || clean.startsWith("/login")) {
    return { surface: "none", vertical: null, editorKind: null, canAuthor: false, label: "" }
  }

  // Studio (/studio, /studio/:vertical/:editor, /studio/live/…).
  if (clean === "/studio" || clean.startsWith("/studio/")) {
    const { vertical, editor, isLive } = parseStudioPath(clean)
    if (isLive) {
      return {
        surface: "studio", vertical: vertical ?? null, editorKind: null,
        canAuthor: false,
        label: vertical ? `Studio · live (${vertical})` : "Studio · live",
      }
    }
    const editorKind = editor ?? null
    const editorLabel = editorKind
      ? STUDIO_EDITOR_LABELS[editorKind] ?? editorKind
      : null
    const scope = [vertical, editorLabel].filter(Boolean).join(" · ")
    return {
      surface: "studio", vertical: vertical ?? null, editorKind,
      // Authoring is armed when a concrete editor is open.
      canAuthor: !!editorKind,
      label: scope ? `Studio · ${scope}` : "Studio",
    }
  }

  // Legacy visual-editor (/visual-editor/:editor) — redirects to Studio, but
  // tolerate it so the bar reads correctly mid-redirect.
  if (clean === "/visual-editor" || clean.startsWith("/visual-editor/")) {
    const editorKind = clean.split("/").filter(Boolean)[1] ?? null
    return {
      surface: "visual-editor", vertical: null, editorKind,
      canAuthor: !!editorKind,
      label: editorKind ? `Visual editor · ${editorKind}` : "Visual editor",
    }
  }

  // MoC TENANT page (/maps/:vertical/:tenantSlug) — H-3: the tenant level.
  const mocTenant = clean.match(/^\/maps\/([^/]+)\/([^/]+)/)
  if (mocTenant) {
    return {
      surface: "moc", vertical: mocTenant[1], editorKind: null,
      canAuthor: true, label: `${mocTenant[1]} › ${mocTenant[2]} · MoC`,
    }
  }
  // MoC vertical page (/maps/:vertical).
  const moc = clean.match(/^\/maps\/([^/]+)/)
  if (moc) {
    return {
      surface: "moc", vertical: moc[1], editorKind: null,
      canAuthor: true, label: `${moc[1]} · MoC`,
    }
  }
  // The PLATFORM MoC (admin root — the hierarchy's top, H-2).
  if (clean === "/") {
    return { surface: "moc", vertical: null, editorKind: null, canAuthor: false, label: "Platform · MoC" }
  }

  // Operational admin (health, tenants, migrations, telemetry, …).
  return { surface: "operational", vertical: null, editorKind: null, canAuthor: false, label: "Operational" }
}

export function useAdminPageContext(): AdminPageContext {
  const { pathname } = useLocation()
  return useMemo(() => derive(pathname), [pathname])
}
