/**
 * QuoteFocusWithAccessories — S-3a display core for the quote Focus.
 *
 * The Act→Decide crossing made concrete. When the user escalates a
 * quote from the command bar ("Build this out →"), the bar CLOSES
 * (§5.15 mutual-exclusivity) and this Focus opens, re-hosting the SAME
 * S-2 surfaces — `surface.quote-preview` as the anchored display CORE
 * and `surface.price-list-reference` as a live-config accessory PIN —
 * now seeded from the extraction the preview held.
 *
 * S-3a is DISPLAY-ONLY (ruled): it proves the crossing + the re-host
 * with shipped machinery. No editing, no add/remove/reprice, no save
 * path. S-3b replaces this wrapper's core with the real edit-canvas
 * line-item editor (mode is already `editCanvas`); the escalation seam,
 * the pin, and the params contract stay unchanged.
 *
 * RE-HOST DISCIPLINE (the architectural point): both widgets mount
 * UNCHANGED via `getWidgetRenderer` — the identical `WidgetRendererProps`
 * contract the command-bar Act host (S-1/S-2) uses. This wrapper owns
 * only spatial layout (core + rail); the widgets are host-agnostic.
 * Follows the shipped `SchedulingFocusWithAccessories` precedent (core
 * in code + accessories beside it) rather than the r96 composition-
 * placement layer (which isn't production-seeding accessories yet).
 *
 * NO DATA CREATED: the draft lives in `currentFocus.params.extraction`
 * (in-memory, passed via `open(id, { params })`) exactly as the preview
 * held it. A page reload drops the params (URL carries only `?focus=`),
 * so the Focus re-opens to the empty state — correct for an ephemeral,
 * never-materialized draft.
 */

import { useFocus } from "@/contexts/focus-context"
import { getWidgetRenderer } from "@/components/focus/canvas/widget-renderers"
import type { FocusConfig } from "@/contexts/focus-registry"
import type { ExtractionContext } from "@/components/command-bar-surfaces/types"

export interface QuoteFocusWithAccessoriesProps {
  focusId: string
  config: FocusConfig
}

export function QuoteFocusWithAccessories({
  focusId,
  config,
}: QuoteFocusWithAccessoriesProps) {
  void focusId
  void config
  const { currentFocus } = useFocus()
  const extraction =
    (currentFocus?.params["extraction"] as ExtractionContext | undefined) ??
    null

  const hasContent =
    !!extraction &&
    (!!extraction.customer || extraction.lines.length > 0)

  if (!hasContent) {
    // Ephemeral draft dropped (e.g. reload) — no data was ever persisted.
    return (
      <div
        className="flex h-full w-full items-center justify-center"
        data-slot="quote-focus"
        data-quote-focus-state="empty"
      >
        <div className="max-w-sm text-center">
          <h2 className="text-h3 font-medium text-content-strong">
            No quote in progress
          </h2>
          <p className="mt-1 text-body-sm text-content-muted">
            Start a quote from the command bar, then choose “Build this out”
            to open it here.
          </p>
        </div>
      </div>
    )
  }

  const QuotePreview = getWidgetRenderer("surface.quote-preview")
  const PriceList = getWidgetRenderer("surface.price-list-reference")
  const hasLines = extraction.lines.length > 0

  return (
    <div
      className="flex h-full w-full gap-4"
      data-slot="quote-focus"
      data-quote-focus-state="active"
    >
      {/* Anchored display CORE — the re-hosted S-2 quote-preview,
          unchanged. Centered in the core region (host owns spatial). */}
      <div className="flex-1 min-w-0 overflow-y-auto">
        <div className="mx-auto w-full max-w-[440px]">
          <QuotePreview
            widgetId="quote-focus:preview"
            variant_id="detail"
            surface="focus_canvas"
            config={{
              customer: extraction.customer,
              lines: extraction.lines,
            }}
          />
        </div>
      </div>

      {/* Live-config accessory PIN — the re-hosted S-2 price-list, its
          config derived from the SAME draft the core shows. */}
      {hasLines && (
        <aside
          className="w-72 flex-shrink-0 overflow-y-auto"
          data-slot="quote-focus-accessory-rail"
          aria-label="Price list reference"
        >
          <PriceList
            widgetId="quote-focus:price-list"
            variant_id="brief"
            surface="focus_canvas"
            config={{
              products: extraction.lines.map((l) => l.productRef),
              customerId: extraction.customer?.id ?? null,
            }}
          />
        </aside>
      )}
    </div>
  )
}
