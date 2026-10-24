/**
 * The Customer Pane, slice 1.
 *
 * James's dispatch, 2026-10-24. Built from the prototype (artifact
 * `3ca35d0b-c93a-4924-8cb2-32772fa49876`, "Customer Pane", updated 2026-10-04).
 *
 * THE PROTOTYPE LINES THIS FOLLOWS, quoted, because the dispatch asks for them:
 *
 *   `.ttl`    `<div class="ttl">${FH.name}</div>`
 *             `.ttl{font-size:1.45em;font-weight:300;letter-spacing:-.012em;line-height:1.2}`
 *   `.meta`   `<div class="meta">Funeral home · ${FH.addr}, ${FH.city} · ${FH.director}, director</div>`
 *             `.meta{font-size:.82em;color:var(--fg-2)}`
 *   action    `<button class="btn primary" data-a="neworder">New order</button>`
 *             `.btn.primary{background:var(--fg);color:#0a0a0a;border-color:var(--fg);font-weight:500}`
 *   `.sech`   `<div class="sech"><span>Open orders</span><span>${ORDERS.length}</span></div>`
 *   `.row`    `<span class="a"><span class="mono">${o.id.slice(-4)}</span>${o.who}</span>`
 *             `<span class="b">${o.what} · ${o.when}</span>`
 *             `<span class="c${o.st==='No driver'?' neg':''}">${o.st}</span>`
 *             `.row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.1em 1em}`
 *   account   `<div class="line">$5,810 balance · <span class="neg">$1,590 past due</span> · Net 30 …`
 *   tabs      `['people','People',…]`, `['recent','Recent',…]`, `['knows','What Opas knows',…]`
 *   knows     `<span>Usual vault</span><span>Monticello 51% · Venetian 23% …</span>`
 *
 * ⚠️ LEFT OUT BY RULING: the "Right now" offers, the contact flow, presenting mode, the
 * Office/Driver/Accounting views, and the prototype's `How they run` tab. Also dropped
 * from "What Opas knows": `Setup photo`, `Best reached by` and the alias list — none is
 * derivable from orders, and the ruling is "only worked out from real orders".
 *
 * ⚠️ AND THE DISPATCH OVERRIDES THE PROTOTYPE ON ONE LINE. The prototype shows
 * `Monticello 51%`; the dispatch says counts ("Monticello · 2 of 3 orders") and "Not
 * enough orders yet" under three orders. The counts ship. CLAUDE.md §12: the spec wins,
 * and a percentage over two orders reads as a finding while being an arithmetic accident.
 *
 * ⚠️ THE SERVER COMPOSES EVERY SENTENCE IT CAN. `meta`, `account.line`, each habit's
 * `line`, and `overdue_label` all arrive as strings. That is deliberate: the order list
 * learned on 2026-10-23 that a second place deciding what a status is called drifts from
 * the first. This component lays out; it does not phrase.
 */
import { useEffect, useRef, useState } from "react"

import {
  getCustomerDetail,
  type CustomerDetail,
  type CustomerOrderRow,
} from "@/services/order-list-service"

const HAIRLINE = "1px solid rgba(255,255,255,.08)"
const LABEL = { color: "#9a9a9a", margin: 0 } as const
const SERIF = '"IBM Plex Serif", ui-serif, Georgia, serif'
/** `.sech{…letter-spacing:.14em;text-transform:uppercase;color:var(--fg-3)}` */
const SECH = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "baseline",
  fontSize: 11,
  letterSpacing: ".14em",
  textTransform: "uppercase",
  color: "#5e5e5e",
  padding: "0 0 6px",
  margin: "14px 0 0",
} as const
/** `--terra:#cc7452` — the prototype's `.neg`. */
const TERRA = "#cc7452"

type Tab = "people" | "recent" | "knows"

export interface CustomerPaneProps {
  readonly customerId: string
  /** Opens one of this customer's orders in the Sales Order Pane. */
  readonly onOpenOrder?: (orderId: string) => void
  /** Starts a capture with the funeral home already filled.
   *
   *  ⚠️ BOTH ARGUMENTS, AND THEY DO DIFFERENT JOBS. The opening line goes in the BAR so
   *  the screen matches what was captured; the prefill is stored on the SESSION so the
   *  debounced whole-text re-read cannot clear the choice. Passing only the first is
   *  the bug James walked into on 2026-10-24 — the home showed for about a second. */
  readonly onNewOrder?: (
    openingLine: string,
    prefill?: Readonly<Record<string, string>>,
  ) => void
  /** The customer, as read, handed up so the host can answer in the reply line. */
  readonly onLoaded?: (detail: CustomerDetail) => void
}

