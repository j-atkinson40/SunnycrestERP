/**
 * S-2 (§4.3) quote-preview surface widget (surface.quote-preview).
 *
 * Renders the in-flight quote as the REAL quote document (the server
 * renders quote.standard through the same Jinja env the final PDF uses;
 * this widget just mounts the returned HTML in a sandboxed paper iframe).
 * The chrome caption carries the honest money summary: the subtotal, the
 * "calculated at order" truth when tax hasn't resolved, and the
 * price-on-request note for call-office items.
 *
 * HOST-AGNOSTIC (the S-3/S-5 re-host seam): the widget self-fetches from
 * config and holds NO host knowledge. The §4.3 Act discipline (ephemeral,
 * non-draggable, max 2–3) lives entirely in CommandBarSurfaceHost.
 */

import { useEffect, useRef, useState } from "react"
import { Loader2 } from "lucide-react"

import type { WidgetRendererProps } from "@/components/focus/canvas/widget-renderers"
import { registerWidgetRenderer } from "@/components/focus/canvas/widget-renderers"
import { Card } from "@/components/ui/card"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import {
  fetchQuotePreview,
  type QuotePreviewResponse,
} from "@/services/quote-preview-service"

interface QuoteDraftLine {
  productRef: string
  productId?: string
  quantity: number
}

interface QuotePreviewConfig {
  customer?: { id?: string; name: string } | null
  lines?: QuoteDraftLine[]
}

export function QuotePreviewWidget({ config }: WidgetRendererProps) {
  const draft = (config ?? {}) as QuotePreviewConfig
  // Amortize the per-fill refetch — the trigger gates WHEN surfaces show;
  // this debounce keeps the fetch off every intermediate config change.
  const debounced = useDebouncedValue(
    JSON.stringify({ c: draft.customer ?? null, l: draft.lines ?? [] }),
    200,
  )

  const [data, setData] = useState<QuotePreviewResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    const parsed = JSON.parse(debounced) as {
      c: { id?: string; name: string } | null
      l: QuoteDraftLine[]
    }
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setLoading(true)
    setError(false)
    fetchQuotePreview(
      {
        customer_id: parsed.c?.id ?? null,
        customer_name: parsed.c?.name ?? null,
        lines: parsed.l.map((l) => ({
          product_ref: l.productRef,
          product_id: l.productId,
          quantity: l.quantity,
        })),
      },
      ctrl.signal,
    )
      .then((res) => {
        setData(res)
        setLoading(false)
      })
      .catch((e) => {
        if (ctrl.signal.aborted) return
        // Axios cancellation surfaces as a thrown CanceledError too.
        if ((e as { code?: string })?.code === "ERR_CANCELED") return
        setError(true)
        setLoading(false)
      })
    return () => ctrl.abort()
  }, [debounced])

  return (
    <Card
      elevation="raised"
      size="sm"
      className="w-full gap-2"
      data-testid="quote-preview-surface"
    >
      <div className="flex items-center justify-between">
        <span className="text-body-sm font-medium text-content-strong">
          Quote preview
        </span>
        <span className="flex items-center gap-1 text-caption text-content-muted">
          {loading && <Loader2 className="h-3 w-3 animate-spin" />}
          Draft
        </span>
      </div>

      {error ? (
        <div className="py-6 text-center text-body-sm text-content-muted">
          Couldn't build the preview.
        </div>
      ) : (
        <iframe
          // Sandboxed, script-free: pure display of the server-rendered
          // quote document on its own white "paper" — the print CSS reads
          // correctly regardless of app light/dark mode.
          srcDoc={data?.html ?? ""}
          sandbox=""
          title="Quote preview"
          className="h-[320px] w-full rounded-base border border-border-subtle bg-white"
        />
      )}

      {data && <PreviewCaption data={data} />}
    </Card>
  )
}

function PreviewCaption({ data }: { data: QuotePreviewResponse }) {
  const parts: React.ReactNode[] = []

  if (data.subtotal_formatted) {
    parts.push(
      <span key="sub">
        Subtotal{" "}
        <span className="font-medium tabular-nums text-content-strong">
          {data.subtotal_formatted}
        </span>
      </span>,
    )
  }

  if (data.tax_resolved && data.total_formatted) {
    parts.push(
      <span key="total">
        Total{" "}
        <span className="font-medium tabular-nums text-content-strong">
          {data.total_formatted}
        </span>{" "}
        incl. tax
      </span>,
    )
  } else if (data.subtotal_formatted) {
    // Honest: no fabricated tax/total mid-draft.
    parts.push(
      <span key="tax" className="text-content-muted">
        Tax calculated at order
      </span>,
    )
  }

  const hasBody = parts.length > 0 || data.has_call_office

  return (
    <div className="flex flex-col gap-1 text-caption text-content-muted">
      {parts.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
          {parts.map((p, i) => (
            <span key={i} className="flex items-center gap-2">
              {i > 0 && <span aria-hidden>·</span>}
              {p}
            </span>
          ))}
        </div>
      )}
      {data.has_call_office && (
        <span>Some items are priced on request.</span>
      )}
      {data.unresolved_products.length > 0 && (
        <span className="text-status-warning">
          Couldn't find: {data.unresolved_products.join(", ")}
        </span>
      )}
      {!hasBody && data.line_count === 0 && (
        <span>Start typing a product to price it.</span>
      )}
    </div>
  )
}

registerWidgetRenderer("surface.quote-preview", QuotePreviewWidget)
