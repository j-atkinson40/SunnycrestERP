/**
 * The Sales Order Pane. Read-only, plus one action.
 *
 * ⚠️ MEASURED FROM `docs/prototypes/2026-10-04-sales-order-pane.html` (81544 bytes, md5
 * `1fe0b3083812cb92ed0975f8c17c5926`), not chosen. Digests and the provenance caveat are
 * in `docs/prototypes/PROVENANCE-2026-10-19-sales-order-pane.md`; the cited dispatch URL
 * does not resolve and that file says so.
 *
 * The prototype lines this follows, quoted:
 *
 *   :334  return {key:'so',kind:'Sales order',main:true,render:()=>{
 *   title <div class="ttl dec">${esc(O.dec)}</div>
 *   meta  <div class="meta">${O.id} · <button type="button" class="lnk" data-a="fh">${O.fh}</button></div>
 *   :330  const s=[['Proof',...],['Scheduled',...],['Delivered',''],['Invoiced','']];
 *         <div class="steps" role="img" aria-label="Order progress"> … <i></i> …
 *   kv    Vault (data-a="prod") · Personalization · Cemetery (data-a="cem")
 *         `${O.cem}, ${O.town}` · Service `Fri Oct 2 · ${O.time} AM graveside`
 *         · Equipment · Total
 *   tabs  S.push(['bill','Billing',…]) ; S.push(['hist','History',HIST.length,…])
 *   css   .dec{font-family:"IBM Plex Serif",Georgia,serif;font-weight:400}
 *         .steps{display:flex;align-items:center;gap:.35em;font-size:.78em;color:var(--fg-3)}
 *         .steps .done{color:var(--fg)}
 *         .steps .done::before{background:var(--ok);border-color:var(--ok)}
 *         .tabs button[aria-pressed="true"]{background:rgba(255,255,255,.1);color:var(--fg)}
 *         .hist{display:grid;grid-template-columns:auto minmax(0,1fr);gap:.3em .9em;font-size:.84em}
 *
 * ⚠️ THE STEPS ARE THE DISPATCH'S THREE, NOT THE PROTOTYPE'S FOUR. `Confirmed ->
 * Delivered -> Invoiced` against the prototype's `Proof -> Scheduled -> Delivered ->
 * Invoiced`. The prototype predates the confirm step (updated 2026-10-04; Approve began
 * confirming on 2026-10-16) and contains the word "Confirmed" zero times. Look and
 * layout from the prototype; state vocabulary from the dispatch.
 *
 * ⚠️ WHAT IS DELIBERATELY NOT HERE, from James's own list: the "Right now" alerts, the
 * proof, the scheduling Focus, the contact flow, and the Office/Driver/Accounting views.
 * Each depends on something not built. Also absent: the prototype's Delivery kv row
 * (`deliveries` has 0 rows for Sunnycrest and the dispatch's row list omits it) and its
 * "Hopkins is Net 30" clause (`customers.payment_terms` is NULL on all 22 customers
 * platform-wide — it would be invented).
 *
 * ⚠️ IT READS. Every value comes from `GET /order-list/orders/{id}`. The one write is
 * Undo confirm, which goes through `PATCH /sales-orders/{id}` — the existing rule, the
 * existing refusal message, no second copy here.
 */
import { useEffect, useState, type CSSProperties } from "react"

import { salesService } from "@/services/sales-service"
import {
  getSalesOrderSummary,
  type OrderDetailRow,
  type SalesOrderSummary,
} from "@/services/order-list-service"

/** The prototype's muted label colour and tracking. */
const LABEL: CSSProperties = {
  color: "#5e5e5e",
  fontSize: 11,
  letterSpacing: ".12em",
  textTransform: "uppercase",
}

const SERIF = "'IBM Plex Serif', Georgia, serif"
const HAIRLINE = "1px solid rgba(255,255,255,.09)"
const LINK_COLOR = "#8aa4bd"

type Tab = "bill" | "hist"

export interface SalesOrderPaneProps {
  readonly orderId: string
  /** Opens the vault in the existing Product Pane. Absent in tests that only read. */
  readonly onOpenProduct?: (variantTemplateId: string) => void
  /** Called after a successful Undo confirm so the host can re-read. */
  readonly onChanged?: () => void
}

