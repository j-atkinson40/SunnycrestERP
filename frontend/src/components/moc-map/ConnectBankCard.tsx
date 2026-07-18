/**
 * "Connect your bank" — the accounting area's SETUP CARD (Plaid B-1; the
 * onboarding vision's first real setup task).
 *
 * STATES (all honest):
 *   loading   → nothing (no flash of a wrong claim)
 *   none + admin      → the connect CTA (Link opens on click)
 *   none + non-admin  → who to ask, plainly — gated, not hidden
 *   connected → the minimal connected state ("Connected: First Platypus
 *               Bank · 2 accounts"; credit cards badged; degraded items
 *               named). The GROWN card (inventory, re-auth UX, linking)
 *               is B-3's.
 *
 * FAILURE HONESTY: Link exit is calm (no toast storm — the user closed
 * it); a failed exchange surfaces the server's legible Plaid error and
 * never half-records (the backend is transactional).
 *
 * react-plaid-link rides the Turnstile npm-wrapper precedent — the token
 * is minted on click (admin route), Link opens when ready.
 */
import { useCallback, useEffect, useState } from "react"
import { CreditCard, Landmark } from "lucide-react"
import { usePlaidLink } from "react-plaid-link"

import {
  createLinkToken, disconnectPlaidItem, exchangePublicToken, getPlaidItems,
  getReconciliationAccounts, linkBankAccount,
  type PlaidItemSummary, type ReconAccount,
} from "@/services/plaid-service"

function LinkOpener({
  token, onSuccess, onExit,
}: {
  token: string
  onSuccess: (publicToken: string, metadata: { institution?: { institution_id?: string; name?: string } | null }) => void
  onExit: () => void
}) {
  const { open, ready } = usePlaidLink({
    token,
    onSuccess: (publicToken, metadata) =>
      onSuccess(publicToken, metadata as never),
    onExit,
  })
  useEffect(() => {
    if (ready) open()
  }, [ready, open])
  return null
}