export function CustomerPane({
  customerId, onOpenOrder, onNewOrder, onLoaded,
}: CustomerPaneProps) {
  const [row, setRow] = useState<CustomerDetail | null>(null)
  const [failed, setFailed] = useState(false)
  const [tab, setTab] = useState<Tab | null>(null)

  // ⚠️ THROUGH A REF, the same reason `SalesOrderPane` gives: `onLoaded` is an inline
  // arrow in the host, so a new identity every render, and in the dep list below it
  // would re-read the customer on every host render.
  const onLoadedRef = useRef(onLoaded)
  onLoadedRef.current = onLoaded

  useEffect(() => {
    let alive = true
    setFailed(false)
    setRow(null)
    getCustomerDetail(customerId)
      .then((next) => {
        if (!alive) return
        setRow(next)
        onLoadedRef.current?.(next)
      })
      .catch(() => {
        if (alive) setFailed(true)
      })
    return () => {
      alive = false
    }
  }, [customerId])

  // The tab resets with the customer, or a second customer opens on a tab it may not have.
  useEffect(() => {
    setTab(null)
  }, [customerId])

  if (failed) {
    return (
      <p data-testid="opas-customer-failed" style={{ color: TERRA, fontSize: 13, margin: 0 }}>
        This customer could not be read.
      </p>
    )
  }
  if (row === null) {
    return (
      <p data-testid="opas-customer-loading" style={{ color: "#5e5e5e", fontSize: 13, margin: 0 }}>
        Reading the customer…
      </p>
    )
  }

  // ⚠️ BUILT FROM WHAT EXISTS, which is how People can be absent entirely: "contacts on
  // the record, if any; otherwise leave the tab out". On production there are zero
  // contacts for the tenant, so this pane ships with two tabs, not three.
  const tabs: { id: Tab; label: string; count?: number }[] = [
    ...(row.people !== undefined && row.people.length > 0
      ? [{ id: "people" as Tab, label: "People", count: row.people.length }]
      : []),
    ...(row.recent.length > 0
      ? [{ id: "recent" as Tab, label: "Recent", count: row.recent.length }]
      : []),
    { id: "knows", label: "What Opas knows" },
  ]

  return (
    <div data-testid="opas-customer">
      <h2
        data-testid="opas-customer-title"
        style={{
          margin: "4px 0 2px",
          fontFamily: SERIF,
          fontWeight: 400,
          fontSize: 22,
          color: "#f2f2f2",
        }}
      >
        {row.name}
      </h2>
      {/* ⚠️ ABSENT, NOT EMPTY. No address, town, director or kind on the record means no
          line at all — rendering an empty `<p>` would leave a gap that reads as a
          loading state. */}
      {row.meta !== undefined && (
        <p data-testid="opas-customer-meta" style={{ margin: "0 0 10px", color: "#9a9a9a", fontSize: 13 }}>
          {row.meta}
        </p>
      )}

      {/* ── the one action ─────────────────────────────────────────────────── */}
      <button
        type="button"
        data-testid="opas-customer-new-order"
        onClick={() => onNewOrder?.(row.action.opening_line, row.action.prefill)}
        style={{
          marginTop: row.meta === undefined ? 10 : 2,
          border: "1px solid #f2f2f2",
          borderRadius: 999,
          background: "#f2f2f2",
          color: "#0a0a0a",
          fontWeight: 500,
          fontSize: 13,
          padding: "5px 14px",
          cursor: "pointer",
        }}
      >
        {row.action.label}
      </button>

      <OrderGroup
        heading="Open orders"
        rows={row.open_orders}
        empty="Nothing coming up."
        onOpenOrder={onOpenOrder}
        testid="open"
      />
      {/* ⚠️ RENDERED ONLY WHEN IT HAS ROWS, unlike "Open orders" which says so when
          empty. An empty overdue group is good news and does not need a heading to
          announce itself; an empty "Open orders" is the answer to a question the
          director is asking by opening the pane. */}
      {row.overdue.length > 0 && (
        <OrderGroup
          heading={row.overdue_label}
          rows={row.overdue}
          onOpenOrder={onOpenOrder}
          testid="overdue"
          negative
        />
      )}

      {/* ── account ────────────────────────────────────────────────────────── */}
      <div style={SECH}>
        <span>Account</span>
      </div>
      {"none" in row.account ? (
        <p data-testid="opas-customer-account-none" style={{ margin: 0, fontSize: 13, color: "#5e5e5e" }}>
          {row.account.none}
        </p>
      ) : (
        <p
          data-testid="opas-customer-account"
          style={{
            margin: 0,
            fontSize: 13,
            borderTop: HAIRLINE,
            paddingTop: 7,
            color: row.account.past_due ? TERRA : "#f2f2f2",
          }}
        >
          {row.account.line}
        </p>
      )}

      {/* ── tabs ───────────────────────────────────────────────────────────── */}
      <div
        data-testid="opas-customer-tabs"
        style={{ display: "flex", gap: 6, margin: "14px 0 0", flexWrap: "wrap" }}
      >
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            aria-pressed={tab === t.id}
            data-testid={`opas-customer-tab-${t.id}`}
            onClick={() => setTab((cur) => (cur === t.id ? null : t.id))}
            style={{
              border: 0,
              borderRadius: 999,
              padding: "3px 11px",
              fontSize: 12,
              cursor: "pointer",
              background: tab === t.id ? "rgba(255,255,255,.10)" : "rgba(255,255,255,.04)",
              color: tab === t.id ? "#f2f2f2" : "#9a9a9a",
            }}
          >
            {t.label}
            {t.count !== undefined ? ` ${t.count}` : ""}
          </button>
        ))}
      </div>

      {tab === "people" && row.people !== undefined && <People people={row.people} />}
      {tab === "recent" && <Recent entries={row.recent} />}
      {tab === "knows" && <Knows knows={row.knows} />}
    </div>
  )
}

