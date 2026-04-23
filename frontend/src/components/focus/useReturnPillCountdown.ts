/**
 * useReturnPillCountdown — Phase A Session 4.
 *
 * 15-second countdown for the Focus return pill. On timer expiry the
 * pill auto-dismisses via `onExpire`. Full re-arm semantics (per
 * Session 4 user decision):
 *
 *   - Hover pauses the timer; mouse-leave resumes.
 *   - Tab visibility hide pauses; visible restores to FULL 15s
 *     (not resume-from-paused — "welcome back, here's your pill
 *     again" not "finishing the countdown from earlier").
 *   - Different focus opened/closed while pill visible re-arms via
 *     the `resetKey` prop — consumers pass `lastClosedFocus.id +
 *     openedAt.getTime()` so any change triggers a fresh 15s.
 *   - Layout updates from server response (passed in as `resetKey`
 *     via response metadata in Session 4+) re-arm.
 *
 * Deferred (post-arc): real-time data-subscription re-arm — requires
 * WebSocket/SSE infrastructure. See FEATURE_SESSIONS.md Session 4.
 *
 * Visual binding: the hook returns `remainingMs` + `isPaused`. The
 * pill renders a countdown bar whose `width` is
 * `(remainingMs / TOTAL_MS) * 100%`. The CSS transition on width
 * uses `cubic-bezier(0.32, 0.72, 0, 1)` which approximates spring
 * decay feel without a physics library.
 */

import { useCallback, useEffect, useRef, useState } from "react"


export const RETURN_PILL_COUNTDOWN_MS = 15_000
const TICK_MS = 100


export interface UseReturnPillCountdownOptions {
  /** Called when the countdown reaches zero. */
  onExpire: () => void
  /** When this value changes, the countdown re-arms to full duration.
   *  Consumers pass something that changes on every "fresh pill event"
   *  — typically `closedAt.getTime() + focusId`. Null disables the
   *  countdown entirely (pill inactive state). */
  resetKey: string | number | null
  /** Duration in ms. Defaults to 15_000. Tunable for tests. */
  totalMs?: number
}


export interface ReturnPillCountdownState {
  /** Milliseconds until expiry. Drops to 0 at expiry. */
  remainingMs: number
  /** True while paused via hover or tab-hidden. */
  isPaused: boolean
  /** Total duration (for computing the visual bar width). */
  totalMs: number
  /** Register hover interactions. Consumer wires these to the pill
   *  element's onPointerEnter/Leave. */
  onHoverStart: () => void
  onHoverEnd: () => void
}


export function useReturnPillCountdown(
  options: UseReturnPillCountdownOptions,
): ReturnPillCountdownState {
  const { onExpire, resetKey, totalMs = RETURN_PILL_COUNTDOWN_MS } = options

  const [remainingMs, setRemainingMs] = useState(totalMs)
  const [isHovered, setIsHovered] = useState(false)
  const [isTabHidden, setIsTabHidden] = useState(() =>
    typeof document !== "undefined" && document.visibilityState === "hidden",
  )

  // Latest-onExpire ref so the tick closure always calls the current
  // callback without re-subscribing the interval on every render.
  const onExpireRef = useRef(onExpire)
  useEffect(() => {
    onExpireRef.current = onExpire
  }, [onExpire])

  // "Already expired for this arm" latch. Prevents the interval
  // from firing onExpire repeatedly after remainingMs reaches zero
  // — important because the consumer typically removes the pill in
  // onExpire, but the unmount path isn't always synchronous (e.g.
  // when dismissReturnPill is async or batched).
  const expiredRef = useRef(false)

  const isPaused = isHovered || isTabHidden

  // Re-arm on resetKey change OR when transitioning back from
  // tab-hidden. Both reset to full 15s per Session 4 spec.
  useEffect(() => {
    if (resetKey === null) return
    setRemainingMs(totalMs)
    expiredRef.current = false
  }, [resetKey, totalMs])

  // Tab visibility → pause / re-arm. Per spec, returning visible
  // re-arms to full duration (not resume-from-paused).
  useEffect(() => {
    if (typeof document === "undefined") return
    const handler = () => {
      if (document.visibilityState === "hidden") {
        setIsTabHidden(true)
      } else {
        setIsTabHidden(false)
        setRemainingMs(totalMs)
      }
    }
    document.addEventListener("visibilitychange", handler)
    return () => document.removeEventListener("visibilitychange", handler)
  }, [totalMs])

  // The tick loop. Runs while NOT paused AND countdown is active
  // (resetKey non-null). Decrements remainingMs, fires onExpire at
  // zero. `expiredRef` prevents repeated fires if the pill stays
  // mounted past expiry for any reason.
  useEffect(() => {
    if (resetKey === null) return
    if (isPaused) return
    const interval = setInterval(() => {
      setRemainingMs((prev) => {
        const next = prev - TICK_MS
        if (next <= 0) {
          if (!expiredRef.current) {
            expiredRef.current = true
            onExpireRef.current()
          }
          return 0
        }
        return next
      })
    }, TICK_MS)
    return () => clearInterval(interval)
  }, [resetKey, isPaused])

  const onHoverStart = useCallback(() => setIsHovered(true), [])
  const onHoverEnd = useCallback(() => setIsHovered(false), [])

  return {
    remainingMs,
    isPaused,
    totalMs,
    onHoverStart,
    onHoverEnd,
  }
}
