/**
 * The mirror — a layer behind the bar's textarea that lays out the same text the
 * same way, so something can be drawn UNDER individual characters.
 *
 * ⚠️ ONE BOX CONSTANT, SPREAD INTO BOTH, RATHER THAN TWO MATCHING STYLE BLOCKS. A
 * textarea renders text the browser owns; a div renders text we own. They agree on
 * where a line breaks only if every property that affects line breaking is identical
 * — font, size, weight, line-height, letter-spacing, padding, border, white-space,
 * wrapping and tab-size. Two blocks that "look the same" drift the first time
 * somebody tunes one of them, and the symptom is a tint sliding a character to the
 * left on the last line of a long order. `MIRROR_BOX` makes that unexpressible:
 * there is one source and both consume it.
 *
 * ⚠️ `border: 0` IS PART OF THE CONTRACT, not an omission. A border on one and not
 * the other shifts the content box and every wrap point with it.
 *
 * ⚠️ WIDTH IS NOT IN THE CONSTANT, DELIBERATELY. Both elements are stretched by the
 * same positioned parent (`MirrorStack`), so the width is shared by construction
 * rather than by two numbers agreeing. A declared width would be a third place to
 * get it wrong.
 *
 * Step 1 of James's 2026-10-16 dispatch. On its own it changes nothing visible; the
 * tinting and the ghost are drawn into it afterwards.
 */
import {
  useEffect,
  type CSSProperties,
  type ReactNode,
  type RefObject,
} from "react"

import type { CaptureSpan } from "@/services/opas-capture-service"
import { mirrorPieces } from "./mirror-spans"

/**
 * Every property that decides where a line breaks, shared by the textarea and the
 * mirror. ⚠️ ADDING A TYPOGRAPHIC PROPERTY TO THE BAR MEANS ADDING IT HERE, not to
 * the textarea's own style block — `mirror-box.test.tsx` asserts the textarea
 * carries no competing typographic property of its own.
 */
export const MIRROR_BOX = {
  fontFamily: "'IBM Plex Mono', ui-monospace, Menlo, monospace",
  fontSize: 15,
  lineHeight: 1.45,
  fontWeight: 400,
  letterSpacing: "normal",
  padding: "10px 0",
  border: 0,
  whiteSpace: "pre-wrap",
  // ⚠️ `break-word`, MATCHING WHAT A TEXTAREA DOES WITH A LONG UNBROKEN RUN. A pasted
  // URL or a 60-character product code wraps inside the textarea; a mirror set to
  // `normal` would let it overflow and every line after it would be one line too high.
  overflowWrap: "break-word",
  wordBreak: "normal",
  tabSize: 4,
  maxHeight: "40vh",
} as const satisfies CSSProperties

/** The mirror sits behind; the textarea's own background must not hide it. */
export const MIRROR_TEXTAREA_EXTRA = {
  background: "transparent",
  position: "relative",
  zIndex: 1,
} as const satisfies CSSProperties

/**
 * Keep the mirror's scroll aligned with the textarea's, and re-align when anything
 * that affects layout changes.
 *
 * ⚠️ THE TEXTAREA STILL SCROLLS AT THE 40vh CAP EVEN THOUGH `overflow: hidden`.
 * Hidden stops the scrollbar, not the scrolling — a browser moves `scrollTop` to keep
 * the caret visible regardless. So past the cap the two layers diverge unless this
 * runs, and the divergence is invisible until an order is long enough to reach it,
 * which is exactly when the director is least able to spot it.
 *
 * ⚠️ `document.fonts.ready` IS NOT OPTIONAL. IBM Plex Mono is self-hosted and loads
 * after first paint; until it resolves the bar is laid out in the fallback metric.
 * Both layers use the same font so they agree either way — but the ALIGNMENT TEST
 * screenshots can be taken mid-swap, and a drift measured then would be a real
 * measurement of a transient state. Re-syncing on `fonts.ready` makes the settled
 * state the one that is observed.
 */
export function useMirrorSync(
  textarea: RefObject<HTMLTextAreaElement | null>,
  mirror: RefObject<HTMLDivElement | null>,
  value: string,
): void {
  useEffect(() => {
    const ta = textarea.current
    const mi = mirror.current
    if (!ta || !mi) return

    const sync = () => {
      const t = textarea.current
      const m = mirror.current
      if (!t || !m) return
      m.scrollTop = t.scrollTop
      m.scrollLeft = t.scrollLeft
    }

    sync()
    ta.addEventListener("scroll", sync)
    window.addEventListener("resize", sync)

    // ⚠️ ResizeObserver ON THE TEXTAREA, NOT A WINDOW LISTENER ALONE. The bar grows
    // from its own `scrollHeight` as the order is typed, and that growth is not a
    // window resize — without this the mirror keeps the height it had when the order
    // was one line.
    let ro: ResizeObserver | undefined
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(sync)
      ro.observe(ta)
    }

    let cancelled = false
    const fonts = (document as Document & { fonts?: FontFaceSet }).fonts
    if (fonts?.ready) void fonts.ready.then(() => { if (!cancelled) sync() })

    return () => {
      cancelled = true
      ta.removeEventListener("scroll", sync)
      window.removeEventListener("resize", sync)
      ro?.disconnect()
    }
  }, [textarea, mirror, value])
}

