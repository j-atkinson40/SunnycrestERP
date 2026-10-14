import type { OrderTotals } from "@/services/order-list-service"

/** Dollars the server counted. Whole amounts drop the cents; the rest keep two. */
export function formatMoney(amount: string | null | undefined): string | null {
  if (amount == null || amount === "") return null
  const n = Number(amount)
  if (!Number.isFinite(n)) return null
  const abs = Math.abs(n)
  const cents = Math.round(abs * 100) % 100
  const formatted = abs.toLocaleString("en-US", {
    minimumFractionDigits: cents === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  })
  return n < 0 ? `-$${formatted}` : `$${formatted}`
}

/** The one total line. A schedule question is a count; money is added when the server sent it. */
export function totalsLine(totals: OrderTotals | null | undefined): string | null {
  if (totals == null) return null
  const noun = totals.count === 1 ? "order" : "orders"
  const parts = [`${totals.count} ${noun}`]
  if (totals.show_not_invoiced && (totals.not_invoiced ?? 0) > 0) {
    parts.push(`${totals.not_invoiced} not invoiced`)
  }
  const money = totals.show_money === false ? null : formatMoney(totals.total)
  if (money) parts.push(money)
  return parts.join(" · ")
}
