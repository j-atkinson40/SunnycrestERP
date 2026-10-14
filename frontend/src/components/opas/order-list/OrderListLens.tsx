/**
 * The glasses line, inside the order pane.
 *
 * Tap advances three names. A double tap returns to the list. Three or fewer
 * open the first order on a tap — the cue the server sent says which.
 */
import { useEffect, useRef, useState } from "react"

import type { OrderLens } from "@/services/order-list-service"

export function OrderListLens({
  lens,
  onOpen,
  onLeave,
}: {
  lens: OrderLens
  onOpen: (orderId: string) => void
  onLeave: () => void
}) {
  const [page, setPage] = useState(0)
  const timer = useRef<number | null>(null)
  const pages = lens.pages
  const shown = pages[Math.min(page, Math.max(pages.length - 1, 0))]

  useEffect(() => {
    setPage(0)
  }, [lens.heading, lens.pages.length])

  useEffect(() => () => {
    if (timer.current !== null) window.clearTimeout(timer.current)
  }, [])

  const openFirst = lens.cue.includes("open the first") && lens.first_order_id

  function tap() {
    if (timer.current !== null) return
    timer.current = window.setTimeout(() => {
      timer.current = null
      if (openFirst && lens.first_order_id) {
        onOpen(lens.first_order_id)
        onLeave()
        return
      }
      setPage((current) => (pages.length === 0 ? 0 : (current + 1) % pages.length))
    }, 220)
  }

  function doubleTap() {
    if (timer.current !== null) {
      window.clearTimeout(timer.current)
      timer.current = null
    }
    onLeave()
  }

  return (
    <button
      type="button"
      data-testid="opas-order-lens"
      onClick={tap}
      onDoubleClick={doubleTap}
      style={{
        display: "block",
        width: "100%",
        textAlign: "left",
        background: "#050505",
        color: "#3f9c63",
        border: "1px solid rgba(63,156,99,.35)",
        borderRadius: 12,
        padding: "22px 18px",
        cursor: "pointer",
        fontFamily: "'IBM Plex Mono', ui-monospace, Menlo, monospace",
        fontSize: 13,
        lineHeight: 1.55,
      }}
    >
      <div>{lens.heading}</div>
      {shown !== undefined && shown.items.length > 0 && (
        <div data-testid="opas-order-lens-bits" style={{ marginTop: 8 }}>
          {shown.items.join(" · ")}
        </div>
      )}
      <div data-testid="opas-order-lens-cue" style={{ marginTop: 10, color: "#3f9c63" }}>
        {lens.cue}
      </div>
    </button>
  )
}