/** `.sech` + `.row`s. The prototype's grid, with the funeral home left out of `.b`. */
function OrderGroup({
  heading, rows, empty, onOpenOrder, testid, negative,
}: {
  heading: string
  rows: readonly CustomerOrderRow[]
  empty?: string
  onOpenOrder?: (orderId: string) => void
  testid: string
  negative?: boolean
}) {
  return (
    <div data-testid={`opas-customer-group-${testid}`}>
      <div style={SECH}>
        <span>{heading}</span>
        <span style={{ letterSpacing: 0, textTransform: "none", fontSize: 13 }}>
          {rows.length > 0 ? rows.length : ""}
        </span>
      </div>
      {rows.length === 0
        ? empty !== undefined && (
            <p data-testid={`opas-customer-${testid}-empty`} style={{ margin: 0, fontSize: 13, color: "#5e5e5e" }}>
              {empty}
            </p>
          )
        : rows.map((r) => (
            <button
              key={r.id}
              type="button"
              data-testid={`opas-customer-order-${r.number}`}
              onClick={() => onOpenOrder?.(r.id)}
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(0,1fr) auto",
                gap: "1px 14px",
                width: "100%",
                textAlign: "left",
                background: "none",
                border: 0,
                borderTop: HAIRLINE,
                padding: "7px 0",
                cursor: "pointer",
                color: "inherit",
                font: "inherit",
              }}
            >
              <span style={{ fontSize: 14, color: "#f2f2f2" }}>
                <span
                  style={{
                    fontFamily: '"IBM Plex Mono", ui-monospace, Menlo, monospace',
                    fontSize: 12,
                    color: "#5e5e5e",
                    marginRight: 7,
                  }}
                >
                  {r.short}
                </span>
                {r.deceased_name}
              </span>
              <span
                style={{
                  gridRow: "1 / span 2",
                  gridColumn: 2,
                  alignSelf: "center",
                  fontSize: 12,
                  textAlign: "right",
                  color: negative ? TERRA : "#9a9a9a",
                }}
              >
                {r.status}
              </span>
              <span style={{ gridColumn: 1, fontSize: 12, color: "#9a9a9a" }}>
                {[r.what, whenLabel(r)].filter((part) => part !== undefined && part !== "").join(" · ")}
              </span>
            </button>
          ))}
    </div>
  )
}

/** "Wed Oct 28 10:00", from the same keys `format_when` writes for the order list. */
export function whenLabel(r: CustomerOrderRow): string {
  return [r.date_primary, r.time_label].filter((p) => p !== undefined && p !== "").join(" ")
}

