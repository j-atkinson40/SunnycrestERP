/**
 * Block renderer registry — Phase D-10 (June 2026).
 *
 * Each block kind has a frontend renderer that produces an
 * editor-quality preview (not pixel-perfect to the PDF output, but
 * representative). Variables resolve against sample_context from the
 * template version + the active sample data set.
 *
 * Renderers are intentionally simple — the admin's source of truth
 * for the rendered output is the backend Test Render endpoint
 * (full Jinja + WeasyPrint). These previews are for fast in-editor
 * iteration.
 */
import type { TemplateBlock } from "@/bridgeable-admin/services/document-blocks-service"


type SampleContext = Record<string, unknown>


function resolveVariable(expr: string, ctx: SampleContext): string {
  // Trivial substitution for `{{ var }}` and `{{ var.path }}` — no
  // control flow. Backend Test Render handles full fidelity.
  return expr.replace(/\{\{\s*([\w.]+)\s*\}\}/g, (_match, path) => {
    const parts = (path as string).split(".")
    let v: unknown = ctx
    for (const part of parts) {
      if (v && typeof v === "object" && part in (v as Record<string, unknown>)) {
        v = (v as Record<string, unknown>)[part]
      } else {
        return `[${path}]`
      }
    }
    return String(v ?? `[${path}]`)
  })
}


// ─── Header ───────────────────────────────────────────────────


export function HeaderBlockRenderer({
  block,
  context,
}: {
  block: TemplateBlock
  context: SampleContext
}) {
  const title = resolveVariable(
    String(block.config.title ?? "{{ document_title }}"),
    context,
  )
  const subtitle = resolveVariable(
    String(block.config.subtitle ?? ""),
    context,
  )
  const accent = String(block.config.accent_color ?? "#9C5640")
  const showLogo = block.config.show_logo !== false
  const showDate = block.config.show_date !== false
  const docDate = resolveVariable("{{ document_date }}", context)

  return (
    <header
      className="flex items-end justify-between border-b-2 px-4 py-3"
      style={{ borderColor: accent }}
      data-testid={`block-preview-header-${block.id}`}
    >
      <div className="flex items-center gap-3">
        {showLogo && (
          <div className="flex h-12 w-12 items-center justify-center rounded-sm bg-surface-sunken text-caption text-content-muted">
            logo
          </div>
        )}
        <div>
          <h1 className="text-h2 font-plex-serif text-content-strong">
            {title}
          </h1>
          {subtitle && (
            <p className="text-caption text-content-muted">{subtitle}</p>
          )}
        </div>
      </div>
      {showDate && (
        <div className="font-plex-mono text-caption text-content-muted">
          {docDate}
        </div>
      )}
    </header>
  )
}


// ─── Body Section ────────────────────────────────────────────


export function BodySectionBlockRenderer({
  block,
  context,
}: {
  block: TemplateBlock
  context: SampleContext
}) {
  const heading = String(block.config.heading ?? "")
  const body = resolveVariable(String(block.config.body ?? ""), context)
  const accent = String(block.config.accent_color ?? "")

  return (
    <section
      className="px-4 py-2"
      data-testid={`block-preview-body-section-${block.id}`}
    >
      {heading && (
        <h2
          className="mb-2 text-h4 font-plex-serif"
          style={{ color: accent || "var(--accent)" }}
        >
          {heading}
        </h2>
      )}
      <div
        className="text-body-sm text-content-base"
        // Body content can include simple HTML (rendered as-is in
        // editor preview; backend Jinja handles full rendering).
        dangerouslySetInnerHTML={{ __html: body }}
      />
    </section>
  )
}


// ─── Line Items ──────────────────────────────────────────────


