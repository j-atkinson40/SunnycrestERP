/**
 * useDelayedLoading — DESIGN_LANGUAGE §18.1 "never flash a skeleton".
 *
 * The 150ms arm / 300ms minimum-display pair:
 *   - Loading UI appears only after `armMs` (150ms) of continuous loading —
 *     fast responses render directly with NO loading UI at all.
 *   - Once shown, it persists at least `minVisibleMs` (300ms) before being
 *     replaced — no single-frame flicker.
 *
 * The single threshold is the 150ms timer (per §18.1's unified rule):
 * operations the platform knows are local/synchronous simply never set
 * `loading` true, so they never arm it.
 *
 * Usage:
 *     const showSkeleton = useDelayedLoading(isLoading)
 *     {showSkeleton ? <SkeletonLines/> : content}
 */
import { useEffect, useRef, useState } from "react"

export function useDelayedLoading(
  loading: boolean,
  armMs = 150,
  minVisibleMs = 300,
): boolean {
  const [show, setShow] = useState(false)
  const shownAtRef = useRef<number | null>(null)

  useEffect(() => {
    let timer: number | null = null
    if (loading) {
      if (!show) {
        // Arm: only show after armMs of continuous loading.
        timer = window.setTimeout(() => {
          shownAtRef.current = Date.now()
          setShow(true)
        }, armMs)
      }
    } else if (show) {
      // Hold: once visible, persist at least minVisibleMs total.
      const shownFor = Date.now() - (shownAtRef.current ?? 0)
      const remaining = Math.max(0, minVisibleMs - shownFor)
      if (remaining === 0) {
        shownAtRef.current = null
        setShow(false)
      } else {
        timer = window.setTimeout(() => {
          shownAtRef.current = null
          setShow(false)
        }, remaining)
      }
    }
    return () => {
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [loading, show, armMs, minVisibleMs])

  return show
}