export function ConnectBankCard({
  isAdmin, autoConnect = false,
}: { isAdmin: boolean; autoConnect?: boolean }) {
  const [items, setItems] = useState<PlaidItemSummary[] | null>(null)
  const [platformAccounts, setPlatformAccounts] = useState<ReconAccount[]>([])
  const [reauthItemId, setReauthItemId] = useState<string | null>(null)
  const [linkToken, setLinkToken] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(() => {
    getPlaidItems().then(setItems).catch(() => setItems([]))
    getReconciliationAccounts().then(setPlatformAccounts).catch(() => {})
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  // The ponder's "Connect a bank" action lands with ?connect=1 — Link
  // opens without a second click (admin only; once).
  const autoRef = { fired: false }
  useEffect(() => {
    if (autoConnect && isAdmin && items !== null && !autoRef.fired) {
      autoRef.fired = true
      startConnect()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoConnect, isAdmin, items === null])

  const startConnect = useCallback(async (itemId?: string) => {
    setError(null)
    setBusy(true)
    setReauthItemId(itemId ?? null)
    try {
      setLinkToken(await createLinkToken(itemId))
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })
        .response?.data?.detail
      setError(
        typeof detail === "string"
          ? detail
          : "Couldn't start the bank connection. Try again in a moment.",
      )
      setBusy(false)
    }
  }, [])

  const onLinkSuccess = useCallback(
    async (
      publicToken: string,
      metadata: { institution?: { institution_id?: string; name?: string } | null },
    ) => {
      setLinkToken(null)
      if (reauthItemId) {
        // UPDATE MODE (re-auth): Plaid re-authorized the EXISTING item —
        // no exchange, no new item. The next sync flips status active.
        setReauthItemId(null)
        setBusy(false)
        refresh()
        return
      }
      try {
        await exchangePublicToken({
          public_token: publicToken,
          institution_id: metadata.institution?.institution_id ?? null,
          institution_name: metadata.institution?.name ?? null,
        })
        refresh()
      } catch (e) {
        const detail = (e as {
          response?: { data?: { detail?: { message?: string } | string } }
        }).response?.data?.detail
        setError(
          typeof detail === "string"
            ? detail
            : detail?.message ??
              "The bank responded but the connection couldn't be recorded. Nothing was saved — try again.",
        )
      } finally {
        setBusy(false)
      }
    },
    [refresh, reauthItemId],
  )

  const onLinkExit = useCallback(() => {
    // The user closed Link — calm, not an error.
    setLinkToken(null)
    setBusy(false)
  }, [])

  if (items === null) return null // loading — claim nothing

  const connected = items.filter((i) => i.status !== "disconnected")

  return (
    <section
      className="rounded-md bg-surface-elevated p-4 shadow-level-1"
      data-testid="connect-bank-card"
    >
      {connected.length === 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            <Landmark size={18} className="mt-0.5 flex-none text-accent" />
            <div>
              <p className="text-body font-medium text-content-strong">
                Connect your bank
              </p>
              <p className="mt-0.5 max-w-xl text-body-sm text-content-muted">
                Bridgeable pulls transactions in on a schedule and keeps
                reconciliation fed — bank and credit-card accounts both.
              </p>
            </div>
          </div>
          {isAdmin ? (
            <button
              type="button"
              onClick={() => startConnect()}
              disabled={busy}
              className="focus-ring-accent rounded-md bg-accent px-3.5 py-2 text-body-sm font-medium text-content-on-accent transition-opacity duration-quick disabled:opacity-60"
              data-testid="connect-bank-cta"
            >
              {busy ? "Opening…" : "Connect a bank"}
            </button>
          ) : (
            <p
              className="text-body-sm text-content-muted"
              data-testid="connect-bank-nonadmin"
            >
              An administrator connects the bank — ask them to set this up.
            </p>
          )}
        </div>
      ) : (
        <div data-testid="connect-bank-connected" className="space-y-4">
          {connected.map((item) => (
            <div key={item.id}>
              <div className="flex flex-wrap items-center gap-2">
                <Landmark size={15} className="flex-none text-accent" />
                <span className="text-body-sm font-medium text-content-strong">
                  Connected: {item.institution_name ?? "Your bank"}
                </span>
                <span className="text-body-sm text-content-muted">
                  · {item.accounts.length} account
                  {item.accounts.length === 1 ? "" : "s"}
                </span>
                {item.accounts.some((a) => a.is_credit) ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-surface-sunken px-2 py-0.5 text-micro text-content-muted">
                    <CreditCard size={9} /> credit card
                  </span>
                ) : null}
                {item.status !== "active" ? (
                  <span
                    className="rounded-full bg-status-warning-muted px-2 py-0.5 text-micro font-medium text-status-warning"
                    data-testid="connect-bank-degraded"
                  >
                    needs re-connecting
                  </span>
                ) : null}
                {isAdmin ? (
                  <span className="ml-auto flex items-center gap-2">
                    {item.status !== "active" ? (
                      <button
                        type="button"
                        onClick={() => startConnect(item.id)}
                        disabled={busy}
                        className="focus-ring-accent rounded-md bg-accent px-2.5 py-1 text-caption font-medium text-content-on-accent disabled:opacity-60"
                        data-testid="connect-bank-reauth"
                      >
                        Re-connect
                      </button>
                    ) : null}
                    <button
                      type="button"
                      onClick={() => {
                        // HONEST CONSEQUENCES, stated before the act.
                        if (window.confirm(
                          "Disconnect " + (item.institution_name ?? "this bank") +
                          "? The feed stops; history and matches remain.",
                        )) {
                          disconnectPlaidItem(item.id).then(refresh).catch(() => {})
                        }
                      }}
                      className="focus-ring-accent rounded-md text-caption text-content-subtle underline-offset-2 hover:text-content-muted hover:underline"
                      data-testid="connect-bank-disconnect"
                    >
                      Disconnect
                    </button>
                  </span>
                ) : null}
              </div>

              {/* THE ACCOUNTS + LINKING MANAGEMENT — which bank account
                  feeds which platform account. Unlinked is honest, not an
                  error; the mask/subtype auto-match is editable here. */}
              <ul className="mt-2 space-y-1" data-testid="connect-bank-accounts">
                {item.accounts.map((a) => (
                  <li
                    key={a.id}
                    className="flex flex-wrap items-center gap-2 rounded-md bg-surface-sunken/60 px-2.5 py-1.5"
                  >
                    <span className="text-body-sm text-content-base">
                      {a.name}
                      {a.mask ? (
                        <span className="font-plex-mono text-caption text-content-subtle"> ····{a.mask}</span>
                      ) : null}
                    </span>
                    <span className="rounded-full bg-surface-sunken px-1.5 py-0.5 text-micro text-content-subtle">
                      {a.is_credit ? "credit card" : a.account_subtype ?? a.account_type}
                    </span>
                    {isAdmin ? (
                      <select
                        value={a.financial_account_id ?? ""}
                        onChange={(e) => {
                          linkBankAccount(a.id, e.target.value || null)
                            .then(refresh)
                            .catch(() => {})
                        }}
                        className="focus-ring-accent ml-auto rounded-md border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-base"
                        data-testid={`connect-bank-link-${a.id}`}
                      >
                        <option value="">Not feeding reconciliation</option>
                        {platformAccounts.map((fa) => (
                          <option key={fa.id} value={fa.id}>
                            feeds: {fa.account_name}
                          </option>
                        ))}
                      </select>
                    ) : a.financial_account_id ? (
                      <span className="ml-auto text-caption text-content-subtle">
                        feeds reconciliation
                      </span>
                    ) : (
                      <span className="ml-auto text-caption text-content-subtle">
                        not linked
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
          {isAdmin ? (
            <button
              type="button"
              onClick={() => startConnect()}
              disabled={busy}
              className="focus-ring-accent rounded-md text-body-sm text-accent underline-offset-2 hover:underline disabled:opacity-60"
              data-testid="connect-bank-add-another"
            >
              {busy ? "Opening…" : "Add another bank"}
            </button>
          ) : null}
        </div>
      )}

      {error ? (
        <p
          className="mt-2 rounded-md bg-status-error-muted px-2.5 py-1.5 text-body-sm text-status-error"
          data-testid="connect-bank-error"
        >
          {error}
        </p>
      ) : null}

      {linkToken ? (
        <LinkOpener
          token={linkToken}
          onSuccess={onLinkSuccess}
          onExit={onLinkExit}
        />
      ) : null}
    </section>
  )
}
