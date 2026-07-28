/**
 * QuoteEditCanvasCore — S-3b editable quote core (replaces the S-3a
 * display-only preview).
 *
 * The first EDITABLE Focus core. Directors add / remove / reprice /
 * reorder(*) line items and watch the total move.  (*reorder is deferred
 * per the S-3b ruling — not built here.)
 *
 * State lives in a LOCAL reducer owned by the host wrapper and passed
 * down (draft-reducer.ts) — NOT an app-level externalized context. Prices
 * come from the SAME S-2 endpoint the display preview uses (structured
 * `lines`), so the drift guard holds and refusal-under-ambiguity fires
 * for an EDITED ambiguous line exactly as it does for an extracted one.
 *
 * This component is presentation + edit intent only. Repricing +
 * persistence live in the host (QuoteFocusWithAccessories) so the
 * price-list accessory pin can read the same live draft.
 */

import { Loader2, X } from "lucide-react"

import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import type { QuotePreviewLineResult, QuotePreviewResponse } from "@/services/quote-preview-service"

import { AddLineCombobox } from "./AddLineCombobox"
import type { DraftAction, QuoteDraft } from "./draft-reducer"

export interface QuoteEditCanvasCoreProps {
  draft: QuoteDraft
  dispatch: React.Dispatch<DraftAction>
  price: QuotePreviewResponse | null
  pricing: boolean
}

export function QuoteEditCanvasCore({
  draft,
  dispatch,
  price,
  pricing,
}: QuoteEditCanvasCoreProps) {
  const priceLines = price?.lines ?? []

  return (
    <Card
      elevation="raised"
      size="default"
      className="mx-auto flex h-full w-full max-w-[560px] flex-col gap-0"
      data-testid="quote-edit-canvas"
      data-quote-focus-state="active"
    >
      {/* Header — customer + draft marker */}
      <header className="flex items-center justify-between border-b border-border-subtle pb-3">
        <div className="min-w-0">
          <h2 className="truncate text-h4 font-medium text-content-strong">
            {draft.customer?.name ?? "New quote"}
          </h2>
          <p className="text-caption text-content-muted">
            Draft · edits saved automatically
          </p>
        </div>
        <span className="flex items-center gap-1 text-caption text-content-muted">
          {pricing && <Loader2 className="size-3 animate-spin" />}
          Pricing
        </span>
      </header>

      {/* Column labels */}
      <div className="grid grid-cols-[1fr_4.5rem_6.5rem_6rem_1.75rem] items-center gap-2 border-b border-border-subtle/60 py-2 text-micro font-medium uppercase tracking-wide text-content-subtle">
        <span>Product</span>
        <span className="text-right">Qty</span>
        <span className="text-right">Unit price</span>
        <span className="text-right">Line total</span>
        <span aria-hidden />
      </div>

      {/* Line rows */}
      <div className="flex-1 overflow-y-auto">
        {draft.lines.length === 0 ? (
          <div className="py-10 text-center text-body-sm text-content-muted">
            No lines yet. Add a product to start pricing.
          </div>
        ) : (
          <ul>
            {draft.lines.map((line, i) => (
              <LineRow
                key={line.lineId}
                index={i}
                productRef={line.productRef}
                quantity={line.quantity}
                override={line.unitPriceOverride}
                priced={priceLines[i]}
                onQuantity={(q) =>
                  dispatch({
                    type: "setQuantity",
                    lineId: line.lineId,
                    quantity: q,
                  })
                }
                onOverride={(value) =>
                  dispatch({
                    type: "setOverride",
                    lineId: line.lineId,
                    value,
                  })
                }
                onRemove={() =>
                  dispatch({ type: "removeLine", lineId: line.lineId })
                }
              />
            ))}
          </ul>
        )}
      </div>

      {/* Add line */}
      <div className="border-t border-border-subtle pt-3">
        <AddLineCombobox
          onAdd={(l) =>
            dispatch({
              type: "addLine",
              productRef: l.productRef,
              productId: l.productId,
            })
          }
        />
      </div>

      {/* Subtotal / total */}
      <footer className="mt-3 flex flex-col gap-1 border-t border-border-subtle pt-3">
        <div className="flex items-center justify-between text-body-sm">
          <span className="text-content-muted">Subtotal</span>
          <span
            className="font-medium tabular-nums text-content-strong"
            data-testid="quote-subtotal"
          >
            {price?.subtotal_formatted ?? "—"}
          </span>
        </div>
        <div className="flex items-center justify-between text-caption">
          <span className="text-content-subtle">
            {price?.tax_resolved && price?.total_formatted
              ? "Total incl. tax"
              : "Tax calculated at order"}
          </span>
          {price?.tax_resolved && price?.total_formatted && (
            <span className="font-medium tabular-nums text-content-strong">
              {price.total_formatted}
            </span>
          )}
        </div>
        {price?.has_call_office && (
          <span className="text-caption text-content-muted">
            Some items are priced on request.
          </span>
        )}
      </footer>
    </Card>
  )
}

