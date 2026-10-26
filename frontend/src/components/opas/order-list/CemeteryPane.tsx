/**
 * The Cemetery Pane. Read-only; slice 1 of James's dispatch of 2026-10-26.
 *
 * Built from the prototype (artifact `0f3ee586-8baf-4b5e-b058-a9848aabc3ce`, "Contact,
 * Cemetery, Invoice Panes", updated 2026-10-03 — the bytes and digests are in
 * `docs/prototypes/`, with `PROVENANCE-2026-10-26-cemetery-pane.md`). Same glass,
 * density and header as the Customer and Sales Order panes.
 *
 * THE PROTOTYPE LINES THIS FOLLOWS, quoted from its `cemPane`:
 *
 *   .ttl        `<div class="ttl">${c.n}</div>`
 *   .meta       `<div class="meta">${c.town}, NY · <button type="button" class="lnk"
 *                data-a="cem:${c.other}">${c.not}</button></div>`
 *   action      `<button class="btn…">Directions</button>`
 *   essentials  `<div class="sech"><span>The essentials</span></div><div class="kv">`
 *               `<div><span>Address</span><span>${esc(c.addr)}</span></div>`
 *   coming up   `<div class="sech"><span>Coming up here</span><span>${c.up.length}</span></div>`
 *               `<button type="button" class="row" …><span class="a">${u[0]}</span>
 *                 <span class="b">${esc(u[1])} · ${esc(u[2])} · …</span>
 *                 <span class="c">›</span></button>`
 *   knows       `<div><span>Deliveries this year</span><span>${c.year}</span></div>`
 *               `<div><span>Next delivery</span><span>…</span></div>`
 *               `<div><span>Same name elsewhere</span><span><button … class="lnk">…`
 *
 * ⚠️ LEFT OUT BY RULING: the "Right now" closures, Sections, Driver notes, the "Call
 * the sexton" action, the "Also called" alias list, and the People tab. "Almost none of
 * that is recorded yet, so this slice shows only what Bridgeable actually knows and
 * leaves the rest out rather than faking it" (James, 2026-10-26).
 *
 * ⚠️ THE PROTOTYPE'S `.row` IS A SINGLE `<button>` AND THIS ONE CANNOT BE. Its row has
 * one target; ours has two — the row opens the order and the funeral home opens that
 * customer's pane. A button inside a button is invalid markup and the inner one does not
 * reliably receive the click, so the row is a GRID DIV holding two buttons plus the
 * status. Same three cells, same baseline; one fewer nesting error.
 *
 * ⚠️ THE SERVER COMPOSES EVERY SENTENCE IT CAN — `meta`, `essentials_empty`, each
 * `same_name.line`, `overdue_label`, `next_delivery.line`. This component lays out; it
 * does not phrase. Same rule as the Customer Pane, for the same reason: a second place
 * deciding what something is called drifts from the first.
 */
import { useEffect, useRef, useState } from "react"

import {
  getCemeteryDetail,
  type CemeteryDetail,
  type CemeteryOrderRow,
} from "@/services/order-list-service"

const HAIRLINE = "1px solid rgba(255,255,255,.08)"
const SERIF = '"IBM Plex Serif", ui-serif, Georgia, serif'
const MONO = '"IBM Plex Mono", ui-monospace, Menlo, monospace'
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
/** `.lnk{…color:var(--fg-2);text-decoration:underline…}` */
const LNK = {
  background: "none",
  border: 0,
  padding: 0,
  color: "#9a9a9a",
  font: "inherit",
  fontSize: "inherit",
  cursor: "pointer",
  textDecoration: "underline",
  textDecorationColor: "rgba(255,255,255,.16)",
  textUnderlineOffset: 3,
} as const

export interface CemeteryPaneProps {
  readonly cemeteryId: string
  /** Opens one of the orders at this cemetery in the Sales Order Pane. */
  readonly onOpenOrder?: (orderId: string) => void
  /** Opens the funeral home on a row, or the other cemetery of the same name. */
  readonly onOpenCustomer?: (customerId: string, name: string) => void
  readonly onOpenCemetery?: (cemeteryId: string, name: string) => void
  /** The cemetery, as read, handed up so the host can answer in the reply line. */
  readonly onLoaded?: (detail: CemeteryDetail) => void
}

