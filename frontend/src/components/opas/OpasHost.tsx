/**
 * Opas — sphere, veil, command line, and the glass panes a request opens.
 *
 * ⚠️ MEASURED FROM `docs/prototypes/2026-10-01-opas-overlay.html` (93177 bytes, md5
 * a52a1e95153bd5c686b88d0acffc31e6), not chosen. Every value below that matches the
 * prototype is marked; where this differs, the reason is stated.
 *
 * Verified from the prototype's own source, not inferred:
 *   orb.addEventListener('click', open)
 *   veil.addEventListener('pointerdown', tuck)      <- pointerdown, not click
 *   Escape -> pending ? cancelPick() : textarea ? input.focus() : tuck()
 *   tuck() -> veil off, wins.forEach(w => w.el.classList.add('tucked'))   panes STAY
 *   open() -> wins.forEach(w => w.el.classList.remove('tucked'))         panes RETURN
 *   orb.classList.toggle('session', wins.length > 0)
 * and in its visible UI: "Esc — tuck everything away; it comes back where you left it".
 *
 * ⚠️ NOT BUILT, DELIBERATELY: the prototype binds Cmd/Ctrl+K to toggle itself. This app
 * binds Cmd+K to the command bar, and taking it would change existing command-bar
 * behaviour. The sphere click is the entrance. Logged in STATE as James's call after the walk.
 *
 * ⚠️ ADMIN-ONLY, via the EXISTING role check (`useAuth().isAdmin`). No new flag mechanism.
 */
import { useCallback, useEffect, useRef, useState } from "react"

import { useAuth } from "@/contexts/auth-context"
import { useOpas } from "@/contexts/opas-context"
import { isCatalogRequest, routeResolution } from "./opas-routing"
import { resolvePhrase } from "@/services/opas-catalog-service"
import { ProductListPane } from "./ProductListPane"
import { ProductPane } from "./ProductPane"

/** The prototype's glass, as one object so panes and the command line cannot drift apart. */
const GLASS: React.CSSProperties = {
  background:
    "linear-gradient(160deg,rgba(50,50,50,.48) 0%,rgba(22,22,22,.42) 55%,rgba(14,14,14,.5) 100%)",
  backdropFilter: "blur(26px) saturate(1.5)",
  WebkitBackdropFilter: "blur(26px) saturate(1.5)",
  boxShadow:
    "inset 0 1px 0 rgba(255,255,255,.16),inset 0 0 0 1px rgba(255,255,255,.06)," +
    "inset 0 -1px 0 rgba(0,0,0,.45),0 34px 80px rgba(0,0,0,.55),0 10px 26px rgba(0,0,0,.38)",
}