export function SalesOrderPane({ orderId, onOpenProduct, onChanged }: SalesOrderPaneProps) {
  const [row, setRow] = useState<SalesOrderSummary | null>(null)
  const [failed, setFailed] = useState(false)
  const [tab, setTab] = useState<Tab | null>(null)
  const [undoing, setUndoing] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  // ⚠️ A COUNTER, NOT A BOOLEAN. Undo confirm re-reads the order, and a boolean "reload"
  // flag would have to be flipped back — a second render in between would re-fire.
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let alive = true
    setFailed(false)
    setRow(null)
    getSalesOrderSummary(orderId)
      .then((next) => {
        if (alive) setRow(next)
      })
      .catch(() => {
        if (alive) setFailed(true)
      })
    return () => {
      alive = false
    }
  }, [orderId, reload])

  // ⚠️ THE TAB RESETS WITH THE ORDER. Without this, opening a second order while the
  // History tab was showing would leave the pane on a tab that order may not have.
  useEffect(() => {
    setTab(null)
    setNotice(null)
  }, [orderId])

  if (failed) {
    return (
      <p data-testid="opas-sales-order-failed" style={{ color: "#cc7452", fontSize: 13, margin: 0 }}>
        This order could not be read.
      </p>
    )
  }
  if (row === null) {
    return (
      <p data-testid="opas-sales-order-loading" style={{ color: "#5e5e5e", fontSize: 13, margin: 0 }}>
        Reading the order…
      </p>
    )
  }

  async function undoConfirm() {
    if (row === null || undoing) return
    setUndoing(true)
    setNotice(null)
    try {
      await salesService.updateSalesOrder(row.id, { status: "draft" })
      setNotice(`${row.number} is a draft again — it will not be delivered or invoiced.`)
      setReload((n) => n + 1)
      onChanged?.()
    } catch (err: unknown) {
      // ⚠️ THE SERVER'S OWN SENTENCE. `undo_confirm_blocker` names the remedy ("void the
      // invoice first", "cancel instead"); replacing it with "could not undo" would throw
      // away the only part the office can act on.
      const detail = (err as { response?: { data?: { detail?: unknown } } })
        ?.response?.data?.detail
      setNotice(
        typeof detail === "string" && detail ? detail : "Could not undo the confirmation.",
      )
    } finally {
      setUndoing(false)
    }
  }

  const history = row.history ?? []
  // ⚠️ THE TAB LIST IS BUILT FROM WHAT EXISTS, which is why History can be absent
  // entirely: "if none, say so and leave the tab out rather than faking it".
  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: "bill", label: "Billing" },
    ...(history.length > 0
      ? [{ id: "hist" as Tab, label: "History", count: history.length }]
      : []),
  ]

  return (
    <div data-testid="opas-sales-order">
      {/* ── title and meta — prototype's `.ttl.dec` and `.meta` ───────────── */}
      <h2
        data-testid="opas-sales-order-title"
        style={{
          margin: "4px 0 2px",
          fontFamily: SERIF,
          fontWeight: 400,
          fontSize: 22,
          color: "#f2f2f2",
        }}
      >
        {row.title}
      </h2>
      <p style={{ margin: "0 0 10px", color: "#9a9a9a", fontSize: 13 }}>
        <span data-testid="opas-sales-order-number">{row.number}</span>
        {" · "}
        {/* ⚠️ THE FUNERAL HOME IS A LINK IN THE PROTOTYPE (`data-a="fh"`) AND IS NOT ONE
            HERE. The Customer Pane is the NEXT slice; linking it now would be the dead
            click the dispatch forbids for the cemetery. Plain text until it exists. */}
        <span data-testid="opas-sales-order-fh">{row.funeral_home}</span>
      </p>

      <OrderSteps state={row.state} />

      {/* ── "The order" — absent rows are absent ─────────────────────────── */}
      <dl data-testid="opas-sales-order-rows" style={{ margin: "12px 0 0" }}>
        {row.order.map((field) => (
          <Row key={field.label} field={field} onOpenProduct={onOpenProduct} />
        ))}
      </dl>

      {/* ── tabs — prototype's `.tabs` ────────────────────────────────────── */}
      <div
        data-testid="opas-sales-order-tabs"
        style={{ display: "flex", gap: 6, margin: "14px 0 0" }}
      >
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            aria-pressed={tab === t.id}
            data-testid={`opas-sales-order-tab-${t.id}`}
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

      {tab === "bill" && <Billing billing={row.billing} />}
      {tab === "hist" && history.length > 0 && <History entries={history} />}

      {/* ── the one action ───────────────────────────────────────────────── */}
      {row.can_undo_confirm && (
        <button
          type="button"
          data-testid="opas-sales-order-undo-confirm"
          disabled={undoing}
          onClick={() => void undoConfirm()}
          style={{
            marginTop: 14,
            border: HAIRLINE,
            borderRadius: 999,
            background: "transparent",
            color: "#9a9a9a",
            fontSize: 12,
            padding: "4px 12px",
            cursor: undoing ? "default" : "pointer",
          }}
        >
          {undoing ? "Working…" : "Undo confirm"}
        </button>
      )}
      {notice !== null && (
        <p
          data-testid="opas-sales-order-notice"
          style={{ margin: "8px 0 0", fontSize: 12, color: "#cc9a52" }}
        >
          {notice}
        </p>
      )}

      <p style={{ margin: "14px 0 0", fontSize: 12, color: "#5e5e5e" }}>
        <a href={`/ar/orders/${row.id}`} style={{ color: LINK_COLOR }}>
          Open the full order
        </a>
      </p>
    </div>
  )
}