export function CemeteryPane({
  cemeteryId, onOpenOrder, onOpenCustomer, onOpenCemetery, onLoaded,
}: CemeteryPaneProps) {
  const [row, setRow] = useState<CemeteryDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const mounted = useRef(true)
  const onLoadedRef = useRef(onLoaded)
  onLoadedRef.current = onLoaded

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  useEffect(() => {
    let live = true
    setRow(null)
    setError(null)
    getCemeteryDetail(cemeteryId)
      .then((d) => {
        if (!live || !mounted.current) return
        setRow(d)
        onLoadedRef.current?.(d)
      })
      .catch(() => {
        if (!live || !mounted.current) return
        setError("Could not read that cemetery")
      })
    return () => {
      live = false
    }
  }, [cemeteryId])

  if (error !== null) {
    return (
      <p data-testid="opas-cemetery-error" style={{ margin: 0, fontSize: 13, color: TERRA }}>
        {error}
      </p>
    )
  }
  if (row === null) {
    return (
      <p data-testid="opas-cemetery-loading" style={{ margin: 0, fontSize: 13, color: "#5e5e5e" }}>
        Reading…
      </p>
    )
  }

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <div data-testid="opas-cemetery-title" style={{ fontSize: 23, fontWeight: 300, letterSpacing: "-.012em", lineHeight: 1.2, fontFamily: SERIF }}>
        {row.name}
      </div>

      {/* ⚠️ THE TOWN AND THE DISAMBIGUATOR SHARE ONE LINE, as in the prototype. The
          "not the St. Mary's in Auburn" half is absent unless a second cemetery in this
          tenant really carries the name — measured 2026-10-26, no production row does. */}
      {(row.meta !== undefined || row.same_name !== undefined) && (
        <div data-testid="opas-cemetery-meta" style={{ fontSize: 13, color: "#9a9a9a", marginTop: 3 }}>
          {row.meta}
          {row.same_name !== undefined && (
            <>
              {row.meta !== undefined ? " · " : null}
              <button
                type="button"
                data-testid="opas-cemetery-not-the-other"
                style={LNK}
                onClick={() =>
                  onOpenCemetery?.(row.same_name!.cemetery_id, row.same_name!.name)
                }
              >
                {row.same_name.line}
              </button>
            </>
          )}
        </div>
      )}

      {/* ⚠️ AN ANCHOR, NOT A BUTTON, AND IT LEAVES THE APP. Directions open a maps tab;
          `rel="noreferrer"` because the destination has no business knowing where the
          click came from. Absent on every cemetery today — no address is recorded. */}
      {row.action !== undefined && (
        <div style={{ display: "flex", gap: 7, marginTop: 11 }}>
          <a
            data-testid="opas-cemetery-directions"
            href={row.action.url}
            target="_blank"
            rel="noreferrer"
            style={{
              border: "1px solid rgba(255,255,255,.2)",
              background: "rgba(255,255,255,.07)",
              borderRadius: 999,
              padding: "7px 14px",
              fontSize: 13,
              color: "#f2f2f2",
              textDecoration: "none",
            }}
          >
            {row.action.label}
          </a>
        </div>
      )}

      <div style={SECH}>
        <span>The essentials</span>
      </div>
      {/* ⚠️ ONE OR THE OTHER, NEVER BOTH AND NEVER NEITHER. The server sends
          `essentials` when it holds anything and `essentials_empty` when it does not, so
          this heading is never left standing over nothing. */}
      {row.essentials !== undefined ? (
        <div data-testid="opas-cemetery-essentials" style={{ display: "flex", flexDirection: "column" }}>
          {row.essentials.map((kv) => (
            <div
              key={kv.label}
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 14,
                padding: "6px 0",
                borderTop: HAIRLINE,
                fontSize: 13,
              }}
            >
              <span style={{ color: "#5e5e5e" }}>{kv.label}</span>
              <span style={{ textAlign: "right", color: "#f2f2f2" }}>{kv.value}</span>
            </div>
          ))}
        </div>
      ) : (
        <p data-testid="opas-cemetery-essentials-empty" style={{ margin: 0, fontSize: 13, color: "#5e5e5e" }}>
          {row.essentials_empty}
        </p>
      )}

      <Group
        heading="Coming up here"
        testid="coming"
        rows={row.coming}
        empty="Nothing coming up here"
        onOpenOrder={onOpenOrder}
        onOpenCustomer={onOpenCustomer}
      />
      {/* ⚠️ ONLY WHEN THERE ARE ANY — "overdue drafts in their own small group, as
          elsewhere" (dispatch). An empty fourth group on every quiet cemetery would be
          the blank-label problem one heading up. */}
      {row.overdue.length > 0 && (
        <Group
          heading={row.overdue_label}
          testid="overdue"
          rows={row.overdue}
          onOpenOrder={onOpenOrder}
          onOpenCustomer={onOpenCustomer}
          negative
        />
      )}

      <div style={SECH}>
        <span>What Opas knows</span>
      </div>
      <div data-testid="opas-cemetery-knows" style={{ display: "flex", flexDirection: "column" }}>
        <Kv label={`Deliveries in ${row.knows.year}`} value={String(row.knows.deliveries_this_year)} />
        {/* ⚠️ "None scheduled" IS THE PROTOTYPE'S OWN WORDING for the absent case, and
            it is a measured absence rather than a missing field — we counted the
            upcoming orders and there were none. That is why this row shows rather than
            dropping out the way an unrecorded field does. */}
        <Kv label="Next delivery" value={row.knows.next_delivery?.line ?? "None scheduled"} />
        {row.knows.same_name !== undefined && (
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: 14,
              padding: "6px 0",
              borderTop: HAIRLINE,
              fontSize: 13,
            }}
          >
            <span style={{ color: "#5e5e5e" }}>Same name elsewhere</span>
            <button
              type="button"
              data-testid="opas-cemetery-same-name"
              style={{ ...LNK, textAlign: "right" }}
              onClick={() =>
                onOpenCemetery?.(row.knows.same_name!.cemetery_id, row.knows.same_name!.name)
              }
            >
              {row.knows.same_name.town !== undefined
                ? `${row.knows.same_name.name}, ${row.knows.same_name.town}`
                : row.knows.same_name.name}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function Kv({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        gap: 14,
        padding: "6px 0",
        borderTop: HAIRLINE,
        fontSize: 13,
      }}
    >
      <span style={{ color: "#5e5e5e" }}>{label}</span>
      <span style={{ textAlign: "right", color: "#f2f2f2" }}>{value}</span>
    </div>
  )
}

