/**
 * S-2 (§4.3) trigger seam (ruled decision 6).
 *
 * v1 emits reason:"extraction_settled" — the surfaces appear once the
 * debounced extraction has produced content (the overlay already
 * debounces at 600ms, so this is the "user paused and we have something
 * to show" moment, not a per-keystroke flicker). The seam OWNS the
 * ~1s minimum-visibility floor so that discipline never leaks into
 * individual surfaces.
 *
 * The return SHAPE carries rhythm context (msSinceLastKeystroke,
 * cursorMoved, inputText) that v1 populates best-effort. S-4's pause
 * sensor swaps the IMPLEMENTATION to emit reason:"pause" with a real
 * adaptive threshold + rhythm — the host and surfaces never change.
 * Do NOT build pause detection here.
 */

import { useCallback, useEffect, useRef, useState } from "react"

import type {
  ContextualSurfaceTrigger,
  ExtractionContext,
  SurfaceTriggerSignal,
} from "./types"

export function useContextualSurfaceTrigger(opts: {
  context: ExtractionContext | null
  minVisibleMs?: number
}): ContextualSurfaceTrigger {
  const { context, minVisibleMs = 1000 } = opts

  const [active, setActive] = useState(false)
  const [dismissed, setDismissed] = useState(false)
  const shownAtRef = useRef<number>(0)

  const hasContent =
    !!context && (!!context.customer || context.lines.length > 0)

  // Re-arm on a fresh session (context cleared when the overlay closes).
  useEffect(() => {
    if (context === null) {
      setActive(false)
      setDismissed(false)
    }
  }, [context])

  // Reveal once there's content (the settle). Surfaces then update in
  // place as fields fill; v1 never auto-hides mid-compose.
  useEffect(() => {
    if (dismissed) return
    if (hasContent && !active) {
      setActive(true)
      shownAtRef.current = Date.now()
    }
  }, [hasContent, active, dismissed])

  const dismiss = useCallback(() => {
    const hide = () => {
      setActive(false)
      setDismissed(true)
    }
    const elapsed = Date.now() - shownAtRef.current
    if (active && elapsed < minVisibleMs) {
      // Honor the minimum-visibility floor (anti-flicker).
      window.setTimeout(hide, minVisibleMs - elapsed)
    } else {
      hide()
    }
  }, [active, minVisibleMs])

  const signal: SurfaceTriggerSignal | null =
    active && context
      ? {
          reason: "extraction_settled",
          msSinceLastKeystroke: null, // best-effort; S-4 populates this
          cursorMoved: false,
          inputText: context.rawInput,
        }
      : null

  return { active, signal, dismiss }
}
