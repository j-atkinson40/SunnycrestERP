/**
 * S-2 (§4.3) contextual-surface data services.
 *
 * Two param-keyed hydration calls (NOT entity-id-keyed):
 *   - fetchQuotePreview → the REAL quote document rendered to HTML with
 *     the price the order will actually charge (order resolver).
 *   - fetchPriceListReference → the PUBLISHED tiered price list for the
 *     quoted products (the reference display; tiered columns correct here).
 *
 * Both are self-fetched by their widgets from config — no data flows
 * through the host (that host-agnosticism is the S-3/S-5 re-host seam).
 */

import apiClient from "@/lib/api-client"

export interface QuotePreviewLineInput {
  product_ref: string
  product_id?: string
  quantity: number
}

export interface QuotePreviewRequest {
  customer_id?: string | null
  customer_name?: string | null
  lines: QuotePreviewLineInput[]
}

/** A ref that matched MULTIPLE catalog products — the preview refuses to
 *  guess a price and asks the user which one they meant. */
export interface AmbiguousRef {
  product_ref: string
  candidates: string[]
}

export interface QuotePreviewResponse {
  html: string
  subtotal_formatted: string
  /** null when tax did not resolve mid-draft — render "calculated at order". */
  total_formatted: string | null
  tax_resolved: boolean
  has_call_office: boolean
  unresolved_products: string[]
  ambiguous_products: AmbiguousRef[]
  line_count: number
}

export async function fetchQuotePreview(
  body: QuotePreviewRequest,
  signal?: AbortSignal,
): Promise<QuotePreviewResponse> {
  const { data } = await apiClient.post<QuotePreviewResponse>(
    "/command-bar/quote-preview",
    body,
    { signal },
  )
  return data
}

export interface PriceListRow {
  product_name: string
  on_list: boolean
  standard_price_formatted: string
  contractor_price_formatted: string
  homeowner_price_formatted: string
  unit: string
}

export interface PriceListReferenceResponse {
  version_label: string | null
  rows: PriceListRow[]
}

export async function fetchPriceListReference(
  products: string[],
  customerId: string | null | undefined,
  signal?: AbortSignal,
): Promise<PriceListReferenceResponse> {
  const { data } = await apiClient.post<PriceListReferenceResponse>(
    "/command-bar/price-list-reference",
    { products, customer_id: customerId ?? null },
    { signal },
  )
  return data
}