function Group({
  heading, testid, rows, empty, onOpenOrder, onOpenCustomer, negative,
}: {
  heading: string
  testid: string
  rows: readonly CemeteryOrderRow[]
  empty?: string
  onOpenOrder?: (orderId: string) => void
  onOpenCustomer?: (customerId: string, name: string) => void
  negative?: boolean
}) {
  return (
    <div data-testid={`opas-cemetery-group-${testid}`}>
      <div style={SECH}>
        <span>{heading}</span>
        <span style={{ letterSpacing: 0, textTransform: "none", fontSize: 13 }}>
          {rows.length > 0 ? rows.length : ""}
        </span>
      </div>
      {rows.length === 0
        ? empty !== undefined && (
            <p data-testid={`opas-cemetery-${testid}-empty`} style={{ margin: 0, fontSize: 13, color: "#5e5e5e" }}>
              {empty}
            </p>
          )
        : rows.map((r) => (
            <div
              key={r.id}
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(0,1fr) auto",
                gap: "1px 14px",
                borderTop: HAIRLINE,
                padding: "7px 0",
              }}
            >
              <button
                type="button"
                data-testid={`opas-cemetery-order-${r.number}`}
                onClick={() => onOpenOrder?.(r.id)}
                style={{
                  gridColumn: 1,
                  textAlign: "left",
                  background: "none",
                  border: 0,
                  padding: 0,
                  cursor: "pointer",
                  color: "#f2f2f2",
                  font: "inherit",
                  fontSize: 14,
                }}
              >
                <span style={{ fontFamily: MONO, fontSize: 12, color: "#5e5e5e", marginRight: 7 }}>
                  {r.short}
                </span>
                {whenLabel(r)}
                {whenLabel(r) !== "" ? " · " : ""}
                {r.deceased_name}
              </button>
              {/* ⚠️ THE FUNERAL HOME IS ITS OWN TARGET, which is the second half of the
                  walk: cemetery -> order -> Hopkins. Plain text when the order has no
                  customer row, rather than a button that cannot resolve. */}
              <span style={{ gridColumn: 1, gridRow: 2, fontSize: 12, color: "#9a9a9a" }}>
                {r.funeral_home !== undefined
                  ? r.customer_id !== undefined
                    ? (
                        <button
                          type="button"
                          data-testid={`opas-cemetery-home-${r.number}`}
                          style={LNK}
                          onClick={() => onOpenCustomer?.(r.customer_id!, r.funeral_home!)}
                        >
                          {r.funeral_home}
                        </button>
                      )
                    : r.funeral_home
                  : null}
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
            </div>
          ))}
    </div>
  )
}

/** "Wed 10:00", or "Fri Oct 16 11:00" when it is outside this week. */
export function whenLabel(r: CemeteryOrderRow): string {
  const day = r.date_primary ?? r.date_head ?? ""
  return [day, r.time_label].filter((p) => p !== undefined && p !== "").join(" ")
}
