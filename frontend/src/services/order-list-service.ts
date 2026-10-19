/** Reads for the Opas order list and the shortened sales order. */
// ⚠️ DEFAULT IMPORT. `api-client` default-exports; a named import compiles and is
// undefined at runtime.
import apiClient from "@/lib/api-client"

export interface OrderQuestion {
  funeral_home?: string
  cemetery?: string
  vault?: string
  decedent?: string
  unresolved_subject?: string
  subject_hint?: "vault" | "either"
  service_from?: string
  service_to?: string
  when_label?: string
  delivered?: boolean | null
  invoiced?: boolean | null
  going_out?: boolean
  about_money?: boolean
  is_default?: boolean
  surface?: "pane" | "lens"
  title?: string
}

export interface OrderRow {
  id: string
  number: string
  deceased_name: string
  meta?: string
  stage: "proof" | "scheduled" | "delivered" | "invoiced"
  stage_label: string
  dots_filled: number
  invoiced: boolean
  service_date?: string
  date_in_week?: boolean
  date_primary?: string
  date_head?: string
  date_day?: string
  time_label?: string
  flag?: "change" | "proof" | "nodriver" | "close"
  flag_label?: string
  action?: "proof" | "scheduling" | "close"
  action_label?: string
}

export interface OrderGroup {
  id: string
  label: string
  count: number
  orders: OrderRow[]
}

export interface OrderPill {
  id: string
  label: string
}

export interface OrderTotals {
  count: number
  not_invoiced?: number
  show_money?: boolean
  total?: string | null
  show_not_invoiced?: boolean
}

export interface OrderLens {
  heading: string
  pages: { items: string[]; more: number }[]
  cue: string
  first_order_id?: string | null
}

export interface OrderPick {
  n: number
  label: string
  question?: OrderQuestion
  order_id?: string
}

/** One answer from `POST /order-list/ask`. Absent keys are absent, not null. */
export interface OrderListSnapshot {
  kind: "question" | "unrecognized" | "open_order" | "picks" | "total"
  layout?: "grouped" | "flat" | "picks"
  title?: string
  question?: OrderQuestion
  pills?: OrderPill[]
  groups?: OrderGroup[]
  orders?: OrderRow[]
  totals?: OrderTotals | null
  footer?: string
  lens?: OrderLens
  surface?: "pane" | "lens"
  empty?: string
  hint?: string
  open_order_id?: string
  picks?: OrderPick[]
}

/** Where a kv row's value can take you. Absent means the value is plain text. */
export interface OrderRowLink {
  /** `"product"` opens the Product Pane; `"cemetery"` is inert in slice 1. */
  kind: "product" | "cemetery"
  /** Present only for `kind: "product"`, and only when the vault name resolved to
   *  exactly ONE catalog variant. `products.variant_template_id` is NULL on every
   *  product platform-wide, so the server resolves the line's NAME instead — an
   *  ambiguous name yields no link rather than an arbitrary one. */
  variant_template_id?: string
  /** `true` for a link that is deliberately not wired yet. The pane renders the
   *  reason rather than a dead click. */
  inert?: boolean
  why?: string
}

export interface OrderDetailRow {
  label: string
  value: string
  link?: OrderRowLink
}

/** Confirmed -> Delivered -> Invoiced, or the state instead of steps.
 *
 * ⚠️ `kind` DISCRIMINATES, AND `steps` IS ABSENT ON THE OTHER TWO. "Draft and
 * cancelled show as such, not as steps" (James, 2026-10-19), so a draft has no
 * step list to render half-filled. */
export type OrderState =
  | { kind: "steps"; steps: { id: string; label: string; done: boolean }[]; stage: string }
  | { kind: "draft"; label: string }
  | { kind: "cancelled"; label: string }

export interface OrderBillingLine {
  description: string
  quantity: string
  unit_price: string | null
  line_total: string | null
}

export interface OrderBilling {
  lines: OrderBillingLine[]
  total: string | null
  /** The real invoicing line, from the customer's own setting, honest about sending. */
  sentence: string
}

export interface OrderHistoryEntry {
  action: string
  who?: string
  /** ISO 8601. */
  when?: string
  detail?: string
  /** Present INSTEAD of `detail` when the audit row recorded no fields — which is every
   *  `updated` row, because `sales_service.update_sales_order` logs without `changes`. */
  detail_absent?: string
}

/** One order, shortened. Absent keys are absent, not null — the pane's
 *  render-only-what-exists rule depends on that, same as the Product Pane. */
export interface SalesOrderSummary {
  id: string
  number: string
  deceased_name: string
  funeral_home: string
  stands_at: string
  vault?: string
  service?: string
  cemetery?: string
  /** The deceased's name, title-cased. The pane's largest text. */
  title: string
  state: OrderState
  order: OrderDetailRow[]
  billing: OrderBilling
  /** ⚠️ ABSENT when the order has no audit trail, and the pane then leaves the tab
   *  out — "if none, say so and leave the tab out rather than faking it". */
  history?: OrderHistoryEntry[]
  /** True only for a `confirmed` order. The SERVER owns the rest of the rule and
   *  refuses the PATCH with the sentence that names the remedy. */
  can_undo_confirm: boolean
  customer_id?: string
}

export async function askOrderList(body: {
  phrase?: string
  question?: OrderQuestion
  remove_pill?: string
  teach_phrase?: string
}): Promise<OrderListSnapshot> {
  const r = await apiClient.post<OrderListSnapshot>("/order-list/ask", body)
  return r.data
}

export async function getSalesOrderSummary(orderId: string): Promise<SalesOrderSummary> {
  const r = await apiClient.get<SalesOrderSummary>(`/order-list/orders/${orderId}`)
  return r.data
}