export function LineItemsBlockRenderer({
  block,
  context,
}: {
  block: TemplateBlock
  context: SampleContext
}) {
  const itemsVar = String(block.config.items_variable ?? "items")
  const columns = (block.config.columns as Array<{
    header: string
    field: string
  }> | undefined) ?? [
    { header: "Description", field: "description" },
    { header: "Qty", field: "quantity" },
    { header: "Unit Price", field: "unit_price" },
    { header: "Total", field: "line_total" },
  ]
  const items = (context[itemsVar] as Array<Record<string, unknown>>) ?? []

  return (
    <div
      className="px-4 py-2"
      data-testid={`block-preview-line-items-${block.id}`}
    >
      <table className="w-full border-collapse text-caption">
        <thead>
          <tr className="border-b border-border-base bg-surface-sunken">
            {columns.map((c) => (
              <th key={c.field} className="px-2 py-1.5 text-left text-content-strong">
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-2 py-3 text-center font-plex-mono text-content-subtle"
              >
                {"{% for item in "}{itemsVar}{" %}"}
                <br />
                <span className="text-[10px]">
                  (no sample data for {itemsVar} — populate sample_context)
                </span>
              </td>
            </tr>
          ) : (
            items.map((item, i) => (
              <tr
                key={i}
                className="border-b border-border-subtle"
              >
                {columns.map((c) => (
                  <td key={c.field} className="px-2 py-1.5 text-content-base">
                    {String(item[c.field] ?? `[${c.field}]`)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}


// ─── Totals ──────────────────────────────────────────────────


export function TotalsBlockRenderer({
  block,
  context,
}: {
  block: TemplateBlock
  context: SampleContext
}) {
  const rows = (block.config.rows as Array<{
    label: string
    variable: string
    emphasis?: boolean
  }> | undefined) ?? [
    { label: "Subtotal", variable: "subtotal" },
    { label: "Tax", variable: "tax" },
    { label: "Total", variable: "total", emphasis: true },
  ]

  return (
    <div
      className="flex justify-end px-4 py-2"
      data-testid={`block-preview-totals-${block.id}`}
    >
      <table className="min-w-[240px] text-caption">
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={i}
              className={
                r.emphasis
                  ? "border-t-2 border-content-strong font-bold"
                  : ""
              }
            >
              <td className="px-2 py-1 text-content-base">{r.label}</td>
              <td className="px-2 py-1 text-right font-plex-mono text-content-strong">
                {String(context[r.variable] ?? `[${r.variable}]`)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}


// ─── Signature ───────────────────────────────────────────────


export function SignatureBlockRenderer({
  block,
}: {
  block: TemplateBlock
  context: SampleContext
}) {
  const parties = (block.config.parties as Array<{ role: string }> | undefined) ?? [
    { role: "Customer" },
  ]
  const showDates = block.config.show_dates !== false

  return (
    <section
      className="grid gap-6 px-4 py-4"
      style={{
        gridTemplateColumns: `repeat(${Math.min(parties.length, 3)}, minmax(0, 1fr))`,
      }}
      data-testid={`block-preview-signature-${block.id}`}
    >
      {parties.map((party, i) => (
        <div key={i} className="flex flex-col gap-2">
          <div className="text-micro uppercase tracking-wider text-content-muted">
            {party.role}
          </div>
          <div className="border-b border-content-strong font-plex-mono text-content-subtle">
            ___________________________
          </div>
          {showDates && (
            <div className="font-plex-mono text-caption text-content-muted">
              Date: ____________
            </div>
          )}
        </div>
      ))}
    </section>
  )
}


// ─── Conditional Wrapper ─────────────────────────────────────


export function ConditionalWrapperBlockRenderer({
  block,
  children,
}: {
  block: TemplateBlock
  context: SampleContext
  children?: React.ReactNode
}) {
  const condition = block.condition || "(no condition)"
  return (
    <div
      className="rounded-md border border-dashed border-status-info/40 bg-status-info-muted/30 px-3 py-2"
      data-testid={`block-preview-conditional-${block.id}`}
    >
      <div className="mb-2 flex items-center gap-1.5 text-caption text-status-info">
        <span className="font-plex-mono">{`{% if ${condition} %}`}</span>
      </div>
      <div className="space-y-2">{children}</div>
      <div className="mt-2 font-plex-mono text-caption text-status-info">
        {"{% endif %}"}
      </div>
    </div>
  )
}


// ─── Registry ────────────────────────────────────────────────


type BlockRenderer = React.ComponentType<{
  block: TemplateBlock
  context: SampleContext
  children?: React.ReactNode
}>


const RENDERERS: Record<string, BlockRenderer> = {
  header: HeaderBlockRenderer,
  body_section: BodySectionBlockRenderer,
  line_items: LineItemsBlockRenderer,
  totals: TotalsBlockRenderer,
  signature: SignatureBlockRenderer,
  conditional_wrapper: ConditionalWrapperBlockRenderer,
}


export function getBlockRenderer(kind: string): BlockRenderer | null {
  return RENDERERS[kind] ?? null
}


/** Fallback used when a block kind is not registered. */
export function UnknownBlockRenderer({ block }: { block: TemplateBlock }) {
  return (
    <div
      className="rounded-md border border-dashed border-status-warning/40 bg-status-warning-muted/40 px-3 py-2 text-caption"
      data-testid={`block-preview-unknown-${block.id}`}
    >
      <div className="font-medium text-status-warning">
        Unknown block kind: {block.block_kind}
      </div>
      <div className="text-content-muted">
        No renderer registered for this kind.
      </div>
    </div>
  )
}
