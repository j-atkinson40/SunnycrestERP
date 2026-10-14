/**
 * The shortened sales order, opened beside the list.
 *
 * ⚠️ IT READS. Times, drivers, and prices are changed somewhere else. A quiet
 * link reaches the existing order page for the cases this card does not hold.
 */
import { useEffect, useState, type CSSProperties } from "react"

import { getSalesOrderSummary, type SalesOrderSummary } from "@/services/order-list-service"

const LABEL: CSSProperties = {
  color: "#5e5e5e",
  fontSize: 11,
  letterSpacing: ".12em",
  textTransform: "uppercase",
}

export function SalesOrderPane({ orderId }: { orderId: string }) {
  const [row, setRow] = useState<SalesOrderSummary | null>(null)
  const [failed, setFailed] = useState(false)

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

  const fields: { label: string; value?: string }[] = [
    { label: "Vault", value: row.vault },
    { label: "Service", value: row.service },
    { label: "Cemetery", value: row.cemetery },
    { label: "Stands at", value: row.stands_at },
  ]

  return (
    <div data-testid="opas-sales-order">
      <h2
        style={{
          margin: "4px 0 2px",
          fontFamily: "'IBM Plex Serif', Georgia, serif",
          fontWeight: 450,
          fontSize: 22,
          color: "#f2f2f2",
        }}
      >
        {row.deceased_name}
      </h2>
      <p style={{ margin: "0 0 14px", color: "#9a9a9a", fontSize: 13 }}>
        {row.number} · {row.funeral_home}
      </p>
      <dl style={{ margin: 0 }}>
        {fields.map((field) =>
          field.value ? (
            <div
              key={field.label}
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 16,
                padding: "8px 0",
                borderTop: "1px solid rgba(255,255,255,.09)",
                fontSize: 14,
              }}
            >
              <dt style={LABEL}>{field.label}</dt>
              <dd style={{ margin: 0, color: "#f2f2f2", textAlign: "right" }}>{field.value}</dd>
            </div>
          ) : null,
        )}
      </dl>
      <p style={{ margin: "14px 0 0", fontSize: 12, color: "#5e5e5e" }}>
        The sales order pane, shortened here.{" "}
        <a href={`/sales-orders/${row.id}`} style={{ color: "#8aa4bd" }}>
          Open the full order
        </a>
      </p>
    </div>
  )
}
