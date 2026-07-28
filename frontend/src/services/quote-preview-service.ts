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
  /** S-3b — per-line unit-price override. When set, the preview uses this
   *  price instead of the order resolver's. Absent = resolver price. */
  unit_price_override?: number
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

/** S-3b — the structured per-line breakdown, 1:1 with the input lines and
 *  IN ORDER (including unresolved / ambiguous / call-office lines). The
 *  edit canvas renders each row's price + total + status from this. */
export interface QuotePreviewLineResult {
  product_ref: string
  status: "resolved" | "unresolved" | "ambiguous" | "call_office"
  quantity: number
  product_id: string | null
  description: string
  unit_price: string | null
  unit_price_formatted: string
  line_total: string | null
  line_total_formatted: string
  candidates: string[]
  price_overridden: boolean
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
  /** S-3b — structured per-line breakdown for the edit canvas. */
  lines: QuotePreviewLineResult[]
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

/** S-3b — a product suggestion for the add-line combobox. */
export interface ProductSuggestion {
  id: string
  name: string
}

/** S-3b — typeahead for the add-line combobox. Best-effort: on any error
 *  (e.g. the user lacks products.view) the caller falls back to free-text
 *  entry — the preview endpoint still resolves + refuses whatever ref the
 *  user types. */
export async function searchQuoteProducts(
  query: string,
  signal?: AbortSignal,
): Promise<ProductSuggestion[]> {
  const { data } = await apiClient.get<{
    items: { id: string; name: string }[]
  }>("/products", { params: { search: query, per_page: 8 }, signal })
  return (data.items ?? []).map((p) => ({ id: p.id, name: p.name }))
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