export function OpasHost() {
  const { isAdmin } = useAuth()
  const opas = useOpas()
  const inputRef = useRef<HTMLInputElement>(null)
  const [text, setText] = useState("")
  const [busy, setBusy] = useState(false)
  const [said, setSaid] = useState<string | null>(null)

  // ⚠️ Escape at the document level, with the prototype's three branches. `onEscape` owns
  // the ordering; this only supplies what is focused and honours the verdict.
  useEffect(() => {
    if (!opas.isOpen) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== "Escape") return
      const tag = (document.activeElement as HTMLElement | null)?.tagName
      const outcome = opas.onEscape(tag)
      e.preventDefault()
      if (outcome === "refocused-input") inputRef.current?.focus()
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [opas])

  useEffect(() => {
    if (opas.isOpen) inputRef.current?.focus()
  }, [opas.isOpen])

  /**
   * ⚠️ CMD+K — THE ONE PIECE OF EXISTING COMMAND-BAR BEHAVIOUR JAMES AUTHORIZED CHANGING,
   * and only for users who can see the sphere.
   *
   * CAPTURE PHASE, and that is the mechanism rather than a detail. `CommandBarProvider`
   * listens for Cmd+K on `document` in the BUBBLE phase; for the same target, capture
   * listeners run first. So this sees the key, stops it, and the bar's handler never runs —
   * no flicker, and no edit to CommandBarProvider.
   *
   * ⚠️ MOUNTED ONLY WHEN `isAdmin && canRender`. For everyone else this effect does nothing
   * and Cmd+K is bit-for-bit unchanged — which is why the existing command-bar tests pass
   * unmodified.
   *
   * ⚠️ FOCUS STILL WINS: `canRender` is false while a Focus is open, so the listener is not
   * even attached and Cmd+K does nothing, exactly as the bar's own `if (focusIsOpen) return`
   * already guaranteed.
   */
  useEffect(() => {
    if (!isAdmin || !opas.canRender) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key.toLowerCase() !== "k") return
      if (!(e.metaKey || e.ctrlKey)) return
      if (e.altKey || e.shiftKey) return
      e.preventDefault()
      // ⚠️ stopImmediatePropagation, not stopPropagation: the bar's listener is on the SAME
      // target, so only the immediate form keeps it from running.
      e.stopImmediatePropagation()
      // The prototype: isOpen ? tuck() : open()
      if (opas.isOpen) opas.tuck()
      else opas.open()
    }
    document.addEventListener("keydown", onKeyDown, true)
    return () => document.removeEventListener("keydown", onKeyDown, true)
  }, [isAdmin, opas])

  /**
   * Drag, built the way the prototype's `wire(w)` does, with the differences named.
   *
   * SAME AS THE PROTOTYPE: left button only (`e.button !== 0`); interactive descendants
   * excluded; `setPointerCapture(e.pointerId)` rather than document listeners, so a fast
   * drag cannot escape the element; and a **4px dead zone** (`Math.hypot(...) < 4`) so a
   * click is not a drag.
   *
   * ⚠️ DIFFERENT FROM THE PROTOTYPE, DELIBERATELY: it binds `pointerdown` on the WHOLE PANE
   * (`el.addEventListener('pointerdown', ...)` where `el` is the `.win`). The dispatch's
   * requirement list says "drag by the pane header", so the handle is the header only.
   * Reported rather than silently reconciled — the prototype is draggable anywhere, which
   * James will have felt when he walked it.
   *
   * ⚠️ BOUNDS: the pane cannot be dragged fully off screen. 80px of width and the full
   * header depth are kept on screen in every direction, so there is always something left
   * to grab. The prototype's anchoring code clamps with `Math.max(16, ...)`; I did not find
   * a clamp on its drag path, so this is stated as our requirement rather than as measured.
   */
  const dragStart = useCallback(
    (
      e: React.PointerEvent<HTMLDivElement>,
      id: string,
      placed: { x: number; y: number; anchored: boolean } | undefined,
      index: number,
    ) => {
      if (e.button !== 0) return
      if ((e.target as HTMLElement).closest("button,textarea,input,a") !== null) return
      const handle = e.currentTarget
      const pane = handle.parentElement
      if (pane === null) return
      handle.setPointerCapture(e.pointerId)

      const rect = pane.getBoundingClientRect()
      const start = { px: e.clientX, py: e.clientY, x: placed?.x ?? rect.left, y: placed?.y ?? rect.top }
      let moved = false

      const onMove = (ev: PointerEvent) => {
        const dx = ev.clientX - start.px
        const dy = ev.clientY - start.py
        // ⚠️ THE DEAD ZONE. Without it, raising a pane by clicking its header would nudge it.
        if (!moved && Math.hypot(dx, dy) < 4) return
        moved = true
        const KEEP = 80
        const maxX = window.innerWidth - KEEP
        const maxY = window.innerHeight - rect.height > 0 ? window.innerHeight - KEEP : 0
        const x = Math.min(Math.max(start.x + dx, KEEP - rect.width), maxX)
        const y = Math.min(Math.max(start.y + dy, 0), maxY)
        opas.movePane(id, x, y)
      }
      const onUp = (ev: PointerEvent) => {
        handle.releasePointerCapture?.(ev.pointerId)
        handle.removeEventListener("pointermove", onMove)
        handle.removeEventListener("pointerup", onUp)
        handle.removeEventListener("pointercancel", onUp)
      }
      handle.addEventListener("pointermove", onMove)
      handle.addEventListener("pointerup", onUp)
      handle.addEventListener("pointercancel", onUp)
      void index
    },
    [opas],
  )

  const submit = useCallback(async () => {
    const phrase = text.trim()
    if (phrase === "" || busy) return
    setBusy(true)
    setSaid(null)
    try {
      // ⚠️ RULE-BASED FIRST. "the catalog" is a fixed phrase and never reaches the resolver.
      if (isCatalogRequest(phrase)) {
        opas.openPane({ kind: "product-list", label: "Catalog" })
        setText("")
        return
      }
      const r = await resolvePhrase(phrase)
      const route = routeResolution(r)
      if (route.kind === "product") {
        opas.openPane({
          kind: "product",
          label: "Product",
          variantTemplateId: route.variantTemplateId,
        })
      } else if (route.kind === "numbered-pick") {
        // ⚠️ A NUMBERED PICK, not a filtered list and not a guess. The discriminators say
        // what would narrow it, which is the only thing that tells the director WHY they
        // are being asked.
        opas.setPendingPick(route.candidateIds)
        opas.openPane({
          kind: "product-list",
          label: "Which one?",
          candidateIds: route.candidateIds,
        })
        setSaid(
          route.discriminators.length > 0
            ? `${route.candidateIds.length} match — differs by ${route.discriminators.join(", ")}`
            : `${route.candidateIds.length} match`,
        )
      } else {
        opas.openPane({ kind: "product-list", label: "Catalog", unmatchedPhrase: phrase })
        setSaid(`no match for “${phrase}”`)
      }
      setText("")
    } finally {
      setBusy(false)
    }
  }, [text, busy, opas])

  // ⚠️ The sphere is admin-only for now. Not rendering is the whole gate: a hidden-but-
  // mounted sphere would still answer keyboard and pointer events.
  if (!isAdmin || !opas.canRender) return null

  return (
    <>
      {/* VEIL — blur(7px) saturate(.9) and rgba(6,6,6,.38) are the prototype's values.
          pointerdown, not click, also the prototype's. */}
      <div
        data-testid="opas-veil"
        aria-hidden="true"
        onPointerDown={() => opas.tuck()}
        style={{
          position: "fixed",
          inset: 0,
          zIndex: 30,
          background: "rgba(6,6,6,.38)",
          backdropFilter: "blur(7px) saturate(.9)",
          WebkitBackdropFilter: "blur(7px) saturate(.9)",
          opacity: opas.isOpen ? 1 : 0,
          pointerEvents: opas.isOpen ? "auto" : "none",
          transition: "opacity .4s cubic-bezier(0.4,0,0.4,1)",
        }}
      />

      {/* PANES — above the veil. `tucked` hides without unmounting, so the session
          survives: opacity 0 / pointer-events none, exactly the prototype's `.win.tucked`. */}
      <div data-testid="opas-desk" style={{ position: "fixed", inset: 0, zIndex: 35, pointerEvents: "none" }}>
        {opas.panes.map((pane, i) => {
          const placed = opas.placements[pane.id]
          const isFront = opas.frontPaneId === pane.id
          return (
          <div
            key={pane.id}
            data-testid={`opas-pane-${pane.id}`}
            data-tucked={opas.isOpen ? "false" : "true"}
            data-focused={isFront ? "true" : "false"}
            onPointerDown={() => opas.raisePane(pane.id)}
            style={{
              ...GLASS,
              position: "absolute",
              // ⚠️ A DRAGGED PANE USES left/top; AN ANCHORED ONE CASCADES FROM right/top.
              // Mixing them is what keeps "new panes still cascade" true after another pane
              // has been moved: `anchored` decides which pair applies, per pane.
              ...(placed !== undefined && !placed.anchored
                ? { left: placed.x, top: placed.y }
                : { right: 24 + i * 18, top: 72 + i * 22 }),
              zIndex: opas.zOf(pane.id),
              // `.win.focused` from the prototype: a stronger shadow on the front pane, and
              // the others dimmed to .8 rather than hidden.
              boxShadow: isFront
                ? "inset 0 1px 0 rgba(255,255,255,.24),inset 0 0 0 1px rgba(255,255,255,.10)," +
                  "inset 0 -1px 0 rgba(0,0,0,.45),0 44px 100px rgba(0,0,0,.65),0 14px 32px rgba(0,0,0,.45)"
                : GLASS.boxShadow,
              opacity: opas.isOpen ? (isFront ? 1 : 0.8) : 0,
              width: "min(390px, calc(100vw - 32px))",
              maxHeight: "calc(100vh - 160px)",
              overflowY: "auto",
              borderRadius: 22,
              pointerEvents: opas.isOpen ? "auto" : "none",
              transform: opas.isOpen ? "none" : "translateY(12px) scale(.96)",
              transition: "opacity .4s cubic-bezier(0.2,0,0.1,1), transform .45s cubic-bezier(0.2,0,0.1,1)",
            }}
          >
            <div
              data-testid={`opas-pane-handle-${pane.id}`}
              onPointerDown={(e) => dragStart(e, pane.id, placed, i)}
              style={{
                display: "flex", alignItems: "center", gap: 10, padding: "14px 10px 6px 20px",
                cursor: "grab", touchAction: "none", userSelect: "none",
              }}
            >
              <span style={{ fontSize: 11, letterSpacing: ".14em", textTransform: "uppercase", color: "#5e5e5e" }}>
                {pane.label}
              </span>
              <button
                type="button"
                aria-label="Close pane"
                data-testid={`opas-pane-close-${pane.id}`}
                onClick={() => opas.closePane(pane.id)}
                style={{
                  marginLeft: "auto", width: 26, height: 26, borderRadius: "50%", border: 0,
                  background: "rgba(255,255,255,.06)", color: "#9a9a9a", cursor: "pointer",
                }}
              >
                ×
              </button>
            </div>
            <div style={{ padding: "0 20px 20px" }}>
              {pane.kind === "product-list" ? (
                <ProductListPane
                  candidateIds={pane.candidateIds}
                  unmatchedPhrase={pane.unmatchedPhrase}
                  onOpenProduct={(id) => {
                    opas.setPendingPick(null)
                    opas.openPane({ kind: "product", label: "Product", variantTemplateId: id })
                  }}
                />
              ) : (
                <ProductPane variantTemplateId={pane.variantTemplateId!} />
              )}
            </div>
          </div>
          )
        })}
      </div>

      {/* COMMAND LINE — glass pill at the sphere's corner. */}
      {opas.isOpen && (
        <div
          data-testid="opas-command-line"
          style={{
            ...GLASS, position: "fixed", zIndex: 44, right: 24, bottom: 24,
            width: "min(600px, calc(100vw - 48px))", borderRadius: 28, padding: "6px 8px 6px 10px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span
              aria-hidden="true"
              style={{
                flex: "none", width: 30, height: 30, borderRadius: "50%",
                background: "radial-gradient(circle at 36% 30%,#4a4a4a,#111 70%)",
                boxShadow: "0 0 12px 1px rgba(138,164,189,.35)",
              }}
            />
            <input
              ref={inputRef}
              data-testid="opas-input"
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void submit()
              }}
              placeholder="the catalog"
              aria-label="Ask Opas"
              style={{
                flex: 1, minWidth: 0, background: "transparent", border: 0, padding: "10px 0",
                color: "#f2f2f2", fontFamily: "'IBM Plex Mono', ui-monospace, Menlo, monospace",
                fontSize: 15, outline: "none",
              }}
            />
          </div>
          {said !== null && (
            <div data-testid="opas-said" style={{ padding: "0 0 6px 52px", fontSize: 12, color: "#9a9a9a" }}>
              {said}
            </div>
          )}
        </div>
      )}

      {/* SPHERE — 56px, right 24 bottom 24, the prototype's geometry. `session` shows a held
          set of panes: orb.classList.toggle('session', wins.length > 0). */}
      <button
        type="button"
        data-testid="opas-sphere"
        data-session={opas.hasSession ? "true" : "false"}
        aria-label="Open Opas"
        onClick={() => opas.open()}
        style={{
          position: "fixed", right: 24, bottom: 24, width: 56, height: 56, border: 0, padding: 0,
          borderRadius: "50%", background: "radial-gradient(circle at 36% 30%,#3c3c3c 0,#181818 42%,#060606 78%)",
          boxShadow: opas.hasSession
            ? "0 18px 36px rgba(0,0,0,.75), 0 0 18px 2px rgba(214,214,214,.30)"
            : "0 18px 36px rgba(0,0,0,.75), 0 0 16px 2px rgba(138,164,189,.30)",
          cursor: "pointer", zIndex: 45,
          opacity: opas.isOpen ? 0 : 1,
          transform: opas.isOpen ? "scale(.7)" : "none",
          pointerEvents: opas.isOpen ? "none" : "auto",
          transition: "opacity .2s cubic-bezier(0.2,0,0.1,1), transform .2s cubic-bezier(0.2,0,0.1,1)",
        }}
      />
    </>
  )
}
