/**
 * Bank Activity — the READ view over the bank feed (Session-1 cash wire,
 * the operator's add). Transactions get WORKED in reconciliation; here
 * they get read: account filter, date range, category shown, pending
 * badged. Removed/superseded rows are excluded per the B-2 canon — a
 * retraction surfaces through its own review path, never as activity.
 */
import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { ChevronLeft, ChevronRight, Landmark } from "lucide-react"

import {
  getBankActivity, getCashPosition,
  type BankActivityItem, type CashPositionAccount,
} from "@/services/plaid-service"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"

export default function BankActivityPage() {
  const [accounts, setAccounts] = useState<CashPositionAccount[]>([])
  const [accountId, setAccountId] = useState<string>("")
  const [start, setStart] = useState("")
  const [end, setEnd] = useState("")
  const [page, setPage] = useState(1)
  const [items, setItems] = useState<BankActivityItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const perPage = 50

  useEffect(() => {
    getCashPosition()
      .then((p) => setAccounts(p.accounts))
      .catch(() => setAccounts([]))
  }, [])

  const load = useCallback(() => {
    setLoading(true)
    getBankActivity({
      account_id: accountId || undefined,
      start: start || undefined,
      end: end || undefined,
      page, per_page: perPage,
    })
      .then((r) => { setItems(r.items); setTotal(r.total) })
      .catch(() => { setItems([]); setTotal(0) })
      .finally(() => setLoading(false))
  }, [accountId, start, end, page])

  useEffect(() => { load() }, [load])

  const pages = Math.max(1, Math.ceil(total / perPage))

  return (
    <div className="space-y-6 p-6" data-testid="bank-activity-page">
      <div>
        <h1 className="flex items-center gap-2 text-h1 font-semibold text-content-strong">
          <Landmark size={22} className="text-accent" /> Bank Activity
        </h1>
        <p className="mt-1 text-body-sm text-content-muted">
          The feed as it happened — read-only. Matching and exceptions live in{" "}
          <Link to="/financials/board" className="text-accent underline-offset-2 hover:underline">
            reconciliation
          </Link>.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="text-caption text-content-muted">Account</label>
          <select
            value={accountId}
            onChange={(e) => { setAccountId(e.target.value); setPage(1) }}
            className="block h-9 rounded-md border border-border-base bg-surface-raised px-2 text-body-sm"
            data-testid="bank-activity-account-filter"
          >
            <option value="">All accounts</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}{a.mask ? ` ····${a.mask}` : ""}{a.is_credit ? " (credit)" : ""}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-caption text-content-muted">From</label>
          <Input type="date" value={start} onChange={(e) => { setStart(e.target.value); setPage(1) }} className="h-9" />
        </div>
        <div>
          <label className="text-caption text-content-muted">To</label>
          <Input type="date" value={end} onChange={(e) => { setEnd(e.target.value); setPage(1) }} className="h-9" />
        </div>
        <span className="pb-2 text-caption text-content-subtle">{total} transactions</span>
      </div>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <p className="p-6 text-center text-body-sm text-content-muted">Loading…</p>
          ) : items.length === 0 ? (
            <p className="p-6 text-center text-body-sm text-content-muted" data-testid="bank-activity-empty">
              {accounts.length === 0
                ? "No bank connected — activity appears here once a feed is live."
                : "Nothing in this range."}
            </p>
          ) : (
            <table className="w-full text-body-sm">
              <thead>
                <tr className="border-b border-border-subtle text-left text-caption uppercase tracking-wide text-content-subtle">
                  <th className="px-4 py-2.5">Date</th>
                  <th className="px-4 py-2.5">Account</th>
                  <th className="px-4 py-2.5">Description</th>
                  <th className="px-4 py-2.5">Category</th>
                  <th className="px-4 py-2.5 text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {items.map((t) => (
                  <tr key={t.id} className="border-b border-border-subtle/60">
                    <td className="whitespace-nowrap px-4 py-2 text-content-muted">{t.date}</td>
                    <td className="whitespace-nowrap px-4 py-2 text-content-muted">
                      {t.account_name}{t.account_mask ? ` ····${t.account_mask}` : ""}
                    </td>
                    <td className="px-4 py-2 text-content-base">
                      {t.description}
                      {t.pending ? (
                        <span className="ml-2 rounded-full bg-status-info-muted px-1.5 py-0.5 text-[10px] text-status-info">pending</span>
                      ) : null}
                    </td>
                    <td className="px-4 py-2 text-content-muted">
                      {t.expense_category ?? t.plaid_category_primary ?? "—"}
                    </td>
                    <td className={`whitespace-nowrap px-4 py-2 text-right font-medium ${Number(t.amount) >= 0 ? "text-status-success" : "text-content-strong"}`}>
                      {Number(t.amount) >= 0 ? "+" : ""}${Math.abs(Number(t.amount)).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      {pages > 1 ? (
        <div className="flex items-center justify-end gap-2 text-body-sm">
          <button
            className="focus-ring-accent rounded-md border border-border-base p-1.5 disabled:opacity-40"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            <ChevronLeft size={14} />
          </button>
          <span className="text-content-muted">{page} / {pages}</span>
          <button
            className="focus-ring-accent rounded-md border border-border-base p-1.5 disabled:opacity-40"
            disabled={page >= pages}
            onClick={() => setPage((p) => p + 1)}
          >
            <ChevronRight size={14} />
          </button>
        </div>
      ) : null}
    </div>
  )
}
