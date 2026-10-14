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

export interface SalesOrderSummary {
  id: string
  number: string
  deceased_name: string
  funeral_home: string
  stands_at: string
  vault?: string
  service?: string
  cemetery?: string
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