interface LineRowProps {
  index: number
  productRef: string
  quantity: number
  override?: string
  priced?: QuotePreviewLineResult
  onQuantity: (q: number) => void
  onOverride: (value: string) => void
  onRemove: () => void
}

function LineRow({
  productRef,
  quantity,
  override,
  priced,
  onQuantity,
  onOverride,
  onRemove,
}: LineRowProps) {
  const status = priced?.status
  const isAmbiguous = status === "ambiguous"
  const isUnresolved = status === "unresolved"
  const isCallOffice = status === "call_office"
  const flagged = isAmbiguous || isUnresolved

  return (
    <li
      className="grid grid-cols-[1fr_4.5rem_6.5rem_6rem_1.75rem] items-center gap-2 border-b border-border-subtle/40 py-2"
      data-testid="quote-line-row"
    >
      {/* Product */}
      <div className="min-w-0">
        <span
          className={cn(
            "block truncate text-body-sm",
            flagged ? "text-status-warning" : "text-content-strong",
          )}
        >
          {priced?.description || productRef}
        </span>
        {isAmbiguous && priced && (
          <span className="block text-micro text-status-warning">
            Which: {priced.candidates.join(", ")}?
          </span>
        )}
        {isUnresolved && (
          <span className="block text-micro text-status-warning">
            Not found in catalog
          </span>
        )}
      </div>

      {/* Qty */}
      <Input
        type="number"
        min={1}
        value={quantity}
        onChange={(e) => {
          const n = parseInt(e.target.value, 10)
          if (!Number.isNaN(n)) onQuantity(n)
        }}
        className="h-8 px-2 text-right tabular-nums"
        aria-label="Quantity"
        data-testid="quote-line-qty"
      />

      {/* Unit price override */}
      <Input
        inputMode="decimal"
        value={override ?? ""}
        placeholder={
          isCallOffice
            ? "On request"
            : priced?.unit_price_formatted && priced.unit_price_formatted !== "—"
              ? priced.unit_price_formatted
              : "—"
        }
        onChange={(e) => onOverride(e.target.value)}
        className={cn(
          "h-8 px-2 text-right tabular-nums",
          priced?.price_overridden && "text-accent",
        )}
        aria-label="Unit price override"
        data-testid="quote-line-price"
      />

      {/* Line total */}
      <span
        className="text-right text-body-sm tabular-nums text-content-strong"
        data-testid="quote-line-total"
      >
        {priced?.line_total_formatted ?? "—"}
      </span>

      {/* Remove */}
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove ${productRef}`}
        className="flex size-6 items-center justify-center rounded text-content-subtle hover:bg-status-error-muted hover:text-status-error"
        data-testid="quote-line-remove"
      >
        <X className="size-3.5" />
      </button>
    </li>
  )
}
