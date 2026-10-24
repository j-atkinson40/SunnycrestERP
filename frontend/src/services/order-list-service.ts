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
  /** Resolved by the SERVER from `when_phrase`, never by the model (James,
   *  2026-10-23). Read-only as far as the client is concerned. */
  service_from?: string
  service_to?: string
  when_label?: string
  /** The person's own date words ("next week", "thursday"). The model returns these;
   *  `order_list/when.resolve_when` turns them into the window above against the
   *  tenant's local today. A model payload carrying the three fields above is void. */
  when_phrase?: string
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
  /** Position on the four-dot ladder. NOT a status — see `status`. */
  stage: "proof" | "confirmed" | "delivered" | "invoiced"
  /** ⚠️ WHAT THE ORDER IS. There is deliberately no "scheduled": nothing in the
   *  platform schedules an order as a state, so nothing may say that it did
   *  (James, 2026-10-23). A draft reads "Draft", not one rung up the ladder. */
  status: "draft" | "cancelled" | "confirmed" | "delivered" | "invoiced"
  /** The words for `status`. The row shows `flag_label ?? stage_label`. */
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
  kind:
    | "question"
    | "unrecognized"
    | "open_order"
    | "picks"
    | "total"
    /** A bare customer name or prefix ("hopkins"). Carries `customer_id`/`customer_name`. */
    | "open_customer"
    /** Two or more customers could be meant. Carries `picks` with `customer_id`. */
    | "customer_picks"
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
  /** For `kind: "open_customer"`. */
  customer_id?: string
  customer_name?: string
  /** For `kind: "customer_picks"` — a separate list from `picks`, deliberately.
   *
   *  ⚠️ NOT REUSING `picks`. An `OrderPick` carries a `question` that narrows the ORDER
   *  LIST; a customer pick carries an id that OPENS A PANE. Sharing the field would
   *  make every consumer of `picks` test which kind it was holding, and the one that
   *  forgot would send a customer id into `askOrderList` as a question. */
  customer_picks?: { label: string; customer_id: string }[]
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
  /** The account's id, so the funeral home name can be a link.
   *
   *  ⚠️ ABSENT WHEN THE ORDER HAS NO CUSTOMER ROW — `_order_extras` LEFT JOINs, so this
   *  is optional rather than guaranteed, and the pane renders plain text in that case
   *  rather than a button that cannot resolve.
   *
   *  ⚠️ IT WAS ALREADY DECLARED HERE, UNDOCUMENTED, AT THE END OF THIS INTERFACE — AND
   *  NOTHING PRODUCED OR READ IT. `tsc` found the duplicate when I added this one;
   *  checking the tree before today, `customer_id` appeared in exactly one place in the
   *  whole frontend: that declaration. The server did not send it until 2026-10-24.
   *  So `row.customer_id` was permanently `undefined`, and any future reader would have
   *  taken an optional field with no producer for a live one — CLAUDE.md §11's
   *  unprovisioned-entrance class, in the small. The undocumented copy is deleted; this
   *  one is real as of today. */
  customer_id?: string
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
}

export async function askOrderList(body: {
  phrase?: string
  question?: OrderQuestion
  remove_pill?: string
  teach_phrase?: string
  /** The kind of the pane in front, for the decision log.
   *
   *  ⚠️ THE ONE THING THE SERVER CANNOT DERIVE, which is why it travels. "only hopkins"
   *  is a refinement with a list open and nothing at all in a cold bar, so a log that
   *  did not record which it was would hold cases with no single right answer. Pane
   *  kinds are already the vocabulary `surface_for` reads — do not invent a second one. */
  front?: string
}): Promise<OrderListSnapshot> {
  const r = await apiClient.post<OrderListSnapshot>("/order-list/ask", body)
  return r.data
}

export async function getSalesOrderSummary(orderId: string): Promise<SalesOrderSummary> {
  const r = await apiClient.get<SalesOrderSummary>(`/order-list/orders/${orderId}`)
  return r.data
}

/** One order row on the Customer Pane. */
export interface CustomerOrderRow {
  readonly id: string
  readonly number: string
  /** The prototype's `.mono` — the last four of the number. */
  readonly short: string
  readonly deceased_name: string
  /** "Monticello Burial Vault · St. Mary\'s Cemetery". Absent when neither is recorded. */
  readonly what?: string
  /** From the order's REAL status — Draft / Cancelled / Confirmed / Delivered / Invoiced. */
  readonly status: string
  readonly date_in_week?: boolean
  readonly date_primary?: string
  readonly date_head?: string
  readonly date_day?: string
  readonly time_label?: string
}

/** One "usual vault" / "usual cemetery" line, counted from records. */
export interface CustomerHabit {
  readonly name: string
  readonly count: number
  readonly of: number
  /** "Monticello · 2 of 3 orders" — composed by the server so one rule writes it. */
  readonly line: string
}

/**
 * The Customer Pane.
 *
 * ⚠️ OPTIONAL MEANS THE RECORD DOES NOT HOLD IT, NOT THAT THE SERVER FORGOT. "Missing
 * fields are left out, never shown as blank labels" (James, 2026-10-24). Measured on
 * production: every address, town, director and kind is NULL for all five of
 * Sunnycrest's customers and there are zero contacts, so `meta` and `people` are both
 * absent there. Rendering `undefined` as "—" would turn an empty record into a measured
 * emptiness.
 */
export interface CustomerDetail {
  readonly id: string
  readonly name: string
  /** "Funeral home · 12 Genesee St, Skaneateles, NY · Ruth Hopkins, director". */
  readonly meta?: string
  readonly action: {
    readonly kind: "new_order"
    readonly label: string
    /** "order Hopkins Funeral Home " — note the trailing space. */
    readonly opening_line: string
  }
  readonly open_orders: readonly CustomerOrderRow[]
  readonly overdue: readonly CustomerOrderRow[]
  /** The order list's own fourth-group heading, so one wording serves both. */
  readonly overdue_label: string
  readonly account:
    | { readonly line: string; readonly past_due: boolean; readonly invoices: number }
    | { readonly none: string }
  readonly knows:
    | { readonly not_enough: string; readonly orders: number }
    | {
        readonly usual_vault: readonly CustomerHabit[]
        readonly usual_cemeteries: readonly CustomerHabit[]
        readonly orders: number
      }
  readonly recent: readonly {
    readonly kind: "order" | "invoice"
    readonly label: string
    readonly when?: string
    readonly detail?: string
  }[]
  /** Absent when the record has no contacts — the tab is left out, not empty. */
  readonly people?: readonly { readonly name: string; readonly detail?: string }[]
}

export async function getCustomerDetail(customerId: string): Promise<CustomerDetail> {
  const r = await apiClient.get<CustomerDetail>(`/order-list/customers/${customerId}`)
  return r.data
}
