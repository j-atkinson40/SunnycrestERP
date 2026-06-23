/**
 * Maps of Content — deep-link helper.
 *
 * Maps a resolved MoC row ({builder, artifact_id, routing}) to the Studio
 * URL that opens THAT artifact in its builder, preselected. Returns a
 * studio-relative path (unwrapped, mirroring `studioPath`'s contract) —
 * the row renderer wraps it with `adminPath()` at the call site, per the
 * established `adminPath(studioPath(...))` idiom.
 *
 * The four wired builders' preselect contracts are read from their editor
 * pages (witnessed, not assumed):
 *   - workflows  → /studio/[vertical/]workflows?workflow_type=&scope=
 *                  (WorkflowEditorPage reads workflow_type + scope)
 *   - focuses    → /studio/[vertical/]focuses?tier=2&template=<id>
 *                  (FocusEditorPage: tier "2" = template; `template` = the
 *                   focus_template id, i.e. the row's artifact_id)
 *   - documents  → /studio/[vertical/]documents?template_id=<id>
 *                  (DocumentsEditorPage reads template_id; = artifact_id)
 *   - widgets    → /studio/widget-builder/<widget_id>
 *                  (WidgetBuilderPage uses a :slug route param = widget_id;
 *                   NOT the `widgets` list editor, NOT a query param)
 *
 * Returns null when the routing lacks the fields a given builder's URL
 * requires (e.g. an orphaned reference whose routing came back empty) —
 * the caller renders such a row as unavailable rather than linking.
 */

import { studioPath, type StudioEditorKey } from "@/bridgeable-admin/lib/studio-routes"

export type MoCBuilder = "workflows" | "focuses" | "widgets" | "documents"

/** The builder-specific routing fields the resolver hands back. */
export interface MoCRowRouting {
  // workflows
  workflow_type?: string | null
  scope?: string | null
  // shared (workflows / focuses / documents may carry a vertical)
  vertical?: string | null
  // focuses
  template_slug?: string | null
  // widgets
  widget_id?: string | null
  // documents
  template_key?: string | null
}

export interface MoCDeepLinkInput {
  builder: string
  artifact_id: string
  routing?: MoCRowRouting | null
}

const WIRED: ReadonlySet<string> = new Set<MoCBuilder>([
  "workflows",
  "focuses",
  "widgets",
  "documents",
])

export function isWiredBuilder(builder: string): builder is MoCBuilder {
  return WIRED.has(builder)
}

export function mocDeepLink(row: MoCDeepLinkInput): string | null {
  const routing = row.routing ?? {}
  const vertical = routing.vertical ?? null

  switch (row.builder) {
    case "workflows": {
      // workflow_type is the editor's required preselect key.
      if (!routing.workflow_type) return null
      return studioPath({
        vertical,
        editor: "workflows" as StudioEditorKey,
        query: {
          workflow_type: routing.workflow_type,
          scope: routing.scope ?? undefined,
        },
      })
    }
    case "focuses": {
      // tier "2" = template; `template` param is the focus_template id.
      if (!row.artifact_id) return null
      return studioPath({
        vertical,
        editor: "focuses" as StudioEditorKey,
        query: { tier: "2", template: row.artifact_id },
      })
    }
    case "documents": {
      if (!row.artifact_id) return null
      return studioPath({
        vertical,
        editor: "documents" as StudioEditorKey,
        query: { template_id: row.artifact_id },
      })
    }
    case "widgets": {
      // The per-artifact widget builder is a :slug ROUTE, not a query and
      // not the `widgets` list editor. slug = widget_id (NOT artifact_id,
      // which is the widget_definitions row id).
      if (!routing.widget_id) return null
      return `/studio/widget-builder/${encodeURIComponent(routing.widget_id)}`
    }
    default:
      return null
  }
}
