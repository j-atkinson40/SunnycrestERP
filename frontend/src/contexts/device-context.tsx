// device-context.tsx — Provides resolved device type + preference override
// Effective device = preference ?? physical device type

import { createContext, useContext, useMemo, type ReactNode } from "react"
import { useDeviceType, type DeviceType } from "@/hooks/use-device-type"
import { useDevicePreference } from "@/hooks/use-device-preference"

interface DeviceContextValue {
  /** The physical device type from viewport width */
  physicalDevice: DeviceType
  /** User override preference (null = auto) */
  preference: DeviceType | null
  /** Effective device: preference ?? physicalDevice */
  effectiveDevice: DeviceType
  /** Update or clear the user preference */
  setPreference: (pref: DeviceType | null) => void
  /** Convenience: effectiveDevice === "mobile" */
  isMobile: boolean
  /** Convenience: effectiveDevice === "tablet" */
  isTablet: boolean
  /** Convenience: effectiveDevice === "desktop" */
  isDesktop: boolean
}

const DeviceContext = createContext<DeviceContextValue | null>(null)

interface DeviceProviderProps {
  userId: string | null
  children: ReactNode
}

export function DeviceProvider({ userId, children }: DeviceProviderProps) {
  const physicalDevice = useDeviceType()
  const { preference, setPreference } = useDevicePreference(userId)

  const value = useMemo<DeviceContextValue>(() => {
    const effectiveDevice = preference ?? physicalDevice
    return {
      physicalDevice,
      preference,
      effectiveDevice,
      setPreference,
      isMobile: effectiveDevice === "mobile",
      isTablet: effectiveDevice === "tablet",
      isDesktop: effectiveDevice === "desktop",
    }
  }, [physicalDevice, preference, setPreference])

  return (
    <DeviceContext.Provider value={value}>
      {children}
    </DeviceContext.Provider>
  )
}

/**
 * Access the device context. Must be within <DeviceProvider>.
 */
export function useDevice(): DeviceContextValue {
  const ctx = useContext(DeviceContext)
  if (!ctx) throw new Error("useDevice must be used within DeviceProvider")
  return ctx
}
