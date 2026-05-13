/**
 * StudioLivePlaceholderPage — placeholder for Live mode.
 *
 * Live mode wrap (RuntimeEditorShell mount + impersonation handshake +
 * chrome conflict resolution) ships in Studio 1a-i.A2. In A1 the route
 * is registered so URL paths + mode toggle work; the page itself shows
 * an explanatory panel + a link to the still-working standalone
 * `/runtime-editor`.
 */
import { Link } from "react-router-dom"
import { Eye, ExternalLink } from "lucide-react"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"


export default function StudioLivePlaceholderPage() {
  return (
    <div
      className="mx-auto flex max-w-[760px] flex-col gap-4 px-6 py-12"
      data-testid="studio-live-placeholder"
    >
      <div className="flex items-center gap-2 text-caption uppercase tracking-wide text-content-subtle">
        <Eye size={12} />
        Live mode
      </div>
      <h1 className="text-h2 font-plex-serif font-medium text-content-strong">
        Coming next sub-arc
      </h1>
      <p className="text-body text-content-muted">
        Live mode lets you author against a specific tenant's live
        pages — click a widget, edit its theme tokens or per-component
        prop overrides, and see changes immediately. This wraps the
        existing runtime editor inside the Studio shell so scope, mode
        toggle, and rail behave consistently.
      </p>
      <p className="text-body text-content-muted">
        Live mode wrap ships in Studio 1a-i.A2 — the next sub-arc.
        Until then, the standalone runtime editor is still operational
        at <code className="rounded-sm bg-surface-sunken px-1.5 py-0.5 font-plex-mono text-caption">/runtime-editor</code>.
      </p>
      <div className="mt-2">
        <Link
          to={adminPath("/runtime-editor")}
          className="inline-flex items-center gap-1.5 rounded-sm border border-border-subtle bg-surface-elevated px-3 py-1.5 text-body-sm text-content-strong hover:border-accent"
          data-testid="studio-live-placeholder-runtime-editor-link"
        >
          <ExternalLink size={14} />
          Open standalone runtime editor
        </Link>
      </div>
    </div>
  )
}