/** `Confirmed -> Delivered -> Invoiced`, or the state instead of steps. */
function OrderSteps({ state }: { state: SalesOrderSummary["state"] }) {
  if (state.kind !== "steps") {
    return (
      <p
        data-testid={`opas-sales-order-state-${state.kind}`}
        style={{
          margin: 0,
          fontSize: 12,
          letterSpacing: ".06em",
          textTransform: "uppercase",
          color: state.kind === "cancelled" ? "#cc7452" : "#9a9a9a",
        }}
      >
        {state.label}
      </p>
    )
  }
  return (
    <div
      data-testid="opas-sales-order-steps"
      role="img"
      aria-label={`Order progress: ${state.steps
        .map((s) => `${s.label} ${s.done ? "done" : "not yet"}`)
        .join(", ")}`}
      style={{
        display: "flex",
        alignItems: "center",
        gap: ".35em",
        fontSize: 12,
        color: "#5e5e5e",
      }}
    >
      {state.steps.map((step, i) => (
        <span key={step.id} style={{ display: "flex", alignItems: "center", gap: ".35em" }}>
          {i > 0 && (
            <i
              aria-hidden="true"
              style={{
                width: 14,
                height: 1,
                background: "rgba(255,255,255,.14)",
                display: "inline-block",
              }}
            />
          )}
          <span
            data-testid={`opas-sales-order-step-${step.id}`}
            data-done={step.done ? "true" : "false"}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 5,
              color: step.done ? "#f2f2f2" : "#5e5e5e",
            }}
          >
            <span
              aria-hidden="true"
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                // `.steps .done::before{background:var(--ok);border-color:var(--ok)}`
                background: step.done ? "#6f9f78" : "transparent",
                border: step.done ? "1px solid #6f9f78" : "1px solid rgba(255,255,255,.22)",
              }}
            />
            {step.label}
          </span>
        </span>
      ))}
    </div>
  )
}

function Row({
  field,
  onOpenProduct,
}: {
  field: OrderDetailRow
  onOpenProduct?: (variantTemplateId: string) => void
}) {
  const link = field.link
  const openable =
    link?.kind === "product" && link.variant_template_id !== undefined && onOpenProduct !== undefined

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        gap: 16,
        padding: "7px 0",
        borderTop: HAIRLINE,
        fontSize: 14,
      }}
    >
      <dt style={LABEL}>{field.label}</dt>
      <dd style={{ margin: 0, color: "#f2f2f2", textAlign: "right" }}>
        {openable ? (
          <button
            type="button"
            data-testid={`opas-sales-order-open-${field.label.toLowerCase()}`}
            onClick={() => onOpenProduct?.(link!.variant_template_id!)}
            style={{
              border: 0,
              background: "transparent",
              padding: 0,
              font: "inherit",
              color: LINK_COLOR,
              cursor: "pointer",
              textAlign: "right",
            }}
          >
            {field.value}
          </button>
        ) : link?.inert ? (
          /* ⚠️ NOT A BUTTON, BY DISPATCH: "inert until the Cemetery Pane exists: say so
             in a tooltip, no dead click". A disabled button still reads as a control
             that will work later; dotted-underlined text with a title does not. */
          <span
            data-testid={`opas-sales-order-inert-${field.label.toLowerCase()}`}
            title={link.why}
            style={{
              borderBottom: "1px dotted rgba(255,255,255,.22)",
              cursor: "help",
            }}
          >
            {field.value}
          </span>
        ) : (
          field.value
        )}
      </dd>
    </div>
  )
}

