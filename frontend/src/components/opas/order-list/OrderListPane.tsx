/**
 * The order list pane.
 *
 * ⚠️ THE LIST DOES NOT EDIT. A row opens the sales order. A fix button goes to
 * the proof, the scheduling Focus, or the order page — and does not also open
 * the row. The question, the groups, and the total are what the server sent.
 */
import { useEffect, useState, type CSSProperties, type MouseEvent, type ReactNode } from "react"

import { useFocusOptional } from "@/contexts/focus-context"
import type { OrderListSnapshot, OrderRow } from "@/services/order-list-service"

import { totalsLine } from "./order-list-format"
import { OrderListLens } from "./OrderListLens"

export type OrderListDensity = "compact" | "comfortable"
export type OrderListLayout = "phone" | "desktop"

const SANS = "'IBM Plex Sans', -apple-system, sans-serif"
const SERIF = "'IBM Plex Serif', Georgia, serif"

function usePhoneWidth(): boolean {
  const [phone, setPhone] = useState(false)
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 640px)")
    const apply = () => setPhone(mq.matches)
    apply()
    mq.addEventListener("change", apply)
    return () => mq.removeEventListener("change", apply)
  }, [])
  return phone
}

function Dots({ row }: { row: OrderRow }) {
  return (
    <span
      data-testid="opas-order-dots"
      data-filled={row.dots_filled}
      aria-label={row.stage_label}
      style={{ display: "inline-flex", gap: 3, alignItems: "center" }}
    >
      {[0, 1, 2, 3].map((i) => (
        <span
          key={i}
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: i < row.dots_filled ? "#3f9c63" : "transparent",
            boxShadow: i < row.dots_filled ? "none" : "inset 0 0 0 1px rgba(255,255,255,.4)",
          }}
        />
      ))}
    </span>
  )
}

function FixAction({
  row,
  onFix,
}: {
  row: OrderRow
  onFix?: (row: OrderRow) => void
}) {
  const focus = useFocusOptional()
  if (!row.action || !row.action_label) return null
  const stop = (event: MouseEvent) => {
    event.stopPropagation()
    event.preventDefault()
  }
  const style: CSSProperties = {
    border: "1px solid rgba(255,255,255,.14)",
    background: "rgba(255,255,255,.04)",
    color: "#f2f2f2",
    borderRadius: 999,
    padding: "3px 10px",
    fontSize: 12,
    cursor: "pointer",
    fontFamily: SANS,
  }
  if (row.action === "scheduling") {
    return (
      <button
        type="button"
        data-testid={`opas-order-action-${row.id}`}
        style={style}
        onClick={(event) => {
          stop(event)
          if (onFix) onFix(row)
          else {
            focus?.open("funeral-scheduling", {
              params: { orderId: row.id, date: row.service_date },
            })
          }
        }}
      >
        {row.action_label}
      </button>
    )
  }
  const href = row.action === "proof" ? `/legacy/proof/${row.id}` : `/sales-orders/${row.id}`
  return (
    <a
      href={href}
      data-testid={`opas-order-action-${row.id}`}
      style={{ ...style, textDecoration: "none" }}
      onClick={(event) => event.stopPropagation()}
    >
      {row.action_label}
    </a>
  )
}

function DateCell({ row, phone }: { row: OrderRow; phone: boolean }) {
  if (!row.date_primary && !row.time_label) return <span />
  if (phone && row.date_head && row.date_day) {
    return (
      <div style={{ color: "#9a9a9a", fontSize: "0.78em", lineHeight: 1.2 }}>
        <div>{row.date_head}</div>
        <div style={{ color: "#f2f2f2", fontSize: "1.15em" }}>{row.date_day}</div>
        {row.time_label && <div>{row.time_label}</div>}
      </div>
    )
  }
  return (
    <div style={{ color: "#9a9a9a", fontSize: "0.78em", lineHeight: 1.25 }}>
      {row.date_primary && <div style={{ color: "#f2f2f2" }}>{row.date_primary}</div>}
      {row.time_label && <div>{row.time_label}</div>}
    </div>
  )
}

