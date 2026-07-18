/**
 * Bank category map — the tenant-adjustable Plaid→platform mapping
 * (Plaid B-3). FORWARD-ONLY stated plainly; seeded rows distinguishable
 * from tenant edits; the uncategorized count with its rows reachable.
 * Admin edits; everyone reads.
 */
import { useCallback, useEffect, useState } from "react"
import { ChevronDown, Tags } from "lucide-react"

import { useAuth } from "@/contexts/auth-context"
import {
  getCategoryMappings, getUncategorized, setCategoryOverride,
  type CategoryMapResponse, type UncategorizedTxn,
} from "@/services/plaid-service"

export default function BankCategoriesSettings() {
  const { isAdmin } = useAuth()
  const [data, setData] = useState<CategoryMapResponse | null>(null)
  const [uncat, setUncat] = useState<UncategorizedTxn[] | null>(null)

  const load = useCallback(() => {
    getCategoryMappings().then(setData).catch(() => setData(null))
  }, [])
  useEffect(() => { load() }, [load])

  if (data === null) return null

  return (
    <div className="space-y-6 p-6" data-testid="bank-categories-settings">
      <div>
        <h1 className="flex items-center gap-2 text-h1 font-semibold text-content-strong">
          <Tags size={20} className="text-accent" /> Bank categories
        </h1>
        <p className="mt-1 max-w-2xl text-body text-content-muted">
          How bank transactions become expense categories. Changes apply to
          new transactions — history is never silently rewritten.
        </p>
      </div>

      {/* THE HONEST UNCATEGORIZED — the count, and its rows reachable. */}
      <section className="rounded-md bg-surface-elevated p-4 shadow-level-1">
        <button
          type="button"
          className="focus-ring-accent flex items-center gap-1.5 rounded-md text-body-sm text-content-base"
          onClick={() =>
            uncat === null
              ? getUncategorized().then(setUncat).catch(() => setUncat([]))
              : setUncat(null)
          }
          data-testid="bank-categories-uncat-toggle"
        >
          <ChevronDown
            size={13}
            className={"transition-transform duration-quick " + (uncat ? "" : "-rotate-90")}
          />
          <span className="font-medium">{data.uncategorized_count}</span>
          uncategorized transaction{data.uncategorized_count === 1 ? "" : "s"}
        </button>
        {uncat ? (
          <ul className="mt-2 space-y-1" data-testid="bank-categories-uncat-rows">
            {uncat.map((t) => (
              <li key={t.id} className="flex gap-3 text-body-sm text-content-muted">
                <span className="font-plex-mono text-caption">{t.date}</span>
                <span className="text-content-base">{t.description}</span>
                <span className="ml-auto font-plex-mono">{t.amount}</span>
                <span className="text-content-subtle">
                  {t.plaid_category_detailed ?? t.plaid_category_primary ?? "no bank category"}
                </span>
              </li>
            ))}
            {uncat.length === 0 ? (
              <li className="text-body-sm text-content-subtle">Nothing waiting.</li>
            ) : null}
          </ul>
        ) : null}
      </section>

      <section className="rounded-md bg-surface-elevated shadow-level-1">
        <table className="w-full text-body-sm">
          <thead>
            <tr className="border-b border-border-subtle text-left text-caption uppercase tracking-wide text-content-subtle">
              <th className="px-4 py-2.5 font-medium">Bank category (Plaid)</th>
              <th className="px-4 py-2.5 font-medium">Becomes</th>
              <th className="px-4 py-2.5 font-medium">Source</th>
            </tr>
          </thead>
          <tbody>
            {data.mappings.map((m) => (
              <tr key={m.plaid_category} className="border-b border-border-subtle/50">
                <td className="px-4 py-2 font-plex-mono text-caption text-content-base">
                  {m.plaid_category}
                </td>
                <td className="px-4 py-2">
                  {isAdmin ? (
                    <select
                      value={m.expense_category}
                      onChange={(e) =>
                        setCategoryOverride(m.plaid_category, e.target.value)
                          .then(load).catch(() => {})
                      }
                      className="focus-ring-accent rounded-md border border-border-base bg-surface-raised px-2 py-1 text-caption"
                      data-testid={`bank-cat-select-${m.plaid_category}`}
                    >
                      {data.expense_categories.map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  ) : (
                    <span className="text-content-base">{m.expense_category}</span>
                  )}
                </td>
                <td className="px-4 py-2">
                  {m.source === "yours" ? (
                    <span className="inline-flex items-center gap-2">
                      <span className="rounded-full bg-accent-subtle px-2 py-0.5 text-micro font-medium text-accent">
                        yours
                      </span>
                      {isAdmin ? (
                        <button
                          type="button"
                          onClick={() =>
                            setCategoryOverride(m.plaid_category, null)
                              .then(load).catch(() => {})
                          }
                          className="focus-ring-accent rounded-md text-micro text-content-subtle underline-offset-2 hover:underline"
                          data-testid={`bank-cat-clear-${m.plaid_category}`}
                        >
                          use the seeded default
                        </button>
                      ) : null}
                    </span>
                  ) : (
                    <span className="rounded-full bg-surface-sunken px-2 py-0.5 text-micro text-content-subtle">
                      seeded
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