function People({ people }: { people: NonNullable<CustomerDetail["people"]> }) {
  return (
    <div data-testid="opas-customer-people" style={{ marginTop: 10 }}>
      {people.map((p) => (
        <div key={p.name} style={{ borderTop: HAIRLINE, padding: "6px 0", fontSize: 13 }}>
          <span style={{ color: "#f2f2f2" }}>{p.name}</span>
          {p.detail !== undefined && (
            <span style={{ color: "#9a9a9a", display: "block", fontSize: 12 }}>{p.detail}</span>
          )}
        </div>
      ))}
    </div>
  )
}

function Recent({ entries }: { entries: CustomerDetail["recent"] }) {
  return (
    <div
      data-testid="opas-customer-recent"
      style={{
        marginTop: 10,
        display: "grid",
        gridTemplateColumns: "auto minmax(0,1fr)",
        gap: ".3em .9em",
        fontSize: 13,
      }}
    >
      {entries.map((e, i) => (
        <div key={`${e.label}-${i}`} style={{ display: "contents" }}>
          <span style={{ color: "#5e5e5e", whiteSpace: "nowrap" }}>{shortDate(e.when)}</span>
          <span style={{ color: "#f2f2f2" }}>
            {e.label}
            {e.detail !== undefined && <span style={{ color: "#9a9a9a" }}>{` · ${e.detail}`}</span>}
          </span>
        </div>
      ))}
    </div>
  )
}

/**
 * The start of the rulebook, shown on screen.
 *
 * ⚠️ NO MODEL IS INVOLVED AND THAT IS THE POINT. Every number here is a count over this
 * customer's own orders, so the office can check it against what they know. "That's the
 * start of the rulebook, shown on screen" (James, 2026-10-24).
 */
function Knows({ knows }: { knows: CustomerDetail["knows"] }) {
  if ("not_enough" in knows) {
    return (
      <p data-testid="opas-customer-knows-not-enough" style={{ margin: "10px 0 0", fontSize: 13, color: "#5e5e5e" }}>
        {knows.not_enough}
      </p>
    )
  }
  return (
    <div data-testid="opas-customer-knows" style={{ marginTop: 10 }}>
      <KnowsRow
        label="Usual vault"
        habits={knows.usual_vault}
        empty={knows.usual_vault_varies}
      />
      <KnowsRow
        label="Usual cemeteries"
        habits={knows.usual_cemeteries}
        empty={knows.usual_cemeteries_varies}
      />
    </div>
  )
}

function KnowsRow({
  label, habits, empty,
}: {
  label: string
  habits: readonly { name: string; line: string }[]
  /** The server's "Varies, no usual vault yet". Rendered INSTEAD of the habits. */
  empty?: string
}) {
  // ⚠️ AN EMPTY LIST IS AN ANSWER NOW, NOT AN ABSENCE (James, 2026-10-24). This row used
  // to return null, so a customer with ten orders and no habit showed the same blank as
  // a customer whose vaults Opas had never counted. The thresholds make empty the COMMON
  // case, which is exactly why it has to say something.
  // ⚠️ ONE ROW STYLE FOR BOTH STATES, so "Varies" sits on the same hairline and baseline
  // as a habit list. A differently-shaped empty state reads as a rendering fault.
  const row = {
    display: "flex",
    justifyContent: "space-between",
    gap: 16,
    padding: "6px 0",
    borderTop: HAIRLINE,
    fontSize: 13,
  } as const
  if (habits.length === 0) {
    if (empty === undefined) return null
    return (
      <div data-testid="opas-customer-knows-varies" style={row}>
        <span style={LABEL}>{label}</span>
        {/* Quieter than a habit, because it is the absence of one. */}
        <span style={{ color: "#5e5e5e", textAlign: "right" }}>{empty}</span>
      </div>
    )
  }
  return (
    <div style={row}>
      <span style={LABEL}>{label}</span>
      <span style={{ color: "#f2f2f2", textAlign: "right" }}>
        {habits.map((h) => h.line).join(" · ")}
      </span>
    </div>
  )
}

/** `"2026-10-19T13:22:53+00:00"` -> `"Oct 19"`. Falls back to the raw value. */
export function shortDate(iso: string | undefined): string {
  if (iso === undefined) return ""
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" })
}
