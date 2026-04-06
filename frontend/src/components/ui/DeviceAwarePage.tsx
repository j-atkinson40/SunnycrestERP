// DeviceAwarePage.tsx — Wrapper that renders the right layout per device type
// Pages can provide up to 3 render functions; falls back gracefully.

import { useDevice } from "@/contexts/device-context"
import type { ReactNode } from "react"

interface DeviceAwarePageProps {
  /** Desktop layout (required — used as fallback for all) */
  desktop: () => ReactNode
  /** Tablet layout (optional — falls back to desktop) */
  tablet?: () => ReactNode
  /** Mobile layout (optional — falls back to tablet, then desktop) */
  mobile?: () => ReactNode
}

/**
 * Renders the appropriate layout based on the effective device type.
 *
 * Fallback chain: mobile → tablet → desktop
 *
 * Usage:
 * ```tsx
 * <DeviceAwarePage
 *   desktop={() => <DesktopLayout />}
 *   mobile={() => <MobileLayout />}
 * />
 * ```
 */
export default function DeviceAwarePage({ desktop, tablet, mobile }: DeviceAwarePageProps) {
  const { effectiveDevice } = useDevice()

  switch (effectiveDevice) {
    case "mobile":
      return <>{(mobile ?? tablet ?? desktop)()}</>
    case "tablet":
      return <>{(tablet ?? desktop)()}</>
    case "desktop":
    default:
      return <>{desktop()}</>
  }
}
