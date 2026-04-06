// DeviceToggle.tsx — Floating button to override device layout
// Shows current effective device icon; click cycles through auto → mobile → tablet → desktop

import { Monitor, Tablet, Smartphone, RotateCcw } from "lucide-react"
import { useDevice } from "@/contexts/device-context"
import type { DeviceType } from "@/hooks/use-device-type"

const ICON_MAP: Record<DeviceType, typeof Monitor> = {
  desktop: Monitor,
  tablet: Tablet,
  mobile: Smartphone,
}

const CYCLE_ORDER: Array<DeviceType | null> = [null, "mobile", "tablet", "desktop"]

export default function DeviceToggle() {
  const { effectiveDevice, preference, setPreference } = useDevice()

  function handleClick() {
    const currentIdx = CYCLE_ORDER.indexOf(preference)
    const nextIdx = (currentIdx + 1) % CYCLE_ORDER.length
    setPreference(CYCLE_ORDER[nextIdx])
  }

  const Icon = preference === null ? RotateCcw : ICON_MAP[effectiveDevice]
  const label = preference === null ? "Auto-detect" : `Forced: ${effectiveDevice}`

  return (
    <button
      onClick={handleClick}
      title={label}
      className="fixed bottom-4 right-4 z-50 flex items-center justify-center
        h-10 w-10 rounded-full bg-gray-900 text-white shadow-lg
        hover:bg-gray-700 transition-colors
        ring-2 ring-white/20"
    >
      <Icon className="h-4.5 w-4.5" />
      {preference !== null && (
        <span className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-amber-400 border border-white" />
      )}
    </button>
  )
}