/**
 * The positioned parent both layers stretch to.
 *
 * ⚠️ IT CARRIES `flex: 1, minWidth: 0` — THE PROPERTIES THE TEXTAREA USED TO CARRY.
 * The textarea was a direct flex child; wrapping it without moving those would give
 * the stack an intrinsic width and the bar would stop filling its pill. `minWidth: 0`
 * is the one that is easy to drop and it is load-bearing: without it a flex child
 * refuses to shrink below its content, so a long unbroken word would widen the bar
 * instead of wrapping.
 */
export function MirrorStack({ children }: { children: ReactNode }) {
  return (
    <div style={{ position: "relative", flex: 1, minWidth: 0, display: "flex" }}>
      {children}
    </div>
  )
}

/**
 * How each state reads. ⚠️ SUBTLE ON PURPOSE — this sits UNDER text the director is
 * reading, so anything with real contrast competes with the words. The captured tint
 * is a wash at 8% rather than a highlighter.
 *
 * ⚠️ THE UNRECOGNIZED MARK IS A DOTTED UNDERLINE, NOT A COLOUR. "Not understood" is
 * not an error — it is text the engine had nothing to say about — and colouring it
 * red would make every half-typed order look broken mid-sentence.
 */
const SPAN_STYLE: Record<string, CSSProperties> = {
  captured: {
    background: "rgba(74,160,110,0.14)",
    borderRadius: 3,
    boxShadow: "0 0 0 1px rgba(74,160,110,0.10)",
  },
  conflict: {
    background: "rgba(224,168,74,0.18)",
    borderRadius: 3,
    boxShadow: "0 0 0 1px rgba(224,168,74,0.35)",
  },
  unrecognized: {
    textDecoration: "underline dotted rgba(214,214,214,0.55)",
    textUnderlineOffset: 3,
  },
}

/** What a span looks like while its pane row is hovered. */
const SPAN_LIT: CSSProperties = {
  background: "rgba(138,164,189,0.26)",
  boxShadow: "0 0 0 1px rgba(138,164,189,0.5)",
  borderRadius: 3,
}

export function CaptureMirror({
  value,
  mirrorRef,
  spans,
  spansForText,
  litFieldIds,
  ghostSuffix,
  children,
  debugOutline = false,
}: {
  readonly value: string
  readonly mirrorRef: RefObject<HTMLDivElement | null>
  readonly spans?: readonly CaptureSpan[]
  readonly spansForText?: string | null
  /** Field ids whose span should read as lit — the hovered pane row. */
  readonly litFieldIds?: readonly string[]
  /** Faint completion drawn after the text. See `ghost.ts`. */
  readonly ghostSuffix?: string | null
  readonly children?: ReactNode
  /**
   * ⚠️ THE ALIGNMENT GATE'S INSTRUMENT, and it ships rather than living in a scratch
   * file. James's dispatch requires a 1px outline on every character run before
   * anything is built on this layer; a measurement harness that is deleted after one
   * use cannot be re-run when somebody later tunes the bar's font.
   */
  readonly debugOutline?: boolean
}) {
  return (
    <div
      ref={mirrorRef}
      data-testid="capture-mirror"
      aria-hidden="true"
      style={{
        ...MIRROR_BOX,
        position: "absolute",
        inset: 0,
        overflow: "hidden",
        pointerEvents: "none",
        // ⚠️ THE TEXT IS INVISIBLE HERE. The textarea renders the readable copy; this
        // layer exists only to position decoration under it. Rendering it visibly
        // would double every glyph at a one-subpixel offset.
        color: "transparent",
      }}
    >
      {mirrorPieces(value, spans, spansForText).map((piece, i) => {
        const lit =
          piece.fieldIds.length > 0 &&
          (litFieldIds ?? []).some((f) => piece.fieldIds.includes(f))
        return (
          <span
            key={i}
            data-span-state={piece.state ?? undefined}
            data-span-fields={piece.fieldIds.join(",") || undefined}
            style={{
              ...(piece.state ? SPAN_STYLE[piece.state] : undefined),
              ...(lit ? SPAN_LIT : undefined),
              ...(debugOutline ? { outline: "1px solid rgba(255,0,0,.9)" } : undefined),
            }}
          >
            {piece.text}
          </span>
        )
      })}
      {/* ⚠️ THE GHOST LIVES IN THE MIRROR, NOT IN A SEPARATE LAYER, so it inherits
          the same box and lands exactly where the next character would. A second
          absolutely-positioned element would need the caret's pixel position, which
          a textarea does not expose. */}
      {ghostSuffix ? (
        <span data-testid="capture-ghost" style={{ color: "rgba(214,214,214,0.42)" }}>
          {ghostSuffix}
        </span>
      ) : null}
      {children}
      {/* ⚠️ A TRAILING NEWLINE NEEDS A CHARACTER AFTER IT OR THE LAST LINE COLLAPSES.
          A textarea reserves a final empty line; a div does not, so "a\n" is two lines
          in one layer and one in the other, and everything after drifts by a line. */}
      {value.endsWith("\n") ? "​" : null}
    </div>
  )
}