function OrderRowView({
  row,
  phone,
  selected,
  pad,
  onOpen,
  onFix,
}: {
  row: OrderRow
  phone: boolean
  selected: boolean
  pad: string
  onOpen: (id: string) => void
  onFix?: (row: OrderRow) => void
}) {
  const status = (
    <div
      data-testid={`opas-order-status-${row.id}`}
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: phone ? "flex-start" : "flex-end",
        gap: 4,
        marginTop: phone ? 6 : 0,
      }}
    >
      <span style={{ display: "inline-flex", alignItems: "center", gap: 8, color: "#9a9a9a", fontSize: "0.78em" }}>
        {row.flag_label ?? row.stage_label}
        <Dots row={row} />
      </span>
      <FixAction row={row} onFix={onFix} />
    </div>
  )
  return (
    <div
      role="button"
      tabIndex={0}
      data-testid={`opas-order-row-${row.id}`}
      data-selected={selected ? "true" : "false"}
      onClick={() => onOpen(row.id)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault()
          onOpen(row.id)
        }
      }}
      style={{
        display: "grid",
        gridTemplateColumns: phone ? "3.8em 1fr" : "4.4em 1fr auto",
        gap: "0.4em 0.7em",
        alignItems: "start",
        padding: pad,
        borderTop: "1px solid rgba(255,255,255,.09)",
        background: selected ? "rgba(255,255,255,.06)" : "transparent",
        cursor: "pointer",
        textAlign: "left",
        width: "100%",
        color: "#f2f2f2",
        fontFamily: SANS,
      }}
    >
      <DateCell row={row} phone={phone} />
      <div>
        <div style={{ fontFamily: SERIF, fontSize: "1.05em" }}>{row.deceased_name}</div>
        {row.meta && (
          <div style={{ color: "#9a9a9a", fontSize: "0.78em", marginTop: 2 }}>{row.meta}</div>
        )}
        {phone && status}
      </div>
      {!phone && status}
    </div>
  )
}

function GroupBlock({
  id,
  label,
  count,
  orders,
  phone,
  selectedId,
  pad,
  onOpen,
  onFix,
}: {
  id: string
  label: string
  count: number
  orders: OrderRow[]
  phone: boolean
  selectedId?: string
  pad: string
  onOpen: (id: string) => void
  onFix?: (row: OrderRow) => void
}) {
  return (
    <section data-testid={`opas-order-group-${id}`} style={{ marginTop: 14 }}>
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          color: "#5e5e5e",
          fontSize: 11,
          letterSpacing: ".14em",
          textTransform: "uppercase",
        }}
      >
        <span>{label}</span>
        <span>{count}</span>
      </header>
      {orders.map((row) => (
        <OrderRowView
          key={row.id}
          row={row}
          phone={phone}
          selected={selectedId === row.id}
          pad={pad}
          onOpen={onOpen}
          onFix={onFix}
        />
      ))}
    </section>
  )
}

