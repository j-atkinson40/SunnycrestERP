/**
 * DocumentsEditorPage — placeholder for the Phase 2 Documents Editor.
 *
 * Reservation page only. The route exists in navigation so the
 * top-level structure of the visual editor is established; the
 * actual authoring capability ships in the next phase.
 *
 * Will be backed by the existing Documents arc substrate:
 *   • Phase D-1 → D-9 (migrations r20 through r28)
 *   • DocumentTemplate + DocumentTemplateVersion registry
 *   • document_renderer (Jinja + WeasyPrint)
 *   • Active prompts in CLAUDE.md §4 "Document Service R2 Migration"
 *     and §14 entries D-1 through D-9.
 */
import { FileText, Sparkles } from "lucide-react"


export default function DocumentsEditorPage() {
  return (
    <div
      className="mx-auto max-w-[820px] px-6 py-12"
      data-testid="documents-editor-placeholder"
    >
      <div className="flex items-start gap-4">
        <div className="rounded-md border border-border-subtle bg-surface-elevated p-3 shadow-level-1">
          <FileText size={28} className="text-accent" />
        </div>
        <div className="flex-1">
          <div className="mb-3 flex items-center gap-2">
            <h1 className="text-h1 font-plex-serif font-medium text-content-strong">
              Documents Editor
            </h1>
            <span
              className="inline-flex items-center gap-1 rounded-sm bg-status-info-muted px-2 py-0.5 text-caption text-status-info"
              data-testid="documents-coming-in-phase-2"
            >
              <Sparkles size={10} />
              Coming in Phase 2
            </span>
          </div>
          <p className="text-body text-content-base">
            Document authoring shipping in the next phase. Will support
            full document template creation and editing — price lists,
            invoices, BOLs, certificates, arrangement summaries, service
            programs, and any document type.
          </p>
          <div className="mt-6 rounded-md border border-border-subtle bg-surface-elevated p-5">
            <h2 className="mb-2 text-h4 font-plex-serif text-content-strong">
              Capabilities planned
            </h2>
            <ul className="ml-4 list-disc space-y-1.5 text-body-sm text-content-base marker:text-content-subtle">
              <li>Template creation from scratch (no clone-an-existing dependency)</li>
              <li>Block library — header, body sections, signature blocks, attachments, table layouts</li>
              <li>Variable binding — entity-aware tokens that resolve at render time</li>
              <li>Conditional sections — render-or-skip per template variable</li>
              <li>Vertical-default templates — manufacturing, funeral_home, cemetery, crematory variants</li>
              <li>Live preview against sample data — verify before committing</li>
              <li>
                Template fork mechanic — tenants fork platform/vertical defaults
                into independent tenant copies, parallel to the workflow editor
                fork pattern
              </li>
            </ul>
          </div>
          <div className="mt-4 rounded-md border border-border-subtle bg-surface-sunken p-4">
            <h3 className="mb-1 text-caption font-medium uppercase tracking-wider text-content-muted">
              Built on
            </h3>
            <p className="text-body-sm text-content-base">
              The existing Documents arc substrate (Phase D-1 through D-9,
              migrations r20 through r28). Same{" "}
              <code className="rounded bg-surface-elevated px-1 py-0.5 font-plex-mono text-caption">
                DocumentTemplate
              </code>{" "}
              +{" "}
              <code className="rounded bg-surface-elevated px-1 py-0.5 font-plex-mono text-caption">
                DocumentTemplateVersion
              </code>{" "}
              registry the platform's invoices, statements, and
              certificates render through today.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