function Billing({ billing }: { billing: SalesOrderSummary["billing"] }) {
  return (
    <div data-testid="opas-sales-order-billing" style={{ marginTop: 10 }}>
      <dl style={{ margin: 0 }}>
        {billing.lines.map((line, i) => (
          <div
            key={`${line.description}-${i}`}
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: 16,
              padding: "5px 0",
              borderTop: HAIRLINE,
              fontSize: 13,
            }}
          >
            <dt style={{ color: "#9a9a9a" }}>
              {line.description}
              {line.quantity !== "1" ? ` × ${line.quantity}` : ""}
            </dt>
            <dd
              style={{
                margin: 0,
                color: "#f2f2f2",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {line.line_total}
            </dd>
          </div>
        ))}
      </dl>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: 16,
          padding: "6px 0 0",
          borderTop: HAIRLINE,
          fontSize: 14,
        }}
      >
        <span style={LABEL}>Total</span>
        <span
          data-testid="opas-sales-order-billing-total"
          style={{ color: "#f2f2f2", fontVariantNumeric: "tabular-nums" }}
        >
          {billing.total}
        </span>
      </div>
      <p
        data-testid="opas-sales-order-billing-sentence"
        style={{ margin: "8px 0 0", fontSize: 12, color: "#9a9a9a" }}
      >
        {billing.sentence}
      </p>
    </div>
  )
}

/** `.hist{display:grid;grid-template-columns:auto minmax(0,1fr)}` — the prototype's grid. */
function History({ entries }: { entries: NonNullable<SalesOrderSummary["history"]> }) {
  return (
    <div
      data-testid="opas-sales-order-history"
      style={{
        marginTop: 10,
        display: "grid",
        gridTemplateColumns: "auto minmax(0,1fr)",
        gap: ".3em .9em",
        fontSize: 13,
      }}
    >
      {entries.map((entry, i) => (
        <HistoryEntry key={`${entry.action}-${entry.when ?? i}`} entry={entry} />
      ))}
    </div>
  )
}

function HistoryEntry({
  entry,
}: {
  entry: NonNullable<SalesOrderSummary["history"]>[number]
}) {
  return (
    <>
      <span style={{ color: "#5e5e5e", whiteSpace: "nowrap" }}>{formatWhen(entry.when)}</span>
      <span style={{ color: "#f2f2f2" }}>
        {entry.action}
        {entry.detail !== undefined && (
          <span style={{ color: "#9a9a9a" }}>{` · ${entry.detail}`}</span>
        )}
        {/* ⚠️ "no fields recorded" IS THE TRUTH ABOUT THE ROW, NOT A PLACEHOLDER. Every
            `updated` audit row has `changes` NULL because `update_sales_order` logs
            without them, so the trail records that something changed and not what.
            Saying so is the dispatch's "from whatever audit trail exists". */}
        {entry.detail_absent !== undefined && (
          <span
            data-testid="opas-sales-order-history-no-detail"
            style={{ color: "#5e5e5e" }}
          >{` · ${entry.detail_absent}`}</span>
        )}
        {entry.who !== undefined && (
          <span style={{ color: "#5e5e5e" }}>{` · ${entry.who}`}</span>
        )}
      </span>
    </>
  )
}

/** `"2026-10-19T12:03:59+00:00"` -> `"Oct 19"`. Falls back to the raw value. */
export function formatWhen(iso: string | undefined): string {
  if (iso === undefined) return ""
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" })
}
