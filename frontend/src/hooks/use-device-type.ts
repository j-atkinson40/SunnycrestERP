// use-device-type.ts — Detects physical device type from viewport width
// Breakpoints: mobile <768, tablet 768-1023, desktop >=1024

import { useState, useEffect, useCallback, useRef } from "react"

export type DeviceType = "mobile" | "tablet" | "desktop"

const BREAKPOINTS = {
  mobile: 768,   // < 768 = mobile
  tablet: 1024,  // 768–1023 = tablet, >= 1024 = desktop
} as const

function getDeviceType(width: number): DeviceType {
  if (width < BREAKPOINTS.mobile) return "mobile"
  if (width < BREAKPOINTS.tablet) return "tablet"
  return "desktop"
}

/**
 * Detects the physical device type based on viewport width.
 * Uses a debounced resize listener (150ms) to avoid thrashing.
 */
export function useDeviceType(): DeviceType {
  const [deviceType, setDeviceType] = useState<DeviceType>(() =>
    getDeviceType(window.innerWidth)
  )
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleResize = useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => {
      setDeviceType(getDeviceType(window.innerWidth))
    }, 150)
  }, [])

  useEffect(() => {
    window.addEventListener("resize", handleResize)
    return () => {
      window.removeEventListener("resize", handleResize)
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [handleResize])

  return deviceType
}

/** True when physical viewport is mobile-width */
export function useIsMobile(): boolean {
  return useDeviceType() === "mobile"
}

/** True when physical viewport is tablet-width */
export function useIsTablet(): boolean {
  return useDeviceType() === "tablet"
}

/** True when physical viewport is desktop-width */
export function useIsDesktop(): boolean {
  return useDeviceType() === "desktop"
}