export function OrderListPane({
  snapshot,
  selectedId,
  density = "compact",
  layout,
  onOpenOrder,
  onFix,
  onRemovePill,
  onAskHint,
}: {
  snapshot: OrderListSnapshot
  selectedId?: string
  density?: OrderListDensity
  /** Set in tests. Omitted, the pane follows a 640px media query. */
  layout?: OrderListLayout
  onOpenOrder: (orderId: string) => void
  onFix?: (row: OrderRow) => void
  onRemovePill?: (pillId: string) => void
  onAskHint?: () => void
}) {
  const measuredPhone = usePhoneWidth()
  const phone = layout === "phone" || (layout === undefined && measuredPhone)
  const [leftLens, setLeftLens] = useState(false)
  const pad = density === "comfortable" ? "14px 0" : "7px 0"
  const titleSize = density === "comfortable" ? "1.35em" : "1.15em"

  useEffect(() => {
    setLeftLens(false)
  }, [snapshot])

  const surface = leftLens ? "pane" : (snapshot.surface ?? "pane")
  const pills = snapshot.pills ?? []
  const groups = snapshot.groups ?? []
  const orders = snapshot.orders ?? []
  const line = totalsLine(snapshot.totals)

  /**
   * ⚠️ THE `picks` BODY IS GONE (James, 2026-10-20: "Replace the floating pick pane...
   * Remove the old pick pane and its code; the bug where it stayed open goes with it.").
   *
   * It rendered `snapshot.picks` as a numbered `<ol data-testid="opas-order-picks">`
   * inside this pane. Answering one opened the order and left THIS pane showing the
   * list — the stale question the ruling names. `OpasHost.settleOrderAnswer` now routes
   * `kind: "picks"` into the reply above the bar instead, and never opens or patches a
   * pane for it.
   *
   * ⚠️ THE SERVER SHAPE IS UNCHANGED. `OrderListSnapshot.kind` still has `"picks"` and
   * `picks` is still on it; what changed is only which surface reads them. A
   * `picks` snapshot reaching this component at all would now be a routing bug, so the
   * fall-through renders the empty state rather than silently nothing.
   */
  let body: ReactNode
  if (surface === "lens" && snapshot.lens) {
    body = (
      <OrderListLens
        lens={snapshot.lens}
        onOpen={onOpenOrder}
        onLeave={() => setLeftLens(true)}
      />
    )
  } else if (snapshot.layout === "grouped") {
    body = groups.map((group) => (
      <GroupBlock
        key={group.id}
        id={group.id}
        label={group.label}
        count={group.count}
        orders={group.orders}
        phone={phone}
        selectedId={selectedId}
        pad={pad}
        onOpen={onOpenOrder}
        onFix={onFix}
      />
    ))
  } else {
    body = orders.map((row) => (
      <OrderRowView
        key={row.id}
        row={row}
        phone={phone}
        selected={selectedId === row.id}
        pad={pad}
        onOpen={onOpenOrder}
        onFix={onFix}
      />
    ))
  }

  return (
    <div
      data-testid="opas-order-list"
      data-layout={phone ? "phone" : "desktop"}
      data-density={density}
      data-order-list-root=""
      style={{ fontFamily: SANS, fontSize: 16, color: "#f2f2f2" }}
    >
      <style>
        {`@media (min-width: 641px) and (max-width: 1180px) {
          [data-order-list-root] { font-size: 18px; }
        }`}
      </style>
      {snapshot.title && (
        <h2
          data-testid="opas-order-title"
          style={{
            margin: "2px 0 8px",
            fontSize: titleSize,
            fontWeight: 500,
            fontFamily: SANS,
          }}
        >
          {snapshot.title}
        </h2>
      )}
      {pills.length > 0 && (
        <div data-testid="opas-order-pills" style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
          {pills.map((pill) => (
            <span
              key={pill.id}
              data-testid={`opas-order-pill-${pill.id}`}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                border: "1px solid rgba(255,255,255,.14)",
                borderRadius: 999,
                padding: "2px 8px 2px 10px",
                fontSize: 12,
                color: "#f2f2f2",
              }}
            >
              {pill.label}
              <button
                type="button"
                aria-label={`Remove ${pill.label}`}
                data-testid={`opas-order-pill-remove-${pill.id}`}
                onClick={() => onRemovePill?.(pill.id)}
                style={{
                  border: 0,
                  background: "transparent",
                  color: "#9a9a9a",
                  cursor: "pointer",
                  padding: 0,
                  fontSize: 14,
                }}
              >
                ×
              </button>
            </span>
          ))}
          <button
            type="button"
            data-testid="opas-order-ask"
            onClick={() => onAskHint?.()}
            style={{
              border: 0,
              background: "transparent",
              color: "#8aa4bd",
              cursor: "pointer",
              fontSize: 12,
              fontFamily: SANS,
            }}
          >
            Change the question
          </button>
        </div>
      )}
      {body}
      {snapshot.empty && orders.length === 0 && groups.length === 0 && snapshot.kind !== "picks" && surface !== "lens" && (
        <p data-testid="opas-order-empty" style={{ color: "#9a9a9a", fontSize: 13, margin: "12px 0 0" }}>
          {snapshot.empty}
        </p>
      )}
      {line && surface !== "lens" && (
        <p
          data-testid="opas-order-totals"
          style={{
            margin: "12px 0 0",
            paddingTop: 8,
            borderTop: "1px solid rgba(255,255,255,.09)",
            display: "flex",
            justifyContent: "space-between",
            fontSize: 13,
          }}
        >
          <span>{line.replace(/ · \$[\d,]+(?:\.\d+)?$/, "")}</span>
          {snapshot.totals?.show_money !== false && snapshot.totals?.total && (
            <span>{line.match(/\$[\d,]+(?:\.\d+)?$/)?.[0]}</span>
          )}
        </p>
      )}
      {snapshot.footer && surface !== "lens" && (
        <p data-testid="opas-order-footer" style={{ margin: "10px 0 0", color: "#5e5e5e", fontSize: 12 }}>
          {snapshot.footer}
        </p>
      )}
    </div>
  )
}
