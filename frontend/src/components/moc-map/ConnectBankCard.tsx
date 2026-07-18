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
  createLinkToken, exchangePublicToken, getPlaidItems,
  type PlaidItemSummary,
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

export function ConnectBankCard({ isAdmin }: { isAdmin: boolean }) {
  const [items, setItems] = useState<PlaidItemSummary[] | null>(null)
  const [linkToken, setLinkToken] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(() => {
    getPlaidItems().then(setItems).catch(() => setItems([]))
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const startConnect = useCallback(async () => {
    setError(null)
    setBusy(true)
    try {
      setLinkToken(await createLinkToken())
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
    [refresh],
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
              onClick={startConnect}
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
        <div data-testid="connect-bank-connected">
          {connected.map((item) => (
            <div
              key={item.id}
              className="flex flex-wrap items-center gap-2 py-1"
            >
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
            </div>
          ))}
          {isAdmin ? (
            <button
              type="button"
              onClick={startConnect}
              disabled={busy}
              className="focus-ring-accent mt-1.5 rounded-md text-body-sm text-accent underline-offset-2 hover:underline disabled:opacity-60"
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
